"""Headline scan for possible tripwires (Google News RSS).

This only proposes candidates. A tripwire fires when a person confirms it with
two credible sources (see `monitor.py tripwire`), as the brief requires.
"""

import html
import re
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from . import get

# tripwire id -> search queries (Google News syntax). Kept narrow on purpose.
QUERIES = {
    "capex_cut": ['(Microsoft OR Alphabet OR Amazon OR Meta) capex (cut OR lower OR reduce OR "digestion" OR pause)'],
    "nvidia_guide": ['Nvidia guidance (below OR cut OR lower OR "sequential decline")'],
    "dc_cancellations": ['data center (lease cancel OR cancels leases OR abandons OR "excess capacity") (Microsoft OR Meta OR Amazon OR Google)'],
    "memory_price_fall": ['(DRAM OR HBM) contract prices (fall OR decline OR drop) quarter'],
    "lab_down_round": ['(OpenAI OR Anthropic) (IPO delay OR "down round" OR "below IPO price" OR postpones IPO)'],
    "openai_defers": ['OpenAI (defers OR renegotiates OR scales back) compute (Oracle OR CoreWeave OR Microsoft OR AMD OR Broadcom)'],
    "neocloud_distress": ['CoreWeave (covenant OR "missed payment" OR "distressed exchange" OR restructuring OR rescue OR default)',
                          '(Nebius OR IREN OR Lambda OR Crusoe) (covenant OR default OR restructuring)'],
    "oracle_junk": ['Oracle downgrade (junk OR "high yield" OR "BB+")', 'Oracle (cuts OR delays OR defers) data center'],
    "private_credit_gate": ['(private credit OR BDC) (redemption gate OR limits withdrawals OR caps redemptions)', 'data center financing (fails OR pulled OR collapses)'],
    "guarantee_called": ['(Nvidia OR Broadcom) guarantee (called OR triggered OR backstop payment)'],
    "efficiency_shock": ['Nvidia shares (plunge OR tumble) cheaper AI model'],
    "fed_hawkish": ['Fed hike hawkish (10-year OR Treasury yield) 5.25'],
    "geopolitics": ['(Taiwan blockade OR "export controls" chips OR "grid emergency" data centers)'],
    "depreciation": ['(Microsoft OR Alphabet OR Amazon OR Meta) (server useful life shorten OR impairment AI)'],
    "going_concern": ['AI (data center OR infrastructure) "going concern"'],
    "ai_incident": ['AI (agent OR model OR system) (killed OR deaths OR casualties OR "critical infrastructure") incident',
                    'AI incident (emergency rules OR moratorium OR "deployment pause" OR ban OR liability)'],
    # Watch topics (never fire).
    "insurer_exclusions": ['insurers (exclude OR exclusion OR withdraw OR "pull back") AI (liability OR coverage OR risks)'],
    "agent_pauses": ['(pauses OR halts OR suspends OR "rolls back") "AI agents" (after OR incident OR error OR outage)'],
    "ai_laws": ['AI (law OR act OR ruling) (liability OR licensing OR ban OR enforcement OR fine) (signed OR passed OR court OR regulator)'],
}


def search(query, days=3):
    url = f"https://news.google.com/rss/search?q={quote_plus(query + f' when:{days}d')}&hl=en-US&gl=US&ceid=US:en"
    xml = get(url).text
    items = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
        src = re.search(r"<source[^>]*>(.*?)</source>", item, re.S)
        if not title:
            continue
        try:
            when = parsedate_to_datetime(pub.group(1)).strftime("%Y-%m-%d") if pub else ""
        except (TypeError, ValueError):
            when = ""
        items.append({
            "title": html.unescape(title.group(1)).strip(),
            "link": html.unescape(link.group(1)).strip() if link else "",
            "date": when,
            "source": html.unescape(src.group(1)).strip() if src else "",
        })
    return items


def scan(days=3, per_query=5):
    """Returns {tripwire_id: [headline, ...]} for tripwires with any hits."""
    out = {}
    for tid, queries in QUERIES.items():
        hits = []
        for q in queries:
            try:
                hits.extend(search(q, days)[:per_query])
            except Exception:
                continue
        seen, uniq = set(), []
        for h in hits:
            if h["title"] not in seen:
                seen.add(h["title"])
                uniq.append(h)
        if uniq:
            out[tid] = uniq[:per_query]
    return out
