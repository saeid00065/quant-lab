"""Small desktop app: download Dukascopy 1-minute BID/ASK data and save it as one CSV.

Run: py -3 scripts/dukascopy_app.py   (or double-click "Dukascopy Downloader.pyw")

Uses the same engine as the dashboard (src/modules/dukascopy.py, src/data_export.py):
- raw day files are cached in data/raw/dukascopy and never modified; a stopped run resumes;
- `date` in the CSV is the UTC bar START; minutes without ticks are left out, nothing is filled;
- volume is Dukascopy's tick-volume proxy, not total market volume.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import traceback
from datetime import date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_export import PRICES, TIMEFRAMES, build_export, write_export  # noqa: E402
from src.modules.dukascopy import INSTRUMENT_INFO, DukascopyBlocked, Stopped, _sleep, download  # noqa: E402

RAW = ROOT / "data/raw/dukascopy"
EXPORTS = ROOT / "data/exports"
EARLIEST = date(2003, 1, 1)
ROUNDS, ROUND_WAIT = 3, 120  # retry rounds when Dukascopy throttles
# state -> (color, label) of the status line
STATES = {
    "idle": ("#666666", "READY"),
    "working": ("#1a7f37", "WORKING"),
    "building": ("#1a7f37", "WORKING"),
    "waiting": ("#b35900", "WAITING"),
    "done": ("#0b5cad", "DONE"),
    "warning": ("#b35900", "DONE WITH GAPS"),
    "stopped": ("#666666", "STOPPED"),
    "blocked": ("#c62828", "NOT WORKING"),
    "error": ("#c62828", "NOT WORKING"),
}


def validate(symbol: str, start: str, end: str) -> tuple[date, date]:
    if symbol not in INSTRUMENT_INFO:
        raise ValueError(f"Unknown symbol {symbol!r}")
    try:
        s, e = date.fromisoformat(start.strip()), date.fromisoformat(end.strip())
    except ValueError:
        raise ValueError("Dates must be YYYY-MM-DD") from None
    yesterday = date.today() - timedelta(days=1)
    if s < EARLIEST or e > yesterday:
        raise ValueError(f"Dates must be between {EARLIEST} and {yesterday} (today is not complete yet)")
    if s > e:
        raise ValueError("Start date is after end date")
    return s, e


def run(req: dict, post, should_stop) -> None:
    """Worker thread: download -> combine -> export. Talks to the UI only through `post`."""
    def progress(done, total, failed):
        post("progress", (done, total, failed))

    def on_wait(reason, seconds):
        post("log", f"Dukascopy {reason}. Retrying in {seconds:.0f} s")
        post("state", ("waiting", f"Dukascopy {reason}", seconds))

    try:
        for rnd in range(1, ROUNDS + 1):
            post("state", ("working", f"Connecting to Dukascopy (round {rnd} of {ROUNDS})", 0))
            post("log", f"Round {rnd}: downloading {req['symbol']} BID + ASK {req['start']} .. {req['end']}")
            stats = download(req["symbol"], req["start"], req["end"], RAW, log=lambda *a, **k: None,
                             progress=progress, on_wait=on_wait, should_stop=should_stop)
            post("log", f"  {stats['downloaded']} downloaded, {stats['cached']} already cached, "
                        f"{stats['empty']} empty (no trading), {len(stats['failed'])} failed")
            if not stats["failed"]:
                break
            if rnd < ROUNDS:
                post("log", f"  Retrying failed files in {ROUND_WAIT // 60} min...")
                post("state", ("waiting", f"{len(stats['failed'])} files failed, retrying them", ROUND_WAIT))
                _sleep(ROUND_WAIT, should_stop)
        post("log", "Combining BID + ASK, sorting, building timeframe...")
        post("state", ("building", "Combining BID + ASK and writing CSV", 0))
        df, summary = build_export(req["symbol"], req["start"], req["end"], req["timeframe"], req["price"], RAW)
        name = f"{req['symbol']}_{req['timeframe']}_{req['price']}_{req['start']}_{req['end']}.csv"
        path = write_export(df, Path(req["out_dir"]) / name)
        post("log", f"Saved {summary['rows']:,} rows -> {path}")
        post("log", f"  first {summary['first']}, last {summary['last']} (UTC bar start)")
        post("log", f"  filler minutes left out: {summary['filler_minutes_excluded']:,}; "
                    f"rows with one side only: {summary['rows_one_side_only']:,}; duplicates: {summary['duplicates']}")
        if summary["missing_day_files"]:
            post("log", f"  WARNING: {len(summary['missing_day_files'])} day files could not be downloaded; "
                        "run again later to fill them.")
            post("state", ("warning", f"Saved {summary['rows']:,} rows, but "
                                      f"{len(summary['missing_day_files'])} day files are missing", 0))
        else:
            post("state", ("done", f"Finished: {summary['rows']:,} rows saved", 0))
        post("done", str(path))
    except Stopped:
        post("log", "Stopped. Files already downloaded are kept; start again to continue.")
        post("state", ("stopped", "Stopped by you", 0))
        post("done", None)
    except DukascopyBlocked as exc:
        post("log", f"Dukascopy is refusing downloads from this connection ({str(exc).split(' after ')[0]}). "
                    "Try later, another network/VPN, or put your VPN app's local proxy address in proxy.txt "
                    "in the project folder (e.g. socks5h://127.0.0.1:10808).")
        post("state", ("blocked", "Dukascopy server cannot be reached from this connection", 0))
        post("done", None)
    except Exception as exc:
        post("log", f"ERROR: {exc}\n{traceback.format_exc(limit=3)}")
        post("state", ("error", f"NOT WORKING: {exc}", 0))
        post("done", None)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dukascopy Downloader")
        self.minsize(560, 460)
        self.events: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_file: str | None = None

        yesterday = date.today() - timedelta(days=1)
        self.symbol = tk.StringVar(value="XAUUSD")
        self.start = tk.StringVar(value=(yesterday - timedelta(days=30)).isoformat())
        self.end = tk.StringVar(value=yesterday.isoformat())
        self.timeframe = tk.StringVar(value="1m")
        self.price = tk.StringVar(value="bid_ask")
        self.out_dir = tk.StringVar(value=str(EXPORTS))
        self.status = tk.StringVar(value="Ready")

        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        symbols = [f"{k}  -  {v[0]}" for k, v in INSTRUMENT_INFO.items()]
        rows = [
            ("Symbol", ttk.Combobox(f, values=symbols, state="readonly")),
            ("Start (UTC day)", ttk.Entry(f, textvariable=self.start)),
            ("End (UTC day, incl.)", ttk.Entry(f, textvariable=self.end)),
            ("Timeframe", ttk.Combobox(f, textvariable=self.timeframe, values=list(TIMEFRAMES), state="readonly")),
            ("Price", ttk.Combobox(f, textvariable=self.price, values=list(PRICES), state="readonly")),
        ]
        for r, (label, w) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            w.grid(row=r, column=1, columnspan=2, sticky="ew", pady=3)
        self.sym_box = rows[0][1]
        self.sym_box.current(list(INSTRUMENT_INFO).index("XAUUSD"))

        ttk.Label(f, text="Save to").grid(row=5, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.out_dir).grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Button(f, text="Browse...", command=self.browse).grid(row=5, column=2, padx=(6, 0))

        bar = ttk.Frame(f)
        bar.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        self.start_btn = ttk.Button(bar, text="Download", command=self.start_job)
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop_job, state="disabled")
        self.open_btn = ttk.Button(bar, text="Open folder", command=self.open_folder)
        for b in (self.start_btn, self.stop_btn, self.open_btn):
            b.pack(side="left", padx=(0, 6))

        self.light = tk.Label(f, anchor="w", font=("Segoe UI", 11, "bold"))
        self.light.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        line = ttk.Frame(f)
        line.grid(row=8, column=0, columnspan=3, sticky="ew", pady=4)
        line.columnconfigure(0, weight=1)
        self.bar = ttk.Progressbar(line, mode="determinate")
        self.bar.grid(row=0, column=0, sticky="ew")
        self.pct = ttk.Label(line, text="0%", width=6, anchor="e")
        self.pct.grid(row=0, column=1)
        ttk.Label(f, textvariable=self.status).grid(row=10, column=0, columnspan=3, sticky="w")
        self.log = tk.Text(f, height=12, wrap="word", state="disabled")
        self.log.grid(row=11, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        f.rowconfigure(11, weight=1)
        self.wait_until = 0.0
        self.set_state("idle", "press Download", 0)

        self.write("Data: Dukascopy public feed, 1-minute BID and ASK quotes (not trades).")
        self.write("Timestamps are UTC bar start. Volume is Dukascopy tick volume, not market volume.")
        self.after(100, self.pump)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def browse(self) -> None:
        d = filedialog.askdirectory(initialdir=self.out_dir.get() or str(ROOT))
        if d:
            self.out_dir.set(d)

    def open_folder(self) -> None:
        d = Path(self.out_dir.get())
        d.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(d)

    def start_job(self) -> None:
        symbol = self.sym_box.get().split()[0]
        try:
            s, e = validate(symbol, self.start.get(), self.end.get())
        except ValueError as exc:
            messagebox.showerror("Check the inputs", str(exc))
            return
        req = {"symbol": symbol, "start": s, "end": e, "timeframe": self.timeframe.get(),
               "price": self.price.get(), "out_dir": self.out_dir.get()}
        self.stop_flag.clear()
        self.bar["value"] = 0
        self.status.set("Starting...")
        self.pct["text"] = "0%"
        self.set_state("working", "Starting", 0)
        self.start_btn["state"], self.stop_btn["state"] = "disabled", "normal"
        post = lambda kind, data: self.events.put((kind, data))  # noqa: E731
        self.worker = threading.Thread(target=run, args=(req, post, self.stop_flag.is_set), daemon=True)
        self.worker.start()

    def stop_job(self) -> None:
        self.stop_flag.set()
        self.status.set("Stopping...")

    def pump(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.write(data)
                elif kind == "state":
                    self.set_state(*data)
                elif kind == "progress":
                    done, total, failed = data
                    self.set_state("working", f"downloaded {done} of {total} day files", 0)
                    self.bar["maximum"], self.bar["value"] = max(total, 1), done
                    self.pct["text"] = f"{done / max(total, 1):.0%}"
                    self.status.set(f"Day files: {done}/{total} done, {failed} failed")
                elif kind == "done":
                    self.last_file = data
                    self.status.set("Finished" if data else "Not finished - see log")
                    if data:
                        self.bar["value"] = self.bar["maximum"]
                        self.pct["text"] = "100%"
                    self.start_btn["state"], self.stop_btn["state"] = "normal", "disabled"
        except queue.Empty:
            pass
        if self.state == "waiting":
            left = max(0, round(self.wait_until - time.monotonic()))
            self.light["text"] = f"\u25cf  WAITING - {self.state_text}, retrying in {left} s"
        self.after(100, self.pump)

    def set_state(self, state: str, text: str, seconds: float) -> None:
        """Colored status line + bar mode, so it is obvious whether the download is working."""
        color, label = STATES[state]
        self.state, self.state_text = state, text
        self.wait_until = time.monotonic() + seconds
        self.light.configure(fg=color, text=f"\u25cf  {label} - {text}")
        busy = state in ("waiting", "building")  # moving bar: alive, but no file finished yet
        if busy and str(self.bar["mode"]) != "indeterminate":
            self.bar.configure(mode="indeterminate")
            self.bar.start(15)
        elif not busy and str(self.bar["mode"]) != "determinate":
            self.bar.stop()
            self.bar.configure(mode="determinate")

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Download running", "Stop the download and close? Downloaded files are kept."):
                return
            self.stop_flag.set()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
