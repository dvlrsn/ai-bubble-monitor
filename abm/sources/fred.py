"""FRED series via the public CSV download (no API key needed)."""

import csv
import io

from . import get

SERIES = {
    "BAMLH0A0HYM2": "US high-yield bond spread (%)",
    "BAMLH0A3HYC": "CCC-rated bond spread (%)",
    "BAMLC0A0CM": "Investment-grade bond spread (%)",
    "BAA10Y": "Baa corporate minus 10-year Treasury (%)",
    "DGS10": "10-year Treasury yield (%)",
    "DGS30": "30-year Treasury yield (%)",
    "DFII10": "10-year real (inflation-protected) yield (%)",
    "T10Y3M": "10-year minus 3-month Treasury (%)",
    "T10Y2Y": "10-year minus 2-year Treasury (%)",
    "NFCI": "Chicago Fed financial conditions index",
    "STLFSI4": "St. Louis Fed financial stress index",
    "VIXCLS": "VIX volatility index",
    "NASDAQCOM": "Nasdaq Composite",
    "DCOILWTICO": "WTI crude oil ($/barrel)",
    "CPIAUCSL": "Consumer price index",
    "NCBEILQ027S": "Market value of US corporate equities ($M)",
    "GDP": "US nominal GDP ($B, annual rate)",
    "DFEDTARU": "Fed funds target, upper bound (%)",
}


def fetch(series_id):
    # FRED resets connections that claim to be a browser but are not; the
    # library's own User-Agent is accepted.
    r = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", ua=None)
    rows = csv.reader(io.StringIO(r.text))
    next(rows, None)
    out = []
    for row in rows:
        if len(row) < 2:
            continue
        d, v = row[0], row[1]
        if v in ("", "."):
            continue
        try:
            out.append((d, float(v)))
        except ValueError:
            continue
    if not out:
        raise RuntimeError(f"FRED {series_id}: no data")
    return out
