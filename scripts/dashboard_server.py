"""Quant Lab dashboard server: serves dist/ and a small local API for Dukascopy downloads.

Run: py -3 scripts/dashboard_server.py [PORT] [--open]   (default 8502, bound to 127.0.0.1 only;
     a busy port is skipped; --open opens the Data page once the server is up)

API (JSON):
  GET  /api/instruments              symbols, timeframes, price options
  POST /api/download                 {symbol, start, end, timeframe, price} -> {job}
  GET  /api/jobs/<id>                progress / result
  GET  /api/jobs/<id>/file           the finished CSV (bid and ask in one file)
  POST /api/jobs/<id>/cancel
  GET  /api/exports                  previous exports
One download job runs at a time, so Dukascopy is not hammered.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import uuid
from datetime import date, timedelta
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_export import PRICES, TIMEFRAMES, build_export, shape, write_export  # noqa: E402
from src.data_import import combine_imports  # noqa: E402
from src.modules.dukascopy import INSTRUMENT_INFO, DukascopyBlocked, Stopped, _sleep, download  # noqa: E402

DIST = ROOT / "dist"
# Overridable only for testing with sample files.
RAW = Path(os.environ.get("QUANTLAB_RAW_DIR", ROOT / "data/raw/dukascopy"))
EXPORTS = Path(os.environ.get("QUANTLAB_EXPORT_DIR", ROOT / "data/exports"))
IMPORTS = Path(os.environ.get("QUANTLAB_IMPORT_DIR", ROOT / "data/imports"))  # uploaded files kept as-is
MAX_UPLOAD = 1_500_000_000
EARLIEST = date(2003, 1, 1)
ROUNDS, ROUND_WAIT = 3, 120  # retry rounds when Dukascopy throttles

JOBS: dict[str, dict] = {}
RUN_LOCK = threading.Lock()


def parse_request(body: dict) -> dict:
    symbol = str(body.get("symbol", "")).upper()
    if symbol not in INSTRUMENT_INFO:
        raise ValueError(f"Unknown symbol {symbol!r}")
    tf, price = str(body.get("timeframe", "")), str(body.get("price", ""))
    if tf not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {tf!r}")
    if price not in PRICES:
        raise ValueError(f"Unknown price {price!r}")
    start, end = date.fromisoformat(str(body.get("start"))), date.fromisoformat(str(body.get("end")))
    yesterday = date.today() - timedelta(days=1)
    if start < EARLIEST or end > yesterday:
        raise ValueError(f"Dates must be between {EARLIEST} and {yesterday} (today is not complete yet)")
    if start > end:
        raise ValueError("Start date is after end date")
    return {"symbol": symbol, "start": start, "end": end, "timeframe": tf, "price": price}


BLOCKED_MSG = ("Dukascopy is refusing downloads from this internet connection ({detail}). This is a temporary "
               "block on their side, usually for a few hours. Nothing is wrong with your settings. Options: try again "
               "later, switch network (e.g. phone hotspot / VPN), put your VPN app's local proxy address in proxy.txt in the "
               "project folder (e.g. socks5h://127.0.0.1:10808), or use 'Import from Dukascopy website' below.")


def run_job(job: dict) -> None:
    req = job["request"]
    stop = lambda: job["cancel"]  # noqa: E731

    def progress(done: int, total: int, failed: int) -> None:
        job.update(done=done, total=total, failed=failed, status="downloading",
                   message=f"Downloading BID and ASK day files: {done}/{total}")

    def on_wait(reason: str, seconds: float) -> None:
        job.update(status="waiting", message=f"Dukascopy {reason}. Retrying in {seconds:.0f} s "
                                              f"({job.get('done', 0)}/{job.get('total') or '?'} files done)")

    with RUN_LOCK:
        try:
            if stop():
                raise Stopped()
            stats = {"failed": []}
            for rnd in range(1, ROUNDS + 1):
                job.update(status="downloading", message=f"Contacting Dukascopy (round {rnd})")
                stats = download(req["symbol"], req["start"], req["end"], RAW, log=lambda *a, **k: None,
                                 progress=progress, on_wait=on_wait, should_stop=stop)
                job["cached"] = stats["cached"]
                if not stats["failed"]:
                    break
                if rnd < ROUNDS:
                    job.update(status="waiting", message=f"{len(stats['failed'])} files failed. Retrying them in {ROUND_WAIT // 60} min")
                    _sleep(ROUND_WAIT, stop)
            job.update(status="building", message="Combining BID + ASK, sorting, building timeframe")
            df, summary = build_export(req["symbol"], req["start"], req["end"], req["timeframe"], req["price"], RAW)
            name = f"{req['symbol']}_{req['timeframe']}_{req['price']}_{req['start']}_{req['end']}.csv"
            write_export(df, EXPORTS / name)
            done_msg = f"Ready: {summary['rows']:,} rows"
            if summary["missing_day_files"]:
                done_msg += f" (warning: {len(summary['missing_day_files'])} day files could not be downloaded; run again later to fill them)"
            job.update(status="done", message=done_msg, summary=summary, file=name)
        except Stopped:
            job.update(status="cancelled", message="Cancelled. Files already downloaded are kept.")
        except DukascopyBlocked as exc:
            detail = str(exc).split(" after ")[0]
            job.update(status="blocked", message=BLOCKED_MSG.format(detail=detail))
        except Exception as exc:
            job.update(status="error", message=str(exc), trace=traceback.format_exc(limit=3))


def _safe(name: str) -> str:
    import re
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)[:120]
    if not name or name.startswith("."):
        raise ValueError("bad file name")
    return name


def run_import(body: dict) -> dict:
    import pandas as pd

    token = _safe(str(body.get("token", "")))
    symbol = str(body.get("symbol", "")).upper()
    tf, price = str(body.get("timeframe", "")), str(body.get("price", ""))
    if symbol not in INSTRUMENT_INFO or tf not in TIMEFRAMES or price not in PRICES:
        raise ValueError("bad symbol, timeframe or price")
    folder = IMPORTS / token
    files = {side: [(f.name, f.read_bytes()) for f in sorted((folder / side).glob("*"))] for side in ("BID", "ASK")}
    combined, report = combine_imports(files["BID"], files["ASK"])
    src = pd.Timedelta(report["bar_size"])
    want = pd.Timedelta(TIMEFRAMES[tf]) if tf != "1D" else pd.Timedelta("1D")
    if want < src:
        raise ValueError(f"the files have {report['bar_size']} bars; choose a timeframe of at least that size")
    lo, hi = INSTRUMENT_INFO[symbol][2]
    med = combined["mid_close"].median()
    if not lo <= med <= hi:
        report["warnings"].append(f"median price {med:.5f} does not look like {symbol}; check the symbol")
    out = shape(combined, tf, price)
    first, last = out["date"].iloc[0], out["date"].iloc[-1]
    name = f"{symbol}_{tf}_{price}_{first:%Y-%m-%d}_{last:%Y-%m-%d}_imported.csv"
    write_export(out, EXPORTS / name)
    report.update(rows=int(len(out)), first=first.isoformat(), last=last.isoformat(), file=name,
                  filler_minutes_excluded=int((~combined["has_ticks"]).sum()),
                  duplicates=int(out["date"].duplicated().sum()))
    return report


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet except for API calls
        if "/api/" in (self.path or ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=HTTPStatus.OK):
        data = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_cors(self, obj):
        # Only this read-only endpoint is readable cross-origin, so a copy of the page opened
        # from disk (file://) can find the running server and switch to it.
        data = json.dumps(obj, default=str).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _public(self, job):
        return {k: v for k, v in job.items() if k not in ("cancel", "trace")}

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/instruments":
            return self._json_cors({
                "instruments": [{"symbol": k, "label": v[0]} for k, v in INSTRUMENT_INFO.items()],
                "timeframes": list(TIMEFRAMES), "prices": list(PRICES),
                "earliest": EARLIEST.isoformat(), "latest": (date.today() - timedelta(days=1)).isoformat(),
            })
        if p == "/api/exports":
            files = sorted(EXPORTS.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True) if EXPORTS.exists() else []
            return self._json([{"file": f.name, "mb": round(f.stat().st_size / 1e6, 2)} for f in files[:30]])
        if p.startswith("/api/exports/"):
            name = p.rsplit("/", 1)[-1]
            f = EXPORTS / name
            if "/" in name or "\\" in name or ".." in name or not f.is_file():
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return self._send_file(f)
        if p.startswith("/api/jobs/"):
            parts = p.split("/")
            job = JOBS.get(parts[3]) if len(parts) > 3 else None
            if not job:
                return self._json({"error": "unknown job"}, HTTPStatus.NOT_FOUND)
            if len(parts) > 4 and parts[4] == "file":
                if job.get("status") != "done":
                    return self._json({"error": "not ready"}, HTTPStatus.CONFLICT)
                return self._send_file(EXPORTS / job["file"])
            return self._json(self._public(job))
        return super().do_GET()

    def _send_file(self, f: Path):
        size = f.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with f.open("rb") as fh:
            while chunk := fh.read(1 << 20):
                self.wfile.write(chunk)

    def do_POST(self):
        p = self.path.split("?")[0]
        if p == "/api/download":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                req = parse_request(json.loads(self.rfile.read(n) or b"{}"))
            except Exception as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            jid = uuid.uuid4().hex[:10]
            queued = any(j["status"] in ("queued", "downloading", "waiting", "building") for j in JOBS.values())
            job = {"id": jid, "request": req, "status": "queued", "cancel": False, "done": 0, "total": 0, "failed": 0,
                   "message": "Waiting for the previous download to finish" if queued else "Starting"}
            JOBS[jid] = job
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            return self._json(self._public(job))
        if p == "/api/import/file":
            from urllib.parse import parse_qs, urlparse
            try:
                q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                side = q.get("side", "").upper()
                if side not in ("BID", "ASK"):
                    raise ValueError("side must be BID or ASK")
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 < n <= MAX_UPLOAD:
                    raise ValueError("empty or too large file")
                dest = IMPORTS / _safe(q.get("token", "")) / side / _safe(q.get("name", "upload.csv"))
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("wb") as fh:
                    left = n
                    while left:
                        chunk = self.rfile.read(min(left, 1 << 20))
                        if not chunk:
                            raise ValueError("upload interrupted")
                        fh.write(chunk)
                        left -= len(chunk)
                return self._json({"ok": True, "bytes": n})
            except Exception as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if p == "/api/import/combine":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                return self._json(run_import(json.loads(self.rfile.read(n) or b"{}")))
            except Exception as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if p.startswith("/api/jobs/") and p.endswith("/cancel"):
            job = JOBS.get(p.split("/")[3])
            if not job:
                return self._json({"error": "unknown job"}, HTTPStatus.NOT_FOUND)
            job["cancel"] = True
            return self._json({"ok": True})
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)


class ExclusiveServer(ThreadingHTTPServer):
    """Refuse to share a port. Python's default (SO_REUSEADDR) lets a second server bind a busy
    port on Windows, and the old server keeps answering - that caused empty menus."""
    allow_reuse_address = False

    def server_bind(self):
        import socket
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _has_api(port: int) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/instruments", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    import webbrowser

    if sys.stdout is None or sys.stderr is None:  # started windowless (pythonw): log to a file
        log = ROOT / "results" / "dashboard_server.log"
        log.parent.mkdir(exist_ok=True)
        sys.stdout = sys.stderr = open(log, "a", buffering=1, encoding="utf-8")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    open_browser = "--open" in sys.argv
    port = int(args[0]) if args else 8502

    # Port taken: if it is already this server, reuse it; otherwise (e.g. an old static
    # dashboard) try the next ports instead of failing with empty menus.
    server = None
    for p in range(port, port + 10):
        if _has_api(p):
            print(f"Dashboard already running: http://127.0.0.1:{p}", flush=True)
            if open_browser:
                webbrowser.open(f"http://127.0.0.1:{p}/data.html")
            return
        try:
            server = ExclusiveServer(("127.0.0.1", p), partial(Handler, directory=str(DIST)))
            break
        except OSError:
            print(f"Port {p} is used by another program, trying {p + 1}...", flush=True)
    if server is None:
        raise SystemExit(f"No free port between {port} and {port + 9}.")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Quant Lab dashboard: {url}  (keep this window open; Ctrl+C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url + "/data.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
