"""Evil Twin Synthesizer — the core SpecTrojan contribution.

Given ``(target, candidate_spec)``, an attacker LLM is asked to write an alternative
implementation that:

  1. Satisfies the candidate spec (verified by the executor).
  2. Diverges behaviorally from the reference (measured by ``behavioral_distance``).

If we can produce such a twin, the spec is *demonstrably* insufficient: two functions
satisfy the same contract but disagree on the things the user actually wanted.

Pipeline (CEGIS-style):

    for round in range(n_rounds):
        candidates = attacker_llm.propose(target, spec, reference, past_failures, ...)
        for cand in candidates:
            if not satisfies_spec(cand, spec):       record_failure(cand, "spec violated")
            elif distance(cand, ref) < threshold:    record_failure(cand, "too similar")
            else:                                    yield EvilTwin(cand, ...)

Diversity pressure:

  - Prompt-level   — explicit "use a different algorithmic structure" instructions, and a
    rotating list of *strategy hints* (constant, identity, lookup-table, negation, etc.)
    rotated across attempts so we explore the implementation space rather than orbiting
    one local minimum.
  - Token-level    — temperature 0.9+ across attempts.
  - Verifier-level — past failures fed back into the next prompt with their failure reason.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .distance import behavioral_distance
from .executor import satisfies_spec
from .llm import complete
from .types import CandidateSpec, EvilTwin, TargetFunction


# ---------- prompting ------------------------------------------------------

_PROMPT_TEMPLATE = """You are an adversarial program synthesizer. Your job is to find a
DIFFERENT Python function that still satisfies a given specification — proving the
specification is too weak.

The REFERENCE implementation:
```python
{reference_source}
```

The SPECIFICATION (precondition + postcondition):
```python
{precondition_src}

{postcondition_src}
```

Write a function named `{function_name}` with the same signature that:
1. SATISFIES the specification (whenever precondition(*args) is true, postcondition(*args, your_function(*args)) must be true).
2. DISAGREES with the reference on as many inputs as possible.
3. Uses a DIFFERENT structure from the reference. Do not produce a near-copy with renamed variables.

Strategy hint for THIS attempt: {strategy_hint}

{failures_block}

Use only the Python standard library. Define exactly one top-level function `{function_name}`.
Do NOT include the reference implementation, the spec, helper modules, or commentary.

Output ONLY a fenced ```python ... ``` code block."""


_STRATEGY_HINTS = [
    "Return a constant value that the spec happens to permit (e.g. always True, the empty string/list, 0).",
    "Ignore one of the inputs entirely; route the answer through only the others.",
    "Return the input unchanged or with a trivial transformation (identity, .upper(), len() in place of the real answer).",
    "Use a lookup table that hard-codes a few specific input/output pairs; return a default for everything else.",
    "Recursively call a helper that always bottoms out at a constant; the spec may not constrain the recursive path.",
    "Read the spec carefully and pick a value that you can prove the postcondition accepts — even if that value has nothing to do with the function's intended behavior.",
    "Negate one branch of the reference's logic, then patch the cases that would otherwise violate the precondition.",
]


def _failure_summary(failures: list[dict], max_examples: int = 4) -> str:
    """Format prior failed attempts for inclusion in the next prompt."""
    if not failures:
        return "No prior attempts yet."
    lines = ["Past attempts that FAILED — do not repeat them:"]
    for i, f in enumerate(failures[-max_examples:], start=1):
        lines.append(f"\nAttempt {i} ({f['reason']}):\n```python\n{f['source'].strip()}\n```")
    return "\n".join(lines)


def _build_prompt(
    target: TargetFunction,
    spec: CandidateSpec,
    past_failures: list[dict],
    attempt_idx: int,
) -> str:
    hint = _STRATEGY_HINTS[attempt_idx % len(_STRATEGY_HINTS)]
    return _PROMPT_TEMPLATE.format(
        reference_source=target.source.strip(),
        precondition_src=spec.precondition_src.strip() or "# (no precondition supplied — assume True)",
        postcondition_src=spec.postcondition_src.strip(),
        function_name=target.name,
        strategy_hint=hint,
        failures_block=_failure_summary(past_failures),
    )


# ---------- response parsing ----------------------------------------------

_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _extract_block(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else text


def _compile_callable(source: str, function_name: str) -> tuple[Callable | None, str | None]:
    """Compile ``source`` and return (callable, error). Disallows imports for safety."""
    if re.search(r"^\s*(import|from)\s+\S", source, re.MULTILINE):
        return None, "twin tried to import a module — rejected for safety"
    ns: dict = {}
    try:
        exec(compile(source, f"<twin-{function_name}>", "exec"), ns)
    except Exception as exc:
        return None, f"compile/exec failed: {type(exc).__name__}: {exc}"
    fn = ns.get(function_name)
    if not callable(fn):
        return None, f"no callable named {function_name!r} in generated code"
    return fn, None


# ---------- main entry point ----------------------------------------------

@dataclass
class _Attempt:
    source: str
    reason: str  # human-readable failure reason


def synthesize_evil_twins(
    target: TargetFunction,
    spec: CandidateSpec,
    attacker_model: str = "groq:llama-3.3-70b-versatile",
    n_rounds: int = 3,
    n_candidates_per_round: int = 4,
    distance_threshold: float = 0.20,
    temperature_start: float = 0.85,
    spec_check_examples: int = 80,
) -> tuple[list[EvilTwin], list[_Attempt]]:
    """Synthesize evil twins for ``(target, spec)``.

    Returns (twins, all_attempts). ``all_attempts`` includes both successful evil twins and
    failed attempts — useful for the report's effort / yield analysis.

    Stops early if at least one evil twin has been found AND the round budget is half-spent;
    otherwise runs the full budget.
    """
    if spec.postcondition is None:
        return [], [_Attempt(source="", reason="spec has no postcondition — nothing to attack")]

    twins: list[EvilTwin] = []
    failures: list[dict] = []  # for prompt feedback
    all_attempts: list[_Attempt] = []
    attempt_idx = 0

    for round_idx in range(n_rounds):
        for cand_idx in range(n_candidates_per_round):
            temperature = min(1.3, temperature_start + 0.05 * attempt_idx)
            prompt = _build_prompt(target, spec, failures, attempt_idx)
            attempt_idx += 1

            try:
                resp = complete(
                    model_id=attacker_model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=1024,
                    use_cache=False,  # we want diverse samples — cache would collapse to one
                )
                source = _extract_block(resp.text)
            except Exception as exc:
                attempt = _Attempt(source="", reason=f"api_error: {type(exc).__name__}: {exc}")
                all_attempts.append(attempt)
                continue

            callable_fn, err = _compile_callable(source, target.name)
            if callable_fn is None:
                attempt = _Attempt(source=source, reason=err or "compile failed")
                all_attempts.append(attempt)
                failures.append({"source": source, "reason": err or "compile failed"})
                continue

            # Reject literal copies of the reference.
            if source.strip() == target.source.strip():
                attempt = _Attempt(source=source, reason="exact copy of reference")
                all_attempts.append(attempt)
                failures.append({"source": source, "reason": "exact copy of reference"})
                continue

            if not satisfies_spec(target, callable_fn, spec, max_examples=spec_check_examples):
                attempt = _Attempt(source=source, reason="did not satisfy spec")
                all_attempts.append(attempt)
                failures.append({"source": source, "reason": "did not satisfy spec"})
                continue

            dist = behavioral_distance(target, callable_fn, n_random=40)
            if dist["score"] < distance_threshold:
                attempt = _Attempt(source=source, reason=f"too similar (distance={dist['score']:.2f})")
                all_attempts.append(attempt)
                failures.append({"source": source, "reason": f"too similar to reference (distance={dist['score']:.2f})"})
                continue

            twins.append(EvilTwin(
                target_name=target.name,
                spec_id=f"{spec.model}:{spec.attempt_id}",
                attacker_model=attacker_model,
                twin_source=source,
                distance_score=dist["score"],
                distance_breakdown=dist,
                attack_round=round_idx,
                prompt_strategy=_STRATEGY_HINTS[(attempt_idx - 1) % len(_STRATEGY_HINTS)],
            ))
            all_attempts.append(_Attempt(source=source, reason=f"EVIL TWIN (distance={dist['score']:.2f})"))

        # Early-exit heuristic: a twin per round is plenty.
        if len(twins) >= n_rounds and round_idx >= n_rounds // 2:
            break

    return twins, all_attempts
