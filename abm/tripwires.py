"""Event tripwires (brief section 11). Each confirmed one lifts the regime a level.

A tripwire fires only when a person records it with two credible sources
(`python monitor.py tripwire fire <id> --source URL --source URL`).
"""

TRIPWIRES = {
    # Demand and capex
    "capex_cut": ("A hyperscaler cuts capex guidance or talks of 'digestion', 'optimization' or 'pause'",
                  "A big tech company cut its AI spending plans."),
    "nvidia_guide": ("Nvidia guides revenue flat or down sequentially, or cuts margin guidance beyond memory costs",
                     "Nvidia expects its sales to stop growing."),
    "dc_cancellations": ("A hyperscaler cancels data-center leases, abandons a campus or sells excess capacity",
                         "Big tech is cancelling data centers it no longer needs."),
    "memory_price_fall": ("DRAM contract prices fall q/q, HBM prices are cut, or Samsung/SK Hynix cut capex",
                          "Memory chip prices have started falling."),
    "gpu_rent_collapse": ("H100 rental index falls 25% from its high, or used-GPU prices collapse",
                          "Prices to rent AI chips have collapsed."),
    # Financing
    "lab_down_round": ("OpenAI or Anthropic raises at a lower valuation, delays/withdraws an IPO, prices below its last round, or trades below its IPO price",
                       "A leading AI lab had to accept a lower price for its shares."),
    "openai_defers": ("OpenAI defers or renegotiates compute commitments (Oracle, CoreWeave, AMD, Broadcom, Microsoft)",
                      "OpenAI is backing out of, or delaying, promised computing purchases."),
    "neocloud_distress": ("A neocloud misses a payment, seeks covenant relief, launches a distressed exchange or needs a rescue",
                          "An AI chip-rental company can't pay its debts on the original terms."),
    "oracle_junk": ("Oracle is downgraded to high yield, or cuts or defers data-center plans",
                    "Oracle's debt was downgraded to 'junk' or it scaled back its data centers."),
    "private_credit_gate": ("A new private-credit redemption gate, a failed data-center financing, or insurers and pensions pulling back",
                            "Private lenders are blocking withdrawals or refusing to fund data centers."),
    "guarantee_called": ("A supplier's customer-financing guarantee is called (Nvidia, Broadcom)",
                         "Nvidia or Broadcom had to pay out on a guarantee for a customer."),
    # Shocks
    "efficiency_shock": ("A model matches the frontier at a fraction of the cost, knocking Nvidia down 10%+ in a day",
                         "A much cheaper AI model appeared and made chip demand look overestimated."),
    "fed_hawkish": ("A Fed hike with hawkish guidance while the 10-year is above 5.25%, or a disorderly bond sell-off",
                    "The Fed raised rates and signalled more while long-term rates are very high."),
    "geopolitics": ("China-Taiwan escalation, new export controls, or grid emergency limits on data centers",
                    "A political shock (Taiwan, export bans, power limits) is hitting the chip supply chain."),
    # Both halves are needed: markets shrugged off the July 2026 Hugging Face breach, and
    # the lasting damage would come from the rules and liability that follow a disaster.
    "ai_incident": ("An AI system causes deaths or major damage AND governments respond with emergency rules, "
                    "deployment pauses, bans or liability rulings that slow AI use",
                    "An AI disaster hurt people, and governments are now restricting AI because of it."),
    # Accounting
    "depreciation": ("A hyperscaler shortens server useful lives or impairs AI assets",
                     "A big tech company admitted its AI equipment is worth less than its books said."),
    "going_concern": ("Going-concern language or auditor problems at an AI infrastructure company",
                      "Auditors doubt an AI infrastructure company can survive."),
}

# Watch topics: slower signs that AI is getting harder or costlier to use. The headline scan
# and the AI review show them, but they never fire and never change the risk level.
WATCH = {
    "insurer_exclusions": ("Insurers exclude, withdraw or sharply reprice cover for AI-caused damage",
                           "Insurers are refusing to cover damage caused by AI."),
    "agent_pauses": ("Large companies pause or roll back AI agents after an incident or failure",
                     "Big companies are pulling back AI agents after something went wrong."),
    "ai_laws": ("New AI laws, enforcement or court rulings with real teeth: deployment limits, licensing, "
                "liability for AI makers",
                "New AI laws or court rulings are making AI slower or more expensive to use."),
}

# Stages of a typical bust (brief section 3); order can vary.
STAGES = [
    ("sentiment", "Extreme optimism and crowded bets", "Investors are all-in and very optimistic."),
    ("weak_links", "Stress at the weakest borrowers", "The most indebted AI companies struggle to borrow."),
    ("narrow", "Narrow leadership and selling on good news", "Only a few giants carry the market, and good news no longer lifts prices."),
    ("capex_cut", "A first spending cut or supplier warning", "A big tech company cuts spending, or a chip supplier warns."),
    ("broad_credit", "Broad credit spreads widening", "Borrowing gets harder for all risky companies, not just AI ones."),
    ("downgrades", "Earnings downgrades spreading beyond AI", "Profit forecasts fall across the whole economy."),
]
