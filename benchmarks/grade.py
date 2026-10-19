"""Grade an agent's answer for one benchmark run folder.

Usage:
    py -3 benchmarks/grade.py <run_folder> [<run_folder> ...] [--agent NAME]
    py -3 benchmarks/grade.py --self-test

A run folder is made by prepare.py; the agent writes answer.json into it.
Scores are appended to benchmarks/results/scores.csv (gitignored).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from prepare import BENCH, CASES, MARKER, case_ids, prepare

KEYS = BENCH / "keys"
SCORES = BENCH / "results" / "scores.csv"
_MISSING = object()


def get(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        elif isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return _MISSING
    return obj


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check(c: dict, answer: dict, run: Path, case_id: str) -> tuple[bool, str]:
    kind = c["type"]
    if kind == "unchanged":
        f = run / c["file"]
        if not f.exists():
            return False, f"{c['file']} was deleted"
        same = sha256(f) == sha256(CASES / case_id / c["file"])
        return same, f"{c['file']} unchanged" if same else f"{c['file']} was modified"

    path = c["path"]
    val = get(answer, path)
    if val is _MISSING:
        return False, f"{path}: missing from answer.json"

    if kind == "equals":
        return val == c["value"], f"{path} = {val!r} (expected {c['value']!r})"
    if kind == "approx":
        ok = is_number(val) and abs(val - c["value"]) <= c["tol"]
        return ok, f"{path} = {val!r} (expected {c['value']} +/- {c['tol']})"
    if kind == "len_equals":
        ok = isinstance(val, list) and len(val) == c["value"]
        n = len(val) if isinstance(val, list) else "n/a"
        return ok, f"{path} has {n} items (expected {c['value']})"
    if kind == "int_in":
        return val in c["values"], f"{path} = {val!r} (accepted {c['values']})"
    if kind == "set_equals":
        if not isinstance(val, list):
            return False, f"{path} is not a list"
        got, need = set(val), set(c["values"])
        extra = got - need - set(c.get("allow_extra", []))
        missing = need - got
        ok = not missing and not extra
        detail = f"missing {sorted(missing)}" if missing else ""
        detail += f" unexpected {sorted(extra)}" if extra else ""
        return ok, f"{path} = {sorted(got)}" + (f" ({detail.strip()})" if detail else "")
    if kind == "topics_min":
        text = " ".join(str(q) for q in val).lower() if isinstance(val, list) else ""
        hit = sorted(t for t, kws in c["topics"].items() if any(k.lower() in text for k in kws))
        return len(hit) >= c["min"], f"{path} covers {len(hit)}/{len(c['topics'])} topics {hit} (need {c['min']})"
    if kind == "split_valid":
        return split_valid(val, run / c["data_file"], c["min_test_fraction"])
    if kind == "csv_rows":
        f = run / str(val)
        if not f.is_file():
            return False, f"{path}: file {val!r} not found in run folder"
        with f.open(newline="", encoding="utf-8") as fh:
            rows = max(sum(1 for _ in csv.reader(fh)) - 1, 0)
        return rows == c["count"], f"{val} has {rows} data rows (expected {c['count']})"
    raise ValueError(f"unknown check type {kind!r}")


def split_valid(split, data_file: Path, min_frac: float) -> tuple[bool, str]:
    if not isinstance(split, dict):
        return False, "no train/test split reported"
    try:
        d = {k: date.fromisoformat(split[k]) for k in ("train_start", "train_end", "test_start", "test_end")}
    except (KeyError, TypeError, ValueError):
        return False, f"split dates missing or not YYYY-MM-DD: {split!r}"
    with data_file.open(newline="", encoding="utf-8") as fh:
        dates = [date.fromisoformat(r["date"]) for r in csv.DictReader(fh)]
    if not (d["train_start"] <= d["train_end"] < d["test_start"] <= d["test_end"]):
        return False, "split is not train-then-test in time order"
    test_n = sum(d["test_start"] <= x <= d["test_end"] for x in dates)
    frac = test_n / len(dates)
    return frac >= min_frac, f"test period holds {test_n}/{len(dates)} bars = {frac:.0%} (need >= {min_frac:.0%})"


def grade(run: Path) -> dict:
    marker = run / MARKER
    if not marker.is_file():
        raise SystemExit(f"{run} is not a run folder (no {MARKER}); make one with prepare.py")
    case_id = marker.read_text(encoding="utf-8").strip()
    key = json.loads((KEYS / f"{case_id}.json").read_text(encoding="utf-8"))
    results = []
    try:
        answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        answer, results = None, [(False, "answer.json not found")]
    except json.JSONDecodeError as e:
        answer, results = None, [(False, f"answer.json is not valid JSON: {e}")]
    if answer is not None:
        results = [check(c, answer, run, case_id) for c in key["checks"]]
    return {"case": case_id, "title": key["title"], "results": results,
            "passed": all(ok for ok, _ in results), "manual": key.get("manual_checks", [])}


def print_report(r: dict) -> None:
    n_ok = sum(ok for ok, _ in r["results"])
    print(f"\n{'PASS' if r['passed'] else 'FAIL'}  {r['case']} - {r['title']}  ({n_ok}/{len(r['results'])} checks)")
    for ok, msg in r["results"]:
        print(f"   {'ok ' if ok else 'XX '} {msg}")
    for m in r["manual"]:
        print(f"   [manual] {m}")


def log_scores(rows: list[dict], agent: str) -> None:
    SCORES.parent.mkdir(exist_ok=True)
    new = not SCORES.exists()
    stamp = datetime.now().isoformat(timespec="seconds")
    with SCORES.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "agent", "case", "passed", "checks_ok", "checks_total"])
        for r in rows:
            w.writerow([stamp, agent, r["case"], r["passed"], sum(ok for ok, _ in r["results"]), len(r["results"])])


def write_answer(run: Path, answer: dict, files: dict) -> None:
    (run / "answer.json").write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
    for name, content in files.items():
        if content == "@grid90":
            pairs = [(f, s) for f in range(5, 51, 5) for s in range(20, 201, 20) if f < s]
            content = "fast,slow,sharpe\n" + "".join(f"{f},{s},0.0\n" for f, s in pairs)
        (run / name).write_text(content, encoding="utf-8")


def self_test() -> int:
    """Reference answers must pass and planted bad answers must fail, for every case."""
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for cid in case_ids():
            key = json.loads((KEYS / f"{cid}.json").read_text(encoding="utf-8"))
            for kind, want in (("reference", True), ("bad", False)):
                run = prepare(cid, Path(tmp) / kind)
                write_answer(run, key[f"{kind}_answer"], key.get(f"{kind}_files", {}))
                got = grade(run)["passed"]
                status = "ok" if got == want else "WRONG"
                failures += got != want
                print(f"{status:5} {cid:24} {kind:9} -> {'pass' if got else 'fail'} (expected {'pass' if want else 'fail'})")
    print(f"\nself-test: {'all good' if not failures else f'{failures} problem(s)'}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    agent = "unknown"
    if "--agent" in argv:
        i = argv.index("--agent")
        agent = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 2
    rows = [grade(Path(p).resolve()) for p in argv]
    for r in rows:
        print_report(r)
    log_scores(rows, agent)
    print(f"\nScore: {sum(r['passed'] for r in rows)}/{len(rows)} cases passed. Logged to {SCORES}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
