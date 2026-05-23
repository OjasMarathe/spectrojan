"""Generate candidate specs from multiple LLMs for a given target function.

Module API:

    specs = generate_specs(
        target,
        n_per_model=3,
        models=["groq:llama-3.3-70b-versatile", "gemini:gemini-2.5-flash"],
    )

Each returned CandidateSpec contains executable ``precondition`` / ``postcondition`` callables,
parsed from the model's fenced Python block. Models are prompted for a strict format —
a single fenced Python block defining two top-level functions:

    def precondition(*args) -> bool: ...
    def postcondition(*args, result) -> bool: ...
"""
from __future__ import annotations

import re
from typing import Callable

from .llm import complete
from .types import CandidateSpec, TargetFunction


PROMPT_TEMPLATE_WITH_SOURCE = """You are writing a formal specification for the following Python function.

```python
{source}
```

Intended behavior (docstring):
{docstring}

Domain hint: {domain}

Produce a specification as TWO Python functions in a single fenced code block:

1. `precondition(*args)` — returns True iff the inputs are in the function's intended domain.
2. `postcondition(*args, result)` — returns True iff `result` is a valid output for these inputs.

The specification should be:
- Total (terminates on all inputs)
- Pure (no I/O, no globals)
- Strict enough to reject obviously wrong outputs
- Lenient enough to accept all genuinely correct outputs
- Use ONLY the Python standard library

Match the target function's parameter names. Use `result` as the last parameter of `postcondition`.

Return ONLY the fenced ```python ... ``` code block — no commentary, no other text."""


PROMPT_TEMPLATE_INTENT_ONLY = """You are writing a formal specification for a Python function based ONLY on its signature and high-level intent. You do NOT have access to the implementation.

Function signature:
```python
def {function_name}{signature}: ...
```

Intent (from the function's public description):
{docstring}

Domain hint: {domain}

Produce a specification as TWO Python functions in a single fenced code block:

1. `precondition(*args)` — returns True iff the inputs are in the function's intended domain.
2. `postcondition(*args, result)` — returns True iff `result` is a valid output for these inputs.

The specification should be:
- Total (terminates on all inputs)
- Pure (no I/O, no globals)
- Strict enough to reject obviously wrong outputs
- Lenient enough to accept all genuinely correct outputs
- Use ONLY the Python standard library

Match the function's parameter names. Use `result` as the last parameter of `postcondition`.

Return ONLY the fenced ```python ... ``` code block — no commentary, no other text."""


def build_prompt(target: TargetFunction, intent_only: bool = False) -> str:
    """Build the spec-generation prompt for a target.

    When ``intent_only`` is True, the prompt shows only the function signature and
    a (deliberately abstracted) docstring — mirroring the realistic case where the spec
    author does not have access to the reference implementation. This is the framing used
    for the Bio Honeypot demo.
    """
    import inspect

    # Prefer a PUBLIC_DOCSTRING (defined by the corpus file) when present — used in the
    # honeypot to deliberately under-specify the criteria the LLM has to constrain.
    docstring = getattr(target, "public_docstring", None) or target.docstring

    if intent_only:
        sig = str(inspect.signature(target.reference_impl))
        return PROMPT_TEMPLATE_INTENT_ONLY.format(
            function_name=target.name,
            signature=sig,
            docstring=docstring.strip(),
            domain=target.domain,
        )
    return PROMPT_TEMPLATE_WITH_SOURCE.format(
        source=target.source.strip(),
        docstring=docstring.strip(),
        domain=target.domain,
    )


# Preserve old name for backward compat with already-imported code.
PROMPT_TEMPLATE = PROMPT_TEMPLATE_WITH_SOURCE


# ---------- parsing --------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _extract_python_block(text: str) -> str:
    """Return the contents of the first ```python ... ``` block, or the raw text."""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1)
    # Fallback: maybe the model returned bare code (no fence).
    return text


def _split_pre_post(block: str) -> tuple[str, str]:
    """Return (precondition_src, postcondition_src), each containing a single function def.

    Handles a code block that contains a `precondition` and `postcondition` defined at top level,
    plus optional helper definitions which we keep in both source strings (so each function can
    reference the helpers when exec'd).
    """
    pre_match = re.search(r"^(?:def\s+precondition\b.*?)(?=^def\s+\w+\(|\Z)", block, re.MULTILINE | re.DOTALL)
    post_match = re.search(r"^(?:def\s+postcondition\b.*?)(?=^def\s+\w+\(|\Z)", block, re.MULTILINE | re.DOTALL)
    pre_src = pre_match.group(0).rstrip() if pre_match else ""
    post_src = post_match.group(0).rstrip() if post_match else ""
    return pre_src, post_src


SAFE_GLOBALS: dict[str, object] = {
    "__builtins__": __builtins__,
}


def parse_spec_response(
    text: str,
    target_name: str,
    model: str,
    attempt_id: int,
) -> CandidateSpec:
    """Parse an LLM response into a CandidateSpec with callable pre/postcondition.

    On parse or exec failure, returns a CandidateSpec with parse_error set and
    pre/postcondition = None — the executor will treat such specs as vacuously true,
    but we filter them out before running ETS.
    """
    block = _extract_python_block(text)
    pre_src, post_src = _split_pre_post(block)

    precondition: Callable | None = None
    postcondition: Callable | None = None
    parse_error: str | None = None

    try:
        # Use a SINGLE namespace so helper functions defined in the block remain visible
        # to precondition/postcondition via their __globals__. Splitting globals/locals
        # would hide helpers from the spec functions.
        ns: dict[str, object] = dict(SAFE_GLOBALS)
        exec(block, ns)
        precondition = ns.get("precondition")  # type: ignore[assignment]
        postcondition = ns.get("postcondition")  # type: ignore[assignment]
        if not callable(precondition) and not callable(postcondition):
            parse_error = "neither precondition nor postcondition found"
        elif not callable(postcondition):
            parse_error = "no postcondition function found"
            postcondition = None
        elif not callable(precondition):
            # A missing precondition is OK — treated as 'True' by the executor.
            precondition = None
    except Exception as exc:
        parse_error = f"exec failed: {type(exc).__name__}: {exc}"
        precondition = None
        postcondition = None

    return CandidateSpec(
        target_name=target_name,
        model=model,
        attempt_id=attempt_id,
        raw_text=text,
        precondition_src=pre_src,
        postcondition_src=post_src,
        precondition=precondition if callable(precondition) else None,
        postcondition=postcondition if callable(postcondition) else None,
        parse_error=parse_error,
    )


# ---------- top-level generation ------------------------------------------

DEFAULT_MODELS = [
    "groq:llama-3.3-70b-versatile",
    "gemini:gemini-2.5-flash",
]


def generate_specs(
    target: TargetFunction,
    n_per_model: int = 3,
    models: list[str] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    intent_only: bool = False,
) -> list[CandidateSpec]:
    """Generate ``n_per_model`` specs from each of the listed models.

    The temperature is bumped slightly across attempts to encourage variety. The LLM
    cache means repeated runs cost nothing once the responses are cached. Pass
    ``intent_only=True`` to use the Bio-Honeypot-style prompt that hides the reference
    implementation.
    """
    models = models or DEFAULT_MODELS
    prompt = build_prompt(target, intent_only=intent_only)
    specs: list[CandidateSpec] = []

    for model in models:
        for attempt in range(n_per_model):
            attempt_temp = min(1.2, temperature + 0.1 * attempt)
            try:
                resp = complete(
                    model_id=model,
                    prompt=prompt,
                    temperature=attempt_temp,
                    max_tokens=max_tokens,
                )
                spec = parse_spec_response(resp.text, target.name, model, attempt)
            except Exception as exc:
                spec = CandidateSpec(
                    target_name=target.name,
                    model=model,
                    attempt_id=attempt,
                    raw_text="",
                    precondition_src="",
                    postcondition_src="",
                    parse_error=f"api_error: {type(exc).__name__}: {exc}",
                )
            specs.append(spec)

    return specs


def usable_specs(specs: list[CandidateSpec]) -> list[CandidateSpec]:
    """Filter out specs that failed to parse or are missing a postcondition."""
    return [s for s in specs if s.parse_error is None and s.postcondition is not None]
