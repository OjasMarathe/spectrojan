"""Run metamorphic spec testing across the cached LLM specs.

Uses specs saved in evals/runs/corpus_comparison/<run>/per_function/ — no LLM calls needed.
Outputs a Markdown table for the report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from spectrojan.corpus_loader import load_target  # noqa: E402
from spectrojan.metamorphic import metamorphic_robustness  # noqa: E402
from spectrojan.spec_generator import parse_spec_response  # noqa: E402


SWEEP_DIR = ROOT / "evals" / "runs" / "corpus_comparison"
OUT_PATH = ROOT / "reports" / "metamorphic_results.md"


def latest_sweep_dir() -> Path | None:
    dirs = sorted([p for p in SWEEP_DIR.iterdir() if p.is_dir()])
    return dirs[-1] if dirs else None


def main() -> int:
    sweep = latest_sweep_dir()
    if sweep is None:
        print("no corpus_comparison sweep found", file=sys.stderr)
        return 1
    rows: list[tuple] = []

    for jp in sorted((sweep / "per_function").glob("*.json")):
        d = json.loads(jp.read_text())
        if not d.get("n_specs_usable", 0):
            continue
        domain = d["domain"]
        target_path = ROOT / "corpus" / domain / f"{d['target']}.py"
        target = load_target(target_path)

        for s_meta in d["specs"]:
            if s_meta.get("parse_error"):
                continue
            block = (
                "```python\n"
                + s_meta["precondition_src"]
                + "\n\n"
                + s_meta["postcondition_src"]
                + "\n```"
            )
            spec = parse_spec_response(block, target.name, s_meta["model"], s_meta["attempt_id"])
            if spec.postcondition is None:
                continue
            try:
                res = metamorphic_robustness(target, spec)
            except Exception as exc:
                res = {"robustness": None, "n_applied": 0, "n_accepted": 0, "error": str(exc)}
            rows.append((
                target.name,
                f"{s_meta['model']}#{s_meta['attempt_id']}",
                res.get("robustness"),
                res.get("n_applied"),
                res.get("n_accepted"),
            ))

    # Write Markdown report.
    lines = ["# Metamorphic Spec Testing — Results\n"]
    lines.append("Each row: a (target, candidate spec) pair. We apply five semantics-preserving")
    lines.append("code transforms to the reference implementation and report the fraction the spec accepts.")
    lines.append("A robust spec accepts ALL transforms; failures indicate the spec is overfit to syntax.\n")
    lines.append("| Target | Spec | Transforms applied | Accepted | Robustness |")
    lines.append("|---|---|---|---|---|")
    n_robust = 0
    n_total = 0
    for name, spec_id, rob, n_applied, n_accepted in rows:
        if rob is None:
            cell = "N/A"
        else:
            cell = f"{rob:.0%}"
        lines.append(f"| `{name}` | `{spec_id}` | {n_applied} | {n_accepted} | {cell} |")
        if isinstance(rob, float):
            n_total += 1
            if rob >= 0.99:
                n_robust += 1

    lines.append("")
    lines.append(f"**Summary**: {n_robust}/{n_total} (spec, transform-suite) pairs were fully robust.")
    lines.append(
        "\nMetamorphic failures (robustness < 100%) flag specs that are syntactically rigid — "
        "rejecting alternative *but equivalent* implementations of the same function. This is "
        "a covert failure mode orthogonal to under-constraint."
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines))
    print(f"wrote {OUT_PATH}")

    # Also print to stdout
    print()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
