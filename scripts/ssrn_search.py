"""Search SSRN (through Crossref) and arXiv q-fin for trading-strategy papers.

SSRN itself refuses automated requests (HTTP 403), but every SSRN paper has a
Crossref DOI under prefix 10.2139, with title, authors, year, abstract and a
citation count. arXiv has an open API; its quantitative-finance papers (q-fin)
add recent work that never went to SSRN, but arXiv gives no citation count.
This script runs keyword queries against the chosen sources, merges and
de-duplicates the hits, and writes them to research/ssrn/papers.json and .csv.

Usage:
    python scripts/ssrn_search.py "intraday momentum" "overnight returns" --rows 40
    python scripts/ssrn_search.py --default --since 2015
    python scripts/ssrn_search.py "gold seasonality" --source all
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.crossref.org/works"
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}
SSRN_PREFIX = "10.2139"
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "ssrn"
FIELDS = "DOI,title,author,issued,abstract,is-referenced-by-count"
MAILTO = "quant-lab-research@example.invalid"

# Broad sweep of trading-strategy topics used by --default.
DEFAULT_QUERIES = [
    "time series momentum trading strategy",
    "cross-sectional momentum anomaly",
    "intraday momentum strategy",
    "overnight return anomaly",
    "short-term reversal strategy",
    "mean reversion pairs trading",
    "trend following futures",
    "carry trade currency strategy",
    "volatility risk premium strategy",
    "seasonality calendar anomaly returns",
    "post earnings announcement drift",
    "factor timing strategy",
    "machine learning return prediction trading",
    "order flow imbalance intraday returns",
    "cryptocurrency trading strategy returns",
    "gold futures trading strategy",
    "forex technical trading rules profitability",
    "replication anomalies out-of-sample",
]


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(html.unescape(text))).strip()


def query_crossref(query: str, rows: int, since: int | None) -> list[dict]:
    filters = [f"prefix:{SSRN_PREFIX}"]
    if since:
        filters.append(f"from-pub-date:{since}-01-01")
    params = {
        "query": query,
        "filter": ",".join(filters),
        "rows": rows,
        "select": FIELDS,
        "mailto": MAILTO,
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"quant-lab-ssrn/1.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        items = json.load(resp)["message"]["items"]
    papers = []
    for it in items:
        doi = it.get("DOI", "")
        ssrn_id = doi.rsplit("ssrn.", 1)[-1] if "ssrn." in doi else ""
        year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip() for a in it.get("author", [])
        )
        papers.append({
            "ssrn_id": ssrn_id,
            "doi": doi,
            "url": f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={ssrn_id}" if ssrn_id else f"https://doi.org/{doi}",
            "title": _clean((it.get("title") or [""])[0]),
            "authors": authors,
            "year": year,
            "citations": it.get("is-referenced-by-count", 0),
            "abstract": _clean(it.get("abstract")),
            "source": "ssrn",
            "queries": [query],
        })
    return papers


def query_arxiv(query: str, rows: int, since: int | None) -> list[dict]:
    terms = " AND ".join(f"all:{w}" for w in query.split())
    params = {"search_query": f"cat:q-fin.* AND {terms}", "max_results": rows, "sortBy": "relevance"}
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "quant-lab-ssrn/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        root = ET.fromstring(resp.read())
    papers = []
    for e in root.findall("a:entry", ARXIV_NS):
        abs_url = e.findtext("a:id", "", ARXIV_NS)
        arxiv_id = re.sub(r"v\d+$", "", abs_url.rsplit("/abs/", 1)[-1])
        year = int(e.findtext("a:published", "0000", ARXIV_NS)[:4])
        if since and year < since:
            continue
        papers.append({
            "ssrn_id": "",
            "doi": f"arXiv:{arxiv_id}",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "title": _clean(e.findtext("a:title", "", ARXIV_NS)),
            "authors": ", ".join(a.findtext("a:name", "", ARXIV_NS) for a in e.findall("a:author", ARXIV_NS)),
            "year": year,
            "citations": None,  # arXiv reports none; not zero
            "abstract": _clean(e.findtext("a:summary", "", ARXIV_NS)),
            "source": "arxiv",
            "queries": [query],
        })
    return papers


SOURCES = {"ssrn": query_crossref, "arxiv": query_arxiv}

# Pre-screen so the agent reads a short list instead of hundreds of abstracts.
RULE_TERMS = ["strategy", "trading rule", "signal", "long-short", "portfolio", "sharpe", "abnormal return",
              "out-of-sample", "transaction cost", "net of cost", "after cost", "profitab", "backtest",
              "predict", "excess return", "alpha", "intraday", "futures", "forex", "currency", "gold"]
THEORY_TERMS = ["we model", "equilibrium", "theoretical", "survey", "literature review", "regulation",
                "policy", "corporate governance", "accounting standard"]


def screen_score(p: dict) -> float:
    text = f"{p['title']} {p['abstract']}".lower()
    score = sum(t in text for t in RULE_TERMS) - 2 * sum(t in text for t in THEORY_TERMS)
    score += min(p["citations"] or 0, 200) ** 0.5 / 2  # citations help, capped
    score += 1 if (p["year"] or 0) >= 2018 else 0
    return score if p["abstract"] else score - 3  # abstract-less papers can't be judged cheaply


def seen_ids(ideas_md: Path) -> set[str]:
    if not ideas_md.exists():
        return set()
    t = ideas_md.read_text(encoding="utf-8")
    return set(re.findall(r"abstract_id=(\d+)", t)) | {f"arXiv:{i}" for i in re.findall(r"arxiv\.org/abs/([\w.]+)", t)}


def write_shortlist(papers: list[dict], n: int, out: Path) -> int:
    seen = seen_ids(out / "ideas.md")
    fresh = [p for p in papers if p["ssrn_id"] not in seen and p["doi"] not in seen]
    top = sorted(fresh, key=screen_score, reverse=True)[:n]
    lines = [f"# Shortlist: top {len(top)} of {len(papers)} by pre-screen score "
             f"({len(papers) - len(fresh)} already in ideas.md skipped)",
             "id | year | cites | score | title | abstract (first 300 chars)", ""]
    for p in top:
        pid = p["ssrn_id"] or p["doi"]
        cites = "-" if p["citations"] is None else p["citations"]
        lines.append(f"{pid} | {p['year']} | {cites} | {screen_score(p):.1f} | {p['title']} | {p['abstract'][:300]}")
    (out / "shortlist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(top)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queries", nargs="*", help="keyword queries")
    ap.add_argument("--default", action="store_true", help="add the built-in sweep of strategy topics")
    ap.add_argument("--rows", type=int, default=40, help="hits per query (max 1000)")
    ap.add_argument("--since", type=int, help="earliest publication year")
    ap.add_argument("--source", choices=["ssrn", "arxiv", "all"], default="ssrn")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--shortlist", type=int, default=40, help="papers written to shortlist.md (0 = none)")
    args = ap.parse_args()

    queries = list(args.queries) + (DEFAULT_QUERIES if args.default else [])
    if not queries:
        ap.error("give at least one query or --default")

    sources = list(SOURCES) if args.source == "all" else [args.source]
    merged: dict[str, dict] = {}
    for src in sources:
        for q in queries:
            try:
                hits = SOURCES[src](q, args.rows, args.since)
            except Exception as exc:  # report and continue; a failed query is logged, not hidden
                print(f"FAILED  {src:5s} {q!r}: {exc}")
                continue
            new = 0
            for p in hits:
                if p["doi"] in merged:
                    merged[p["doi"]]["queries"].append(q)
                else:
                    merged[p["doi"]] = p
                    new += 1
            print(f"{len(hits):4d} hits ({new:3d} new)  {src:5s} {q!r}")
            time.sleep(3 if src == "arxiv" else 1)  # arXiv asks for 3 s between calls

    papers = sorted(merged.values(), key=lambda p: p["citations"] or 0, reverse=True)
    args.out.mkdir(parents=True, exist_ok=True)
    meta = {
        "source": " + ".join({"ssrn": "Crossref API, prefix 10.2139 (SSRN)", "arxiv": "arXiv API, q-fin"}[s] for s in sources),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queries": queries,
        "rows_per_query": args.rows,
        "since": args.since,
        "n_papers": len(papers),
    }
    (args.out / "papers.json").write_text(json.dumps({"meta": meta, "papers": papers}, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(args.out / "papers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "ssrn_id", "year", "citations", "title", "authors", "url", "queries", "abstract"])
        w.writeheader()
        for p in papers:
            w.writerow({**{k: p[k] for k in w.fieldnames if k != "queries"}, "queries": " | ".join(p["queries"])})
    print(f"\n{len(papers)} unique papers -> {args.out / 'papers.json'}")
    if args.shortlist:
        k = write_shortlist(papers, args.shortlist, args.out)
        print(f"{k} pre-screened papers -> {args.out / 'shortlist.md'}")


if __name__ == "__main__":
    main()
