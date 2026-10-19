"""Builds the dashboard payload and writes out/dashboard.html."""

import json
from datetime import datetime
from pathlib import Path

from . import OUT_DIR
from .indicators import BY_ID, INDICATORS, PILLARS
from .tripwires import TRIPWIRES

TEMPLATE = Path(__file__).with_name("template.html")


def fmt_value(ind, r):
    v = r.get("value")
    if v is None:
        return None
    s = ind["fmt"].format(v)
    unit = ind["unit"]
    if not unit:
        return s
    if unit == "$":
        return "$" + s
    return s + unit if unit.startswith("%") else f"{s} {unit}"


def health(ev, fetch_status):
    out = []
    for s, (when, status) in sorted(fetch_status.items()):
        if not status.startswith("ok"):
            out.append({"kind": "failed", "name": s, "text": f"last fetch failed ({status[:140]})"})
    for i in INDICATORS:
        r = ev["indicators"][i["id"]]
        if r.get("status") == "stale":
            out.append({"kind": "stale", "name": i["name"],
                        "text": f"last reading {r['date']} is {r['age_days']} days old (limit {i['max_age']}); excluded from scores"})
        elif r.get("status") in ("no reading", "no data"):
            out.append({"kind": "stale", "name": i["name"], "text": r["status"]})
    return out


def payload(ev, rg, easy, ec, hist, manual, news, fetch_status):
    pillars = []
    for p, meta in PILLARS.items():
        inds = []
        for i in INDICATORS:
            if i["pillar"] != p:
                continue
            r = ev["indicators"][i["id"]]
            inds.append({
                "id": i["id"], "name": i["name"], "plain": i["plain"], "kind": i["kind"],
                "score": r.get("score"), "level": r.get("level"), "status": r.get("status"),
                "stale_score": r.get("stale_score"), "value_fmt": fmt_value(i, r),
                "date": r.get("date"), "detail": r.get("detail"), "source": r.get("source"),
            })
        inds.sort(key=lambda x: -(x["score"] if x["score"] is not None else -1))
        pillars.append({"id": p, **meta, **ev["pillars"][p], "indicators": inds})
    # Date by which three quarters of hand-entered indicators have a reading;
    # before it the history mostly reflects automated data.
    firsts = sorted(min(r["date"] for r in rs) for rs in manual.get("readings", {}).values() if rs)
    starts = [firsts[int(0.75 * (len(firsts) - 1))]] if firsts else []
    tw = []
    for tid, (desc, plain) in TRIPWIRES.items():
        t = manual.get("tripwires", {}).get(tid, {})
        status = t.get("status", "not_fired")
        if status != "fired" and tid in (news or {}):
            status = "not_fired"
        tw.append({"id": tid, "desc": desc, "plain": plain, "status": status, "date": t.get("date"), "sources": t.get("sources", [])})
    tw.sort(key=lambda t: {"fired": 0, "candidate": 1}.get(t["status"], 2))
    cats = [c for c in sorted(manual.get("catalysts", []), key=lambda c: c["date"]) if c["date"] >= ev["date"]]
    for c in cats:
        c["in_days"] = (datetime.fromisoformat(c["date"]) - datetime.fromisoformat(ev["date"])).days
    return {
        "asof": ev["date"],
        "generated": datetime.now().strftime("%d %b %Y %H:%M"),
        "easy": easy,
        "regime": rg,
        "turn": ev["turn"],
        "vuln": ev["vuln"],
        "edge_core": ec,
        "pillars": pillars,
        "history": [{"d": e["date"], "t": e["turn"], "v": e["vuln"], "r": r["regime"]} for e, r in hist[-260:]],
        "manual_start": min(starts) if starts else ev["date"],
        "tripwires": tw,
        "news": news or {},
        "health": health(ev, fetch_status),
        "catalysts": cats,
    }


def render(data, standalone=True):
    body = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if not standalone:
        return body  # the Artifact host adds its own document skeleton
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + body.replace("<div class=\"top\">", "</head>\n<body>\n<div class=\"top\">", 1)
            + "\n</body>\n</html>\n")


def write(data):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dashboard.html").write_text(render(data, True), encoding="utf-8")
    (OUT_DIR / "artifact.html").write_text(render(data, False), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return OUT_DIR / "dashboard.html"
