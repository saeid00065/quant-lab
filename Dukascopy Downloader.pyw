"""Double-click to open the Dukascopy downloader (no console window)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "scripts" / "dukascopy_app.py"), run_name="__main__")
