"""Backtest of the automated price-and-credit layer (brief section 12, step 7).

AI-specific series (lab revenue, GPU rents, CDS) are too short to test, so this
replays only the parts with decades of daily history: market internals (D),
a credit proxy (Baa minus Treasury, since FRED's high-yield series only covers
three years) and macro (G). It answers two questions:
  1. Around each past top, how early did this layer warn?
  2. How often did it warn when no big fall followed (false alarms)?
"""

import json
from datetime import date, timedelta
from statistics import median

from . import OUT_DIR, store
from .ctx import Ctx
from .indicators import BY_ID, interp

D_IDS = ["sox_drawdown", "ndx_trend", "vix", "kospi_drawdown"]
G_IDS = ["us10y", "real10y", "cpi", "nfci", "yield_curve", "oil"]

# Market tops to study: (label, date of the Nasdaq-100 or S&P 500 peak)
EPISODES = [
    ("Dot-com top", "2000-03-27"),
    ("Housing/credit top", "2007-10-31"),
    ("2021 growth top", "2021-11-19"),
    ("Yen-carry unwind", "2024-07-10"),
    ("Tariff shock", "2025-02-19"),
]


def _baa(c):
    r = c.last("fred:BAA10Y")
    if not r:
        return None
    low = c.min_since("fred:BAA10Y", 365)
    level = interp([(2.0, 0), (2.6, 34), (3.2, 67), (4.5, 100)], r[1])
    widen = interp([(0, 0), (50, 34), (100, 67), (200, 100)], 100 * (r[1] - low))
    return max(level, widen)


def _score(c, iid):
    ind = BY_ID[iid]
    try:
        r = ind["calc"](c)
    except Exception:
        return None
    if not r or c.age_days(r["date"]) > ind["max_age"]:
        return None
    s = interp(ind["points"], r["value"])
    if "extra_score" in r:
        s = max(s, r["extra_score"])
    if "score_floor" in r:
        s = max(s, r["score_floor"])
    return s


def turn_proxy(c):
    d = [x for x in (_score(c, i) for i in D_IDS) if x is not None]
    g = [x for x in (_score(c, i) for i in G_IDS) if x is not None]
    cr = _baa(c)
    parts = [median(d) if d else None, cr, median(g) if g else None]
    parts = [p for p in parts if p is not None]
    return round(sum(parts) / len(parts), 1) if len(parts) >= 2 else None


def _ndx_after(c_all, d0, days):
    """Worst Nasdaq-100 drawdown from d0's close over the next `days` days."""
    s = c_all.series.get("px:^NDX", [])
    end = (date.fromisoformat(d0) + timedelta(days=days)).isoformat()
    window = [v for d, v in s if d0 <= d <= end]
    if not window:
        return None
    return round(100 * (min(window) / window[0] - 1), 1)


def run(start="1996-01-01", log=print):
    series = store.load_all()
    if len(series.get("px:^NDX", [])) < 5000:
        log("The archive lacks long daily history. Run `python monitor.py run` first.")
        return
    base = Ctx(series, {}, date.today().isoformat())
    dates = [d for d, _ in series["px:^NDX"] if d >= start]
    weekly = dates[::5]
    if weekly[-1] != dates[-1]:
        weekly.append(dates[-1])
    log(f"Replaying {len(weekly)} weeks from {weekly[0]}…")
    hist = [(d, turn_proxy(base.at(d))) for d in weekly]
    hist = [(d, v) for d, v in hist if v is not None]
    by_date = dict(hist)

    def val_near(d):
        prior = [v for dd, v in hist if dd <= d]
        return prior[-1] if prior else None

    rows = []
    for label, peak in EPISODES:
        p = date.fromisoformat(peak)
        first50 = next((d for d, v in hist if v >= 50 and (p - timedelta(days=540)).isoformat() <= d <= (p + timedelta(days=365)).isoformat()), None)
        lead = (p - date.fromisoformat(first50)).days if first50 else None
        rows.append({
            "episode": label, "peak": peak,
            "proxy_6m_before": val_near((p - timedelta(days=182)).isoformat()),
            "proxy_at_peak": val_near(peak),
            "proxy_3m_after": val_near((p + timedelta(days=91)).isoformat()),
            "first_50": first50, "lead_days": lead,
            "ndx_fall_next_2y": _ndx_after(base, peak, 730),
        })

    # False alarms: proxy crossing 50 (held 4 weeks) with no 20% Nasdaq fall within a year.
    signals, held = [], 0
    for i, (d, v) in enumerate(hist):
        held = held + 1 if v >= 50 else 0
        if held == 4 and (not signals or (date.fromisoformat(d) - date.fromisoformat(signals[-1]["date"])).days > 365):
            fall = _ndx_after(base, d, 365)
            signals.append({"date": d, "proxy": v, "ndx_fall_next_1y": fall, "hit": fall is not None and fall <= -20})

    now = hist[-1]
    out = {"episodes": rows, "signals": signals, "now": {"date": now[0], "proxy": now[1]},
           "history": hist, "note": __doc__.strip()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "backtest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    log("\nTurn proxy (price, credit and macro only) around past tops; 50+ = warning")
    log(f"{'episode':20} {'peak':10} {'6m before':>9} {'at peak':>8} {'3m after':>8} {'first 50+':>11} {'lead':>6} {'NDX fall 2y':>11}")
    for r in rows:
        fmt = lambda x: "–" if x is None else f"{x:.0f}"
        lead = "–" if r["lead_days"] is None else f"{r['lead_days']:+d}d"
        log(f"{r['episode']:20} {r['peak']:10} {fmt(r['proxy_6m_before']):>9} {fmt(r['proxy_at_peak']):>8} {fmt(r['proxy_3m_after']):>8} "
            f"{r['first_50'] or '–':>11} {lead:>6} {fmt(r['ndx_fall_next_2y']) + '%':>11}")
    hits = sum(s["hit"] for s in signals)
    log(f"\nWarnings (proxy 50+ for 4 weeks), at most one a year: {len(signals)}; followed by a 20%+ Nasdaq-100 fall within a year: {hits}")
    for s in signals:
        log(f"  {s['date']}  proxy {s['proxy']:.0f}  Nasdaq-100 next 12m worst {s['ndx_fall_next_1y']}%  {'HIT' if s['hit'] else 'false alarm'}")
    log(f"\nNow ({now[0]}): proxy {now[1]:.0f}. Saved out/backtest.json")
    log("Positive lead = warned before the peak. This layer is built to confirm a turn, so late warnings are expected.")
