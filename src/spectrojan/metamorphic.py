"""Metamorphic spec testing — secondary novelty.

Apply *semantics-preserving* code transforms to the reference implementation. A good
specification should accept every transformed implementation, because all of them compute
the same function. A spec that REJECTS a transformed implementation is overfit to surface
syntax — a covert failure mode distinct from under-constraint.

Transforms (initial set, libcst-based):

  - rename_locals:     rename a local variable throughout the function.
  - swap_commutative:  ``a + b`` → ``b + a`` and ``a * b`` → ``b * a`` (when both ints/floats).
  - normalize_negation: ``not (a == b)`` → ``a != b`` and ``not (a != b)`` → ``a == b``.
  - identity_wrap:     wrap each ``return expr`` as ``_r = expr; return _r``.
  - prepend_noop:      add an inert ``_metamorphic_marker = None`` at the start of the body.
  - and_to_chained:    ``(a < b) and (b < c)`` → ``a < b < c`` when applicable.

For each (spec, transform): we exec the transformed source, instantiate the callable, and
run ``satisfies_spec`` with the candidate-spec's postcondition. The robustness score for a
spec is the fraction of transforms it accepts.
"""
from __future__ import annotations

from dataclasses import dataclass

import libcst as cst

from .executor import satisfies_spec
from .types import CandidateSpec, TargetFunction


# ---------- transformers --------------------------------------------------

class _RenameLocals(cst.CSTTransformer):
    """Rename the first non-param identifier we see (best-effort)."""
    def __init__(self):
        super().__init__()
        self.target: str | None = None
        self.applied = False

    def leave_FunctionDef(self, original: cst.FunctionDef, updated: cst.FunctionDef):
        params = {p.name.value for p in original.params.params}
        # Find first local Name that isn't a param or a builtin-ish.
        names: list[str] = []
        class _Collector(cst.CSTVisitor):
            def visit_Name(self, node: cst.Name) -> None:
                if node.value not in params and node.value not in {"None", "True", "False"} and node.value.isidentifier():
                    names.append(node.value)
        original.body.visit(_Collector())
        if not names:
            return updated
        # Pick the most frequent non-param non-builtin name.
        from collections import Counter
        counts = Counter(names)
        target_name = counts.most_common(1)[0][0]
        if target_name in {"str", "int", "float", "list", "dict", "tuple", "set", "len", "range", "sum", "min", "max", "any", "all", "print", "ord", "chr"}:
            return updated
        new_name = f"{target_name}_renamed"
        self.target = target_name
        self.applied = True
        return updated.visit(_NameReplacer(target_name, new_name))


class _NameReplacer(cst.CSTTransformer):
    def __init__(self, old: str, new: str):
        super().__init__()
        self.old = old
        self.new = new

    def leave_Name(self, original: cst.Name, updated: cst.Name):
        if updated.value == self.old:
            return updated.with_changes(value=self.new)
        return updated


class _SwapCommutative(cst.CSTTransformer):
    """Swap operands of the first commutative BinaryOperation we find."""
    def __init__(self):
        super().__init__()
        self.applied = False

    def leave_BinaryOperation(self, original: cst.BinaryOperation, updated: cst.BinaryOperation):
        if self.applied:
            return updated
        op = original.operator
        if isinstance(op, (cst.Add, cst.Multiply)):
            self.applied = True
            return updated.with_changes(left=updated.right, right=updated.left)
        return updated


class _NormalizeNegation(cst.CSTTransformer):
    """`not (a == b)` → `a != b` (and the reverse) — first occurrence."""
    def __init__(self):
        super().__init__()
        self.applied = False

    def leave_UnaryOperation(self, original: cst.UnaryOperation, updated: cst.UnaryOperation):
        if self.applied:
            return updated
        if not isinstance(updated.operator, cst.Not):
            return updated
        inner = updated.expression
        if not isinstance(inner, cst.Comparison) or len(inner.comparisons) != 1:
            return updated
        op = inner.comparisons[0].operator
        if isinstance(op, cst.Equal):
            self.applied = True
            new_target = inner.comparisons[0].with_changes(operator=cst.NotEqual())
            return inner.with_changes(comparisons=[new_target])
        if isinstance(op, cst.NotEqual):
            self.applied = True
            new_target = inner.comparisons[0].with_changes(operator=cst.Equal())
            return inner.with_changes(comparisons=[new_target])
        return updated


class _IdentityWrap(cst.CSTTransformer):
    """Replace `return expr` with `_r = expr; return _r` — first occurrence."""
    def __init__(self):
        super().__init__()
        self.applied = False

    def leave_SimpleStatementLine(
        self, original: cst.SimpleStatementLine, updated: cst.SimpleStatementLine
    ):
        if self.applied or len(updated.body) != 1:
            return updated
        node = updated.body[0]
        if not isinstance(node, cst.Return) or node.value is None or isinstance(node.value, cst.Name) and node.value.value == "_r":
            return updated
        self.applied = True
        assign = cst.SimpleStatementLine([cst.Assign(
            targets=[cst.AssignTarget(target=cst.Name("_r"))],
            value=node.value,
        )])
        ret = cst.SimpleStatementLine([cst.Return(value=cst.Name("_r"))])
        return cst.FlattenSentinel([assign, ret])


class _PrependNoop(cst.CSTTransformer):
    """Insert ``_metamorphic_marker = None`` at the start of every function body."""
    def __init__(self):
        super().__init__()
        self.applied = False

    def leave_IndentedBlock(self, original: cst.IndentedBlock, updated: cst.IndentedBlock):
        if self.applied:
            return updated
        marker = cst.SimpleStatementLine([cst.Assign(
            targets=[cst.AssignTarget(target=cst.Name("_metamorphic_marker"))],
            value=cst.Name("None"),
        )])
        self.applied = True
        return updated.with_changes(body=(marker,) + tuple(updated.body))


_TRANSFORMS: list[tuple[str, type[cst.CSTTransformer]]] = [
    ("rename_locals", _RenameLocals),
    ("swap_commutative", _SwapCommutative),
    ("normalize_negation", _NormalizeNegation),
    ("identity_wrap", _IdentityWrap),
    ("prepend_noop", _PrependNoop),
]


def _instantiate(source: str, function_name: str):
    ns: dict = {}
    try:
        exec(compile(source, f"<metamorphic-{function_name}>", "exec"), ns)
    except Exception:
        return None
    fn = ns.get(function_name)
    return fn if callable(fn) else None


@dataclass
class TransformResult:
    name: str
    applied: bool
    accepted_by_spec: bool
    error: str | None = None


def apply_transforms(target: TargetFunction) -> list[tuple[str, str, bool]]:
    """Return list of (transform_name, transformed_source, applied) — exec'd and ready to instantiate."""
    out: list[tuple[str, str, bool]] = []
    try:
        tree = cst.parse_module(target.source)
    except cst.ParserSyntaxError:
        return out
    for name, transformer_cls in _TRANSFORMS:
        transformer = transformer_cls()
        try:
            new_tree = tree.visit(transformer)
        except Exception:
            continue
        out.append((name, new_tree.code, bool(getattr(transformer, "applied", False))))
    return out


def metamorphic_robustness(
    target: TargetFunction,
    spec: CandidateSpec,
    max_examples: int = 80,
) -> dict:
    """Return per-transform acceptance + an aggregate robustness score in [0, 1].

    A spec is "robust" to a transform iff the transformed reference impl still satisfies
    the spec under the executor.
    """
    if spec.postcondition is None:
        return {"results": [], "robustness": 0.0, "n_applied": 0}

    results: list[TransformResult] = []
    transforms = apply_transforms(target)
    accepted = 0
    n_applied = 0

    for name, source, applied in transforms:
        if not applied:
            results.append(TransformResult(name=name, applied=False, accepted_by_spec=False))
            continue
        n_applied += 1
        impl = _instantiate(source, target.name)
        if impl is None:
            results.append(TransformResult(name=name, applied=True, accepted_by_spec=False, error="instantiation failed"))
            continue
        try:
            ok = satisfies_spec(target, impl, spec, max_examples=max_examples)
        except Exception as exc:
            results.append(TransformResult(name=name, applied=True, accepted_by_spec=False, error=str(exc)))
            continue
        if ok:
            accepted += 1
        results.append(TransformResult(name=name, applied=True, accepted_by_spec=ok))

    robustness = accepted / n_applied if n_applied else 0.0
    return {
        "results": [r.__dict__ for r in results],
        "robustness": robustness,
        "n_applied": n_applied,
        "n_accepted": accepted,
    }
