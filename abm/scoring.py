"""Scores indicators, pillars, the two composites and the regime (brief section 12)."""

from datetime import date, timedelta
from statistics import median

from .indicators import INDICATORS, LEVEL_SCORE, PILLARS, interp, level_of
from .tripwires import STAGES, TRIPWIRES

TURN_PILLARS = [p for p, v in PILLARS.items() if v["composite"] == "turn"]
VULN_PILLARS = [p for p, v in PILLARS.items() if v["composite"] == "vuln"]

REGIMES = {
    1: "Boom",
    2: "Fragile",
    3: "Cracking",
    4: "Unwind",
}


def _decel_score(ind, readings):
    """Latest growth as a share of the best of the previous three readings."""
    vals = [r["value"] for r in readings if "value" in r]
    if len(vals) < 2:
        return None, None
    peak = max(vals[-4:-1])
    if peak <= 0:
        return None, None
    ratio = vals[-1] / peak
    return interp([(0.0, 50), (0.5, 34), (1.0, 0)], ratio), ratio


def score_indicator(ind, c):
    out = {"id": ind["id"], "pillar": ind["pillar"], "kind": ind["kind"]}
    if ind["kind"] == "auto":
        try:
            r = ind["calc"](c)
        except Exception as e:  # missing or malformed data for this date
            r = None
            out["error"] = str(e)[:120]
        if not r:
            out.update(score=None, status="no data")
            return out
        score = interp(ind["points"], r["value"])
        if "extra_score" in r:
            score = max(score, r["extra_score"])
        if "score_floor" in r:
            score = max(score, r["score_floor"])
        out.update(value=r["value"], date=r["date"], detail=r["detail"], source="auto")
    else:
        rs = c.readings(ind["id"])
        if not rs:
            out.update(score=None, status="no reading")
            return out
        r = rs[-1]
        out.update(date=r["date"], detail=r.get("note", ""), source=r.get("source", ""))
        if "level" in r:
            score = LEVEL_SCORE[r["level"]]
            out["value"] = None
        else:
            score = interp(ind["points"], r["value"])
            out["value"] = r["value"]
            if ind["decel"]:
                ds, ratio = _decel_score(ind, rs)
                if ds is not None:
                    out["decel_ratio"] = ratio
                    score = max(score, ds)
    age = c.age_days(out["date"])
    out["age_days"] = age
    if age > ind["max_age"]:
        out.update(score=None, status="stale", stale_score=round(score, 1))
        return out
    out.update(score=round(score, 1), level=level_of(score), status="ok")
    return out


def fired_tripwires(manual, asof):
    out = []
    for tid, t in manual.get("tripwires", {}).items():
        if t.get("status") != "fired" or tid not in TRIPWIRES:
            continue
        fired = t.get("date", "")
        expires = t.get("expires_days", 120)
        if fired and fired <= asof and (date.fromisoformat(asof) - date.fromisoformat(fired)).days <= expires:
            out.append(tid)
    return out


def _pillar_scores(inds):
    pillars = {}
    for p in PILLARS:
        scores = [i["score"] for i in inds.values() if i["pillar"] == p and i["score"] is not None]
        pillars[p] = {
            "score": round(median(scores), 1) if scores else None,
            "n": len(scores),
            "total": sum(1 for i in inds.values() if i["pillar"] == p),
        }
        pillars[p]["level"] = level_of(pillars[p]["score"])
    return pillars


def _composite(pillars, keys):
    vals = [pillars[k]["score"] for k in keys if pillars[k]["score"] is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def evaluate(c):
    """Full point-in-time evaluation (no persistence rules; see `regime`)."""
    inds = {i["id"]: score_indicator(i, c) for i in INDICATORS}
    pillars = _pillar_scores(inds)
    return {
        "date": c.asof,
        "indicators": inds,
        "pillars": pillars,
        "turn": _composite(pillars, TURN_PILLARS),
        "vuln": _composite(pillars, VULN_PILLARS),
        "tripwires": fired_tripwires(c.manual, c.asof),
    }


def regime(today, recent):
    """Apply the regime rules with persistence.

    today: evaluate() for the date; recent: the previous evaluations (oldest first),
    used for the 5-of-10-sessions persistence rule on red pillars.
    """
    window = (recent + [today])[-10:]
    red_confirmed = []
    for p in TURN_PILLARS:
        days_red = sum(1 for e in window if (e["pillars"][p]["score"] or 0) >= 67)
        need = min(5, len(window))
        if days_red >= need and (today["pillars"][p]["score"] or 0) >= 67:
            red_confirmed.append(p)
    turn = today["turn"] or 0
    vuln = today["vuln"] or 0
    hy = today["indicators"]["hy_oas"].get("score") or 0
    broad_widening = hy >= 34

    if len(red_confirmed) >= 3 and any(p in red_confirmed for p in ("A", "B")) and broad_widening:
        base, why = 4, "three or more fast pillars red, including demand or capex, with broad credit widening"
    elif len(red_confirmed) >= 2:
        base, why = 3, f"two or more fast pillars red ({', '.join(red_confirmed)})"
    elif turn >= 33:
        base = 2
        why = ("high vulnerability and a rising Turn Index" if vuln > 66 else "Turn Index above 33")
    else:
        base, why = 1, "Turn Index below 33"

    n = len(today["tripwires"])
    final = base
    if n:
        final = min(4, max(base + n, 3, 4 if n >= 2 else 0))
        why += f"; {n} tripwire{'s' if n > 1 else ''} fired"
    return {
        "regime": final,
        "name": REGIMES[final],
        "base": base,
        "why": why,
        "red_confirmed": red_confirmed,
        "red_now": [p for p in TURN_PILLARS if (today["pillars"][p]["score"] or 0) >= 67],
        "broad_widening": broad_widening,
    }


def stages(ev, manual):
    """Where the market sits on the typical bust path: done / starting / not yet."""
    i = ev["indicators"]
    s = lambda k: i[k].get("score") or 0
    p = lambda k: ev["pillars"][k]["score"] or 0
    tw = set(ev["tripwires"])
    st = {}
    st["sentiment"] = "done" if p("F") >= 67 or p("E") >= 67 else "starting" if p("F") >= 34 else "not_yet"
    weak = max(s("coreweave_cds"), s("neocloud_equity"), s("oracle_cds"), s("private_credit_equity"))
    st["weak_links"] = "done" if weak >= 67 or tw & {"neocloud_distress", "oracle_junk", "private_credit_gate"} else "starting" if weak >= 34 else "not_yet"
    narrow = max(s("breadth"), s("beat_and_fall"), s("concentration_trend"))
    st["narrow"] = "done" if narrow >= 50 else "starting" if narrow >= 34 else "not_yet"
    capex = max(s("capex_guidance"), s("supplier_tone"), s("nvidia_guide"))
    st["capex_cut"] = "done" if tw & {"capex_cut", "nvidia_guide"} or capex >= 67 else "starting" if capex >= 34 else "not_yet"
    hy = s("hy_oas")
    st["broad_credit"] = "done" if hy >= 67 else "starting" if hy >= 34 else "not_yet"
    dg = manual.get("readings", {}).get("earnings_revisions", [])
    lvl = dg[-1].get("level") if dg else None
    st["downgrades"] = {"red": "done", "amber": "starting"}.get(lvl, "not_yet" if lvl else "unknown")
    return [{"id": k, "name": n, "plain": pl, "state": st[k]} for k, n, pl in STAGES]


def edge_vs_core(ev):
    """Average score of weak-link vs megacap-core indicators."""
    out = {}
    from .indicators import BY_ID
    for side in ("edge", "core"):
        vals = [v["score"] for k, v in ev["indicators"].items() if BY_ID[k].get("core") == side and v["score"] is not None]
        out[side] = round(sum(vals) / len(vals), 1) if vals else None
    return out


def trading_days(c, start, end):
    """Dates with an S&P 500 close between start and end (inclusive)."""
    return [d for d, _ in c.series.get("px:^GSPC", []) if start <= d <= end]


def history(c, days=400):
    """Evaluate every trading day in the window; returns list of (evaluation, regime)."""
    end = c.asof
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    dates = trading_days(c, start, end)
    if not dates or dates[-1] != end:
        dates.append(end)
    evals, out = [], []
    for d in dates:
        ev = evaluate(c.at(d))
        rg = regime(ev, evals[-9:])
        evals.append(ev)
        out.append((ev, rg))
    return out
