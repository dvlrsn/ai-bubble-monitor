"""One-off: seed data/manual.json with the research brief's 19 Oct 2026 readings.

Refuses to overwrite an existing file unless --force is given.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abm import MANUAL_PATH  # noqa: E402
from abm.tripwires import TRIPWIRES  # noqa: E402

B = "Research brief, 19 Oct 2026 (news and secondary trackers; verify against the primary source)"


def r(date, value=None, level=None, note=""):
    d = {"date": date, "note": note, "source": B}
    if value is not None:
        d["value"] = value
    if level:
        d["level"] = level
    return d


READINGS = {
    "lab_revenue_growth": [r("2026-07-15", 147, note="Anthropic Q2 revenue growth q/q"),
                           r("2026-10-14", 45, note="Anthropic Q3 revenue $16.8B, +45% q/q; OpenAI ~$50B net run-rate")],
    "revenue_quality": [r("2026-10-08", level="amber", note="OpenAI run-rate cut from ~$70B to ~$50B on a net basis; AI stocks fell on the news")],
    "cloud_growth": [r("2026-04-30", level="green", note="Q1 2026: Azure +40%, Google Cloud +63% ($20B), AWS +28%. Q2 figures not in the brief; update after Q3 results (27-30 Oct)")],
    "gpu_rent": [r("2026-10-15", 1.3, note="Ornn H100 $3.13/GPU-hour vs a 3-month range of $2.46-3.17; H200 $6.51, B200 $7.92")],
    "token_growth": [r("2026-05-20", level="green", note="Google 3.2 quadrillion tokens a month in May, about 7x y/y")],
    "lab_unit_economics": [r("2026-10-14", 1.70, note="Anthropic $1.70 revenue per $1 of compute in Q3; adjusted operating margin 11%")],
    "startup_failures": [r("2026-10-13", level="amber", note="Character.AI filed for Chapter 11 on 13 Oct")],
    "capex_guidance": [r("2026-07-30", level="green", note="2026 guidance ~$732.5B (MSFT, GOOGL, AMZN, META) vs ~$410B in 2025; 2027 consensus ~$934.5B; every 2026 revision upward")],
    "nvidia_guide": [r("2026-08-26", 12.2, note="Q3 FY27 guide $108B +/-2% vs Q2 revenue $96.2B; gross margin to bottom at 71-72%")],
    "tsmc_revenue": [r("2026-10-10", 54.6, note="September NT$511.9B, +54.6% y/y; Q4 guide $52.3-54.3B")],
    "korea_chip_exports": [r("2026-10-01", 263, note="September chip exports $60.3B, +263% y/y"),
                           r("2026-10-11", 46.7, note="1-10 October preliminary, +46.7% y/y. Ten-day data swing with working days (Chuseok); compare per working day")],
    "dram_contract": [r("2026-01-05", 92.5, note="Q1 contract +90-95% q/q"),
                      r("2026-03-31", 60.5, note="Q2 contract +58-63% q/q"),
                      r("2026-06-30", 15.5, note="Q3 forecast +13-18% q/q"),
                      r("2026-09-30", 12.5, note="Q4 forecast +10-15% q/q (TrendForce); spot trading weak; CXMT progress hit Korean memory stocks 13 Oct")],
    "dc_construction": [r("2026-10-01", 73, note="August record $84.95B annual rate, +73% y/y (Census C30)")],
    "ai_gdp_share": [r("2026-06-30", 0.8, note="Epoch AI: AI infrastructure ~0.8% of GDP in Q1 2026 (all computing ~1.4-1.5%)")],
    "cancellations": [r("2026-10-15", level="amber", note="Meta floated selling excess capacity; local opposition had blocked ~$130B of projects by July")],
    "supplier_tone": [r("2026-09-11", level="green", note="Broadcom guides AI chip sales from ~$58B (FY26) to $230B (FY28) but says capital may become the constraint")],
    "coreweave_cds": [r("2026-10-16", 1100, note="CDS above 1,000bp (record ~1,195bp); Oct 2031 bond briefly yielded over 16%")],
    "oracle_cds": [r("2026-10-16", 292, note="Record 288-295bp; S&P BBB-, one notch above junk; ~$160B of debt")],
    "private_credit": [r("2026-10-15", level="amber", note="Blue Owl gated two funds in H1 and failed to finance a $4B data center; Oracle lease-deferral clause disclosed")],
    "ipo_window": [r("2026-10-10", level="amber", note="SpaceX ~50% below its post-IPO peak by late July; Firmus pulled its IPO; Anthropic targets November")],
    "ai_cds_other": [r("2026-10-08", level="amber", note="SoftBank CDS 424bp; Broadcom record 136bp")],
    "debt_share_capex": [r("2026-08-15", 32, note="Debt funded 32% of hyperscaler capex over 12 months vs 9% in FY24 (FactSet)")],
    "vendor_financing": [r("2026-08-27", level="amber", note="Nvidia guarantee exposure up to $108.5B incl. up to $105B for OpenAI's Ohio leases; private stakes $42.3B vs $3.2B a year earlier")],
    "beat_and_fall": [r("2026-08-27", 4, note="Nvidia fell the day after each of its last four reports")],
    "cape": [r("2026-10-01", 41, note="Shiller CAPE ~41, above 40 since May (Dec 1999 peak 44.2)")],
    "forward_pe": [r("2026-05-15", 22, note="S&P 500 forward P/E ~22 in May; needs a current FactSet reading")],
    "top10_weight": [r("2026-10-15", 39, note="Top 10 ~39% of the S&P 500; Nvidia ~7.8-8%")],
    "bofa_cash": [r("2026-10-14", 3.9, note="October survey; under the 4.0% sell trigger")],
    "bofa_bullbear": [r("2026-10-14", 8.1, note="Above the 8.0 sell trigger; net 37% overweight tech; long semis most crowded (45%)")],
    "leveraged_etf": [r("2026-06-30", level="amber", note="Global leveraged-ETF assets above $290B (June)")],
    "retail_flows": [r("2026-10-16", level="amber", note="Retail bought a net $66M of CoreWeave in the week of 12 Oct, second-largest week on record")],
    "narrative": [r("2026-10-15", level="amber", note="Broadcom CEO likened AI investing to a casino; Dalio and Burry warnings; IMF GFSR lists an AI-led correction")],
    "fed_hike_odds": [r("2026-10-16", 77, note="~85% odds of an October hold; ~77% odds of a December hike")],
}

CATALYSTS = [
    {"date": "2026-10-21", "event": "Korea exports, 1-20 October", "watch": "Chip export growth vs +46.7% in the first ten days",
     "plain": "South Korea's chip exports are the earliest hard data on chip demand. A sharp slowdown would be an early warning."},
    {"date": "2026-10-28", "event": "FOMC decision (2pm ET)", "watch": "Hike or hold; guidance on December",
     "plain": "The Fed decides on interest rates. Another rise, or hints of one, makes borrowing for AI more expensive."},
    {"date": "2026-10-29", "event": "Q3 results: Microsoft, Alphabet, Meta, Amazon (expected 27-30 Oct)",
     "watch": "2026 capex vs guidance, first 2027 capex color, cloud growth, AI revenue, financing plans",
     "plain": "The biggest test of the month. If any of them cuts AI spending plans, that is historically the clearest sign a boom is ending."},
    {"date": "2026-11-01", "event": "Korea October exports (trade ministry)", "watch": "Chip export growth y/y",
     "plain": "Full-month chip export numbers from South Korea."},
    {"date": "2026-11-03", "event": "US midterm elections", "watch": "Policy and fiscal risk",
     "plain": "The election could change taxes, spending and trade policy."},
    {"date": "2026-11-10", "event": "TSMC October revenue", "watch": "y/y growth vs 54.6% in September",
     "plain": "TSMC makes most AI chips; its monthly sales show whether demand is holding."},
    {"date": "2026-11-15", "event": "US October CPI; BofA November survey; CoreWeave Q3 results (to be confirmed)",
     "watch": "Inflation path; fund-manager cash and crowded trade; neocloud liquidity and backlog",
     "plain": "Inflation decides the Fed's next step, the survey shows how crowded investors are, and CoreWeave's results show how the most indebted AI company is coping."},
    {"date": "2026-11-18", "event": "Nvidia Q3 FY27 results (after close) and FOMC minutes",
     "watch": "Revenue vs the $108B guide, FY28 outlook, DSO, guarantees, and the share-price reaction",
     "plain": "Nvidia is the bellwether of the AI boom. Watch the share price the next day: falling even on great results means good news is already priced in."},
    {"date": "2026-11-25", "event": "Anthropic IPO window (not confirmed)",
     "watch": "Pricing vs the $965B private round and $1.5-2T talk; first-month trading",
     "plain": "If the listing is delayed, priced low, or trades below its first price, money for AI is drying up."},
    {"date": "2026-12-09", "event": "FOMC with projections", "watch": "~77% odds of a hike priced as of 19 Oct; the dot plot",
     "plain": "Another Fed decision on interest rates, with its forecast for next year."},
    {"date": "2026-12-15", "event": "Oracle, Broadcom and Micron results (to be confirmed)",
     "watch": "Oracle capex and financing; Broadcom customer backstops; memory pricing",
     "plain": "Oracle is the biggest borrower in the AI build-out; Micron shows where memory prices are heading."},
    {"date": "2027-02-01", "event": "OpenAI IPO (expected early 2027)", "watch": "The same funding-window tests as Anthropic",
     "plain": "Another test of whether investors will keep paying high prices for AI companies."},
]


def main():
    if MANUAL_PATH.exists() and "--force" not in sys.argv:
        sys.exit(f"{MANUAL_PATH} exists; pass --force to overwrite it.")
    doc = {
        "_help": "Hand-entered readings. Add entries with `python monitor.py add <indicator> <value|green|amber|red> --note ... --source ...` "
                 "or edit this file. The latest entry on or before a date counts; older entries stay as history.",
        "readings": READINGS,
        "tripwires": {k: {"status": "not_fired"} for k in TRIPWIRES},
        "catalysts": CATALYSTS,
    }
    MANUAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_PATH.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {MANUAL_PATH} ({len(READINGS)} indicators)")


if __name__ == "__main__":
    main()
