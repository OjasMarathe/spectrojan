"""Full-corpus comparison sweep: ETS vs mutation testing vs cross-model disagreement.

For each corpus function:
  1. Generate K specs from M models (with-source mode — the realistic case where the spec
     author DOES have access to the reference implementation).
  2. Compute per-spec mutation-kill rate (baseline #1).
  3. Run all-pairs cross-spec disagreement (baseline #2).
  4. Run Evil Twin Synthesis on each usable spec (the headline).
  5. Persist a per-function JSON record + append to summary.csv as we go.

Saves incrementally to ``evals/runs/corpus_comparison/<timestamp>/`` so partial progress
isn't lost on interrupt.

Usage:
    python3 scripts/run_corpus_comparison.py [--n-specs 2] [--intent-only] [--target NAME]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console  # noqa: E402

from spectrojan.baselines.disagreement import find_disagreements  # noqa: E402
from spectrojan.baselines.mutator import mutate  # noqa: E402
from spectrojan.corpus_loader import load_corpus  # noqa: E402
from spectrojan.executor import satisfies_spec  # noqa: E402
from spectrojan.spec_generator import generate_specs, usable_specs  # noqa: E402
from spectrojan.twin_synthesizer import synthesize_evil_twins  # noqa: E402


console = Console()


MODELS = ["groq:llama-3.3-70b-versatile", "gemini:gemini-2.5-flash"]
ATTACKER_MODEL = "groq:llama-3.3-70b-versatile"


def run_one_target(
    target,
    n_specs_per_model: int,
    intent_only: bool,
    n_attack_rounds: int = 2,
    n_attack_candidates: int = 3,
    distance_threshold: float = 0.15,
) -> dict:
    """Run the full comparison on a single target. Returns a serializable dict."""
    t0 = time.time()
    result = {
        "target": target.name,
        "domain": target.domain,
        "intent_only": intent_only,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }

    # ---------- spec generation ----------
    specs = generate_specs(
        target,
        n_per_model=n_specs_per_model,
        models=MODELS,
        intent_only=intent_only,
    )
    valid = usable_specs(specs)
    result["n_specs_requested"] = len(specs)
    result["n_specs_usable"] = len(valid)
    result["specs"] = [
        {
            "model": s.model,
            "attempt_id": s.attempt_id,
            "parse_error": s.parse_error,
            "precondition_src": s.precondition_src,
            "postcondition_src": s.postcondition_src,
        }
        for s in specs
    ]

    if not valid:
        result["elapsed_s"] = time.time() - t0
        result["error"] = "no usable specs"
        return result

    # ---------- baseline #1: mutation kill rate ----------
    mutants = mutate(target)
    result["n_mutants"] = len(mutants)
    mut_kills = {}
    for s in valid:
        spec_id = f"{s.model}#{s.attempt_id}"
        kills = 0
        for m in mutants:
            try:
                if not satisfies_spec(target, m.mutated_impl, s, max_examples=40):
                    kills += 1
            except Exception:
                pass
        mut_kills[spec_id] = {"kills": kills, "total": len(mutants), "rate": kills / max(1, len(mutants))}
    result["mutation_kill_rates"] = mut_kills

    # ---------- baseline #2: cross-spec disagreement ----------
    disagreements = find_disagreements(target, valid, max_examples_per_pair=80)
    result["n_disagreements"] = len(disagreements)
    result["disagreement_examples"] = [
        {
            "spec_a": d.spec_a,
            "spec_b": d.spec_b,
            "inputs": repr(d.inputs),
            "spec_a_verdict": d.spec_a_verdict,
            "spec_b_verdict": d.spec_b_verdict,
        }
        for d in disagreements[:10]
    ]

    # ---------- THE HEADLINE: Evil Twin Synthesis ----------
    all_twins: list[dict] = []
    per_spec_twin_count: dict[str, int] = {}
    for s in valid:
        spec_id = f"{s.model}#{s.attempt_id}"
        try:
            twins, attempts = synthesize_evil_twins(
                target=target,
                spec=s,
                attacker_model=ATTACKER_MODEL,
                n_rounds=n_attack_rounds,
                n_candidates_per_round=n_attack_candidates,
                distance_threshold=distance_threshold,
            )
            per_spec_twin_count[spec_id] = len(twins)
            for t in twins:
                all_twins.append({
                    "spec_id": spec_id,
                    "distance": t.distance_score,
                    "strategy": t.prompt_strategy,
                    "source": t.twin_source,
                    "round": t.attack_round,
                })
        except Exception as exc:
            per_spec_twin_count[spec_id] = -1  # error marker
            console.print(f"  [red]ETS failed on {spec_id}: {exc}[/red]")

    result["per_spec_twin_count"] = per_spec_twin_count
    result["n_twins_total"] = sum(c for c in per_spec_twin_count.values() if c > 0)
    result["twins"] = all_twins
    result["elapsed_s"] = time.time() - t0
    return result


def write_csv_row(csv_path: Path, row: dict) -> None:
    fields = [
        "target", "domain", "intent_only", "n_specs_usable", "n_mutants",
        "n_disagreements", "n_twins_total", "n_specs_with_twins",
        "elapsed_s",
    ]
    n_specs_with_twins = sum(1 for v in row.get("per_spec_twin_count", {}).values() if v > 0)
    summary_row = {
        "target": row.get("target", ""),
        "domain": row.get("domain", ""),
        "intent_only": row.get("intent_only", False),
        "n_specs_usable": row.get("n_specs_usable", 0),
        "n_mutants": row.get("n_mutants", 0),
        "n_disagreements": row.get("n_disagreements", 0),
        "n_twins_total": row.get("n_twins_total", 0),
        "n_specs_with_twins": n_specs_with_twins,
        "elapsed_s": round(row.get("elapsed_s", 0), 1),
    }
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow(summary_row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-specs", type=int, default=2, help="specs per model per target")
    parser.add_argument("--intent-only", action="store_true",
                        help="hide reference impl from spec author (Bio-Honeypot mode)")
    parser.add_argument("--target", default=None, help="run only the named target (debug)")
    parser.add_argument("--n-rounds", type=int, default=2)
    parser.add_argument("--n-candidates", type=int, default=3)
    args = parser.parse_args()

    corpus_root = ROOT / "corpus"
    targets = load_corpus(corpus_root)
    if args.target:
        targets = [t for t in targets if t.name == args.target]
        if not targets:
            console.print(f"[red]no target named {args.target!r}[/red]")
            return 1

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "evals" / "runs" / "corpus_comparison" / run_id
    (out_dir / "per_function").mkdir(parents=True, exist_ok=True)
    summary_csv = out_dir / "summary.csv"

    console.rule(f"[bold cyan]Full-corpus comparison ({len(targets)} targets) — intent_only={args.intent_only}")
    console.print(f"Writing to: {out_dir}\n")

    t_global = time.time()
    for i, target in enumerate(targets, start=1):
        console.rule(f"[{i}/{len(targets)}] {target.name} ({target.domain})")
        try:
            row = run_one_target(
                target,
                n_specs_per_model=args.n_specs,
                intent_only=args.intent_only,
                n_attack_rounds=args.n_rounds,
                n_attack_candidates=args.n_candidates,
            )
        except Exception:
            console.print(f"[red]unhandled exception on {target.name}:\n{traceback.format_exc()}[/red]")
            row = {
                "target": target.name,
                "domain": target.domain,
                "intent_only": args.intent_only,
                "error": "unhandled exception",
                "elapsed_s": 0,
                "per_spec_twin_count": {},
            }

        (out_dir / "per_function" / f"{target.name}.json").write_text(json.dumps(row, indent=2))
        write_csv_row(summary_csv, row)

        n_twins = row.get("n_twins_total", 0)
        n_disag = row.get("n_disagreements", 0)
        n_mut = row.get("n_mutants", 0)
        console.print(f"  → twins: [bold]{n_twins}[/bold]  disagreements: {n_disag}  mutants: {n_mut}  ({row.get('elapsed_s', 0):.1f}s)")

    elapsed = time.time() - t_global
    console.rule(f"Done in {elapsed/60:.1f} min  —  results: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
