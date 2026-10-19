"""S&P 500 breadth: share of members above their 50- and 200-day averages.

Computed from Yahoo prices for today's constituents (Wikipedia list), so older
values carry survivorship bias. Good enough for the recent window that matters.
"""

import re
from concurrent.futures import ThreadPoolExecutor

from . import get, yahoo

WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def constituents():
    html = get(WIKI).text
    table = html.split('id="constituents"', 1)[-1].split("</table>", 1)[0]
    syms = re.findall(r'href="https://www\.(?:nyse|nasdaq)\.com/[^"]*"[^>]*>([A-Z.\-]+)</a>', table)
    syms = list(dict.fromkeys(s.replace(".", "-") for s in syms))
    if len(syms) < 400:
        raise RuntimeError(f"S&P 500 list parse found only {len(syms)} symbols")
    return syms


def _sma_flags(series, n):
    """{date: close > n-day SMA} for each date with enough history."""
    out = {}
    closes = [c for _, c in series]
    run = sum(closes[:n])
    for i in range(n, len(closes) + 1):
        if i > n:
            run += closes[i - 1] - closes[i - 1 - n]
        out[series[i - 1][0]] = closes[i - 1] > run / n
    return out


def fetch(progress=None):
    syms = constituents()

    def one(s):
        try:
            return s, yahoo.fetch(s, "2y")
        except Exception:
            return s, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        data = list(ex.map(one, syms))
    ok = [(s, d) for s, d in data if d and len(d) > 220]
    if progress:
        progress(f"breadth: {len(ok)}/{len(syms)} members fetched")
    counts50, counts200 = {}, {}
    for _, series in ok:
        for d, above in _sma_flags(series, 50).items():
            a, n = counts50.get(d, (0, 0))
            counts50[d] = (a + above, n + 1)
        for d, above in _sma_flags(series, 200).items():
            a, n = counts200.get(d, (0, 0))
            counts200[d] = (a + above, n + 1)
    # Ignore dates where too few members have data (holidays, sparse quotes).
    floor = 0.8 * len(ok)
    pct50 = sorted((d, 100 * a / n) for d, (a, n) in counts50.items() if n >= floor)
    pct200 = sorted((d, 100 * a / n) for d, (a, n) in counts200.items() if n >= floor)
    return pct50, pct200, len(ok)
