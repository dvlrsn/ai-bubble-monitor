"""Free data fetchers. Each returns lists of (date, value) and archives them."""

import json
import os
import time

import requests

from .. import CONFIG_PATH

UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def _sec_ua():
    # SEC asks every client to identify itself with a contact address. It is kept out of the
    # (public) code: set SEC_USER_AGENT, or "sec_user_agent" in data/config.json.
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua and CONFIG_PATH.exists():
        ua = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("sec_user_agent")
    return ua or "AI Bubble Monitor (personal research)"


UA_SEC = _sec_ua()

_session = requests.Session()


def get(url, ua=UA_BROWSER, timeout=30, tries=3, **kw):
    last = None
    for i in range(tries):
        try:
            headers = {"User-Agent": ua} if ua else {}
            r = _session.get(url, headers=headers, timeout=timeout, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                last = RuntimeError(f"HTTP {r.status_code}")
                time.sleep(2 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")
