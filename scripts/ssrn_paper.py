"""Extract the testable facts from one paper and map what it led to.

For each paper id (SSRN abstract id, DOI, or arXiv id) this looks the paper up
in OpenAlex (open citation graph, no key needed), rebuilds its abstract, pulls
the numbers a backtest needs out of that abstract (assets, frequency, sample
period, claimed Sharpe/returns, costs, out-of-sample), and lists:
  - citing papers flagged as replication / critique / costs / decay
    (did the result survive?),
  - the most-cited and the most recent citing papers (what it helped build),
  - the most-cited references (what it builds on) and OpenAlex related works.
Output: research/ssrn/papers/<id>.md, one short file per paper. Extraction is
regex over the abstract only: "not stated" means the abstract does not say,
not that the paper does not.

Usage:
    python scripts/ssrn_paper.py 2089463
    python scripts/ssrn_paper.py 10.2139/ssrn.2089463 arXiv:2105.06573 --cites 15
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OA = "https://api.openalex.org"
MAILTO = "quant-lab-research@example.invalid"
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "ssrn" / "papers"
LIST_FIELDS = "id,doi,title,publication_year,cited_by_count"

# Citing papers whose title/abstract matches these answer "did it hold up?".
CHECK_QUERY = ("replication OR replicate OR critique OR \"out-of-sample\" OR \"transaction costs\" "
               "OR \"data snooping\" OR disappear OR decay OR revisit OR robustness")
CHECK_TAGS = {
    "replication": r"replic|reproduc|revisit|re-?examin|reassess",
    "critique": r"critiq|data[- ]snoop|p-hack|spurious|illusion|myth|not robust|fail",
    "costs": r"transaction cost|trading cost|net of cost|after cost|implementab|capacity",
    "decay": r"disappear|decay|vanish|declin|post-publication|out-of-sample",
}

ASSETS = {
    "equities": r"\bstocks?\b|equit|s&p|crsp", "futures": r"futures", "fx": r"currenc|\bfx\b|forex|exchange rate",
    "bonds": r"bond|treasur|fixed income", "commodities": r"commodit|\boil\b|gold|metal",
    "crypto": r"crypto|bitcoin", "options": r"option|implied vol|\bvix\b", "etfs": r"\betfs?\b",
}
FREQ = {
    "intraday": r"intraday|minute|high-frequency|tick", "daily": r"\bdaily\b|overnight",
    "weekly": r"weekly", "monthly": r"monthly|\bmonths?\b", "quarterly/annual": r"quarterly|annual(ly)? rebalanc",
}


def get(url: str, params: dict | None = None) -> dict:
    params = {**(params or {}), "mailto": MAILTO}
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": f"quant-lab-ssrn/1.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def to_doi(pid: str) -> str:
    pid = pid.strip()
    if pid.isdigit():
        return f"10.2139/ssrn.{pid}"
    m = re.match(r"(?i)arxiv:(.+)", pid) or re.search(r"arxiv\.org/abs/([\w.]+)", pid)
    if m:
        return "10.48550/arXiv." + re.sub(r"v\d+$", "", m.group(1))
    m = re.search(r"abstract_id=(\d+)", pid)
    if m:
        return f"10.2139/ssrn.{m.group(1)}"
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", pid)


def abstract(work: dict) -> str:
    inv = work.get("abstract_inverted_index") or {}
    pos = {i: w for w, idx in inv.items() for i in idx}
    return " ".join(pos[i] for i in sorted(pos))


def extract(text: str) -> dict[str, str]:
    t = text.lower()
    found = lambda table: ", ".join(k for k, rx in table.items() if re.search(rx, t)) or "not stated"
    years = [int(y) for y in re.findall(r"\b(1[89]\d\d|20[0-3]\d)\b", text)]
    period = f"{min(years)}–{max(years)}" if len(years) >= 2 else "not stated"
    span = re.findall(r"(\d+)\s+(?:years|decades)", t)
    nums = lambda rx: "; ".join(dict.fromkeys(m.group(0).strip() for m in re.finditer(rx, text, re.I))) or "not stated"
    return {
        "assets": found(ASSETS),
        "frequency": found(FREQ),
        "sample period": period + (f" ({', '.join(span)} yrs mentioned)" if span else ""),
        "markets/countries": nums(r"\b\d+\s+(?:\w+\s+)?(?:countries|markets|futures|currencies|commodities|stocks|assets|contracts|instruments|firms)"),
        "horizons": nums(r"\b\d+\s*(?:to|-|–)\s*\d+\s*(?:minutes|hours|days|weeks|months|years)|\b\d+-(?:minute|hour|day|week|month|year)\b"),
        "Sharpe claims": nums(r"sharpe ratio[^.;]{0,40}?\d+\.\d+|\d+\.\d+[^.;]{0,20}sharpe"),
        "return claims": nums(r"\d+(?:\.\d+)?\s?(?:%|percent|basis points|bps)(?:[^.;]{0,30}(?:per|a|annual|month|year|day))?"),
        "t-stats": nums(r"t-stat\w*[^.;]{0,15}\d+\.\d+"),
        "costs": "mentioned" if re.search(r"transaction cost|trading cost|net of|after cost|bid-ask|spread", t) else "not stated",
        "out-of-sample": "mentioned" if re.search(r"out-of-sample|holdout|walk-forward|post-publication", t) else "not stated",
    }


def tag(title: str) -> str:
    return ",".join(k for k, rx in CHECK_TAGS.items() if re.search(rx, title or "", re.I)) or "-"


def row(w: dict, with_tag: bool = False) -> str:
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    link = f"https://doi.org/{doi}" if doi else w["id"]
    t = f" | {tag(w.get('title'))}" if with_tag else ""
    return f"| {w.get('publication_year') or '-'} | {w.get('cited_by_count', 0)} | {(w.get('title') or '').strip()[:110]}{t} | {link} |"


def works(params: dict) -> list[dict]:
    time.sleep(0.2)
    return get(f"{OA}/works", {"select": LIST_FIELDS, **params}).get("results", [])


def report(pid: str, n: int) -> tuple[Path, str]:
    doi = to_doi(pid)
    w = get(f"{OA}/works/doi:{doi}")
    wid = w["id"].rsplit("/", 1)[-1]
    text = abstract(w)
    facts = extract(text)
    cites = f"cites:{wid}"
    checks = works({"filter": f"{cites},title_and_abstract.search:{CHECK_QUERY}", "sort": "relevance_score:desc", "per-page": n})
    top = works({"filter": cites, "sort": "cited_by_count:desc", "per-page": n})
    recent = works({"filter": cites, "sort": "publication_date:desc", "per-page": n})
    refs = [r.rsplit("/", 1)[-1] for r in w.get("referenced_works", [])][:100]
    built_on = works({"filter": "openalex:" + "|".join(refs), "sort": "cited_by_count:desc", "per-page": 10}) if refs else []
    rel = [r.rsplit("/", 1)[-1] for r in w.get("related_works", [])]
    related = works({"filter": "openalex:" + "|".join(rel), "per-page": 10}) if rel else []

    authors = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6])
    by_year = ", ".join(f"{c['year']}:{c['cited_by_count']}" for c in sorted(w.get("counts_by_year", []), key=lambda c: c["year"])[-8:])
    hdr = "| year | cites | title | link |\n|---|---|---|---|"
    lines = [
        f"# {w.get('title')}",
        f"{authors} — {w.get('publication_year')} — doi:{doi} — OpenAlex {wid}",
        f"Retrieved {datetime.now(timezone.utc):%Y-%m-%d} UTC from OpenAlex. Cited by {w.get('cited_by_count', 0)} "
        f"(by year: {by_year or 'n/a'}). Abstract only; claims are the paper's, not Quant Lab results.",
        "",
        "## Extracted from abstract",
        *(f"- **{k}:** {v}" for k, v in facts.items()),
        "",
        "## Abstract",
        text or "_OpenAlex has no abstract for this work._",
        "",
        f"## Did it hold up? Citing papers on replication/critique/costs/decay ({len(checks)})",
        "| year | cites | title | tags | link |\n|---|---|---|---|---|",
        *(row(c, True) for c in checks),
        "",
        f"## What it helped: most-cited citing papers ({len(top)})",
        hdr, *(row(c) for c in top),
        "",
        f"## Most recent citing papers ({len(recent)})",
        hdr, *(row(c) for c in recent),
        "",
        f"## Builds on: most-cited references ({len(built_on)} of {len(w.get('referenced_works', []))})",
        hdr, *(row(c) for c in built_on),
        "",
        f"## Related works (OpenAlex) ({len(related)})",
        hdr, *(row(c) for c in related),
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / (re.sub(r"[^\w.-]", "_", doi.split("/", 1)[-1]) + ".md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = (f"{doi}: cited {w.get('cited_by_count', 0)}, {len(checks)} check-papers, "
               f"assets={facts['assets']}, freq={facts['frequency']}, period={facts['sample period']}")
    return out, summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="+", help="SSRN abstract id, DOI, arXiv id, or SSRN/arXiv URL")
    ap.add_argument("--cites", type=int, default=10, help="papers per citing-paper list")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for pid in args.ids:
        try:
            out, summary = report(pid, args.cites)
            print(f"OK      {summary}\n        -> {out}")
        except Exception as exc:  # report and continue; a failed lookup is logged, not hidden
            print(f"FAILED  {pid}: {exc}" + (" (not in OpenAlex)" if "404" in str(exc) else ""))


if __name__ == "__main__":
    main()
