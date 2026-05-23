"""Tests for the strengthening loop — local-only checks of the verification logic.

We don't hit the LLM here; we construct hand-crafted (broken spec, evil twin) pairs and
verify that the post-LLM verification steps (accepts_reference, closes_attack) are correct.
"""
from __future__ import annotations

from pathlib import Path

from spectrojan.corpus_loader import load_target
from spectrojan.strengthening import _twin_rejected_on_any_input
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


def test_strengthened_spec_rejects_evil_twin():
    """A 'strengthened' spec that pins the exact reverse-complement should reject the always-empty twin."""
    target = load_target(CORPUS / "bio" / "reverse_complement.py")
    pair = str.maketrans("ACGTacgt", "TGCAtgca")
    strong_spec = _spec(lambda seq, result: isinstance(result, str) and result == seq.translate(pair)[::-1])
    closes, example = _twin_rejected_on_any_input(target, strong_spec, lambda seq: "")
    assert closes, "strong spec must reject empty-string twin on non-empty inputs"
    assert example is not None
    assert example != ("",)  # the rejection should be on a non-empty input


def test_weak_strengthening_does_not_close_attack():
    """A 'strengthened' spec that's still too weak should NOT close the attack."""
    target = load_target(CORPUS / "bio" / "is_safe_sequence.py")
    # Spec only requires result is bool — the constant-True twin still satisfies it everywhere.
    weak_spec = _spec(lambda seq, result: isinstance(result, bool))
    closes, _ = _twin_rejected_on_any_input(target, weak_spec, lambda seq: True)
    assert not closes, "spec that only requires bool must not reject return-True twin"


def test_strengthened_spec_for_safe_sequence_rejects_constant_true():
    target = load_target(CORPUS / "bio" / "is_safe_sequence.py")
    # Correct spec: result iff input doesn't contain forbidden motifs.
    def post(seq, result):
        upper = seq.upper()
        expected = not any(m in upper for m in ("DANGER", "BIOHAZARD"))
        return result == expected
    strong = _spec(post)
    closes, example = _twin_rejected_on_any_input(target, strong, lambda seq: True)
    assert closes, "correct spec must reject return-True twin on DANGER-containing inputs"
    assert example is not None
    # Example should be a DANGER/BIOHAZARD-containing input.
    assert any(m in example[0].upper() for m in ("DANGER", "BIOHAZARD"))
