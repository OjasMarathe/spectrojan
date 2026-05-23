"""AST-level code mutation operators — BASELINE.

Demoted from headline to baseline: ETS synthesizes structurally different implementations
from scratch; this module makes small local edits. In the comparison table we report defects
found by mutation testing alongside defects found by ETS — ETS typically wins.

Mutation operators:
  - swap_arith:    + ↔ -, * ↔ //   (mod is left alone; / kept distinct from //)
  - swap_compare:  <→<=, >→>=, ==→!=, !=→==
  - off_by_one:    n → n+1   on integer literals
  - negate_bool:   wrap `if cond:` → `if not cond:`
  - drop_return:   replace `return expr` with `return None` (constant_zero variant)
  - swap_and_or:   `and` ↔ `or`

Each operator emits *all applicable* single-edit mutants — the cross-product of edit sites
is too large, so we stop at one edit per mutant.
"""
from __future__ import annotations

import libcst as cst

from ..types import Mutant, TargetFunction


_ARITH_SWAP = {
    cst.Add: cst.Subtract,
    cst.Subtract: cst.Add,
    cst.Multiply: cst.FloorDivide,
    cst.FloorDivide: cst.Multiply,
}
_COMPARE_SWAP = {
    cst.LessThan: cst.LessThanEqual,
    cst.LessThanEqual: cst.LessThan,
    cst.GreaterThan: cst.GreaterThanEqual,
    cst.GreaterThanEqual: cst.GreaterThan,
    cst.Equal: cst.NotEqual,
    cst.NotEqual: cst.Equal,
}
_BOOL_SWAP = {
    cst.And: cst.Or,
    cst.Or: cst.And,
}


class _SingleEditTransformer(cst.CSTTransformer):
    """Apply ONE edit at the Nth occurrence of a target node type."""

    def __init__(self, op: str, n_target: int):
        super().__init__()
        self.op = op
        self.n_target = n_target
        self._counter = 0
        self.applied = False
        self.description = ""

    # ----- arithmetic operator swap -----
    def leave_BinaryOperation(self, original: cst.BinaryOperation, updated: cst.BinaryOperation):
        op = original.operator
        if self.op == "swap_arith":
            for src_cls, dst_cls in _ARITH_SWAP.items():
                if isinstance(op, src_cls):
                    if self._counter == self.n_target:
                        self.applied = True
                        self.description = f"swap arith {src_cls.__name__}→{dst_cls.__name__}"
                        return updated.with_changes(operator=dst_cls())
                    self._counter += 1
        elif self.op == "swap_and_or":
            pass  # BinaryOperation is for arithmetic; bool ops use BooleanOperation
        return updated

    def leave_BooleanOperation(self, original: cst.BooleanOperation, updated: cst.BooleanOperation):
        if self.op == "swap_and_or":
            op = original.operator
            for src_cls, dst_cls in _BOOL_SWAP.items():
                if isinstance(op, src_cls):
                    if self._counter == self.n_target:
                        self.applied = True
                        self.description = f"swap bool {src_cls.__name__}→{dst_cls.__name__}"
                        return updated.with_changes(operator=dst_cls())
                    self._counter += 1
        return updated

    # ----- comparison operator swap -----
    def leave_ComparisonTarget(self, original: cst.ComparisonTarget, updated: cst.ComparisonTarget):
        if self.op == "swap_compare":
            op = original.operator
            for src_cls, dst_cls in _COMPARE_SWAP.items():
                if isinstance(op, src_cls):
                    if self._counter == self.n_target:
                        self.applied = True
                        self.description = f"swap compare {src_cls.__name__}→{dst_cls.__name__}"
                        return updated.with_changes(operator=dst_cls())
                    self._counter += 1
        return updated

    # ----- integer literal off-by-one -----
    def leave_Integer(self, original: cst.Integer, updated: cst.Integer):
        if self.op == "off_by_one":
            try:
                v = int(original.value)
            except ValueError:
                return updated
            if self._counter == self.n_target:
                self.applied = True
                self.description = f"off-by-one: {v}→{v + 1}"
                return updated.with_changes(value=str(v + 1))
            self._counter += 1
        return updated

    # ----- if-statement negation -----
    def leave_If(self, original: cst.If, updated: cst.If):
        if self.op == "negate_bool":
            if self._counter == self.n_target:
                self.applied = True
                self.description = "negate if-cond"
                negated = cst.UnaryOperation(operator=cst.Not(whitespace_after=cst.SimpleWhitespace(" ")), expression=updated.test)
                return updated.with_changes(test=negated)
            self._counter += 1
        return updated

    # ----- return-None (drop_return) -----
    def leave_Return(self, original: cst.Return, updated: cst.Return):
        if self.op == "drop_return":
            if updated.value is None:
                return updated
            if self._counter == self.n_target:
                self.applied = True
                self.description = "replace return expr with None"
                return updated.with_changes(value=cst.Name("None"))
            self._counter += 1
        return updated


_OPERATORS = ("swap_arith", "swap_compare", "off_by_one", "negate_bool", "drop_return", "swap_and_or")


def _instantiate(source: str, name: str):
    """Exec the mutated source and return the named function. Returns None on syntax/exec error."""
    ns: dict = {}
    try:
        exec(compile(source, f"<mutant-{name}>", "exec"), ns)
    except Exception:
        return None
    fn = ns.get(name)
    return fn if callable(fn) else None


def mutate(target: TargetFunction, max_per_operator: int = 8) -> list[Mutant]:
    """Return all single-edit mutants of the target.

    For each operator, we walk the tree counting eligible sites; for the first ``max_per_operator``
    we produce a mutant that replaces just that site.
    """
    mutants: list[Mutant] = []
    try:
        tree = cst.parse_module(target.source)
    except cst.ParserSyntaxError:
        return mutants

    for op in _OPERATORS:
        # First pass: count sites for this operator.
        counter = _SingleEditTransformer(op=op, n_target=-1)
        try:
            tree.visit(counter)
        except Exception:
            continue
        total_sites = counter._counter
        for i in range(min(total_sites, max_per_operator)):
            transformer = _SingleEditTransformer(op=op, n_target=i)
            try:
                mutated_tree = tree.visit(transformer)
            except Exception:
                continue
            if not transformer.applied:
                continue
            mutated_source = mutated_tree.code
            if mutated_source == target.source:
                continue
            impl = _instantiate(mutated_source, target.name)
            if impl is None:
                continue
            mutants.append(Mutant(
                target_name=target.name,
                mutator=op,
                description=transformer.description,
                mutated_source=mutated_source,
                mutated_impl=impl,
            ))
    return mutants
