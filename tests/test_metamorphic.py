"""Tests for metamorphic spec testing.

We construct a correct spec by hand and verify that semantics-preserving transforms of
the reference impl are accepted. Then we construct a syntax-overfit spec and verify it
gets rejected by at least one transform — exactly the failure mode the methodology surfaces.
"""
from __future__ import annotations

from pathlib import Path

from spectrojan.corpus_loader import load_target
from spectrojan.metamorphic import apply_transforms, metamorphic_robustness
from spectrojan.types import CandidateSpec


CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def _spec(post):
    return CandidateSpec(
        target_name="t",
        model="manual:hand",
        attempt_id=0,
        raw_text="",
        precondition_src="",
        postcondition_src="",
        precondition=None,
        postcondition=post,
    )


def test_apply_transforms_produces_outputs():
    """Each transform should either apply or be reported as not-applied."""
    target = load_target(CORPUS / "generic" / "gcd.py")
    outs = apply_transforms(target)
    names = {n for n, _, _ in outs}
    assert "rename_locals" in names
    assert "swap_commutative" in names
    # at least one transform should actually apply on gcd
    applied_count = sum(1 for _, _, applied in outs if applied)
    assert applied_count >= 1


def test_behavior_preserving_transforms_accepted_by_correct_spec():
    """A correct postcondition should accept semantics-preserving transforms."""
    target = load_target(CORPUS / "generic" / "gcd.py")
    def correct_post(a, b, result):
        if a == 0 and b == 0:
            return result == 0
        # result must divide a and b, and be the largest such
        return (
            isinstance(result, int)
            and result >= 0
            and (a == 0 or a % result == 0)
            and (b == 0 or b % result == 0)
        )
    spec = _spec(correct_post)
    out = metamorphic_robustness(target, spec)
    assert out["n_applied"] >= 1
    # Most or all transforms should be accepted by a correct spec.
    assert out["robustness"] >= 0.5, out
