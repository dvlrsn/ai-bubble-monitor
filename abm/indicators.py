"""Indicator definitions: what each one measures, how it is scored, and how to say it plainly.

Scoring: every indicator maps to a 0-100 stress score through piecewise-linear
`points` [(value, score), ...]. Points sit on the brief's flags where it gives
them: amber starts at 34 and red at 67. Unattributed thresholds are starting
points to calibrate by backtest, as the brief says.

Manual indicators read dated entries from data/manual.json. An entry is either
{"value": number} (scored by points) or {"level": "green"|"amber"|"red"}.
`decel` scores a slowdown in a growth series: the latest reading as a share of
the highest of the previous three. It can push a reading up to amber, never red.
"""

from datetime import date

LEVEL_SCORE = {"green": 15, "amber": 50, "red": 80}

PILLARS = {
    "A": {"name": "AI demand and monetization", "plain": "Is AI earning money?", "composite": "turn"},
    "B": {"name": "Capex cycle and supply chain", "plain": "Is the building spree slowing?", "composite": "turn"},
    "C": {"name": "Credit stress", "plain": "Are lenders getting nervous?", "composite": "turn"},
    "D": {"name": "Market internals", "plain": "How are AI stocks behaving?", "composite": "turn"},
    "G": {"name": "Macro, rates and liquidity", "plain": "Interest rates and the economy", "composite": "turn"},
    "E": {"name": "Valuation and concentration", "plain": "How expensive are stocks?", "composite": "vuln"},
    "F": {"name": "Sentiment, positioning and leverage", "plain": "How crowded and borrowed-up are investors?", "composite": "vuln"},
    "Cf": {"name": "Funding structure", "plain": "How much of the building is paid with borrowed money?", "composite": "vuln"},
}


def level_of(score):
    if score is None:
        return None
    return "red" if score >= 67 else "amber" if score >= 34 else "green"


def interp(points, x):
    pts = sorted(points)
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(pts[-1][1])


# ---------------------------------------------------------------------------
# Calculations for automated indicators. Each returns a dict or None:
#   value (number scored by points), date (data date), detail (expert text),
#   optional score_floor (minimum score, for extra conditions).
# ---------------------------------------------------------------------------

def _dd(sid, n=252):
    def f(c):
        r = c.drawdown(sid, n)
        if not r:
            return None
        return {"value": r[0], "date": r[1], "detail": f"{r[0]:.1f}% below its 1-year high"}
    return f


def _avg_dd(sids, n=252):
    def f(c):
        parts = [(s, c.drawdown(s, n)) for s in sids]
        parts = [(s, r) for s, r in parts if r]
        if not parts:
            return None
        v = sum(r[0] for _, r in parts) / len(parts)
        detail = ", ".join(f"{s.split(':')[-1]} -{r[0]:.0f}%" for s, r in parts)
        return {"value": v, "date": max(r[1] for _, r in parts), "detail": f"Average {v:.0f}% below 1-year highs ({detail})"}
    return f


def _vs200(sid, label):
    def f(c):
        r = c.vs_sma(sid, 200)
        if not r:
            return None
        pct, sma, d = r
        prev = c.sma(sid, 200, lag=20)
        falling = prev is not None and sma < prev
        out = {"value": pct, "date": d,
               "detail": f"{label} {pct:+.1f}% vs its 200-day average, which is {'falling' if falling else 'rising'}"}
        if pct < 0 and falling:
            out["score_floor"] = 67
        return out
    return f


def _latest(sid, label, fmt="{:.2f}"):
    def f(c):
        r = c.last(sid)
        if not r:
            return None
        return {"value": r[1], "date": r[0], "detail": f"{label} {fmt.format(r[1])}"}
    return f


def _spread(sid, label, widen_points):
    """Level score, or widening from the trailing 1-year low if that is worse."""
    def f(c):
        r = c.last(sid)
        if not r:
            return None
        low = c.min_since(sid, 365)
        widen = 100 * (r[1] - low)
        return {"value": r[1], "date": r[0], "extra_score": interp(widen_points, widen),
                "detail": f"{label} {r[1]:.2f}%, {widen:.0f}bp above its 1-year low of {low:.2f}%"}
    return f


def semis_relative(c):
    ratio = c.ratio_series("px:SMH", "px:SPY", 252)[-252:]
    if len(ratio) < 200:
        return None
    hi = max(v for _, v in ratio)
    dd = 100 * (1 - ratio[-1][1] / hi)
    return {"value": dd, "date": ratio[-1][0], "detail": f"Chip stocks vs the S&P 500: {dd:.1f}% below their best relative level of the past year"}


def breadth200(c):
    r = c.last("breadth:pct200")
    if not r:
        return None
    p50 = c.last("breadth:pct50")
    dd = c.drawdown("px:^GSPC", 252)
    near = f"; S&P 500 {dd[0]:.1f}% below its high" if dd else ""
    out = {"value": r[1], "date": r[0],
           "detail": f"{r[1]:.0f}% of S&P 500 members above their 200-day average"
                     + (f", {p50[1]:.0f}% above their 50-day" if p50 else "") + near}
    # The brief's specific warning: index near its high while most members lag.
    if dd and dd[0] <= 3 and r[1] < 50:
        out["score_floor"] = 50
    return out


def margin_unwind(c):
    """Two straight monthly declines in margin debt while prices fall."""
    s = c.s("finra:margin_debt")
    if len(s) < 3:
        return None
    (d0, v0), (d1, v1), (d2, v2) = s[-3:]
    falling_debt = v1 < v0 and v2 < v1
    spx_now, spx_then = c.value_ago("px:^GSPC", 0), c.value_ago("px:^GSPC", 61)
    falling_px = spx_now and spx_then and spx_now[1] < spx_then[1]
    chg = 100 * (v2 / v1 - 1)
    value = 80 if (falling_debt and falling_px) else 45 if falling_debt else 10
    return {"value": value, "date": d2,
            "detail": f"Margin debt ${v2/1e6:.2f}T in {d2[:7]} ({chg:+.1f}% m/m); "
                      + ("two straight monthly declines" if falling_debt else "no sustained decline")}


def margin_growth(c):
    s = c.s("finra:margin_debt")
    if len(s) < 13:
        return None
    d, v = s[-1]
    prev = c.value_ago("finra:margin_debt", 365)
    g = 100 * (v / prev[1] - 1)
    return {"value": g, "date": d, "detail": f"Margin debt ${v/1e6:.2f}T in {d[:7]}, {g:+.0f}% over 12 months"}


def concentration_trend(c):
    ratio = c.ratio_series("px:RSP", "px:SPY", 270)
    if len(ratio) < 260:
        return None
    now, then = ratio[-1], ratio[-253]
    chg = 100 * (now[1] / then[1] - 1)
    return {"value": chg, "date": now[0],
            "detail": f"Equal-weight S&P 500 vs the cap-weighted index: {chg:+.1f}% over 12 months"}


def buffett(c):
    mv, gdp = c.last("fred:NCBEILQ027S"), c.last("fred:GDP")
    if not mv or not gdp:
        return None
    # Market value of equities ($M) is quarterly and lags; scale it by the
    # S&P 500's move since that quarter to keep the ratio current.
    spx_then = c.value_ago("px:^GSPC", (date.fromisoformat(c.asof) - date.fromisoformat(mv[0])).days - 45)
    spx_now = c.last("px:^GSPC")
    scale = spx_now[1] / spx_then[1] if spx_then and spx_now else 1.0
    ratio = 100 * (mv[1] / 1000) * scale / gdp[1]
    return {"value": ratio, "date": spx_now[0] if spx_now else mv[0],
            "detail": f"US stock market value about {ratio:.0f}% of GDP (Fed Z.1 {mv[0][:7]} quarter, rolled forward with the S&P 500)"}


def cpi_yoy(c):
    s = c.s("fred:CPIAUCSL")
    if len(s) < 14:
        return None
    d, v = s[-1]
    prev = c.value_ago("fred:CPIAUCSL", 365)
    g = 100 * (v / prev[1] - 1)
    g_prior = 100 * (s[-2][1] / c.value_ago("fred:CPIAUCSL", 365 + 31)[1] - 1)
    return {"value": g, "date": d,
            "detail": f"CPI inflation {g:.1f}% y/y in {d[:7]} ({'up' if g > g_prior else 'down'} from {g_prior:.1f}%)"}


def fed_path(c):
    r = c.last("fred:DFEDTARU")
    ago = c.value_ago("fred:DFEDTARU", 182)
    if not r or not ago:
        return None
    chg = r[1] - ago[1]
    return {"value": chg, "date": r[0],
            "detail": f"Fed funds target top {r[1]:.2f}%, {chg:+.2f} points over 6 months"}


def nfci(c):
    s = c.s("fred:NFCI")
    if len(s) < 5:
        return None
    d, v = s[-1]
    rising = all(s[-i][1] > s[-i - 1][1] for i in range(1, 5))
    out = {"value": v, "date": d,
           "detail": f"Financial conditions index {v:+.2f} (negative = looser than average)"
                     + ("; tightening four weeks running" if rising else "")}
    if rising:
        out["score_floor"] = 40
    return out


def _hyperscaler_quarters(c, concept):
    """{quarter_end: {ticker: value}} for the four hyperscalers."""
    from .sources.edgar import HYPERSCALERS
    out = {}
    for t in HYPERSCALERS:
        for d, v in c.s(f"edgar:{t}:{concept}"):
            out.setdefault(d, {})[t] = v
    return out


def capex_growth(c):
    q = _hyperscaler_quarters(c, "capex")
    full = sorted(d for d, m in q.items() if len(m) == 4)
    if not full:
        return None
    last = full[-1]
    year_ago = [d for d in full if 350 <= (date.fromisoformat(last) - date.fromisoformat(d)).days <= 380]
    if not year_ago:
        return None
    now, then = sum(q[last].values()), sum(q[year_ago[0]].values())
    g = 100 * (now / then - 1)
    return {"value": g, "date": last,
            "detail": f"Microsoft, Alphabet, Amazon and Meta spent ${now/1e9:.0f}B on capex in the quarter to {last}, {g:+.0f}% y/y (cash capex, excludes finance leases)"}


def capex_vs_cash(c):
    cap, ocf = _hyperscaler_quarters(c, "capex"), _hyperscaler_quarters(c, "ocf")
    from .sources.edgar import HYPERSCALERS
    ratios = {}
    for t in HYPERSCALERS:
        qs = sorted(d for d in cap if t in cap[d] and d in ocf and t in ocf[d])[-4:]
        if len(qs) == 4:
            ratios[t] = 100 * sum(cap[d][t] for d in qs) / sum(ocf[d][t] for d in qs)
    if len(ratios) < 3:
        return None
    vals = sorted(ratios.values())
    med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
    over = [t for t, r in ratios.items() if r > 100]
    out = {"value": med, "date": max(cap),
           "detail": "Capex as % of operating cash flow, last 4 quarters: "
                     + ", ".join(f"{t} {r:.0f}%" for t, r in sorted(ratios.items(), key=lambda x: -x[1]))}
    if len(over) >= 2:
        out["score_floor"] = 50
    return out


def oracle_funding(c):
    cap, ocf = c.s("edgar:ORCL:capex")[-4:], c.s("edgar:ORCL:ocf")[-4:]
    if len(cap) < 4 or len(ocf) < 4:
        return None
    r = 100 * sum(v for _, v in cap) / sum(v for _, v in ocf)
    return {"value": r, "date": cap[-1][0],
            "detail": f"Oracle capex ${sum(v for _, v in cap)/1e9:.0f}B vs operating cash flow ${sum(v for _, v in ocf)/1e9:.0f}B over 4 quarters ({r:.0f}%)"}


def nvda_dso(c):
    ar, rev = c.last("edgar:NVDA:receivables"), c.last("edgar:NVDA:revenue")
    if not ar or not rev or ar[0] != rev[0]:
        return None
    dso = ar[1] / rev[1] * 91
    return {"value": dso, "date": ar[0], "detail": f"Nvidia takes {dso:.0f} days to collect payment (receivables ${ar[1]/1e9:.0f}B on quarterly revenue ${rev[1]/1e9:.0f}B)"}


def nvda_inventory(c):
    s = c.s("edgar:NVDA:inventory")
    if len(s) < 2:
        return None
    (d0, v0), (d1, v1) = s[-2:]
    g = 100 * (v1 / v0 - 1)
    return {"value": g, "date": d1, "detail": f"Nvidia inventory ${v1/1e9:.1f}B, {g:+.0f}% q/q"}


# ---------------------------------------------------------------------------
# The indicator list. Fields:
#   id, pillar, name (expert), plain (easy-mode name), kind auto|manual,
#   calc (auto) / unit+fmt (display), points, max_age (days before stale),
#   decel (manual growth series), easy: plain sentences per level,
#   core: "edge" or "core" for the weak-links-versus-megacaps split.
# ---------------------------------------------------------------------------

def I(**kw):
    kw.setdefault("kind", "manual")
    kw.setdefault("fmt", "{:.1f}")
    kw.setdefault("unit", "")
    kw.setdefault("decel", False)
    return kw


INDICATORS = [
    # ---- A: AI demand and monetization ---------------------------------
    I(id="lab_revenue_growth", headline=True, pillar="A", name="Frontier-lab revenue growth (Anthropic, q/q)",
      plain="How fast AI labs' sales are growing", unit="% q/q", fmt="{:.0f}", decel=True, max_age=120,
      points=[(-10, 100), (0, 67), (25, 34), (60, 0)],
      easy={"green": "AI labs' sales are still growing fast.",
            "amber": "AI labs' sales are still growing, but much more slowly than a few months ago.",
            "red": "AI labs' sales have stalled. The companies paying for the data centers are not earning enough."}),
    I(id="revenue_quality", pillar="A", name="Lab revenue quality (gross vs net, restatements)",
      plain="Are AI sales numbers trustworthy?", max_age=120,
      easy={"green": "No red flags in how AI companies report their sales.",
            "amber": "Some AI sales figures turned out smaller than first reported, depending on how they are counted.",
            "red": "AI companies have cut or restated their sales figures."}),
    I(id="cloud_growth", pillar="A", name="Hyperscaler cloud growth (Azure, Google Cloud, AWS)",
      plain="Cloud businesses' growth", max_age=120,
      easy={"green": "Microsoft, Google and Amazon's cloud businesses are growing strongly, so the spending is earning money.",
            "amber": "Cloud growth at the big tech firms is slowing.",
            "red": "Cloud sales are growing more slowly than spending. The return on the building spree is shrinking."}),
    I(id="gpu_rent", pillar="A", name="H100 rental index, % below 90-day high (Ornn)",
      plain="Price to rent an AI chip", unit="% below high", fmt="{:.1f}", max_age=21,
      points=[(5, 0), (15, 34), (25, 67), (40, 100)], core="edge",
      easy={"green": "Renting an AI chip still costs as much as before, so demand is keeping up with supply.",
            "amber": "Prices to rent AI chips are falling, which hints that there may be more chips than buyers.",
            "red": "AI chip rental prices are dropping fast, a classic sign of overbuilding."}),
    I(id="token_growth", pillar="A", name="Token volume growth", plain="How much AI is being used", max_age=180,
      easy={"green": "AI usage keeps multiplying.",
            "amber": "AI usage growth has halved.", "red": "AI usage has stopped growing."}),
    I(id="lab_unit_economics", pillar="A", name="Lab revenue per $1 of compute (Anthropic)",
      plain="Do AI labs earn more than their computing costs?", unit="$", fmt="{:.2f}", max_age=120,
      points=[(0.7, 100), (1.0, 67), (1.5, 34), (2.0, 0)],
      easy={"green": "AI labs earn clearly more than their computing costs.",
            "amber": "AI labs' margins over computing costs are thin.",
            "red": "AI labs barely cover their computing costs."}),
    I(id="startup_failures", pillar="A", name="AI startup failures and down rounds",
      plain="AI startups going bust", max_age=60, core="edge",
      easy={"green": "No unusual wave of AI startup failures.",
            "amber": "Some well-known AI startups have failed or raised money at lower values.",
            "red": "AI startups are failing in clusters."}),

    # ---- B: Capex cycle and supply chain --------------------------------
    I(id="capex_growth", headline=True, pillar="B", kind="auto", calc=capex_growth, name="Hyperscaler capex growth (EDGAR)",
      plain="Growth in big tech's data-center spending", unit="% y/y", fmt="{:+.0f}", max_age=140,
      points=[(-10, 100), (10, 67), (30, 34), (60, 0)], core="core",
      easy={"green": "Big tech is still increasing its AI spending quickly.",
            "amber": "Big tech's AI spending is still rising, but more slowly. Booms often end with a slowdown, not a sudden stop.",
            "red": "Big tech's AI spending growth has almost stopped."}),
    I(id="capex_guidance", headline=True, pillar="B", name="Hyperscaler capex guidance", plain="Big tech's spending plans",
      max_age=120, core="core",
      easy={"green": "Every recent update to big tech's spending plans has been upward.",
            "amber": "Big tech raised its spending plans by less than expected.",
            "red": "A big tech company has cut its spending plans or talks of a 'pause'. Historically this is the most important warning."}),
    I(id="nvidia_guide", headline=True, pillar="B", name="Nvidia guided sequential revenue growth",
      plain="Nvidia's sales forecast", unit="% q/q", fmt="{:+.1f}", max_age=120,
      points=[(-10, 100), (0, 67), (5, 34), (15, 0)], core="core",
      easy={"green": "Nvidia, the main AI chip maker, expects sales to keep rising quickly.",
            "amber": "Nvidia expects only small sales growth next quarter.",
            "red": "Nvidia expects sales to stall or fall."}),
    I(id="nvda_dso", pillar="B", kind="auto", calc=nvda_dso, name="Nvidia days sales outstanding",
      plain="How long Nvidia waits to be paid", unit="days", fmt="{:.0f}", max_age=140,
      points=[(50, 0), (65, 34), (80, 67), (100, 100)], core="core",
      easy={"green": "Nvidia's customers pay on time.",
            "amber": "Nvidia's customers are taking longer to pay, which can hint at quiet financing help.",
            "red": "Nvidia's customers are paying much more slowly."}),
    I(id="nvda_inventory", pillar="B", kind="auto", calc=nvda_inventory, name="Nvidia inventory growth",
      plain="Unsold chips piling up at Nvidia", unit="% q/q", fmt="{:+.0f}", max_age=140,
      points=[(0, 0), (20, 34), (40, 67), (60, 100)], core="core",
      easy={"green": "Nvidia isn't sitting on a pile of unsold chips.",
            "amber": "Nvidia's stock of unsold chips is growing fast.",
            "red": "Unsold chips are piling up at Nvidia."}),
    I(id="tsmc_revenue", pillar="B", name="TSMC monthly revenue growth", plain="Sales at TSMC, which makes most AI chips",
      unit="% y/y", fmt="{:+.0f}", max_age=45, points=[(-15, 100), (0, 67), (25, 34), (40, 0)], core="core",
      easy={"green": "TSMC, which manufactures most AI chips, is selling more than ever.",
            "amber": "TSMC's sales growth is slowing.", "red": "TSMC's sales are shrinking."}),
    I(id="korea_chip_exports", pillar="B", name="Korea chip exports", plain="South Korea's chip exports",
      unit="% y/y", fmt="{:+.0f}", decel=True, max_age=25, points=[(-15, 100), (0, 67), (20, 34), (40, 0)], core="edge",
      easy={"green": "South Korea's chip exports, the earliest hard data on chip demand, are booming.",
            "amber": "South Korea's chip exports are still growing, but the growth is slowing sharply.",
            "red": "South Korea's chip exports are falling."}),
    I(id="dram_contract", pillar="B", name="DRAM contract price change", plain="Memory chip prices",
      unit="% q/q", fmt="{:+.0f}", decel=True, max_age=100, points=[(-10, 100), (0, 67), (5, 34), (30, 0)], core="edge",
      easy={"green": "Memory chip prices are rising strongly.",
            "amber": "Memory chip prices are still rising, but much more slowly. Memory stocks usually peak around this point.",
            "red": "Memory chip prices are falling."}),
    I(id="dc_construction", pillar="B", name="Data-center construction spending (Census)",
      plain="Data-center construction", unit="% y/y", fmt="{:+.0f}", max_age=75,
      points=[(0, 100), (10, 67), (25, 34), (40, 0)],
      easy={"green": "Data-center construction is at a record pace.",
            "amber": "Data-center construction is slowing.", "red": "Data-center construction has stalled."}),
    I(id="ai_gdp_share", pillar="B", name="AI infrastructure investment, % of GDP (Epoch)",
      plain="AI building as a share of the economy", unit="% of GDP", fmt="{:.1f}", max_age=200,
      points=[(0.5, 0), (1, 34), (2, 67), (3, 100)],
      easy={"green": "AI building is still a small part of the economy, smaller than past booms at their peak.",
            "amber": "AI building is now a large part of the economy.",
            "red": "AI building is bigger, relative to the economy, than the telecom boom at its peak."}),
    I(id="cancellations", pillar="B", name="Data-center delays, cancellations, excess capacity",
      plain="Cancelled or delayed data centers", max_age=60,
      easy={"green": "No big data-center projects are being cancelled.",
            "amber": "Some data-center projects are being delayed, blocked or resold.",
            "red": "Big tech is cancelling data-center leases or abandoning sites."}),
    I(id="supplier_tone", pillar="B", name="Supplier tone (Broadcom, AMD, Micron, ASML, SK Hynix, Samsung)",
      plain="What chip suppliers are saying", max_age=120,
      easy={"green": "Chip suppliers say orders are strong.",
            "amber": "Chip suppliers sound more cautious.",
            "red": "Chip suppliers report delayed orders or 'digestion'."}),

    # ---- C: Credit stress (turn) ----------------------------------------
    I(id="hy_oas", headline=True, pillar="C", kind="auto", calc=_spread("fred:BAMLH0A0HYM2", "High-yield spread", [(0, 0), (100, 34), (200, 67), (350, 100)]),
      name="High-yield spread (FRED)", plain="Extra interest risky companies pay", unit="%", fmt="{:.2f}", max_age=10,
      points=[(3.0, 0), (4.0, 34), (5.0, 67), (7.0, 100)],
      easy={"green": "Lenders are still relaxed about risky companies in general.",
            "amber": "Risky companies in general must pay noticeably more to borrow. Stress is spreading beyond AI.",
            "red": "Borrowing costs for risky companies have jumped across the board, a sign of a broad credit squeeze."}),
    I(id="ccc_oas", pillar="C", kind="auto", calc=_spread("fred:BAMLH0A3HYC", "CCC spread", [(0, 0), (200, 34), (400, 67), (700, 100)]),
      name="CCC spread (FRED)", plain="Borrowing costs for the riskiest companies", unit="%", fmt="{:.2f}", max_age=10,
      points=[(9, 0), (14, 34), (16, 67), (20, 100)],
      easy={"green": "Even the riskiest borrowers can still get money.",
            "amber": "The riskiest borrowers are paying noticeably more to borrow.",
            "red": "Borrowing costs for the riskiest companies have jumped sharply this year."}),
    I(id="ig_oas", pillar="C", kind="auto", calc=_spread("fred:BAMLC0A0CM", "Investment-grade spread", [(0, 0), (40, 34), (80, 67), (150, 100)]),
      name="Investment-grade spread (FRED)", plain="Borrowing costs for solid companies", unit="%", fmt="{:.2f}", max_age=10,
      points=[(0.8, 0), (1.05, 34), (1.3, 67), (2.0, 100)],
      easy={"green": "Solid companies borrow cheaply.", "amber": "Even solid companies are paying more to borrow.",
            "red": "Borrowing costs are rising even for solid companies."}),
    I(id="neocloud_equity", pillar="C", kind="auto", calc=_avg_dd(["px:CRWV", "px:NBIS", "px:IREN"]),
      name="Neocloud shares (CRWV, NBIS, IREN) drawdown", plain="Shares of AI chip-rental companies",
      unit="% below high", fmt="{:.0f}", max_age=7, points=[(20, 0), (40, 34), (60, 67), (80, 100)], core="edge",
      easy={"green": "Companies that rent out AI chips are doing fine on the stock market.",
            "amber": "Shares of companies that rent out AI chips (and borrowed heavily to buy them) have fallen a lot.",
            "red": "Shares of the AI chip-rental companies have collapsed. Investors fear they can't repay their debts."}),
    I(id="coreweave_cds", headline=True, pillar="C", name="CoreWeave CDS", plain="Cost of insuring against CoreWeave going bust",
      unit="bp", fmt="{:.0f}", max_age=14, points=[(500, 0), (800, 34), (1000, 67), (1500, 100)], core="edge",
      easy={"green": "Lenders trust CoreWeave, the biggest AI chip-rental company.",
            "amber": "Lenders are getting nervous about CoreWeave, the biggest AI chip-rental company.",
            "red": "Lenders treat CoreWeave, the biggest AI chip-rental company, as a serious default risk. Insuring its debt costs over 10% a year."}),
    I(id="oracle_cds", headline=True, pillar="C", name="Oracle 5-year CDS", plain="Cost of insuring against Oracle defaulting",
      unit="bp", fmt="{:.0f}", max_age=14, points=[(150, 0), (250, 34), (350, 67), (500, 100)], core="edge",
      easy={"green": "Lenders are relaxed about Oracle's AI borrowing.",
            "amber": "Lenders are worried about Oracle, which has borrowed heavily to build AI data centers and is one step above 'junk'.",
            "red": "Oracle's debt is being treated like junk. It is the biggest borrower in the AI build-out."}),
    I(id="oracle_equity", pillar="C", kind="auto", calc=_dd("px:ORCL"), name="Oracle shares drawdown",
      plain="Oracle's share price", unit="% below high", fmt="{:.0f}", max_age=7,
      points=[(15, 0), (30, 34), (50, 67), (70, 100)], core="edge",
      easy={"green": "Oracle's stock is holding up.", "amber": "Oracle's stock has fallen a lot.",
            "red": "Oracle's stock has collapsed."}),
    I(id="private_credit_equity", pillar="C", kind="auto", calc=_avg_dd(["px:OWL", "px:OBDC", "px:ARCC"]),
      name="Private-credit shares (OWL, OBDC, ARCC) drawdown", plain="Shares of private lenders",
      unit="% below high", fmt="{:.0f}", max_age=7, points=[(10, 0), (25, 34), (40, 67), (60, 100)], core="edge",
      easy={"green": "Private lenders, a key source of money for data centers, look healthy.",
            "amber": "Shares of private lenders that fund data centers have dropped noticeably.",
            "red": "Private lenders that fund data centers are in trouble."}),
    I(id="private_credit", pillar="C", name="Private credit: gates and failed financings",
      plain="Private lenders pulling back", max_age=60, core="edge",
      easy={"green": "Private lenders keep funding data centers.",
            "amber": "Some private lenders have limited withdrawals or failed to fund a data center.",
            "red": "Private lenders are pulling back from data centers or taking losses."}),
    I(id="ipo_window", pillar="C", name="IPO window and private marks", plain="Appetite for new AI stock listings",
      max_age=45, core="edge",
      easy={"green": "Investors are eager to buy new AI share listings.",
            "amber": "Some big new listings have fallen sharply or been pulled, so appetite for new AI money-raising is fading.",
            "red": "A major AI lab's stock listing has been delayed or priced below its last private value."}),
    I(id="ai_cds_other", pillar="C", name="Other AI-linked CDS (SoftBank, Broadcom)", plain="Debt insurance costs for other AI funders",
      max_age=30,
      easy={"green": "Other big AI funders look safe to lenders.",
            "amber": "Debt insurance for other AI funders such as SoftBank and Broadcom is at or near records.",
            "red": "Other AI funders' debt insurance costs are spiking alongside falling shares."}),

    # ---- Cf: Funding structure (vulnerability) --------------------------
    I(id="capex_vs_cash", pillar="Cf", kind="auto", calc=capex_vs_cash, name="Capex vs operating cash flow (hyperscalers)",
      plain="Is big tech spending more than it earns in cash?", unit="% of OCF (median)", fmt="{:.0f}", max_age=140,
      points=[(40, 0), (80, 34), (100, 67), (130, 100)], core="core",
      easy={"green": "Big tech mostly pays for its AI building out of its own cash.",
            "amber": "Big tech's AI building eats most of its cash, and some firms spend more than they bring in.",
            "red": "Big tech is spending more than it earns in cash and has to borrow the difference."}),
    I(id="debt_share_capex", pillar="Cf", name="Debt share of capex funding", plain="Share of AI building paid with debt",
      unit="%", fmt="{:.0f}", max_age=150, points=[(10, 0), (25, 34), (40, 67), (60, 100)],
      easy={"green": "Little of the AI building is paid with borrowed money.",
            "amber": "About a third of AI building is now paid with borrowed money, up from under a tenth two years ago.",
            "red": "Much of the AI building is paid with borrowed money. That's how past infrastructure booms ended."}),
    I(id="oracle_funding", pillar="Cf", kind="auto", calc=oracle_funding, name="Oracle capex vs operating cash flow",
      plain="Oracle spending vs its cash", unit="% of OCF", fmt="{:.0f}", max_age=140,
      points=[(60, 0), (100, 34), (150, 67), (250, 100)], core="edge",
      easy={"green": "Oracle pays for its building from its own cash.",
            "amber": "Oracle spends more on building than it brings in.",
            "red": "Oracle spends far more than it brings in and relies on borrowing."}),
    I(id="vendor_financing", pillar="Cf", name="Vendor and circular financing", plain="Chip makers lending to their own customers",
      max_age=120,
      easy={"green": "Suppliers aren't propping up their customers.",
            "amber": "Nvidia and Broadcom increasingly guarantee or fund their own customers' purchases, as telecom suppliers did before 2001.",
            "red": "A supplier's guarantee has been called or written down."}),

    # ---- D: Market internals --------------------------------------------
    I(id="sox_drawdown", pillar="D", kind="auto", calc=_dd("px:^SOX"), name="SOX drawdown from 1-year high",
      plain="Chip stocks' fall from their peak", unit="% below high", fmt="{:.1f}", max_age=7,
      points=[(5, 0), (15, 34), (25, 67), (40, 100)],
      easy={"green": "Chip stocks are near their highs.", "amber": "Chip stocks have dropped well below their peak.",
            "red": "Chip stocks are in a deep slide."}),
    I(id="nvda_trend", pillar="D", kind="auto", calc=_vs200("px:NVDA", "Nvidia"), name="Nvidia vs 200-day average",
      plain="Nvidia's price trend", unit="% vs 200d", fmt="{:+.1f}", max_age=7,
      points=[(-25, 100), (-10, 67), (0, 34), (20, 0)], core="core",
      easy={"green": "Nvidia's share price trend is still up.",
            "amber": "Nvidia's share price has dropped below its long-term trend.",
            "red": "Nvidia's share price is in a clear downtrend."}),
    I(id="semis_relative", pillar="D", kind="auto", calc=semis_relative, name="Semis vs S&P 500 (SMH/SPY)",
      plain="Chip stocks vs the whole market", unit="% below high", fmt="{:.1f}", max_age=7,
      points=[(3, 0), (10, 34), (20, 67), (35, 100)],
      easy={"green": "Chip stocks are still leading the market.", "amber": "Chip stocks have started lagging the rest of the market.",
            "red": "Chip stocks are badly lagging. The leaders are rolling over."}),
    I(id="breadth", pillar="D", kind="auto", calc=breadth200, name="S&P 500 members above 200-day average",
      plain="How many stocks are actually rising", unit="%", fmt="{:.0f}", max_age=7,
      points=[(25, 100), (40, 67), (50, 34), (75, 0)],
      easy={"green": "Most stocks are in uptrends, so the rally is broad.",
            "amber": "Only about half of stocks are in uptrends; a few giants are carrying the index.",
            "red": "Most stocks are falling even though the index looks fine, as in March 2000."}),
    I(id="vix", pillar="D", kind="auto", calc=_latest("px:^VIX", "VIX", "{:.1f}"), name="VIX",
      plain="Fear gauge", fmt="{:.1f}", max_age=7, points=[(14, 0), (22, 34), (30, 67), (45, 100)],
      easy={"green": "Investors are calm.", "amber": "Investors are getting nervous.", "red": "Investors are scared."}),
    I(id="kospi_drawdown", pillar="D", kind="auto", calc=_dd("px:^KS11"), name="KOSPI drawdown from 1-year high",
      plain="South Korean stocks (heavy in AI memory chips)", unit="% below high", fmt="{:.0f}", max_age=7,
      points=[(8, 0), (20, 34), (40, 67), (55, 100)], core="edge",
      easy={"green": "South Korea's market, which is full of memory-chip makers, is holding up.",
            "amber": "South Korea's market, heavy in memory-chip makers, has fallen a lot. It often cracks first.",
            "red": "South Korea's market has crashed."}),
    I(id="ndx_trend", pillar="D", kind="auto", calc=_vs200("px:^NDX", "Nasdaq-100"), name="Nasdaq-100 vs 200-day average",
      plain="Tech index trend", unit="% vs 200d", fmt="{:+.1f}", max_age=7,
      points=[(-15, 100), (-5, 67), (0, 40), (10, 0)], core="core",
      easy={"green": "The tech-heavy index is in an uptrend.", "amber": "The tech-heavy index is close to breaking its long-term trend.",
            "red": "The tech-heavy index is in a downtrend."}),
    I(id="beat_and_fall", pillar="D", name="Nvidia: beats sold off (of last 4)", plain="Selling on good news",
      unit="of 4", fmt="{:.0f}", max_age=120, points=[(0, 0), (2, 30), (3, 45), (4, 60)], core="core",
      easy={"green": "Good results still lift share prices.",
            "amber": "Nvidia's shares have fallen after each of its last strong results. Good news is already priced in, a classic late-boom sign.",
            "red": "Even a raised forecast gets sold hard."}),
    I(id="margin_unwind", pillar="D", kind="auto", calc=margin_unwind, name="Margin debt unwinding (FINRA)",
      plain="Borrowed money being pulled out of stocks", fmt="{:.0f}", max_age=75,
      points=[(0, 0), (100, 100)],
      easy={"green": "Investors aren't being forced to sell borrowed positions.",
            "amber": "Investors are paying back stock-market loans.",
            "red": "Investors are being forced to sell as stock-market loans shrink and prices fall."}),

    # ---- E: Valuation and concentration -----------------------------------
    I(id="cape", pillar="E", name="Shiller CAPE", plain="How expensive stocks are vs 10 years of profits",
      fmt="{:.1f}", max_age=45, points=[(25, 0), (35, 34), (40, 67), (45, 100)],
      easy={"green": "Stocks are fairly priced.", "amber": "Stocks are expensive.",
            "red": "Stocks are as expensive as at the 2000 dot-com peak (one measure was 44 then)."}),
    I(id="buffett", pillar="E", kind="auto", calc=buffett, name="Buffett indicator (market value / GDP)",
      plain="Stock market size vs the economy", unit="% of GDP", fmt="{:.0f}", max_age=120,
      points=[(120, 0), (170, 34), (220, 67), (280, 100)],
      easy={"green": "The stock market's size vs the economy is normal.", "amber": "The stock market is large relative to the economy.",
            "red": "The stock market is worth far more than ever relative to the economy."}),
    I(id="forward_pe", pillar="E", name="S&P 500 forward P/E (FactSet)", plain="Price vs next year's expected profits",
      fmt="{:.1f}", max_age=30, points=[(17, 0), (22, 34), (25, 67), (28, 100)],
      easy={"green": "Prices are reasonable vs expected profits.", "amber": "Prices are high vs expected profits.",
            "red": "Prices are very high vs expected profits."}),
    I(id="top10_weight", pillar="E", name="Top 10 share of the S&P 500", plain="How much rides on a few giant stocks",
      unit="%", fmt="{:.0f}", max_age=45, points=[(25, 0), (30, 34), (35, 67), (42, 100)],
      easy={"green": "The market isn't dominated by a few stocks.",
            "amber": "A handful of giant stocks make up a big part of the market.",
            "red": "The 10 biggest companies are almost 40% of the US market, more than in 2000. When they fall, the whole index falls."}),
    I(id="concentration_trend", pillar="E", kind="auto", calc=concentration_trend, name="Equal-weight vs cap-weight S&P 500, 12 months",
      plain="Average stock vs the giants", unit="%", fmt="{:+.1f}", max_age=7,
      points=[(-20, 100), (-12, 67), (-5, 34), (5, 0)],
      easy={"green": "The average stock is keeping up with the giants.", "amber": "The average stock is falling behind the giants.",
            "red": "The giants have left the average stock far behind."}),

    # ---- F: Sentiment, positioning and leverage ---------------------------
    I(id="bofa_cash", headline=True, pillar="F", name="BofA FMS cash level", plain="How much cash big fund managers hold",
      unit="%", fmt="{:.1f}", max_age=45, points=[(3.5, 100), (4.0, 67), (4.5, 34), (5.5, 0)],
      easy={"green": "Fund managers hold plenty of cash, so there is money left to buy.",
            "amber": "Fund managers hold little cash.",
            "red": "Fund managers have almost no cash left. Historically, that has been a sell signal: few buyers remain."}),
    I(id="bofa_bullbear", pillar="F", name="BofA Bull and Bear indicator", plain="Big investors' optimism",
      fmt="{:.1f}", max_age=45, points=[(5, 0), (7, 34), (8, 67), (9.5, 100)],
      easy={"green": "Big investors are not overly optimistic.", "amber": "Big investors are quite optimistic.",
            "red": "Big investors are extremely optimistic. Historically that has been a contrarian sell signal."}),
    I(id="margin_growth", pillar="F", kind="auto", calc=margin_growth, name="FINRA margin debt, 12-month growth",
      plain="Money borrowed to buy stocks", unit="% y/y", fmt="{:+.0f}", max_age=75,
      points=[(0, 0), (20, 34), (40, 67), (60, 100)],
      easy={"green": "Borrowing to buy stocks is normal.", "amber": "Investors have borrowed a lot to buy stocks, near record amounts.",
            "red": "Borrowing to buy stocks is surging. Any fall can force selling."}),
    I(id="leveraged_etf", pillar="F", name="Leveraged ETF assets and flows", plain="Bets with built-in borrowing",
      max_age=120,
      easy={"green": "Leveraged bets are normal.", "amber": "Record money sits in leveraged funds that amplify moves both ways.",
            "red": "Money is fleeing leveraged funds during a fall, which speeds up the decline."}),
    I(id="retail_flows", pillar="F", name="Retail dip-buying in stressed names", plain="Small investors buying the dip",
      max_age=30,
      easy={"green": "Small investors aren't chasing troubled stocks.",
            "amber": "Small investors are piling into troubled AI stocks as they fall.",
            "red": "Small investors are dumping AI stocks."}),
    I(id="narrative", pillar="F", name="Narrative intensity and insider warnings", plain="Bubble talk",
      max_age=30,
      easy={"green": "Little bubble talk.", "amber": "Industry insiders and famous investors are openly warning of a bubble.",
            "red": "Bubble warnings are everywhere, including from AI company bosses."}),

    # ---- G: Macro, rates and liquidity ------------------------------------
    I(id="us10y", pillar="G", kind="auto", calc=_latest("fred:DGS10", "10-year Treasury", "{:.2f}%"),
      name="10-year Treasury yield", plain="Long-term interest rates", unit="%", fmt="{:.2f}", max_age=10,
      points=[(4.0, 0), (5.0, 34), (5.25, 67), (5.75, 100)],
      easy={"green": "Long-term interest rates are moderate.",
            "amber": "Long-term interest rates are above 5%, the highest since 2007, which makes borrowing for AI building more expensive.",
            "red": "Long-term interest rates are high enough to squeeze expensive stocks and debt-funded building."}),
    I(id="real10y", pillar="G", kind="auto", calc=_latest("fred:DFII10", "10-year real yield", "{:.2f}%"),
      name="10-year real yield", plain="Interest rates after inflation", unit="%", fmt="{:.2f}", max_age=10,
      points=[(1.5, 0), (2.25, 34), (2.75, 67), (3.25, 100)],
      easy={"green": "Interest rates after inflation are modest.", "amber": "Interest rates after inflation are high.",
            "red": "Interest rates after inflation are very high, which weighs hardest on stocks valued for future growth, like AI."}),
    I(id="cpi", pillar="G", kind="auto", calc=cpi_yoy, name="CPI inflation y/y", plain="Inflation",
      unit="% y/y", fmt="{:.1f}", max_age=50, points=[(2.5, 0), (3.0, 34), (3.5, 67), (4.5, 100)],
      easy={"green": "Inflation is under control.", "amber": "Inflation is above target.",
            "red": "Inflation is rising again, so the Fed may keep raising rates."}),
    I(id="fed_path", pillar="G", kind="auto", calc=fed_path, name="Fed funds target change, 6 months",
      plain="Is the Fed raising rates?", unit="pts", fmt="{:+.2f}", max_age=10,
      points=[(-0.5, 0), (0, 20), (0.25, 50), (0.75, 85)],
      easy={"green": "The Fed isn't raising rates.", "amber": "The Fed has started raising rates again.",
            "red": "The Fed is raising rates steadily."}),
    I(id="fed_hike_odds", pillar="G", name="Market odds of another hike by December (CME FedWatch)",
      plain="Odds of another rate rise", unit="%", fmt="{:.0f}", max_age=14,
      points=[(10, 0), (50, 34), (80, 67), (100, 85)],
      easy={"green": "Markets expect no more rate rises.", "amber": "Markets see a good chance of another rate rise.",
            "red": "Markets expect more rate rises."}),
    I(id="nfci", pillar="G", kind="auto", calc=nfci, name="Chicago Fed NFCI", plain="Overall ease of getting money",
      fmt="{:+.2f}", max_age=14, points=[(-0.6, 0), (-0.3, 34), (0, 67), (0.5, 100)],
      easy={"green": "Money is still easy to get across the financial system.",
            "amber": "Money is getting harder to get across the financial system.",
            "red": "Financial conditions are tight."}),
    I(id="yield_curve", pillar="G", kind="auto", calc=_latest("fred:T10Y3M", "10y-3m curve", "{:+.2f}pt"),
      name="Yield curve (10y minus 3m)", plain="Bond market recession signal", unit="pt", fmt="{:+.2f}", max_age=10,
      points=[(-0.5, 67), (0, 40), (0.5, 20), (1.5, 0)],
      easy={"green": "The bond market isn't signalling a recession.", "amber": "The bond market is close to signalling a recession.",
            "red": "The bond market is signalling a recession, as it did before the 2000 bust."}),
    I(id="oil", pillar="G", kind="auto", calc=_latest("fred:DCOILWTICO", "WTI oil $", "{:.0f}"),
      name="WTI crude oil", plain="Oil price", unit="$", fmt="{:.0f}", max_age=10,
      points=[(70, 0), (90, 34), (110, 67), (130, 100)],
      easy={"green": "Oil is cheap enough not to worry about.",
            "amber": "Oil is expensive (around $100), which feeds inflation.",
            "red": "Oil prices are high enough to hurt the economy."}),
]

BY_ID = {i["id"]: i for i in INDICATORS}
