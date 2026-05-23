"""Typer CLI entry point for SpecTrojan.

    spectrojan attack path/to/function.py [--models openai:gpt-4o,gemini:gemini-2.5-pro] [--n-specs 3] [--n-twins 5]
    spectrojan baselines path/to/function.py     # run mutation + disagreement baselines only
    spectrojan report  evals/runs/<run-id>/       # render the Trojan Report
"""
from __future__ import annotations

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="SpecTrojan — adversarial spec validation via Evil Twin Synthesis.",
)


@app.command()
def attack(
    target_path: str,
    models: str = "openai:gpt-4o,gemini:gemini-2.5-pro",
    n_specs: int = 3,
    n_twins: int = 5,
) -> None:
    """Run the full Evil Twin Synthesis pipeline on a target function. TODO: Day 1+2."""
    raise NotImplementedError("Day 1 task")


@app.command()
def baselines(target_path: str, models: str = "openai:gpt-4o,gemini:gemini-2.5-pro", n_specs: int = 3) -> None:
    """Run mutation-testing and cross-model disagreement baselines only. TODO: Day 1."""
    raise NotImplementedError("Day 1 task")


@app.command()
def report(run_dir: str) -> None:
    """Render a Trojan Report from a completed run directory. TODO: Day 3."""
    raise NotImplementedError("Day 3 task")


if __name__ == "__main__":
    app()
