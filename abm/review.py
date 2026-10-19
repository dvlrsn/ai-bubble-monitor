"""AI review of the headline scan: Claude (through the local Claude Code CLI) reads each
candidate, checks it against the web, and says fire / watch / noise for each tripwire.

It only suggests. Nothing fires unless a person says yes, and a fire still needs two
credible sources, exactly as with `monitor.py tripwire fire`.
"""

import glob
import html
import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

from . import OUT_DIR
from .sources import news
from .tripwires import TRIPWIRES

SCHEMA = {
    "type": "object",
    "required": ["overall", "verdicts"],
    "properties": {
        "overall": {"type": "string"},
        "verdicts": {"type": "array", "items": {
            "type": "object",
            "required": ["tripwire", "verdict", "summary", "why", "sources"],
            "properties": {
                "tripwire": {"type": "string", "enum": list(TRIPWIRES)},
                "verdict": {"type": "string", "enum": ["fire", "watch", "noise"]},
                "summary": {"type": "string"},
                "why": {"type": "string"},
                "sources": {"type": "array", "items": {
                    "type": "object", "required": ["outlet", "url"],
                    "properties": {"outlet": {"type": "string"}, "title": {"type": "string"},
                                   "url": {"type": "string"}, "date": {"type": "string"}}}},
            }}},
    },
}

PROMPT = """You review warning signs ("tripwires") for a personal AI-stock-bubble risk monitor.
The owner is not financially savvy. This is risk monitoring, not investment advice: never
tell them to buy or sell.

Today is {today}. A keyword search of Google News found the headlines below. Most are noise:
the search cannot tell "X cut spending" from "will X cut spending? No."

For each tripwire that has headlines, decide:
- "fire": the event in the definition has actually happened (not predicted, not feared,
  not "risk rising"), within the last 30 days, AND you found two independent credible
  outlets reporting it (Reuters, Bloomberg, FT, WSJ, CNBC, AP, the company itself or a
  regulator count; blogs, SEO stock sites and crypto sites do not). Also check the spirit:
  the plain meaning in brackets must be true, not just the letter.
- "watch": something real and related happened but falls short of the definition, or a
  dated event coming up could trigger it.
- "noise": nothing real behind the headlines.
Use web search to confirm anything that is not clearly noise. Be strict: a false alarm
costs the owner more than a day's delay. You are made by Anthropic, so for anything about
Anthropic be especially careful to judge it exactly as you would any other company.

Write "summary" (one or two short plain sentences: what really happened) and "why"
(why that verdict, plainly) for a reader with no finance background. Put the sources you
relied on in "sources" (at least two for "fire"). "overall" is two or three plain sentences
on what today's news means for the risk picture. Return only tripwires that had headlines.

Already fired (still counting): {fired}

Tripwires and headlines:
{items}
"""


def find_claude():
    exe = shutil.which("claude")
    if exe:
        return exe
    home = Path.home() / ".local" / "bin" / "claude.exe"
    if home.exists():
        return str(home)
    # The Claude desktop app keeps its own copy; take the newest.
    found = glob.glob(os.path.expandvars(r"%APPDATA%\Claude\claude-code\*\*\claude.exe"))
    if found:
        return max(found, key=os.path.getmtime)
    raise SystemExit("Claude Code was not found. Install it, or open the Claude desktop app once.")


def build_prompt(hits, manual):
    fired = [k for k, v in manual.get("tripwires", {}).items() if v.get("status") == "fired"]
    lines = []
    for tid, heads in hits.items():
        desc, plain = TRIPWIRES[tid]
        lines.append(f"\n## {tid}: {desc} [{plain}]")
        for h in heads:
            lines.append(f"- {h['date']} | {h['source']} | {h['title']} | {h['link']}")
    return PROMPT.format(today=date.today().isoformat(), fired=", ".join(fired) or "none",
                         items="\n".join(lines))


def ask_claude(prompt, log=print):
    cmd = [find_claude(), "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
           "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch", "WebFetch",
           "--strict-mcp-config", "--no-session-persistence"]
    log("Claude is reading the headlines and checking the web (usually 2-5 minutes)...")
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=1200)
    if "Not logged in" in r.stdout:
        raise SystemExit("Claude Code isn't logged in on this PC. Open a terminal, run `claude auth login` "
                         "once and sign in with your Claude account, then try again.")
    if r.returncode != 0:
        raise SystemExit(f"Claude Code failed: {(r.stderr or r.stdout)[-800:]}")
    out = json.loads(r.stdout)
    if out.get("is_error"):
        raise SystemExit(f"Claude Code failed: {out.get('result')}")
    res = out.get("structured_output")
    if res is None:  # older CLIs return the JSON as text
        text = out.get("result", "")
        res = json.loads(text[text.find("{"):text.rfind("}") + 1])
    return res


def write_html(res, hits):
    order = {"fire": 0, "watch": 1, "noise": 2}
    label = {"fire": "Should fire", "watch": "Worth watching", "noise": "Noise"}
    cards = []
    for v in sorted(res["verdicts"], key=lambda v: order[v["verdict"]]):
        src = "".join(
            f'<li><a href="{html.escape(s["url"])}">{html.escape(s.get("title") or s["url"])}</a>'
            f' <span class="m">{html.escape(s["outlet"])} {html.escape(s.get("date", ""))}</span></li>'
            for s in v["sources"])
        cards.append(f"""<article class="{v['verdict']}"><div class="tag">{label[v['verdict']]}</div>
<h2>{html.escape(TRIPWIRES[v['tripwire']][1])}</h2>
<p>{html.escape(v['summary'])}</p><p class="m">{html.escape(v['why'])}</p>
{'<ul>' + src + '</ul>' if src else ''}</article>""")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI headline review</title>
<style>
:root{{--bg:#f6f5f1;--card:#fff;--ink:#1d1d1b;--mute:#66645e;--line:#e2e0d8;--red:#c0392b;--amber:#b7791f;--grey:#8a877f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151513;--card:#1f1f1c;--ink:#ecebe6;--mute:#a3a198;--line:#33322e;--red:#e5675a;--amber:#e0a84a;--grey:#77756e}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:1.6rem;margin:0 0 4px}} h2{{font-size:1.05rem;margin:4px 0 6px}}
.m{{color:var(--mute);font-size:.92rem}} a{{color:inherit}}
.overall{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:16px 0 24px}}
article{{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--grey);border-radius:10px;padding:12px 16px;margin:0 0 12px}}
article.fire{{border-left-color:var(--red)}} article.watch{{border-left-color:var(--amber)}}
article.noise{{opacity:.75}} .tag{{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--mute)}}
.fire .tag{{color:var(--red)}} .watch .tag{{color:var(--amber)}} ul{{margin:6px 0 0;padding-left:18px}} li{{margin:2px 0}}
</style></head><body><main>
<h1>AI headline review</h1><div class="m">{date.today().isoformat()} · {sum(len(h) for h in hits.values())} headlines checked by Claude. Suggestions only: nothing fires unless you say yes.</div>
<div class="overall">{html.escape(res['overall'])}</div>
{''.join(cards)}
</main></body></html>"""
    path = OUT_DIR / "ai_review.html"
    path.write_text(page, encoding="utf-8")
    return path


def run(manual, log=print):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log("Searching today's headlines...")
    hits = news.scan()
    if not hits:
        raise SystemExit("The headline scan found nothing (or Google News could not be reached).")
    res = ask_claude(build_prompt(hits, manual), log)
    (OUT_DIR / "ai_review.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res, write_html(res, hits)
