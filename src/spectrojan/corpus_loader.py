"""Discover and load corpus targets from corpus/ directories.

Each corpus file is a Python module exposing module-level constants:
- `TARGET`         : the function under test
- `INPUT_HINT`     : a natural-language hint to seed Hypothesis strategy synthesis
- `REFERENCE_EXAMPLES` : a list of (args_tuple, expected_output) for sanity checking

The module's `__doc__` becomes the docstring passed to the spec generator.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .types import TargetFunction


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_target(path: Path) -> TargetFunction:
    module = _load_module(path)
    target_fn = getattr(module, "TARGET")
    return TargetFunction(
        name=target_fn.__name__,
        source=path.read_text(),
        docstring=(module.__doc__ or "").strip(),
        reference_impl=target_fn,
        domain=path.parent.name,
        input_strategy_hint=getattr(module, "INPUT_HINT", ""),
        reference_examples=list(getattr(module, "REFERENCE_EXAMPLES", []) or []),
        explicit_strategy=getattr(module, "STRATEGY", None),
        domain_invariant=getattr(module, "DOMAIN_INVARIANT", None),
        public_docstring=getattr(module, "PUBLIC_DOCSTRING", None),
    )


def load_corpus(root: Path) -> list[TargetFunction]:
    targets: list[TargetFunction] = []
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        targets.append(load_target(path))
    return targets
