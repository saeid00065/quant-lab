"""Copy a benchmark case into a clean run folder that holds no answer keys.

Usage:
    py -3 benchmarks/prepare.py <case_id|all> <dest_parent>

Each run folder gets the project rules (AGENTS.md), the engine (src/),
requirements.txt and the case's public files. benchmarks/keys is never copied.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
CASES = BENCH / "cases"
MARKER = ".bench_case"


def case_ids() -> list[str]:
    return sorted(p.name for p in CASES.iterdir() if p.is_dir())


def prepare(case_id: str, dest_parent: Path) -> Path:
    src_case = CASES / case_id
    if not src_case.is_dir():
        raise SystemExit(f"Unknown case {case_id!r}. Known: {', '.join(case_ids())}")
    run = dest_parent / case_id
    if run.exists():
        raise SystemExit(f"{run} already exists; choose an empty destination.")
    run.mkdir(parents=True)

    shutil.copy2(ROOT / "AGENTS.md", run / "AGENTS.md")
    shutil.copy2(ROOT / "requirements.txt", run / "requirements.txt")
    shutil.copytree(ROOT / "src", run / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for item in src_case.iterdir():
        if item.is_file():
            shutil.copy2(item, run / item.name)
    (run / MARKER).write_text(case_id, encoding="utf-8")
    return run


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    target, dest = argv
    ids = case_ids() if target == "all" else [target]
    for cid in ids:
        run = prepare(cid, Path(dest).resolve())
        print(f"{cid}: {run}")
        print(f"  give the agent the text of {run / 'task.md'}")


if __name__ == "__main__":
    main(sys.argv[1:])
