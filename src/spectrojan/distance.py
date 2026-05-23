"""Behavioral distance between two implementations of the same function.

ETS needs a way to say "this twin is meaningfully different from the reference, not just a
syntactic rewrite." We measure distance on three axes:

  1. Hypothesis sample disagreement — fraction of random inputs (drawn from the
     INPUT_HINT-derived strategy) on which the two functions return different values.
  2. Reference-example disagreement — fraction of the corpus's REFERENCE_EXAMPLES on which
     the twin disagrees with the reference. This is the *intent-bearing* signal — weighted
     heaviest in the combined score.
  3. Domain-invariant violation — fraction of sampled inputs on which the candidate
     violates a domain invariant that the reference respects.

The combined score is in [0, 1]; we use:

    score = 0.55 * example_disagree_rate
          + 0.30 * hypothesis_disagree_rate
          + 0.15 * invariant_violation_rate

A twin must clear ``min_distance`` on the combined score to be considered "meaningfully
divergent" by the synthesizer.
"""
from __future__ import annotations

from typing import Callable

from hypothesis import HealthCheck, given, settings, strategies as st

from .executor import _safe_call, strategy_for
from .types import TargetFunction


def _equal(a: object, b: object) -> bool:
    """Tolerant equality: dicts/lists by structure, floats with small epsilon, else ==."""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except Exception:
            return False
    try:
        return a == b
    except Exception:
        return False


def _disagree_rate(reference: Callable, candidate: Callable, inputs: list[tuple], per_call_timeout_s: float) -> float:
    """Fraction of inputs on which reference and candidate produce different outputs."""
    if not inputs:
        return 0.0
    diffs = 0
    valid = 0
    for args in inputs:
        ref_out, ref_err = _safe_call(reference, args, per_call_timeout_s)
        cand_out, cand_err = _safe_call(candidate, args, per_call_timeout_s)
        if ref_err is not None and cand_err is not None:
            # Both raise — call it a 'match' (both refuse this input identically).
            valid += 1
            continue
        if (ref_err is None) != (cand_err is None):
            valid += 1
            diffs += 1
            continue
        valid += 1
        if not _equal(ref_out, cand_out):
            diffs += 1
    return diffs / valid if valid else 0.0


def _invariant_violation_rate(
    reference: Callable,
    candidate: Callable,
    invariant: Callable,
    inputs: list[tuple],
    per_call_timeout_s: float,
) -> float:
    if not inputs:
        return 0.0
    violations = 0
    counted = 0
    for args in inputs:
        ref_out, ref_err = _safe_call(reference, args, per_call_timeout_s)
        cand_out, cand_err = _safe_call(candidate, args, per_call_timeout_s)
        if ref_err is not None:
            continue  # don't count when the reference refused
        try:
            ref_holds = bool(invariant(args, ref_out))
        except Exception:
            continue
        if not ref_holds:
            continue  # reference itself violates — skip
        if cand_err is not None:
            counted += 1
            violations += 1
            continue
        try:
            cand_holds = bool(invariant(args, cand_out))
        except Exception:
            cand_holds = False
        counted += 1
        if not cand_holds:
            violations += 1
    return violations / counted if counted else 0.0


def _sample_inputs(target: TargetFunction, n: int = 50) -> list[tuple]:
    """Draw n inputs from the target's strategy. Uses the same machinery as the executor."""
    strategy = strategy_for(target)
    sampled: list[tuple] = []

    @given(strategy)
    @settings(
        max_examples=n,
        deadline=None,
        database=None,
        suppress_health_check=list(HealthCheck),
    )
    def _driver(args):
        if len(sampled) < n:
            sampled.append(tuple(args))

    try:
        _driver()
    except Exception:
        pass
    return sampled


def behavioral_distance(
    target: TargetFunction,
    candidate: Callable,
    n_random: int = 50,
    per_call_timeout_s: float = 1.0,
) -> dict:
    """Compute the three sub-rates and the combined distance score for ``candidate``."""
    reference = target.reference_impl
    example_inputs = [tuple(args) for args, _ in target.reference_examples]
    random_inputs = _sample_inputs(target, n=n_random)

    hyp_rate = _disagree_rate(reference, candidate, random_inputs, per_call_timeout_s)
    ex_rate = _disagree_rate(reference, candidate, example_inputs, per_call_timeout_s)

    inv_rate = 0.0
    if target.domain_invariant is not None:
        inv_rate = _invariant_violation_rate(
            reference, candidate, target.domain_invariant, random_inputs, per_call_timeout_s
        )

    score = 0.55 * ex_rate + 0.30 * hyp_rate + 0.15 * inv_rate
    return {
        "hypothesis_disagree_rate": hyp_rate,
        "example_disagree_rate": ex_rate,
        "invariant_violation_rate": inv_rate,
        "score": score,
        "n_random": len(random_inputs),
        "n_examples": len(example_inputs),
    }
