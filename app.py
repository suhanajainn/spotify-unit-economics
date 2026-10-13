"""Streamlit dashboard: Spotify Premium unit economics.

Run with: streamlit run app.py

Reads data/quarterly_metrics.csv and assumptions.md, and reuses the
calculations in scripts/model.py so the dashboard and outputs/ agree.
All amounts are in euros, as reported by Spotify.
"""

import csv
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import model  # noqa: E402

REPO_URL = "https://github.com/suhanajainn/spotify-unit-economics"
ASSUMPTIONS_URL = f"{REPO_URL}/blob/main/assumptions.md"

# Reference categorical palette (slots 1-3), stepped per mode.
PALETTE = {
    "light": {"series": ["#2a78d6", "#eb6834", "#1baf7a"], "grid": "#e4e3df", "text": "#52514e"},
    "dark": {"series": ["#3987e5", "#d95926", "#199e70"], "grid": "#383835", "text": "#c3c2b7"},
}

st.set_page_config(page_title="Spotify Premium unit economics", layout="wide")


# ---------------------------------------------------------------- data

@st.cache_data
def load():
    with open(model.METRICS_CSV) as f:
        metrics = list(csv.DictReader(f))
    churn_cases = model.read_churn_cases(model.ASSUMPTIONS_MD)
    rows = model.build_rows(metrics, churn_cases)
    return metrics, churn_cases, rows


metrics, churn_cases, rows = load()
df = pd.DataFrame(rows)
raw = pd.DataFrame(metrics)
for col in raw.columns:
    if col not in ("quarter", "reported_segment_basis", "source_file", "restated_source"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
df["label"] = df["quarter"].map(model.label)
raw["label"] = raw["quarter"].map(model.label)

latest, prior = rows[-4:], rows[-8:-4]
lw, pw = model.window_label(latest), model.window_label(prior)
gp_ltm = model.mean(latest, "gross_profit_per_sub_month_eur")
gp_prior = model.mean(prior, "gross_profit_per_sub_month_eur")
gm_ltm = model.mean(latest, "premium_gross_margin_pct")
arpu_ltm = model.mean(latest, "premium_arpu_eur")
pgp_ltm = model.total(latest, "premium_gross_profit_eur_m")
sm_ltm = model.total(latest, "sales_and_marketing_eur_m")
coverage_ltm, coverage_prior = pgp_ltm / sm_ltm, model.total(prior, "premium_gross_profit_eur_m") / model.total(prior, "sales_and_marketing_eur_m")
est = {case: model.window_estimates(latest, c) for case, c in churn_cases.items()}
subs_now = rows[-1]["premium_subscribers_m"]

theme = "dark" if getattr(getattr(st.context, "theme", None), "type", "light") == "dark" else "light"
colors = PALETTE[theme]


def eur_delta(value, places=0, unit=""):
    """Signed euro amount with the sign before the symbol: +€2, −€440M."""
    sign = "+" if value >= 0 else "−"
    return f"{sign}€{abs(value):,.{places}f}{unit}"


def line_chart(series, y_title, y_format, hover_format, prefix="", suffix=""):
    """Line chart, one y-axis. series: list of (name, x labels, y values)."""
    fig = go.Figure()
    for i, (name, x, y) in enumerate(series):
        color = colors["series"][i]
        fig.add_trace(go.Scatter(
            x=x, y=y, name=name, mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=8, color=color),
            hovertemplate=f"{name}: {hover_format}<extra></extra>",
            connectgaps=False,
        ))
    # Direct labels at each series' last point (identity never by color alone),
    # nudged apart vertically when end points are close.
    if len(series) > 1:
        ends = []
        for name, x, y in series:
            last = [(xi, yi) for xi, yi in zip(x, y) if pd.notna(yi)][-1]
            ends.append((last[1], last[0], name))
        values = [v for _, _, y in series for v in y if pd.notna(v)]
        min_gap = (max(values) - min(values)) * 0.08
        ends.sort()
        shifts = [0] * len(ends)
        for i in range(1, len(ends)):
            if ends[i][0] - ends[i - 1][0] < min_gap:
                shifts[i - 1] -= 7
                shifts[i] += 7
        for (yv, xv, name), shift in zip(ends, shifts):
            fig.add_annotation(x=xv, y=yv, text=name, showarrow=False, xanchor="left", xshift=8,
                               yshift=shift, font=dict(color=colors["text"], size=12))
    fig.update_layout(
        height=360, margin=dict(l=10, r=120 if len(series) > 1 else 10, t=40, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=colors["text"])),
        showlegend=len(series) > 1,
        yaxis=dict(title=y_title, tickformat=y_format, tickprefix=prefix, ticksuffix=suffix, gridcolor=colors["grid"], zeroline=False),
        xaxis=dict(showgrid=False, type="category", tickangle=-45),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------- 1. header

st.markdown(f"[View the code and data on GitHub]({REPO_URL})")
st.title("Do Spotify's Premium unit economics work, and are they improving?")
st.caption("All amounts are in euros (€), as reported by Spotify. Data: Q3 2023 – "
           f"{model.label(rows[-1]['quarter'])} shareholder decks.")

st.markdown(
    f"""
**Yes, and they've improved, but the case rests mostly on margin, not on anything we can measure about
retention.** In reported data, Premium gross profit per subscriber averaged **€{gp_ltm:.2f} a month** over
{lw}, up from €{gp_prior:.2f} a year earlier, because Premium gross margin rose to {gm_ltm:.1f}%.
Over the same period Premium gross profit covered all sales and marketing spend **{coverage_ltm:.1f}x**
(up from {coverage_prior:.1f}x). Spotify doesn't report churn or acquisition cost, so lifetime value and
payback are estimates: with monthly churn of {churn_cases['low'] * 100:.0f}–{churn_cases['high'] * 100:.0f}%,
LTV-to-CAC is **{est['high']['ratio']:.1f}–{est['low']['ratio']:.1f}x** and a new subscriber pays back
acquisition cost in **{est['high']['payback']:.1f}–{est['low']['payback']:.1f} months**. Treat those as
ranges, not precise figures. Reported sales and marketing is also distorted by share-price-driven
payroll taxes, and those flattered the latest year.
"""
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Premium subscribers", f"{subs_now:.0f}M", help="Reported, " + model.label(rows[-1]["quarter"]))
c2.metric("Gross profit / sub / month", f"€{gp_ltm:.2f}",
          f"{eur_delta(gp_ltm - gp_prior, 2)} vs prior year", help=f"Reported data: Premium ARPU × Premium gross margin, average over {lw}")
c3.metric("Premium gross profit ÷ S&M", f"{coverage_ltm:.1f}x",
          f"{coverage_ltm - coverage_prior:+.1f}x vs prior year", help=f"Reported data, total over {lw}")
c4.metric("Payback, new subscriber (estimate)", f"{est['high']['payback']:.1f}–{est['low']['payback']:.1f} mo",
          help="Estimate. Range across churn cases in assumptions.md", delta=None)
st.caption(f"Gross profit and coverage are averages/totals over the last four quarters ({lw}), compared with the "
           f"four before ({pw}).")

# ---------------------------------------------------------------- 2. trends

st.header("Trends")
st.caption("Reported data. Each chart has a table view below it.")

t1, t2, t3 = st.columns(3)
with t1:
    st.subheader("Users (millions)")
    st.plotly_chart(line_chart(
        [("Premium subscribers", raw["label"], raw["premium_subscribers_m"]),
         ("Ad-supported MAUs", raw["label"], raw["ad_supported_maus_m"])],
        "Millions", ",.0f", "%{y:.0f}M"), use_container_width=True)
    with st.expander("Table"):
        st.dataframe(raw[["label", "premium_subscribers_m", "ad_supported_maus_m"]].rename(columns={
            "label": "Quarter", "premium_subscribers_m": "Premium subscribers (M)",
            "ad_supported_maus_m": "Ad-supported MAUs (M)"}), hide_index=True)

with t2:
    st.subheader("Premium ARPU (€ per month)")
    st.plotly_chart(line_chart(
        [("Premium ARPU", raw["label"], raw["premium_arpu_eur"])],
        "€ per subscriber per month", ".2f", "€%{y:.2f}", prefix="€"), use_container_width=True)
    st.caption(f"Euro ARPU dipped in 2025 because of exchange rates. In constant currency it grew "
               f"{model.mean(latest, 'premium_arpu_yoy_constant_currency_pct'):+.1f}% Y/Y on average over {lw} "
               "(as stated in the decks).")
    with st.expander("Table"):
        st.dataframe(raw[["label", "premium_arpu_eur", "premium_arpu_yoy_constant_currency_pct"]].rename(columns={
            "label": "Quarter", "premium_arpu_eur": "Premium ARPU (€)",
            "premium_arpu_yoy_constant_currency_pct": "Y/Y growth, constant currency (%)"}), hide_index=True)

with t3:
    st.subheader("Gross margin (%)")
    st.plotly_chart(line_chart(
        [("Premium", df["label"], df["premium_gross_margin_pct"]),
         ("Ad-Supported", raw["label"], raw["ad_supported_gross_margin_restated_pct"]),
         ("Total", raw["label"], raw["total_gross_margin_pct"])],
        "Gross margin", ".0f", "%{y:.1f}%", suffix="%"), use_container_width=True)
    st.caption("Segments on Spotify's 2026 definition. Ad-Supported starts in Q1 2024 because restated "
               "2023 figures weren't published. Premium Q3–Q4 2023 use the original definition "
               "(the restatement moved Premium margin by ≤0.1 pt).")
    with st.expander("Table"):
        gm_table = pd.DataFrame({
            "Quarter": df["label"], "Premium (%)": df["premium_gross_margin_pct"],
            "Premium basis": df["premium_gross_margin_basis"],
            "Ad-Supported, restated (%)": raw["ad_supported_gross_margin_restated_pct"],
            "Total (%)": raw["total_gross_margin_pct"],
        })
        st.dataframe(gm_table, hide_index=True)

# ---------------------------------------------------------------- 3. unit economics

st.header("Unit economics")
st.markdown(
    f"Uses gross profit per Premium subscriber of **€{gp_ltm:.2f} a month** (reported, average over {lw}). "
    "Churn and acquisition cost are **assumptions**; move the sliders to test them. "
    f"Defaults are the base case from [assumptions.md]({ASSUMPTIONS_URL})."
)

s1, s2 = st.columns(2)
with s1:
    churn_pct = st.slider("Monthly Premium churn (%)", 1.0, 8.0, churn_cases["base"] * 100, 0.1,
                          help=f"Assumption. assumptions.md range: {churn_cases['low'] * 100:.1f}% (low) – "
                               f"{churn_cases['high'] * 100:.1f}% (high).")
churn = churn_pct / 100
derived_cac = model.window_estimates(latest, churn)["cac"]
with s2:
    link_cac = st.checkbox("Derive acquisition cost from churn", value=True,
                           help="CAC = sales and marketing ÷ (net new subscribers + subscribers lost to churn), "
                                f"over {lw}. Higher churn means more gross adds, so a lower cost per add.")
    cac = st.slider("Acquisition cost per new Premium subscriber (€)", 2.0, 40.0,
                    round(derived_cac, 1) if link_cac else round(est["base"]["cac"], 1), 0.1,
                    disabled=link_cac,
                    help="Assumption. Untick the box above to set it yourself.")
    if link_cac:
        cac = derived_cac

lifetime = 1 / churn
ltv = gp_ltm * lifetime
ratio = ltv / cac
payback = cac / gp_ltm

m1, m2, m3, m4 = st.columns(4)
m1.metric("Lifetime (estimate)", f"{lifetime:.0f} months", help="1 ÷ monthly churn")
m2.metric("LTV (estimate)", f"€{ltv:.0f}", help="Gross profit per subscriber per month × lifetime. Undiscounted.")
m3.metric("LTV : CAC (estimate)", f"{ratio:.1f}x")
m4.metric("Payback (estimate)", f"{payback:.1f} months", help="Acquisition cost ÷ gross profit per subscriber per month")

if payback > lifetime:
    st.error("At these settings a subscriber leaves, on average, before paying back their acquisition cost.")
st.caption(
    "Why LTV:CAC hardly changes when you move churn with acquisition cost linked: higher churn shortens "
    "lifetime but also raises the implied number of new subscribers, so CAC falls too. Most of the ratio "
    f"is Premium gross profit ÷ sales and marketing ({coverage_ltm:.1f}x, reported). Payback is the "
    "number that really depends on churn. Acquisition cost uses all sales and marketing spend, which "
    "also funds ad-supported growth and brand, so it overstates Premium acquisition cost."
)

# ---------------------------------------------------------------- 4. price simulator

st.header("Price increase simulator")
st.markdown(
    "What happens to gross profit if Spotify raises Premium prices and some subscribers leave because of it? "
    f"Starts from the churn above ({churn_pct:.1f}%) and today's {subs_now:.0f}M subscribers."
)

p1, p2 = st.columns(2)
with p1:
    price_pct = st.slider("Price increase (%)", 0.0, 30.0, 10.0, 0.5)
with p2:
    churn_up_pp = st.slider("Increase in monthly churn (percentage points)", 0.0, 3.0, 0.2, 0.05,
                            help="Extra subscribers cancelling each month because of the higher price, "
                                 "added to the churn above.")

new_churn = churn + churn_up_pp / 100
new_gp = gp_ltm * (1 + price_pct / 100)
ltv_before, ltv_after = gp_ltm / churn, new_gp / new_churn
break_even_pp = price_pct / 100 * churn * 100  # churn increase at which LTV is unchanged


def cohort_gross_profit(n0, gp, c, months=12):
    """Gross profit from today's subscribers over `months`, with no new sign-ups (€M)."""
    return sum(n0 * (1 - c) ** t * gp for t in range(months))


gp12_before = cohort_gross_profit(subs_now, gp_ltm, churn)
gp12_after = cohort_gross_profit(subs_now, new_gp, new_churn)

r1, r2, r3 = st.columns(3)
r1.metric("Lifetime gross profit per subscriber", f"€{ltv_after:.0f}", f"{eur_delta(ltv_after - ltv_before)} vs €{ltv_before:.0f} today")
r2.metric("12-month gross profit from today's subscribers", f"€{gp12_after:,.0f}M",
          eur_delta(gp12_after - gp12_before, unit="M"))
r3.metric("Break-even churn increase", f"{break_even_pp:.2f} pp",
          help="The churn increase at which lifetime gross profit per subscriber is unchanged: price % × current churn.")

if abs(ltv_after - ltv_before) < 0.5:
    st.info(f"≈ Break-even: lifetime gross profit per subscriber is roughly unchanged. "
            f"Break-even is a churn increase of {break_even_pp:.2f} percentage points.")
elif ltv_after > ltv_before:
    st.success(f"✓ Profitable: the price increase raises lifetime gross profit per subscriber. "
               f"It would stay profitable up to a churn increase of {break_even_pp:.2f} percentage points.")
else:
    st.error(f"✗ Not profitable: the extra churn outweighs the higher price. Break-even is a churn "
             f"increase of {break_even_pp:.2f} percentage points.")

st.caption(
    "How this works: gross margin % is held constant, because most of Spotify's music costs are a share "
    "of revenue, so gross profit per subscriber rises by the price increase %. It assumes ARPU rises in "
    "line with price; in practice plan and market mix dilute that. The 12-month figure follows today's "
    "subscribers only (no new sign-ups) and is undiscounted. Both the churn response and the price pass-"
    "through are assumptions, not data."
)

# ---------------------------------------------------------------- 5. data and assumptions

st.header("Data and assumptions")
d1, d2 = st.columns(2)
with d1:
    st.subheader("Reported data")
    st.markdown(
        "Taken directly from Spotify's quarterly shareholder decks "
        f"([extraction script]({REPO_URL}/blob/main/scripts/extract_metrics.py)). Nothing estimated.\n\n"
        "- Premium subscribers, ad-supported MAUs, Premium ARPU\n"
        "- Segment revenue and gross margin (original and restated to Spotify's 2026 segment definition)\n"
        "- Sales and marketing expense, operating income\n"
        "- Social Charges in operating expenses; constant-currency ARPU growth\n\n"
        "Calculated from reported data only (no assumptions): gross profit per subscriber, "
        "Premium gross profit ÷ S&M, ad revenue per ad-supported user."
    )
    shown = raw[["label", "premium_subscribers_m", "ad_supported_maus_m", "premium_arpu_eur",
                 "premium_revenue_restated_eur_m", "premium_gross_margin_restated_pct",
                 "total_gross_margin_pct", "sales_and_marketing_eur_m", "opex_social_charges_eur_m",
                 "operating_income_eur_m"]].rename(columns={
        "label": "Quarter", "premium_subscribers_m": "Premium subs (M)", "ad_supported_maus_m": "Ad MAUs (M)",
        "premium_arpu_eur": "ARPU (€)", "premium_revenue_restated_eur_m": "Premium revenue, restated (€M)",
        "premium_gross_margin_restated_pct": "Premium GM, restated (%)", "total_gross_margin_pct": "Total GM (%)",
        "sales_and_marketing_eur_m": "S&M (€M)", "opex_social_charges_eur_m": "Social Charges in opex (€M)",
        "operating_income_eur_m": "Operating income (€M)"})
    st.dataframe(shown, hide_index=True)
    st.caption("Restated columns are blank for 2023: Spotify only published restated 2023 segment figures in "
               "chart images. Full data: data/quarterly_metrics.csv.")

with d2:
    st.subheader("Estimates and assumptions")
    st.markdown(
        f"Spotify doesn't report these. Ranges and reasoning are in [assumptions.md]({ASSUMPTIONS_URL}).\n\n"
        f"| Assumption | Low | Base | High |\n|---|---|---|---|\n"
        f"| Monthly Premium churn | {churn_cases['low'] * 100:.1f}% | {churn_cases['base'] * 100:.1f}% | "
        f"{churn_cases['high'] * 100:.1f}% |\n"
        f"| Acquisition cost (derived, {lw}) | €{est['high']['cac']:.2f} | €{est['base']['cac']:.2f} | "
        f"€{est['low']['cac']:.2f} |\n"
        "| Price elasticity | −0.2 | −0.5 | −1.0 |\n\n"
        "Acquisition cost moves opposite to churn: the low-cost case goes with high churn.\n\n"
        "**Estimates that depend on these:** lifetime, LTV, acquisition cost, LTV:CAC, payback, "
        "and everything in the price simulator.\n\n"
        "**Known weaknesses**\n"
        "- Churn is held constant; we can't tell whether retention improved.\n"
        "- Acquisition cost uses all S&M, which also funds ad-supported growth and brand, and includes "
        "Social Charges and the Q4 2023 severance charges, which Spotify doesn't split out by line.\n"
        "- LTV is undiscounted and assumes today's ARPU and margin for the whole lifetime.\n"
        "- Subscribers are reported in whole millions, so single-quarter figures are noisy."
    )
    st.markdown(f"Full critique and findings: [outputs/summary.md]({REPO_URL}/blob/main/outputs/summary.md)")
