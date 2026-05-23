"""Run the Bio Honeypot demo and print the resulting Markdown path.

Usage:
    python3 scripts/run_bio_honeypot.py [--reset-cache]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-cache", action="store_true", help="clear .llm_cache/ before running")
    args = parser.parse_args()

    if args.reset_cache:
        cache = ROOT / ".llm_cache"
        if cache.exists():
            shutil.rmtree(cache)
            print(f"[bio_honeypot] cleared {cache}")

    from spectrojan.bio_honeypot import run_demo

    path = run_demo()
    print(f"[bio_honeypot] report written to: {path}")
    print(f"[bio_honeypot] preview:\n")
    text = path.read_text()
    # Show the headline section
    for i, line in enumerate(text.splitlines()):
        if i > 80:
            print("... (truncated; open the file for the full report)")
            break
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
