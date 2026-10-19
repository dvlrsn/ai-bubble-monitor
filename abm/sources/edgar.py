"""Company fundamentals from SEC EDGAR XBRL company facts.

Cash-flow lines in 10-Qs are year-to-date (Amazon also files trailing-twelve-month
figures), so quarterly values are derived: a ~90-day fact is used directly,
otherwise the quarter is YTD(end) minus YTD(previous quarter end, same start).
"""

from datetime import date

from . import UA_SEC, get

COMPANIES = {
    "MSFT": 789019,
    "GOOGL": 1652044,
    "AMZN": 1018724,
    "META": 1326801,
    "ORCL": 1341439,
    "NVDA": 1045810,
    "CRWV": 1769628,
}

HYPERSCALERS = ["MSFT", "GOOGL", "AMZN", "META"]

# Concept -> candidate us-gaap tags in order of preference.
FLOW_TAGS = {
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
}
STOCK_TAGS = {
    "receivables": ["AccountsReceivableNetCurrent"],
    "inventory": ["InventoryNet"],
}


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _quarterly(facts):
    """facts: list of dicts with start, end, val. Returns {end: quarterly value}."""
    by_span = {}
    for f in facts:
        if "start" not in f:
            continue
        by_span[(f["start"], f["end"])] = f["val"]
    quarters = {}
    for (s, e), v in by_span.items():
        if 80 <= _days(s, e) <= 100:
            quarters[e] = v
    # Derive the rest from year-to-date differences.
    for (s, e), v in by_span.items():
        span = _days(s, e)
        if e in quarters or span < 150 or span > 290:
            continue
        prev = [(e2, v2) for (s2, e2), v2 in by_span.items() if s2 == s and 80 <= _days(e2, e) <= 100]
        if prev:
            quarters[e] = v - prev[0][1]
    # Q4 = full fiscal year minus the first three quarters (YTD to Q3).
    for (s, e), v in by_span.items():
        span = _days(s, e)
        if e in quarters or not (350 <= span <= 380):
            continue
        q3 = [v2 for (s2, e2), v2 in by_span.items() if s2 == s and 80 <= _days(e2, e) <= 100]
        if q3:
            quarters[e] = v - q3[0]
    return quarters


def _pick(usgaap, tags, kind):
    """Merge candidate tags, preferring earlier ones where both report a period."""
    merged = {}
    for tag in reversed(tags):
        units = usgaap.get(tag, {}).get("units", {}).get("USD")
        if not units:
            continue
        units = [u for u in units if u.get("form") in ("10-Q", "10-K", "10-Q/A", "10-K/A")]
        if kind == "flow":
            merged.update(_quarterly(units))
        else:
            merged.update({u["end"]: u["val"] for u in units})
    return merged


def fetch(ticker):
    """Returns {concept: [(quarter_end, value), ...]}."""
    cik = COMPANIES[ticker]
    j = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", ua=UA_SEC).json()
    usgaap = j.get("facts", {}).get("us-gaap", {})
    out = {}
    for concept, tags in FLOW_TAGS.items():
        out[concept] = sorted(_pick(usgaap, tags, "flow").items())
    for concept, tags in STOCK_TAGS.items():
        out[concept] = sorted(_pick(usgaap, tags, "stock").items())
    return {k: v for k, v in out.items() if v}
