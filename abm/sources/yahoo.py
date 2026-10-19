"""Daily prices from Yahoo Finance's chart endpoint (free, unofficial)."""

from datetime import datetime, timezone
from urllib.parse import quote

from . import get

# Ticker set from the research brief, section 14.
TICKERS = {
    "SPY": "S&P 500 ETF",
    "RSP": "Equal-weight S&P 500 ETF",
    "QQQ": "Nasdaq-100 ETF",
    "^GSPC": "S&P 500 index",
    "^NDX": "Nasdaq-100 index",
    "^SOX": "Philadelphia semiconductor index",
    "SMH": "Semiconductor ETF",
    "NVDA": "Nvidia",
    "AVGO": "Broadcom",
    "AMD": "AMD",
    "MU": "Micron",
    "TSM": "TSMC",
    "ASML": "ASML",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "ORCL": "Oracle",
    "CRWV": "CoreWeave",
    "NBIS": "Nebius",
    "IREN": "IREN",
    "OWL": "Blue Owl",
    "OBDC": "Blue Owl Capital Corp (BDC)",
    "ARCC": "Ares Capital (BDC)",
    "EWY": "South Korea ETF",
    "^KS11": "KOSPI",
    "005930.KS": "Samsung Electronics",
    "000660.KS": "SK Hynix",
    "^TWII": "Taiwan index",
    "^VIX": "VIX",
    "^VXN": "Nasdaq VIX",
    "SOXL": "3x semiconductor ETF",
    "NVDL": "2x Nvidia ETF",
    "TQQQ": "3x Nasdaq-100 ETF",
}

# Long history for backtests of the price layer.
LONG_HISTORY = {"^GSPC", "^NDX", "^SOX", "^VIX", "^KS11"}


def fetch(ticker, range_="5y"):
    base = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?interval=1d&includeAdjustedClose=true"
    if range_ == "max":
        # range=max silently switches to monthly bars; explicit dates stay daily.
        now = int(datetime.now(timezone.utc).timestamp())
        url = f"{base}&period1=0&period2={now}"
    else:
        url = f"{base}&range={range_}"
    j = get(url).json()
    res = (j.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"Yahoo {ticker}: {(j.get('chart') or {}).get('error')}")
    res = res[0]
    ts = res.get("timestamp") or []
    ind = res.get("indicators", {})
    closes = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    offset = res["meta"].get("gmtoffset", 0)
    out = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(t + offset, tz=timezone.utc).strftime("%Y-%m-%d")
        out[d] = c
    return sorted(out.items())
