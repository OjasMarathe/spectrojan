"""Attack-to-Strengthening Loop — secondary novelty.

When the twin synthesizer produces a successful evil twin, this module feeds the broken
spec + the twin back to an LLM and asks: *"Propose the minimal spec strengthening that
rules out this twin while still accepting the reference."*

The proposed strengthening is verified in two stages:

  1. **Accepts the reference?** — the strengthened postcondition must hold on all
     reference-impl outputs within the executor budget. Otherwise the proposal is
     over-strong (it would reject the function it's supposed to verify).
  2. **Closes the attack?** — the strengthened postcondition must REJECT at least one
     output of the original evil twin on an input in the spec's domain. Otherwise the
     proposal is vacuous (the twin still satisfies it).

If both checks pass, the strengthening is a *credited repair*. We also offer an iterative
mode that re-runs ETS against the strengthened spec to see whether a fresh twin can defeat
the repair — turning validation into an arms race we can demo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .executor import _eval_postcondition, _eval_precondition, _safe_call, satisfies_spec, strategy_for
from .llm import complete
from .spec_generator import parse_spec_response
from .types import CandidateSpec, TargetFunction


_PROMPT_TEMPLATE = """You wrote a specification for the following Python function, but the
specification was too weak — an adversarial program synthesizer found an EVIL TWIN
implementation that satisfies your spec yet behaves wrongly.

The reference implementation (the BEHAVIOR your spec should constrain):
```python
{reference_source}
```

Your current (too-weak) specification:
```python
{precondition_src}

{postcondition_src}
```

The evil twin that ALSO satisfies your spec:
```python
{evil_twin_source}
```

Critical reasoning step. Walk through a concrete input where the reference and the twin
disagree. Call that input X.
  - reference(X) returns: ___
  - evil_twin(X) returns: ___
Your new postcondition MUST satisfy:
  - postcondition(X, reference(X)) == True   ← still accept the correct answer
  - postcondition(X, evil_twin(X))  == False ← reject the twin's wrong answer

A common mistake: writing `postcondition` as `(result == True) OR (something about seq)`.
That admits any function that returns True. Use IMPLICATION, not disjunction. If a property
P of `seq` should force a specific value V of `result`, write:
    `(not P) or (result == V)`
NOT `P or (result == V)`.

Propose a strengthened postcondition that follows this discipline.

Return ONLY a fenced ```python ... ``` code block containing the (possibly updated)
`precondition` function and the strengthened `postcondition` function. No commentary."""


@dataclass
class StrengtheningResult:
    proposed_spec_text: str
    parse_error: str | None
    new_postcondition_src: str
    new_precondition_src: str
    accepts_reference: bool
    closes_attack: bool
    rejection_example: tuple | None  # an input where the new spec rejects the twin
    raw_response: str


def _compile_twin_callable(source: str, function_name: str) -> Callable | None:
    ns: dict = {}
    try:
        exec(compile(source, f"<twin-{function_name}>", "exec"), ns)
    except Exception:
        return None
    fn = ns.get(function_name)
    return fn if callable(fn) else None


def _twin_rejected_on_any_input(
    target: TargetFunction,
    new_spec: CandidateSpec,
    twin_callable: Callable,
    per_call_timeout_s: float = 1.0,
    max_examples: int = 80,
) -> tuple[bool, tuple | None]:
    """Search for an input where the new spec rejects the twin's output.

    Tries REFERENCE_EXAMPLES first (high signal), then Hypothesis-sampled inputs.
    Returns (closes_attack, rejection_example).
    """
    strategy = strategy_for(target)
    seeds = [tuple(args) for args, _ in target.reference_examples]

    def _try(args: tuple) -> bool:
        pre_ok, _ = _eval_precondition(new_spec, args)
        if not pre_ok:
            return False
        twin_out, twin_err = _safe_call(twin_callable, args, per_call_timeout_s)
        if twin_err is not None:
            # Twin crashed on a spec-admitted input — that itself counts as the spec
            # rejecting (in our framing): the contract no longer admits the twin.
            return True
        post_ok, post_err = _eval_postcondition(new_spec, args, twin_out)
        if post_err is not None:
            return True  # crash on twin output ≈ rejection
        return not post_ok

    for args in seeds:
        if _try(args):
            return True, args

    sampled: list[tuple] = []
    from hypothesis import HealthCheck, given, settings

    @given(strategy)
    @settings(
        max_examples=max_examples,
        deadline=None,
        database=None,
        suppress_health_check=list(HealthCheck),
    )
    def _driver(args):
        sampled.append(tuple(args))

    try:
        _driver()
    except Exception:
        pass

    for args in sampled:
        if _try(args):
            return True, args
    return False, None


def propose_strengthening(
    target: TargetFunction,
    spec: CandidateSpec,
    evil_twin_source: str,
    spec_author_model: str = "groq:llama-3.3-70b-versatile",
    temperature: float = 0.4,
) -> StrengtheningResult:
    """Ask the LLM for a strengthened spec; verify accepts-reference + closes-attack."""
    prompt = _PROMPT_TEMPLATE.format(
        reference_source=target.source.strip(),
        precondition_src=spec.precondition_src.strip() or "# (no precondition supplied — assume True)",
        postcondition_src=spec.postcondition_src.strip(),
        evil_twin_source=evil_twin_source.strip(),
    )

    try:
        resp = complete(
            model_id=spec_author_model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=1024,
            use_cache=False,
        )
    except Exception as exc:
        return StrengtheningResult(
            proposed_spec_text="",
            parse_error=f"api_error: {type(exc).__name__}: {exc}",
            new_postcondition_src="",
            new_precondition_src="",
            accepts_reference=False,
            closes_attack=False,
            rejection_example=None,
            raw_response="",
        )

    new_spec = parse_spec_response(resp.text, target.name, spec_author_model, attempt_id=999)
    if new_spec.parse_error is not None or new_spec.postcondition is None:
        return StrengtheningResult(
            proposed_spec_text=resp.text,
            parse_error=new_spec.parse_error or "no postcondition",
            new_postcondition_src=new_spec.postcondition_src,
            new_precondition_src=new_spec.precondition_src,
            accepts_reference=False,
            closes_attack=False,
            rejection_example=None,
            raw_response=resp.text,
        )

    # 1. Does the strengthened spec still accept the reference impl?
    accepts_ref = satisfies_spec(target, target.reference_impl, new_spec, max_examples=120)

    # 2. Does it reject the evil twin?
    closes = False
    rejection_example: tuple | None = None
    twin_callable = _compile_twin_callable(evil_twin_source, target.name)
    if twin_callable is not None:
        closes, rejection_example = _twin_rejected_on_any_input(target, new_spec, twin_callable)

    return StrengtheningResult(
        proposed_spec_text=resp.text,
        parse_error=None,
        new_postcondition_src=new_spec.postcondition_src,
        new_precondition_src=new_spec.precondition_src,
        accepts_reference=accepts_ref,
        closes_attack=closes,
        rejection_example=rejection_example,
        raw_response=resp.text,
    )


def iterate_strengthening(
    target: TargetFunction,
    spec: CandidateSpec,
    evil_twin_source: str,
    spec_author_model: str = "groq:llama-3.3-70b-versatile",
    max_rounds: int = 3,
) -> list[StrengtheningResult]:
    """Iteratively strengthen — useful for the demo's "arms race" visual.

    After each successful strengthening, the caller can re-attack with twin_synthesizer
    to see whether a fresh twin defeats the repair. Returning the sequence lets the demo
    show "round 1: hole found and patched", "round 2: another hole if any", etc.
    """
    results: list[StrengtheningResult] = []
    current_spec = spec
    current_twin_source = evil_twin_source
    for _ in range(max_rounds):
        r = propose_strengthening(target, current_spec, current_twin_source, spec_author_model)
        results.append(r)
        if not (r.accepts_reference and r.closes_attack):
            break
        # Build a new CandidateSpec from the strengthened text and continue (caller can
        # decide whether to re-attack and feed back another twin).
        # For now we stop after the first credited repair; arms-race re-attack belongs in
        # a higher-level orchestration script.
        break
    return results
