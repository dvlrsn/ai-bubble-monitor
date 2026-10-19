"""AI Bubble Monitor: tracks signs that the AI equity boom is fading or bursting.

A risk monitor, not a timing model and not investment advice.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
DB_PATH = DATA_DIR / "monitor.db"
MANUAL_PATH = DATA_DIR / "manual.json"
CONFIG_PATH = DATA_DIR / "config.json"
