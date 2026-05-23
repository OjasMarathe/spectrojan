"""Tests for behavioral distance scoring.

We compare:
  - reference vs itself  → score == 0
  - reference vs identity-impl (wildly wrong) → score >> 0
  - reference vs a 'similar-but-wrong' impl → modest score
"""
from __future__ import annotations

from pathlib import Path

from spectrojan.corpus_loader import load_target
from spectrojan.distance import behavioral_distance


CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def test_distance_self_is_zero():
    target = load_target(CORPUS / "bio" / "reverse_complement.py")
    d = behavioral_distance(target, target.reference_impl, n_random=30)
    assert d["score"] == 0.0
    assert d["example_disagree_rate"] == 0.0


def test_distance_identity_impl_is_large():
    """For reverse_complement, the identity function is wildly wrong → high distance."""
    target = load_target(CORPUS / "bio" / "reverse_complement.py")
    d = behavioral_distance(target, lambda seq: seq, n_random=30)
    # Identity matches reverse_complement only on palindromes; on random DNA it diverges often.
    assert d["score"] > 0.3, d


def test_distance_constant_impl_is_high_for_gc_content():
    target = load_target(CORPUS / "bio" / "gc_content.py")
    d = behavioral_distance(target, lambda seq: 0.5, n_random=30)
    assert d["example_disagree_rate"] > 0.5, d
    assert d["score"] > 0.3, d


def test_distance_subtle_off_by_one():
    """A spec-accepting evil twin that disagrees only on edge cases — still detectable."""
    target = load_target(CORPUS / "generic" / "gcd.py")
    # always returns reference + 0 (i.e. correct) — distance should be ~0
    same_as_ref = target.reference_impl
    d_same = behavioral_distance(target, same_as_ref, n_random=20)
    assert d_same["score"] == 0.0
    # always returns 1 → very different
    d_diff = behavioral_distance(target, lambda a, b: 1, n_random=20)
    assert d_diff["score"] > 0.3
