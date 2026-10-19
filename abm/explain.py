"""Easy mode: turns scores into plain sentences. Every sentence comes from a
reading in the data, so the summary never says more than the numbers do."""

from datetime import date

from .indicators import BY_ID, PILLARS
from .scoring import TURN_PILLARS

LEVELS = {
    1: {"label": "Calm", "color": "green",
        "headline": "The AI boom looks healthy. No serious warning signs right now."},
    2: {"label": "Fragile", "color": "yellow",
        "headline": "Prices are high and some warning lights are on, but nothing important is breaking yet."},
    3: {"label": "Cracking", "color": "orange",
        "headline": "Real stress has started in several places at once. This is when booms can turn."},
    4: {"label": "Unwinding", "color": "red",
        "headline": "The evidence says the boom is turning into a bust: spending, credit and prices are all cracking together."},
}

WHERE_IT_LEADS = {
    1: ("If this changes, the first signs usually appear at the weakest, most indebted AI companies, "
        "and in investors selling shares even after good news."),
    2: ("Markets can stay in this state for months or even years. In the dot-com boom, warning signs like these "
        "showed up about two years before the crash. The monitor moves to 'Cracking' if stress spreads from the "
        "weakest borrowers to the wider market, or if a big tech company cuts its AI spending."),
    3: ("Not every crack becomes a crash: 2026 has already seen several sharp drops that recovered within weeks. "
        "But this is how 2000 began, when trouble at weak borrowers spread and spending was later cut. "
        "The key confirmation would be a spending cut by big tech or a broad jump in borrowing costs."),
    4: ("In past busts, this stage lasted many months. Big AI stocks fell most: in 2000-2002 the Nasdaq lost 78% and "
        "Cisco 88%. Spending cuts and profit warnings usually keep arriving for a while after prices have already fallen."),
}

# What would ease the worry, for indicators that are flashing.
CALMING = {
    "coreweave_cds": "CoreWeave's borrowing costs falling back (debt insurance below about 8% a year)",
    "oracle_cds": "Oracle keeping its credit rating and its debt insurance costs easing",
    "oracle_equity": "Oracle's stock steadying",
    "neocloud_equity": "Shares of AI chip-rental companies recovering",
    "ccc_oas": "Borrowing costs for the riskiest companies coming back down",
    "hy_oas": "Borrowing costs for risky companies coming back down",
    "us10y": "Long-term interest rates falling back below 5%",
    "real10y": "Interest rates after inflation easing",
    "cpi": "Inflation cooling, so the Fed can stop raising rates",
    "fed_hike_odds": "Markets dropping their bets on more rate rises",
    "fed_path": "The Fed pausing its rate rises",
    "oil": "Oil prices falling",
    "sox_drawdown": "Chip stocks getting back toward their highs",
    "semis_relative": "Chip stocks leading the market again",
    "kospi_drawdown": "South Korea's chip-heavy market recovering",
    "lab_revenue_growth": "AI labs' sales growth holding up next quarter",
    "korea_chip_exports": "South Korean chip exports keeping strong growth through October",
    "dram_contract": "Memory chip prices continuing to rise",
    "beat_and_fall": "Nvidia's stock rising after its next results on 18 November",
    "breadth": "More stocks joining the rally, not just the giants",
}

STATE_WORDS = {"done": "has happened", "starting": "is starting", "not_yet": "not yet", "unknown": "not tracked yet"}


def meter_words(score, kind):
    if score is None:
        return "not enough data"
    if kind == "vuln":
        return ("Low: prices aren't stretched" if score < 34 else
                "High: prices are stretched and investors are crowded in, so a fall could be big" if score < 67 else
                "Very high: prices and crowding are at extremes, so a fall could be severe")
    return ("Low: no sign a fall is starting" if score < 33 else
            "Rising: early warning signs, mostly at the edges" if score < 50 else
            "High: warning signs in several places" if score < 67 else
            "Very high: the turn may be under way")


def _hot(ev, pillar, n=2):
    items = [(k, v) for k, v in ev["indicators"].items()
             if v["pillar"] == pillar and v.get("score") is not None and v["score"] >= 34]
    # Headline indicators win near-ties: they carry the story a reader needs.
    items.sort(key=lambda kv: -(kv[1]["score"] + (3 if BY_ID[kv[0]].get("headline") else 0)))
    return items[:n]


def happening(ev, limit=6):
    """Up to six plain sentences, one per flashing area first.

    Areas that show whether a fall is starting (the Turn pillars) come before the
    ones that show how far it could go, so live stress is never crowded out by
    valuation, which can stay extreme for years.
    """
    def order(keys):
        ps = [(p, ev["pillars"][p]["score"]) for p in keys if (ev["pillars"][p]["score"] or 0) >= 34]
        return [p for p, _ in sorted(ps, key=lambda x: -x[1])]

    pillars = order(TURN_PILLARS) + order([p for p in PILLARS if p not in TURN_PILLARS])
    out, used = [], set()
    for rnd in (0, 1):
        for p in pillars:
            hot = [kv for kv in _hot(ev, p, 2) if kv[0] not in used]
            if len(out) >= limit or not hot or (rnd == 1 and hot[0][1]["score"] < 60):
                continue
            k, v = hot[0]
            used.add(k)
            out.append({"pillar": p, "text": BY_ID[k]["easy"][v["level"]], "level": v["level"], "id": k})
    return out


def bright_side(ev):
    """Core indicators that are still green."""
    out = []
    for k in ("capex_growth", "capex_guidance", "tsmc_revenue", "nvidia_guide", "gpu_rent", "dc_construction", "cloud_growth"):
        v = ev["indicators"].get(k, {})
        if v.get("level") == "green":
            out.append(BY_ID[k]["easy"]["green"])
    return out[:3]


def edge_core_sentence(ec):
    e, c = ec.get("edge"), ec.get("core")
    if e is None or c is None:
        return None
    if e - c >= 15:
        return ("The trouble is at the edges: heavily indebted AI companies (CoreWeave, Oracle), private lenders and "
                "South Korean chip stocks are under strain, while the giants at the core (Nvidia, Microsoft, Alphabet) "
                "still look solid. In past booms the edges cracked first.")
    if c - e >= 15:
        return "Unusually, the giants at the core of the AI trade look weaker than the smaller, riskier companies."
    if e >= 50 and c >= 50:
        return "Stress has reached both the weak edges and the core giants of the AI trade."
    return "The weak edges and the core giants of the AI trade look about equally healthy."


def changes(today, before, label):
    """Plain list of what moved between two evaluations."""
    out = []
    if before is None:
        return out
    t_r, b_r = today[1], before[1]
    if t_r["regime"] != b_r["regime"]:
        out.append({"kind": "regime", "text": f"Risk level changed from {LEVELS[b_r['regime']]['label']} to {LEVELS[t_r['regime']]['label']} {label}."})
    for p, info in PILLARS.items():
        a, b = today[0]["pillars"][p]["score"], before[0]["pillars"][p]["score"]
        if a is not None and b is not None and abs(a - b) >= 8:
            out.append({"kind": "pillar", "text": f"'{info['plain']}' {'worsened' if a > b else 'improved'} ({b:.0f} → {a:.0f}) {label}."})
    for k, v in today[0]["indicators"].items():
        w = before[0]["indicators"].get(k, {})
        if v.get("level") and w.get("level") and v["level"] != w["level"]:
            worse = ["green", "amber", "red"].index(v["level"]) > ["green", "amber", "red"].index(w["level"])
            out.append({"kind": "indicator", "id": k,
                        "text": f"{BY_ID[k]['plain']}: {w['level']} → {v['level']} ({'worse' if worse else 'better'}) {label}."})
    for t in set(today[0]["tripwires"]) - set(before[0]["tripwires"]):
        out.append({"kind": "tripwire", "text": f"Tripwire fired: {t}."})
    return out


def watch_next(manual, asof, days=45):
    out = []
    today = date.fromisoformat(asof)
    for c in sorted(manual.get("catalysts", []), key=lambda c: c["date"]):
        d = date.fromisoformat(c["date"])
        delta = (d - today).days
        if 0 <= delta <= days:
            out.append({**c, "in_days": delta})
    return out


def next_stage(stg):
    for s in stg:
        if s["state"] in ("not_yet", "starting"):
            return s
    return None


def summary(ev, rg, stg, ec, hist, manual):
    lvl = LEVELS[rg["regime"]]
    nxt = next_stage(stg)
    hot_ids = [k for k, v in ev["indicators"].items() if v.get("score") is not None and v["score"] >= 50]
    hot_ids.sort(key=lambda k: -ev["indicators"][k]["score"])
    calming = [CALMING[k] for k in hot_ids if k in CALMING][:4]
    yesterday = hist[-2] if len(hist) >= 2 else None
    week = hist[-6] if len(hist) >= 6 else None
    chg_day = changes(hist[-1], yesterday, "since the previous trading day")
    chg_week = changes(hist[-1], week, "over the past week")
    return {
        "level": rg["regime"],
        "label": lvl["label"],
        "color": lvl["color"],
        "headline": lvl["headline"],
        "meters": [
            {"id": "vuln", "name": "How far could prices fall?", "score": ev["vuln"], "words": meter_words(ev["vuln"], "vuln")},
            {"id": "turn", "name": "Has a fall started?", "score": ev["turn"], "words": meter_words(ev["turn"], "turn")},
        ],
        "happening": happening(ev),
        "bright_side": bright_side(ev),
        "edge_core": edge_core_sentence(ec),
        "stages": [{**s, "words": STATE_WORDS[s["state"]]} for s in stg],
        "next_stage": nxt,
        "where_it_leads": WHERE_IT_LEADS[rg["regime"]],
        "calming": calming,
        "watch_next": watch_next(manual, ev["date"]),
        "changed": chg_day or chg_week,
        "changed_window": "since the previous trading day" if chg_day else "over the past week",
        "turn_red_pillars": [PILLARS[p]["plain"] for p in rg["red_now"] if p in TURN_PILLARS],
    }
