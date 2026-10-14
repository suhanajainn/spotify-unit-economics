# Spotify Premium unit economics

An outside-in analysis of whether Spotify's Premium subscribers are profitable and whether a price increase
would pay off, built from 12 quarters of public investor data. It includes an interactive dashboard and a
pricing recommendation.

**Dashboard:** runs locally with one command; see [How to run](#how-to-run).
**Recommendation memo:** [memo.md](memo.md) · **Full findings:** [outputs/summary.md](outputs/summary.md)

## The question

Do Spotify's Premium unit economics work, are they improving, and should Spotify raise prices again?

## Approach

1. **Data collection.** Downloaded Spotify's quarterly shareholder decks (Q3 2023–Q2 2026) from its
   investor site. The results page blocks scripted access, so the file list came from the site's own data feed.
2. **Extraction.** [`scripts/extract_metrics.py`](scripts/extract_metrics.py) parses the PDFs into
   [`data/quarterly_metrics.csv`](data/quarterly_metrics.csv): subscribers, ARPU, segment revenue and margin,
   sales and marketing, operating income. Values are cross-checked wherever the decks give a second source,
   e.g. segment revenue must sum to reported total revenue. Spotify's 2026 segment restatement is kept in separate columns, so trend charts
   compare like with like.
3. **Assumptions.** Spotify doesn't report churn, acquisition cost or price elasticity.
   [`assumptions.md`](assumptions.md) sets a low/base/high range for each, with sources and reasoning, and tags
   every number as reported, external, assumption or derived.
4. **Model.** [`scripts/model.py`](scripts/model.py) calculates gross profit per subscriber, LTV, acquisition
   cost, LTV:CAC, payback and price-increase scenarios for every churn and elasticity case.
5. **Self-critique.** Reviewed the analysis as a skeptical CFO would, then fixed what didn't hold up. Two
   headline results turned out to be artifacts of the formulas: the falling acquisition cost was largely
   mechanical, and LTV:CAC mostly restated a reported ratio. Results now lead with what reported data supports.
6. **Dashboard and memo.** [`app.py`](app.py) (Streamlit) lets users change the assumptions and simulate price
   increases. [`memo.md`](memo.md) is a one-page recommendation to Spotify's pricing team.

## Key findings

All amounts in euros. *(est.)* marks figures that depend on assumptions.

- **Premium is more profitable per subscriber.** Gross profit per subscriber averaged €1.63/month over the
  last four quarters, up from €1.59, as Premium gross margin rose from 33.7% to 34.4%.
- **Past price increases stuck.** ARPU in euros was flat only because of exchange rates. In constant currency
  it grew 3.8% Y/Y, while subscribers grew 9–16% Y/Y through three years of price increases.
- **Acquisition spend is well covered.** Premium gross profit covered all sales and marketing 3.8x. A new
  subscriber pays back acquisition cost in 5.6–9.8 months *(est.)*.
- **A 5–10% price increase is likely profitable.** It adds about 4.5% to long-run Premium gross profit at 10%
  and base elasticity *(est.)*. It only loses money if demand is about as price-sensitive as −1.0. The
  verdict depends on elasticity, not on the unverifiable churn rate.
- **First-year results can't confirm success.** Gross profit rises in year one in every scenario, including
  the ones that lose money long-term, so a price test has to be judged on cohort churn against holdout markets.

## Limitations

- Spotify doesn't report churn, acquisition cost or elasticity. These are assumed ranges, and elasticity in
  particular comes from judgment, not a study.
- All results are global averages. Public data can't separate markets or plans.
- Reported sales and marketing includes share-price-driven Social Charges and one-off severance that
  Spotify doesn't break out by line, so acquisition cost is approximate and probably overstated.
- LTV is undiscounted and assumes current ARPU and margin hold for the whole subscriber lifetime.
- Segment restatement: 2023 segment figures exist only on Spotify's old definition.

## Tech stack

- **Python 3.9**
- **pdfplumber**: PDF table and text extraction
- **pandas**: data handling
- **Plotly** and **Streamlit**: interactive dashboard
- **Git / GitHub**

## How to run

```bash
git clone https://github.com/suhanajainn/spotify-unit-economics.git
cd spotify-unit-economics
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at http://localhost:8501. It reads only the CSV files already in the repo, so it needs
no downloads or extraction.

To rebuild the data from the source PDFs in `data/raw/`:

```bash
pip install pdfplumber
python scripts/extract_metrics.py   # PDFs -> data/quarterly_metrics.csv
python scripts/model.py             # -> outputs/unit_economics.csv, scenarios.csv, summary.md
```

## Repository layout

```
app.py                      Streamlit dashboard
memo.md                     Pricing recommendation
assumptions.md              Churn, acquisition cost and elasticity assumptions
data/raw/                   Spotify shareholder decks (PDF)
data/quarterly_metrics.csv  Extracted reported metrics
scripts/extract_metrics.py  PDF -> CSV extraction
scripts/model.py            Unit economics and price scenarios
outputs/                    Model results and written findings
```

Data source: Spotify Technology S.A. quarterly shareholder decks, [investors.spotify.com](https://investors.spotify.com).
