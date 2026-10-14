# Memo: Should Spotify raise Premium prices?

**To:** Premium Pricing team · **Re:** Price increase recommendation · **Basis:** public shareholder decks, Q3 2023–Q2 2026
All amounts in euros. Figures marked *(est.)* depend on assumptions; everything else is reported data.
Sources: `outputs/summary.md`, `outputs/scenarios.csv`, `assumptions.md`.

## Context
Spotify has raised Premium prices in market after market since mid-2023. Every quarterly deck since Q4 2023
credits ARPU growth to "price increase benefits". Over the same period Premium subscribers grew 9–16% Y/Y,
reaching 300M in Q2 2026. The question is whether another increase would add gross profit or cost more in
lost subscribers than it brings in.

## Key findings
1. **Each subscriber is worth more than a year ago.** Gross profit per Premium subscriber averaged
   **€1.63/month** over Q3 2025–Q2 2026, up from €1.59, as Premium gross margin rose from 33.7% to **34.4%**.
2. **Past increases are sticking.** Euro ARPU was flat (€4.71 → €4.72) only because of exchange rates. In
   constant currency ARPU grew **+3.8% Y/Y** on average over the last four quarters.
3. **Acquisition spend is well covered.** Premium gross profit covered all sales and marketing **3.8x**
   (up from 3.6x). Payback on a new subscriber is **5.6–9.8 months** *(est.)*.
4. **The decision depends on elasticity, not churn.** With gross margin held constant, long-run gross
   profit changes by (1 + price rise) × (1 − |elasticity| × price rise), at any churn level. A 10% rise pays
   off as long as elasticity is less negative than **−0.91**.

| Price rise | Elasticity −0.2 | −0.5 (base) | −1.0 | First-year gross profit, today's subscribers |
|---|---|---|---|---|
| 5% | +4.0% | +2.4% | −0.2% | +€205M to +€240M *(est.)* |
| 10% | +7.8% | **+4.5%** | −1.0% | +€402M to +€480M *(est.)* |
| 20% | +15.2% | +8.0% | −4.0% | +€764M to +€956M *(est.)* |

*Change in long-run Premium gross profit (est.).*

## Recommendation
**Raise Premium prices by 5–10%, rolled out in stages with holdout markets.** At the base elasticity a
10% rise adds about 4.5% to long-run Premium gross profit *(est.)*. Only demand as sensitive as −1.0 would
make it lose money, and three years of subscriber growth through repeated increases argue against that. We
favor 5–10% over 20%: the extra upside comes with a larger downside, and our elasticity range is least
reliable far beyond past increases. **Judge the result on cohort churn and new sign-ups against the
holdouts, not on first-year revenue.**

## Risks
- **Early results look good either way.** First-year gross profit rises in every scenario, including the
  loss-making ones, because extra churn builds slowly. A revenue check after 12 months proves nothing.
- **Less than the full increase reaches ARPU.** Plan and market mix diluted past increases, and a lower
  pass-through narrows the margin of safety.
- **Downgrades and competition.** Subscribers may move to cheaper plans or the free tier.
  Rivals bundling music could raise elasticity in key markets.
- **Royalty terms.** We assume music costs move with revenue. Where costs are fixed per subscriber,
  margin gains are *larger* than modeled. If rights holders win higher rates after an increase, they're smaller.

## Data Spotify has internally that would sharpen this
- Churn and cancellation timing by cohort, market and plan, especially around past price changes.
- Results from past price changes in markets that did and didn't get them, to measure elasticity directly.
- Gross adds, trial conversion and downgrade-to-free rates, plus ad revenue retained from downgraders.
- ARPU and price pass-through by plan and market; royalty terms (revenue share vs per-subscriber minimums).
- Sales and marketing split between Premium and ad-supported, excluding Social Charges.

## Limitations
This is an outside-in model. Spotify doesn't report churn, acquisition cost or elasticity. Our churn
range (2–4%/month) and elasticity range (−0.2 to −1.0) are assumptions, and the elasticity range comes
from no study. Results are global averages and can't separate markets or plans. LTV is undiscounted.
Reported sales and marketing includes Social Charges and one-off charges that Spotify doesn't break out by
line.
