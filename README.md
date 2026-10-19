# AI Bubble Monitor

Watches about 60 signals for signs that the AI stock boom is fading or bursting, and sums them up as one of four risk levels:

| Level | Name (easy mode) | Regime (expert) | Meaning |
|---|---|---|---|
| 1 | Calm | Boom | No serious warning signs |
| 2 | Fragile | Fragile | Prices are high and some warning lights are on, but nothing important is breaking |
| 3 | Cracking | Cracking | Real stress in several places at once, or an event tripwire has fired |
| 4 | Unwinding | Unwind | Spending, credit and prices cracking together |

It is a **risk monitor, not a timing model and not investment advice**. It tells you how likely and how severe a fall looks. It cannot tell you the date.

Built from the research brief *AI Bubble Monitor: Research Brief* (19 Oct 2026). The section numbers below refer to it.

## Quick start

```bash
python monitor.py run --open
```

That fetches all free data (about 30 seconds), scores everything, writes `out/dashboard.html` and opens it. The dashboard has an **Easy / Expert** switch at the top:

- **Easy** gives the risk level, two plain meters ("How far could prices fall?" and "Has a fall started?"), what's happening in everyday words, where we are on the usual path of a bust, what would ease the worry, and the dates to watch.
- **Expert** gives the full instrument panel: Turn and Vulnerability indices, all 8 pillars with every indicator, its score, source and date, the regime rules, the tripwires, the headline scan and data health.

The only requirement is Python 3.11+ with `requests` (already installed here).

## Everyday use

| When | Command | What it does |
|---|---|---|
| Daily (or whenever) | `python monitor.py run` | Fetch, score, rebuild the dashboard, send alerts |
| Just a quick read | `python monitor.py status` | Plain summary in the terminal, no fetching |
| After adding readings | `python monitor.py run --no-fetch` | Rescore without fetching |
| Weekly-ish | `python monitor.py list` | Shows which hand-entered readings are stale |

## What updates itself and what you enter by hand

**Automatic (free):** credit spreads, Treasury yields, inflation, oil, financial conditions and the Fed rate (FRED); prices for ~35 tickers incl. Nvidia, chip stocks, CoreWeave, Oracle, private lenders and KOSPI (Yahoo); hyperscaler capex and cash flow, Oracle funding, Nvidia receivables and inventory (SEC filings); margin debt (FINRA); S&P 500 breadth computed from all ~500 members; a Google News headline scan for tripwires.

The archive in `data/monitor.db` keeps everything permanently. This matters for the credit spreads, because FRED only serves the last ~3 years of them.

**By hand:** some numbers only exist in news, surveys or paid data. They live in `data/manual.json`, seeded with the brief's 19 October readings. Add a new reading like this:

```bash
python monitor.py add bofa_cash 4.2 --note "November survey" --source https://...
python monitor.py add capex_guidance red --note "Meta guides 2027 capex down"
```

A reading is a number or a level (`green`, `amber`, `red`). Each indicator has an age limit. Past it, the reading drops out of the scores and shows under "Readings that need updating" in expert mode.

The most useful ones to keep fresh:

| Indicator | Where to find it | How often |
|---|---|---|
| `coreweave_cds`, `oracle_cds` (bp) | News (CNBC, Bloomberg, Reuters) | Weekly |
| `bofa_cash`, `bofa_bullbear` | BofA Fund Manager Survey coverage, mid-month | Monthly |
| `korea_chip_exports` (% y/y) | Korea Customs Service, 1st/11th/21st | 3× a month |
| `tsmc_revenue` (% y/y) | TSMC investor relations, ~10th | Monthly |
| `dram_contract` (% q/q) | TrendForce press center | Quarterly |
| `gpu_rent` (% below 90-day high) | data.ornn.com (H100 index) | Weekly |
| `capex_guidance`, `cloud_growth` (level) | Hyperscaler earnings, late Jan/Apr/Jul/Oct | Quarterly |
| `nvidia_guide` (% q/q), `beat_and_fall` (of 4) | Nvidia results | Quarterly |
| `lab_revenue_growth` (% q/q) | Anthropic/OpenAI reporting | Quarterly |
| `cape`, `forward_pe`, `top10_weight` | multpl.com, FactSet Earnings Insight, SlickCharts | Monthly |
| `fed_hike_odds` (%) | CME FedWatch | Weekly |
| `earnings_revisions` (level) | FactSet Earnings Insight; feeds the bust-path tracker | Monthly |

`python monitor.py list` shows every hand-entered indicator, its last value and its age.

## Tripwires (brief §11)

These are 16 binary events, such as a hyperscaler cutting capex, a CoreWeave covenant breach or Oracle being cut to junk. Each confirmed one lifts the risk level: one tripwire means at least Cracking, two mean Unwind. The headline scan only *proposes* candidates (expert mode, "Possible tripwires to review"). A tripwire fires only when you record it with two credible sources:

```bash
python monitor.py tripwire list
python monitor.py tripwire fire capex_cut --source https://... --source https://... --note "Meta: 2027 capex 'digestion'"
python monitor.py tripwire clear capex_cut
```

A fired tripwire counts for 120 days (change it with `--expires`).

## Alerts

Push alerts go out only when the risk level changes or a tripwire fires, through the ntfy app (as Lönekoll does). Create `data/config.json`:

```json
{"ntfy_topic": "pick-a-long-random-topic-name"}
```

Subscribe to the same topic in the ntfy app. Without a topic, alerts are only printed.

### Daily run on GitHub Actions

`.github/workflows/daily.yml` runs `python monitor.py run` every day at 05:00 UTC, and on demand from the Actions tab. It needs two repository secrets: `NTFY_TOPIC`, and `SEC_USER_AGENT` (a name plus contact email, which SEC asks every client to send; locally the same text goes in `data/config.json` as `sec_user_agent`, so it stays out of the public code). The archive `data/monitor.db` is not in git; the Actions cache carries it from run to run. If the cache is lost, the next run rebuilds it from the sources and only sets a new baseline, so a level change on that day goes unalerted. A failed run sends its own ntfy message, so silence never hides a broken check. Each run's dashboard is kept for 14 days as a downloadable artifact.

Hand-entered readings (`add`, `tripwire fire`) change `data/manual.json`: commit and push it so the next daily run uses them.

## How the scoring works (brief §12)

1. Each indicator gets a 0–100 stress score from the brief's thresholds: amber starts at 34, red at 67. Growth series (lab revenue, Korean exports, memory prices) also score the *slowdown*, because booms end when growth decelerates, not when it turns negative.
2. Each pillar's score is the median of its indicators, so one noisy input can't swing it.
3. **Turn Index** (fast: is a fall starting?) averages pillars A demand, B capex, C credit stress, D market internals and G macro. **Vulnerability Index** (slow: how far could it fall?) averages E valuation, F positioning, and the funding-structure part of C.
4. The regime is the highest rule met. A pillar only counts as red after 5 of the last 10 sessions at 67+, to filter one-day shocks.
5. The dashboard also splits the **edge** (CoreWeave, Oracle, private lenders, memory, Korea) from the **core** (Nvidia, hyperscalers). In past booms the edges cracked first.

## What the backtest says

`python monitor.py backtest` replays the parts with decades of daily data (market internals, a Baa credit-spread proxy, macro) over 1996–2026:

- **Dot-com top (Mar 2000):** warned 2 months *after* the peak, with 59% of the Nasdaq-100's fall still ahead. It also gave a false alarm in late 1998.
- **2007 top:** warned 3 months after the peak, with 41% still ahead.
- **2021 top:** warned late (Jul 2022).
- **3 of 6 warnings** over 30 years were followed by a 20%+ fall within a year.

So the market layer *confirms* a turn rather than predicting it. Earlier warning has to come from the AI-specific and hand-entered signals (lab revenue, capex guidance, CDS, fund-manager positioning) and from tripwires, which can't be backtested because their history is too short. Expect false alarms. 2026 has already had several sharp drops that recovered.

## Files

```
monitor.py            command line
abm/sources/          fetchers: fred, yahoo, edgar, finra, breadth, news
abm/indicators.py     every indicator: thresholds, plain-language text
abm/scoring.py        pillars, composites, regime rules, bust-path stages
abm/explain.py        easy-mode wording
abm/template.html     dashboard
abm/backtest.py       backtest of the price-and-credit layer
data/manual.json      hand-entered readings, tripwires, catalyst calendar
data/monitor.db       permanent archive of every fetched series
out/dashboard.html    the dashboard (out/latest.json is the same data as JSON)
scripts/seed_manual.py  re-creates manual.json from the brief (won't overwrite)
```

## Limits

- Hand-entered readings come from news and secondary trackers, as the brief does. Check the important ones against the primary source.
- Credit default swap prices are paid data. The CoreWeave and Oracle CDS figures need updating from news.
- Breadth uses today's S&P 500 members, so older breadth values carry survivorship bias.
- Yahoo prices are free but unofficial and can break without warning. Failures show under data health and never stop a run.
- Capex from filings is cash capex and excludes finance leases (see the brief's data pitfalls).
