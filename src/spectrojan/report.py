"""Assemble a Spec Quality Report from the three signals.

Day 2-3 module. Renders to Markdown + CSV for inclusion in the final PDF report.
"""
from __future__ import annotations

from pathlib import Path

from .types import SpecQualityReport


def render_markdown(report: SpecQualityReport, out_path: Path) -> None:
    raise NotImplementedError("Day 2-3 task")


def render_csv_summary(reports: list[SpecQualityReport], out_path: Path) -> None:
    raise NotImplementedError("Day 2-3 task")
