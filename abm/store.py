"""SQLite archive of every series the monitor fetches, plus daily score snapshots.

Series are archived permanently because some sources (FRED's ICE BofA spreads)
only serve a rolling window of about three years.
"""

import json
import sqlite3
from contextlib import contextmanager

from . import DB_PATH, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS obs (
    series TEXT NOT NULL,
    date   TEXT NOT NULL,
    value  REAL NOT NULL,
    PRIMARY KEY (series, date)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    series  TEXT PRIMARY KEY,
    fetched TEXT NOT NULL,
    status  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshot (
    date TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def save_series(series, points, status="ok"):
    """points: iterable of (date 'YYYY-MM-DD', value)."""
    from datetime import datetime, timezone

    with connect() as con:
        con.executemany(
            "INSERT OR REPLACE INTO obs(series, date, value) VALUES (?, ?, ?)",
            [(series, d, float(v)) for d, v in points],
        )
        con.execute(
            "INSERT OR REPLACE INTO fetch_log(series, fetched, status) VALUES (?, ?, ?)",
            (series, datetime.now(timezone.utc).isoformat(timespec="seconds"), status),
        )


def log_failure(series, status):
    from datetime import datetime, timezone

    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO fetch_log(series, fetched, status) VALUES (?, ?, ?)",
            (series, datetime.now(timezone.utc).isoformat(timespec="seconds"), status),
        )


def load_all():
    """Return {series: [(date, value), ...]} sorted by date."""
    out = {}
    with connect() as con:
        for s, d, v in con.execute("SELECT series, date, value FROM obs ORDER BY series, date"):
            out.setdefault(s, []).append((d, v))
    return out


def fetch_status():
    with connect() as con:
        return {s: (f, st) for s, f, st in con.execute("SELECT series, fetched, status FROM fetch_log")}


def save_snapshot(date, data):
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO snapshot(date, data) VALUES (?, ?)",
            (date, json.dumps(data)),
        )


def load_snapshots():
    with connect() as con:
        return [(d, json.loads(x)) for d, x in con.execute("SELECT date, data FROM snapshot ORDER BY date")]
