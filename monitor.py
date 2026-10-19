"""AI Bubble Monitor command line.

  python monitor.py run              fetch data, score, write out/dashboard.html, send alerts
  python monitor.py run --no-fetch   rescore from the archive only (after editing readings)
  python monitor.py status           plain-language summary in the terminal
  python monitor.py list             hand-entered indicators and how old each reading is
  python monitor.py add ID VALUE     add a reading (a number, or green/amber/red)
  python monitor.py tripwire ...     list, fire or clear event tripwires
  python monitor.py backtest         how the price-and-credit layer behaved in past busts
  python monitor.py review           Claude checks the headline scan and suggests tripwires to fire
"""

import argparse
import json
import sys
import webbrowser
from datetime import date

from abm import MANUAL_PATH, store
from abm.ctx import Ctx
from abm.indicators import BY_ID, INDICATORS, PILLARS
from abm.tripwires import TRIPWIRES


def load_manual():
    if not MANUAL_PATH.exists():
        sys.exit(f"{MANUAL_PATH} is missing. Run: python scripts/seed_manual.py")
    return json.loads(MANUAL_PATH.read_text(encoding="utf-8"))


def save_manual(m):
    MANUAL_PATH.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def analyse(asof=None):
    from abm import explain, scoring

    manual = load_manual()
    series = store.load_all()
    if asof is None:
        spx = series.get("px:^GSPC")
        asof = max(date.today().isoformat() if not spx else spx[-1][0], "0000")
    c = Ctx(series, manual, asof)
    hist = scoring.history(c, 400)
    ev, rg = hist[-1]
    stg = scoring.stages(ev, manual)
    ec = scoring.edge_vs_core(ev)
    easy = explain.summary(ev, rg, stg, ec, hist, manual)
    return manual, ev, rg, ec, hist, easy


def cmd_run(a):
    from abm import OUT_DIR, alerts, collect, report

    if not a.no_fetch:
        collect.collect(with_breadth=not a.no_breadth, with_news=not a.no_news)
    manual, ev, rg, ec, hist, easy = analyse(a.date)
    news_path = OUT_DIR / "news_candidates.json"
    news = json.loads(news_path.read_text(encoding="utf-8")) if news_path.exists() else {}
    data = report.payload(ev, rg, easy, ec, hist, manual, news, store.fetch_status())
    path = report.write(data)

    snap = {"regime": rg["regime"], "turn": ev["turn"], "vuln": ev["vuln"], "tripwires": ev["tripwires"],
            "tripwire_plain": {k: v[1] for k, v in TRIPWIRES.items()},
            "pillars": {p: v["score"] for p, v in ev["pillars"].items()}}
    snaps = store.load_snapshots()
    # Compare with the last run (same day included), so each change alerts once.
    prev = next((s for d, s in reversed(snaps) if d <= ev["date"]), None)
    store.save_snapshot(ev["date"], snap)
    if not a.date:
        alerts.send(alerts.decide(prev, snap))

    print_status(ev, rg, easy)
    print(f"\nDashboard: {path}")
    if a.open:
        webbrowser.open(path.as_uri())


def print_status(ev, rg, easy):
    print(f"\n=== {easy['label'].upper()} (level {easy['level']} of 4) · {ev['date']} ===")
    print(easy["headline"])
    for m in easy["meters"]:
        print(f"  {m['name']:28} {m['score'] if m['score'] is not None else '–':>5}  {m['words']}")
    print("\nWhat's happening:")
    for h in easy["happening"]:
        print(f"  [{h['level']:5}] {h['text']}")
    if easy["edge_core"]:
        print(f"\n{easy['edge_core']}")
    print("\nThe usual path of a bust:")
    for i, s in enumerate(easy["stages"], 1):
        print(f"  {i}. {s['name']:45} {s['words']}")
    if easy["changed"]:
        print(f"\nWhat changed {easy['changed_window']}:")
        for x in easy["changed"][:6]:
            print(f"  - {x['text']}")
    if easy["watch_next"]:
        print("\nDates to watch:")
        for c in easy["watch_next"][:5]:
            print(f"  {c['date']}  {c['event']}")
    print(f"\nExpert: regime {rg['regime']} {rg['name']} ({rg['why']}); Turn {ev['turn']}, Vulnerability {ev['vuln']}")
    print("  " + "  ".join(f"{p}:{v['score'] if v['score'] is not None else '–'}" for p, v in ev["pillars"].items()))


def cmd_status(a):
    _, ev, rg, _, _, easy = analyse(a.date)
    print_status(ev, rg, easy)


def cmd_list(a):
    m = load_manual()
    today = a.date or date.today().isoformat()
    print(f"{'indicator':22} {'pillar':6} {'last reading':>16} {'age':>5} {'limit':>5}  name")
    for i in INDICATORS:
        if i["kind"] != "manual":
            continue
        rs = sorted(m["readings"].get(i["id"], []), key=lambda r: r["date"])
        if rs:
            r = rs[-1]
            age = (date.fromisoformat(today) - date.fromisoformat(r["date"])).days
            val = r.get("level") or i["fmt"].format(r["value"])
            flag = "  STALE" if age > i["max_age"] else ""
            print(f"{i['id']:22} {i['pillar']:6} {val + ' @ ' + r['date'][5:]:>16} {age:>5} {i['max_age']:>5}  {i['name']}{flag}")
        else:
            print(f"{i['id']:22} {i['pillar']:6} {'none':>16} {'':>5} {i['max_age']:>5}  {i['name']}  MISSING")
    print("\nAlso read by the bust-path tracker: earnings_revisions (green/amber/red; FactSet Earnings Insight).")


def cmd_add(a):
    m = load_manual()
    if a.id not in BY_ID and a.id != "earnings_revisions":
        sys.exit(f"Unknown indicator '{a.id}'. See: python monitor.py list")
    ind = BY_ID.get(a.id)
    if ind and ind["kind"] == "auto":
        sys.exit(f"'{a.id}' is fetched automatically.")
    entry = {"date": a.date or date.today().isoformat(), "note": a.note or "", "source": a.source or ""}
    if a.value.lower() in ("green", "amber", "red"):
        entry["level"] = a.value.lower()
    else:
        try:
            entry["value"] = float(a.value)
        except ValueError:
            sys.exit("VALUE must be a number or green/amber/red")
    rs = [r for r in m["readings"].setdefault(a.id, []) if r["date"] != entry["date"]]
    rs.append(entry)
    m["readings"][a.id] = sorted(rs, key=lambda r: r["date"])
    save_manual(m)
    print(f"Saved {a.id} = {a.value} on {entry['date']}. Run `python monitor.py run --no-fetch` to rescore.")


def cmd_tripwire(a):
    m = load_manual()
    tws = m.setdefault("tripwires", {})
    if a.action == "list":
        for tid, (desc, _) in TRIPWIRES.items():
            t = tws.get(tid, {})
            print(f"{t.get('status', 'not_fired'):10} {tid:20} {desc}")
        return
    if a.id not in TRIPWIRES:
        sys.exit(f"Unknown tripwire '{a.id}'. See: python monitor.py tripwire list")
    if a.action == "fire":
        if len(a.source or []) < 2:
            sys.exit("A tripwire needs two credible sources: --source URL --source URL")
        tws[a.id] = {"status": "fired", "date": a.date or date.today().isoformat(),
                     "sources": a.source, "note": a.note or "", "expires_days": a.expires}
        print(f"Fired {a.id}. It counts for {a.expires} days.")
    elif a.action == "clear":
        tws[a.id] = {"status": "not_fired", "cleared": a.date or date.today().isoformat(), "note": a.note or ""}
        print(f"Cleared {a.id}.")
    save_manual(m)


def cmd_review(a):
    import subprocess

    from abm import ROOT, review

    m = load_manual()
    res, path = review.run(m)
    webbrowser.open(path.as_uri())
    print(f"\n{res['overall']}\n")
    for v in res["verdicts"]:
        if v["verdict"] != "noise":
            print(f"[{v['verdict'].upper():5}] {TRIPWIRES[v['tripwire']][1]}\n        {v['summary']}")
    fires = [v for v in res["verdicts"] if v["verdict"] == "fire" and len(v["sources"]) >= 2]
    if not fires:
        print("\nNothing to fire. The full review is open in your browser.")
        return
    fired = []
    for v in fires:
        print(f"\nClaude suggests firing: {TRIPWIRES[v['tripwire']][1]}\n  {v['why']}")
        for s in v["sources"]:
            print(f"  - {s['outlet']}: {s['url']}")
        if input("Fire this tripwire? It raises the risk level. [y/N] ").strip().lower() == "y":
            m.setdefault("tripwires", {})[v["tripwire"]] = {
                "status": "fired", "date": date.today().isoformat(), "sources": [s["url"] for s in v["sources"]],
                "note": f"AI review: {v['summary']}", "expires_days": 120}
            fired.append(v["tripwire"])
    if not fired:
        print("Nothing fired.")
        return
    save_manual(m)
    print(f"Fired: {', '.join(fired)}. Uploading so the daily check uses it, and rerunning it now...")
    git = lambda *args: subprocess.run(["git", *args], cwd=ROOT, check=True)
    try:
        git("add", "data/manual.json")
        git("commit", "-q", "-m", f"Fire tripwire {', '.join(fired)} (AI review, confirmed by hand)")
        git("push", "-q")
        subprocess.run(["gh", "workflow", "run", "daily.yml"], cwd=ROOT, check=True)
        print("Done. The phone alert follows when the run finishes (a few minutes).")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Saved here, but uploading failed ({e}). Ask Claude to push data/manual.json.")


def cmd_backtest(a):
    from abm import backtest
    backtest.run()


def main():
    p = argparse.ArgumentParser(description="AI Bubble Monitor")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch, score, write the dashboard")
    r.add_argument("--no-fetch", action="store_true", help="skip fetching; rescore the archive")
    r.add_argument("--no-breadth", action="store_true", help="skip the 500-stock breadth fetch")
    r.add_argument("--no-news", action="store_true", help="skip the headline scan")
    r.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    r.add_argument("--date", help="score as of an earlier date (YYYY-MM-DD); no alerts")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("status", help="print the plain-language summary")
    s.add_argument("--date")
    s.set_defaults(fn=cmd_status)
    li = sub.add_parser("list", help="show hand-entered indicators")
    li.add_argument("--date")
    li.set_defaults(fn=cmd_list)
    ad = sub.add_parser("add", help="add a hand-entered reading")
    ad.add_argument("id")
    ad.add_argument("value", help="a number, or green/amber/red")
    ad.add_argument("--date", help="date of the data (default today)")
    ad.add_argument("--note")
    ad.add_argument("--source", help="where the number comes from (URL)")
    ad.set_defaults(fn=cmd_add)
    tw = sub.add_parser("tripwire", help="list, fire or clear tripwires")
    tw.add_argument("action", choices=["list", "fire", "clear"])
    tw.add_argument("id", nargs="?")
    tw.add_argument("--source", action="append", help="credible source URL (twice to fire)")
    tw.add_argument("--note")
    tw.add_argument("--date")
    tw.add_argument("--expires", type=int, default=120, help="days the tripwire keeps counting")
    tw.set_defaults(fn=cmd_tripwire)
    bt = sub.add_parser("backtest", help="price-and-credit layer in past busts")
    bt.set_defaults(fn=cmd_backtest)
    rv = sub.add_parser("review", help="Claude checks the headline scan and suggests tripwires")
    rv.set_defaults(fn=cmd_review)
    a = p.parse_args()
    if a.cmd == "tripwire" and a.action != "list" and not a.id:
        p.error("tripwire fire/clear needs an id")
    a.fn(a)


if __name__ == "__main__":
    # Piped output on Windows defaults to cp1252, which can't print arrows and dots.
    sys.stdout.reconfigure(encoding="utf-8")
    main()
