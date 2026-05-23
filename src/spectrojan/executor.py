"""Spec executor + spec-conformance checker.

Two responsibilities:

  1. ``find_failing_inputs(target, impl, spec)`` — Hypothesis search for inputs where the
     spec's precondition holds but the postcondition rejects ``impl(*xs)``.
  2. ``satisfies_spec(target, impl, spec)`` — boolean wrapper used by the twin synthesizer
     to decide whether a candidate evil twin is admissible.

Both depend on a Hypothesis ``SearchStrategy`` for the target's inputs. Strategies are
chosen in this order:

  - A ``STRATEGY`` callable defined in the corpus module (highest priority — explicit).
  - Heuristic inference from the function signature + INPUT_HINT (fallback).
"""
from __future__ import annotations

import inspect
import re
import signal
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, get_args, get_origin

from hypothesis import HealthCheck, given, settings, strategies as st

from .types import CandidateSpec, TargetFunction


# ---------- failure record -------------------------------------------------

@dataclass
class FailingInput:
    args: tuple
    output: Any
    reason: str  # "spec_rejects_correct_output" | "impl_raised" | "spec_raised"


# ---------- strategy synthesis --------------------------------------------

def _alphabet_from_hint(hint: str) -> str | None:
    """Look for an explicit '{A, C, G, T}' style alphabet in the hint."""
    m = re.search(r"\{([^}]+)\}", hint)
    if not m:
        return None
    chars = [c.strip() for c in m.group(1).split(",")]
    chars = [c for c in chars if len(c) == 1]
    return "".join(chars) if chars else None


def _length_range_from_hint(hint: str, default: tuple[int, int] = (0, 30)) -> tuple[int, int]:
    m = re.search(r"length\s+(\d+)\s*[-–]\s*(\d+)", hint)
    if m:
        return int(m.group(1)), int(m.group(2))
    return default


def _int_range_from_hint(hint: str, default: tuple[int, int] = (-50, 50)) -> tuple[int, int]:
    m = re.search(r"in\s*\[(-?\d+)\s*,\s*(-?\d+)\]", hint)
    if m:
        return int(m.group(1)), int(m.group(2))
    return default


def _strategy_for_param(name: str, annotation: Any, hint: str) -> st.SearchStrategy:
    """Best-effort heuristic strategy for one parameter."""
    origin = get_origin(annotation)

    if annotation is str:
        alphabet = _alphabet_from_hint(hint)
        min_len, max_len = _length_range_from_hint(hint)
        if alphabet:
            return st.text(alphabet=alphabet, min_size=min_len, max_size=max_len)
        return st.text(
            alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            min_size=min_len,
            max_size=max_len,
        )

    if annotation is int:
        lo, hi = _int_range_from_hint(hint)
        return st.integers(min_value=lo, max_value=hi)

    if annotation is float:
        return st.floats(min_value=0.0, max_value=40.0, allow_nan=False, allow_infinity=False)

    if annotation is bool:
        return st.booleans()

    if origin in (list,) or annotation is list:
        args = get_args(annotation)
        inner = args[0] if args else int
        elem_strat = _strategy_for_param(name + "_elem", inner, hint)
        return st.lists(elem_strat, min_size=0, max_size=8)

    if origin in (tuple,) or annotation is tuple:
        args = get_args(annotation)
        if args:
            elem_strats = [_strategy_for_param(name + f"_{i}", a, hint) for i, a in enumerate(args)]
            return st.tuples(*elem_strats)
        return st.tuples(st.integers(), st.integers())

    if origin in (dict,) or annotation is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return st.dictionaries(
                _strategy_for_param("k", args[0], hint),
                _strategy_for_param("v", args[1], hint),
                max_size=5,
            )
        return st.dictionaries(st.text(min_size=1, max_size=4), st.integers(), max_size=5)

    return st.from_type(annotation) if annotation is not inspect.Parameter.empty else st.integers()


def auto_strategy(target: TargetFunction) -> st.SearchStrategy:
    """Heuristic strategy returning the function's argument tuple."""
    sig = inspect.signature(target.reference_impl)
    hint = target.input_strategy_hint
    param_strats = [
        _strategy_for_param(pname, p.annotation, hint)
        for pname, p in sig.parameters.items()
    ]
    return st.tuples(*param_strats) if param_strats else st.tuples()


def strategy_for(target: TargetFunction) -> st.SearchStrategy:
    """Public entry: corpus-supplied explicit_strategy wins; otherwise heuristic."""
    explicit = getattr(target, "explicit_strategy", None)
    return explicit if explicit is not None else auto_strategy(target)


# ---------- safe call helpers ----------------------------------------------

@contextmanager
def _time_limit(seconds: float):
    """POSIX-only soft time limit using SIGALRM. No-op on Windows or in non-main threads."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    try:
        old = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("call timed out")))
    except ValueError:
        # non-main thread — fall back to no timeout
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _safe_call(fn: Callable, args: tuple, per_call_timeout_s: float = 1.0) -> tuple[Any, Exception | None]:
    try:
        with _time_limit(per_call_timeout_s):
            return fn(*args), None
    except Exception as exc:
        return None, exc


# ---------- spec evaluation ------------------------------------------------

def _eval_precondition(spec: CandidateSpec, args: tuple) -> tuple[bool, Exception | None]:
    if spec.precondition is None:
        return True, None
    try:
        with _time_limit(0.5):
            return bool(spec.precondition(*args)), None
    except Exception as exc:
        return False, exc


def _eval_postcondition(spec: CandidateSpec, args: tuple, result: Any) -> tuple[bool, Exception | None]:
    if spec.postcondition is None:
        return True, None
    try:
        with _time_limit(0.5):
            return bool(spec.postcondition(*args, result)), None
    except Exception as exc:
        return False, exc


# ---------- public API -----------------------------------------------------

def _check_one(target, impl, spec, args, failures, per_call_timeout_s):
    """Returns True if a failure was recorded for these args."""
    pre_ok, pre_err = _eval_precondition(spec, args)
    if pre_err is not None:
        failures.append(FailingInput(args=args, output=None, reason="spec_raised"))
        return True
    if not pre_ok:
        return False

    result, impl_err = _safe_call(impl, args, per_call_timeout_s)
    if impl_err is not None:
        failures.append(FailingInput(args=args, output=None, reason="impl_raised"))
        return True

    post_ok, post_err = _eval_postcondition(spec, args, result)
    if post_err is not None:
        failures.append(FailingInput(args=args, output=result, reason="spec_raised"))
        return True
    if not post_ok:
        failures.append(FailingInput(args=args, output=result, reason="spec_rejects_correct_output"))
        return True
    return False


def find_failing_inputs(
    target: TargetFunction,
    impl: Callable,
    spec: CandidateSpec,
    max_examples: int = 200,
    per_call_timeout_s: float = 1.0,
) -> list[FailingInput]:
    """Search for inputs where pre(args) ∧ ¬post(args, impl(args)).

    Strategy: try REFERENCE_EXAMPLES first (cheap, high-signal), then Hypothesis search.
    Caps at 5 distinct failures to keep output manageable.
    """
    failures: list[FailingInput] = []

    for raw_args, _expected in getattr(target, "reference_examples", []) or []:
        if len(failures) >= 5:
            break
        _check_one(target, impl, spec, tuple(raw_args), failures, per_call_timeout_s)

    if len(failures) >= 5:
        return failures

    strategy = strategy_for(target)

    @given(strategy)
    @settings(
        max_examples=max_examples,
        deadline=None,
        derandomize=False,
        database=None,
        suppress_health_check=list(HealthCheck),
    )
    def _driver(args):
        # We never raise — failures accumulate into the closure. Hypothesis then sees
        # every example as "passing" and runs the full budget without shrinking.
        if len(failures) >= 5:
            return
        _check_one(target, impl, spec, tuple(args), failures, per_call_timeout_s)

    try:
        _driver()
    except Exception:
        # Some pathological strategies can raise during generation — recover gracefully.
        pass

    return failures


def satisfies_spec(
    target: TargetFunction,
    impl: Callable,
    spec: CandidateSpec,
    max_examples: int = 150,
    per_call_timeout_s: float = 1.0,
) -> bool:
    return not find_failing_inputs(target, impl, spec, max_examples, per_call_timeout_s)
