"""Push alerts through ntfy (https://ntfy.sh), only on regime changes and new tripwires.

Configure in data/config.json: {"ntfy_topic": "your-secret-topic", "ntfy_server": "https://ntfy.sh"}
or with the NTFY_TOPIC environment variable.
"""

import json
import os

import requests

from . import CONFIG_PATH
from .explain import LEVELS


def config():
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if os.environ.get("NTFY_TOPIC"):
        cfg["ntfy_topic"] = os.environ["NTFY_TOPIC"]
    cfg.setdefault("ntfy_server", "https://ntfy.sh")
    return cfg


def decide(prev, now):
    """prev/now: stored snapshot dicts. Returns a list of (title, message, priority)."""
    out = []
    if prev is None:
        return out
    if now["regime"] != prev["regime"]:
        up = now["regime"] > prev["regime"]
        lvl = LEVELS[now["regime"]]
        out.append((
            f"AI risk level {'up' if up else 'down'}: {lvl['label']}",
            f"{LEVELS[prev['regime']]['label']} → {lvl['label']}. {lvl['headline']}",
            "high" if up and now["regime"] >= 3 else "default",
        ))
    for t in sorted(set(now["tripwires"]) - set(prev["tripwires"])):
        out.append((f"Tripwire fired: {t}", now["tripwire_plain"].get(t, t), "high"))
    return out


def send(alerts, log=print):
    cfg = config()
    topic = cfg.get("ntfy_topic")
    for title, msg, prio in alerts:
        if not topic:
            log(f"  (alert not sent, no ntfy topic set) {title}: {msg}")
            continue
        try:
            # JSON publishing keeps non-ASCII titles intact (headers are Latin-1 only).
            requests.post(cfg["ntfy_server"].rstrip("/"), json={
                "topic": topic, "title": title, "message": msg,
                "priority": 4 if prio == "high" else 3, "tags": ["chart_with_downwards_trend"],
            }, timeout=20).raise_for_status()
            log(f"  alert sent: {title}")
        except requests.RequestException as e:
            log(f"  ! alert failed: {e}")
