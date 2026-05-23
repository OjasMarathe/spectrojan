"""Tests for the cross-spec disagreement baseline. Uses hand-written specs, no API."""
from __future__ import annotations

from pathlib import Path

from spectrojan.baselines.disagreement import find_disagreements
from spectrojan.corpus_loader import load_target
from spectrojan.types import CandidateSpec


CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def _spec(pre, post, attempt_id=0, model="manual:hand"):
    return CandidateSpec(
        target_name="t",
        model=model,
        attempt_id=attempt_id,
        raw_text="",
        precondition_src="",
        postcondition_src="",
        precondition=pre,
        postcondition=post,
    )


def test_agreeing_specs_no_disagreement():
    target = load_target(CORPUS / "bio" / "gc_content.py")
    # Two specs that say the same thing: result is in [0, 1].
    s1 = _spec(None, lambda seq, r: isinstance(r, float) and 0.0 <= r <= 1.0, attempt_id=0)
    s2 = _spec(None, lambda seq, r: isinstance(r, float) and 0.0 <= r <= 1.0, attempt_id=1)
    out = find_disagreements(target, [s1, s2], max_examples_per_pair=30)
    assert out == [], f"got disagreements where there should be none: {out[:1]}"


def test_disagreeing_specs_caught():
    target = load_target(CORPUS / "bio" / "gc_content.py")
    # s1 is correct (close-to-exact). s2 is wrong: requires r > 0.5.
    s1 = _spec(None, lambda seq, r: isinstance(r, float) and 0.0 <= r <= 1.0)
    s2 = _spec(None, lambda seq, r: isinstance(r, float) and r > 0.5)
    out = find_disagreements(target, [s1, s2], max_examples_per_pair=80)
    assert out, "should detect disagreement on low-GC inputs"
