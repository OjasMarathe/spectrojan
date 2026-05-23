"""Tests for the AST mutation baseline.

We exercise a few corpus functions, count mutants per operator, and check that at least
one mutant gives a different output than the reference on a known input — proving the
mutation actually changed semantics.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from spectrojan.baselines.mutator import mutate
from spectrojan.corpus_loader import load_target


CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def test_reverse_complement_produces_mutants():
    target = load_target(CORPUS / "bio" / "reverse_complement.py")
    mutants = mutate(target)
    assert mutants, "expected at least one mutant"
    ops = Counter(m.mutator for m in mutants)
    # The function uses str.maketrans / translate / [::-1] — limited mutation surface but
    # should still produce at least one operator's worth of mutants.
    assert sum(ops.values()) >= 1


def test_gcd_mutants_change_semantics():
    """gcd has a while loop with arithmetic — mutators should produce semantically-different mutants."""
    target = load_target(CORPUS / "generic" / "gcd.py")
    mutants = mutate(target)
    assert mutants
    # At least one mutant must produce a different output on a known case.
    diverged = False
    for m in mutants:
        try:
            if m.mutated_impl(12, 8) != 4:  # gcd(12, 8) = 4
                diverged = True
                break
        except Exception:
            diverged = True
            break
    assert diverged, "no mutant of gcd(12,8) diverged from the reference"


def test_binary_search_off_by_one():
    target = load_target(CORPUS / "generic" / "binary_search.py")
    mutants = mutate(target)
    # binary_search has explicit comparisons (<=, <) and integer literals — expect off-by-one and swap_compare mutants
    op_set = {m.mutator for m in mutants}
    assert "swap_compare" in op_set or "off_by_one" in op_set, f"got ops: {op_set}"


def test_balanced_parens_negation_or_compare():
    target = load_target(CORPUS / "generic" / "balanced_parens.py")
    mutants = mutate(target)
    assert mutants
    # at least one mutant should produce a different answer on a well-formed input
    diverged = False
    for m in mutants:
        try:
            if m.mutated_impl("()") is not True or m.mutated_impl(")") is not False:
                diverged = True
                break
        except Exception:
            diverged = True
            break
    assert diverged
