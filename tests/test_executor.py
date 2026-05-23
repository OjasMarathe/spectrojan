"""Tests for the executor module.

Builds a TargetFunction from corpus/bio/reverse_complement.py, then exercises
satisfies_spec / find_failing_inputs with hand-written specs that are either correct
or deliberately broken.
"""
from __future__ import annotations

from pathlib import Path

from spectrojan.corpus_loader import load_target
from spectrojan.executor import find_failing_inputs, satisfies_spec
from spectrojan.types import CandidateSpec


CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"


def _make_spec(pre, post, name="hand-written") -> CandidateSpec:
    return CandidateSpec(
        target_name="t",
        model="manual:hand",
        attempt_id=0,
        raw_text="",
        precondition_src="",
        postcondition_src="",
        precondition=pre,
        postcondition=post,
    )


def test_correct_spec_accepts_reference_impl():
    """A correct spec should accept the reference implementation: no failing inputs."""
    target = load_target(CORPUS_ROOT / "bio" / "reverse_complement.py")
    # Correct postcondition: result is the reverse complement, computed independently.
    pair = str.maketrans("ACGTacgt", "TGCAtgca")
    def post(seq, result):
        return isinstance(result, str) and result == seq.translate(pair)[::-1]
    spec = _make_spec(pre=None, post=post)
    failures = find_failing_inputs(target, target.reference_impl, spec, max_examples=50)
    assert failures == [], f"unexpected failures: {failures[:2]}"
    assert satisfies_spec(target, target.reference_impl, spec, max_examples=50)


def test_broken_impl_fails_correct_spec():
    """A wrong implementation (identity) should be caught by the correct spec."""
    target = load_target(CORPUS_ROOT / "bio" / "reverse_complement.py")
    pair = str.maketrans("ACGTacgt", "TGCAtgca")
    def post(seq, result):
        return isinstance(result, str) and result == seq.translate(pair)[::-1]
    spec = _make_spec(pre=None, post=post)
    wrong_impl = lambda seq: seq  # identity, not reverse-complement
    failures = find_failing_inputs(target, wrong_impl, spec, max_examples=50)
    assert any(f.reason == "spec_rejects_correct_output" for f in failures), \
        f"correct spec should reject identity-impl outputs; got {failures}"
    assert not satisfies_spec(target, wrong_impl, spec, max_examples=50)


def test_weak_spec_admits_wrong_impl():
    """A weak postcondition ('result is a string') admits the broken identity-impl.

    This is the spec-validation failure mode SpecTrojan is built to expose. We assert that
    the executor reports the spec as satisfied even though the implementation is wrong —
    this is the symptom; ETS is the cure.
    """
    target = load_target(CORPUS_ROOT / "bio" / "reverse_complement.py")
    def weak_post(seq, result):
        return isinstance(result, str)
    spec = _make_spec(pre=None, post=weak_post)
    wrong_impl = lambda seq: seq  # identity
    assert satisfies_spec(target, wrong_impl, spec, max_examples=80), \
        "weak spec should (wrongly) accept the broken impl — that's the bug the tool finds"


def test_gc_content_strategy_uses_hint_alphabet():
    """Sanity: the heuristic strategy honors the {A,C,G,T,...} alphabet from INPUT_HINT."""
    target = load_target(CORPUS_ROOT / "bio" / "gc_content.py")
    def post(seq, result):
        if not seq:
            return result == 0.0
        gc = sum(1 for b in seq.upper() if b in "GC")
        return abs(result - gc / len(seq)) < 1e-9
    spec = _make_spec(pre=None, post=post)
    failures = find_failing_inputs(target, target.reference_impl, spec, max_examples=50)
    assert failures == [], f"alphabet-restricted strategy hit non-DNA chars: {failures[:2]}"
