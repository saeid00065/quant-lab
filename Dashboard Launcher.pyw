"""Small Windows launcher for the static Quant Lab dashboard in dist/."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


PROJECT_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_DIR / "dist"
DASHBOARD_URL = "http://127.0.0.1:8502"


class DashboardLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.process: subprocess.Popen[bytes] | None = None
        self.title("Quant Lab Dashboard")
        self.resizable(False, False)
        self.configure(bg="#10212b")
        self._build_interface()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_interface(self) -> None:
        card = tk.Frame(self, bg="#173442", padx=28, pady=26)
        card.pack(padx=18, pady=18)
        tk.Label(card, text="QUANT LAB", bg="#173442", fg="#f5f4ee", font=("Segoe UI", 21, "bold")).pack(anchor="w")
        tk.Label(card, text="Static research dashboard", bg="#173442", fg="#b6c9cc", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 20))
        self.status = tk.StringVar(value="Ready to start")
        tk.Label(card, textvariable=self.status, bg="#10212b", fg="#e3eff0", width=35, anchor="w", padx=12, pady=9).pack(fill="x", pady=(0, 18))
        buttons = tk.Frame(card, bg="#173442")
        buttons.pack(fill="x")
        self.start_button = tk.Button(buttons, text="Start dashboard", command=self.start_dashboard, bg="#145c72", fg="white")
        self.start_button.pack(side="left", fill="x", expand=True)
        tk.Button(buttons, text="Open", command=self.open_dashboard, bg="#365d67", fg="white").pack(side="left", fill="x", expand=True, padx=8)
        tk.Button(buttons, text="Stop", command=self.stop_dashboard, bg="#9b5144", fg="white").pack(side="left", fill="x", expand=True)

    def start_dashboard(self) -> None:
        if self.process and self.process.poll() is None:
            self.status.set("Dashboard is already running")
            return
        if not (DASHBOARD_DIR / "index.html").exists():
            messagebox.showerror("Quant Lab", "dist/index.html was not found.")
            return
        self.status.set("Starting dashboard…")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "http.server", "8502", "--directory", str(DASHBOARD_DIR)],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._wait_for_dashboard, daemon=True).start()

    def _wait_for_dashboard(self) -> None:
        for _ in range(15):
            try:
                urllib.request.urlopen(DASHBOARD_URL, timeout=1)
            except OSError:
                time.sleep(1)
            else:
                self.after(0, self._dashboard_ready)
                return
        self.after(0, lambda: self.status.set("Could not start dashboard"))

    def _dashboard_ready(self) -> None:
        self.status.set("Running at localhost:8502")
        webbrowser.open(DASHBOARD_URL)

    def open_dashboard(self) -> None:
        webbrowser.open(DASHBOARD_URL)

    def stop_dashboard(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process = None
            self.status.set("Dashboard stopped")

    def _close(self) -> None:
        self.stop_dashboard()
        self.destroy()


if __name__ == "__main__":
    DashboardLauncher().mainloop()
