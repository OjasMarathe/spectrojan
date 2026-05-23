"""Sanity check: every corpus reference implementation produces its REFERENCE_EXAMPLES.

Run with:  python scripts/validate_corpus.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from spectrojan.corpus_loader import _load_module  # noqa: E402


def check_one(path: Path) -> list[str]:
    errors: list[str] = []
    module = _load_module(path)
    target = getattr(module, "TARGET", None)
    examples = getattr(module, "REFERENCE_EXAMPLES", None)
    if target is None:
        errors.append(f"{path}: missing TARGET")
        return errors
    if examples is None:
        errors.append(f"{path}: missing REFERENCE_EXAMPLES")
        return errors
    for args, expected in examples:
        try:
            actual = target(*args)
        except Exception as exc:
            errors.append(f"{path}: target({args!r}) raised {exc!r} (expected {expected!r})")
            continue
        if actual != expected:
            errors.append(f"{path}: target({args!r}) = {actual!r}, expected {expected!r}")
    return errors


def main() -> int:
    corpus_root = ROOT / "corpus"
    all_errors: list[str] = []
    count = 0
    for path in sorted(corpus_root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        count += 1
        all_errors.extend(check_one(path))
    if all_errors:
        print(f"FAIL: {len(all_errors)} error(s) across {count} corpus files\n")
        for e in all_errors:
            print(f"  {e}")
        return 1
    print(f"OK: {count} corpus files validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
