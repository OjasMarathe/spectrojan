"""Cross-spec disagreement detector — BASELINE.

Demoted to baseline. Operates in the *input* space: given two candidate specs for the same
function, find inputs where the postconditions disagree on the reference output. ETS, by
contrast, operates in the *implementation* space.

Useful as (a) a cheap sanity-check that complements ETS and (b) a comparison point in the
final report's results table.
"""
from __future__ import annotations

from ..distance import _sample_inputs
from ..executor import _eval_postcondition, _eval_precondition, _safe_call
from ..types import CandidateSpec, Disagreement, TargetFunction


def find_disagreements(
    target: TargetFunction,
    specs: list[CandidateSpec],
    max_examples_per_pair: int = 120,
    per_call_timeout_s: float = 1.0,
    cap_per_pair: int = 3,
) -> list[Disagreement]:
    """For each pair (spec_a, spec_b), find inputs where they disagree on the reference output.

    Seeds with REFERENCE_EXAMPLES (intent-bearing inputs are the cheapest to find disagreements
    on), then draws Hypothesis-sampled inputs from the target's strategy.
    """
    usable = [s for s in specs if s.postcondition is not None]
    if len(usable) < 2:
        return []

    sampled = _sample_inputs(target, n=max_examples_per_pair)
    seeded = [tuple(args) for args, _ in target.reference_examples]
    candidate_inputs = seeded + sampled

    out: list[Disagreement] = []

    for i, spec_a in enumerate(usable):
        for spec_b in usable[i + 1:]:
            n_disagreements = 0
            for args in candidate_inputs:
                if n_disagreements >= cap_per_pair:
                    break

                pre_a, _ = _eval_precondition(spec_a, args)
                pre_b, _ = _eval_precondition(spec_b, args)
                if not (pre_a and pre_b):
                    continue

                ref_out, err = _safe_call(target.reference_impl, args, per_call_timeout_s)
                if err is not None:
                    continue

                v_a, err_a = _eval_postcondition(spec_a, args, ref_out)
                v_b, err_b = _eval_postcondition(spec_b, args, ref_out)
                if err_a is not None or err_b is not None:
                    continue
                if v_a != v_b:
                    out.append(Disagreement(
                        target_name=target.name,
                        spec_a=f"{spec_a.model}:{spec_a.attempt_id}",
                        spec_b=f"{spec_b.model}:{spec_b.attempt_id}",
                        inputs=args,
                        reference_output=ref_out,
                        spec_a_verdict=v_a,
                        spec_b_verdict=v_b,
                    ))
                    n_disagreements += 1

    return out
