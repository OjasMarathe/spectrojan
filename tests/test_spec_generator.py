"""Tests for spec_generator parsing — these don't hit any API.

End-to-end generation is exercised in tests/test_e2e.py (requires API keys).
"""
from __future__ import annotations

from spectrojan.spec_generator import parse_spec_response


def test_parses_clean_block():
    text = '''```python
def precondition(seq):
    return isinstance(seq, str)

def postcondition(seq, result):
    return isinstance(result, str) and len(result) == len(seq)
```'''
    spec = parse_spec_response(text, "reverse_complement", "test:model", 0)
    assert spec.parse_error is None, spec.parse_error
    assert spec.precondition is not None and spec.postcondition is not None
    assert spec.precondition("ACGT") is True
    assert spec.postcondition("ACGT", "TGCA") is True
    assert spec.postcondition("ACGT", "X") is False


def test_parses_bare_block_without_fence():
    text = '''def precondition(x):
    return True

def postcondition(x, result):
    return result == x * 2
'''
    spec = parse_spec_response(text, "double", "test:model", 0)
    assert spec.parse_error is None
    assert spec.postcondition(3, 6) is True
    assert spec.postcondition(3, 7) is False


def test_parses_with_helper_function():
    text = '''```python
def _is_dna(s):
    return all(c in "ACGT" for c in s)

def precondition(seq):
    return isinstance(seq, str) and _is_dna(seq)

def postcondition(seq, result):
    return isinstance(result, str) and _is_dna(result) and len(result) == len(seq)
```'''
    spec = parse_spec_response(text, "x", "test:model", 0)
    assert spec.parse_error is None
    assert spec.precondition("ACGT") is True
    assert spec.precondition("NNNN") is False
    assert spec.postcondition("ACGT", "TGCA") is True


def test_records_parse_error_on_bad_python():
    text = "```python\ndef precondition(\n    return broken\n```"
    spec = parse_spec_response(text, "x", "test:model", 0)
    assert spec.parse_error is not None
    assert spec.precondition is None
    assert spec.postcondition is None


def test_missing_postcondition_recorded():
    text = "```python\ndef precondition(x):\n    return True\n```"
    spec = parse_spec_response(text, "x", "test:model", 0)
    assert spec.postcondition is None
    assert "postcondition" in (spec.parse_error or "")
