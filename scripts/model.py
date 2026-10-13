"""Quarterly Premium unit economics and ad-supported monetization.

Reads data/quarterly_metrics.csv (reported data) and the base-case churn from
assumptions.md. Writes outputs/unit_economics.csv and outputs/summary.md.

Every output except ad-supported revenue per user depends on the churn
assumption, so it is an estimate, not reported data.

Definitions (monthly unless noted):
  gross profit per sub/month = Premium ARPU × Premium gross margin
  lifetime (months)          = 1 / monthly churn
  LTV                        = Premium ARPU × Premium gross margin × lifetime
  subs lost to churn         = churn × 3 × average Premium subs in the quarter
  gross new subs             = net subscriber growth + subs lost to churn
  CAC                        = sales and marketing / gross new subs
  LTV:CAC                    = LTV / CAC
  payback (months)           = CAC / gross profit per sub per month
  ad revenue per ad user     = Ad-Supported revenue / average Ad-Supported MAUs / 3

Segment basis: Spotify reclassified some revenue from Ad-Supported to Premium
effective 2026 (see assumptions.md / quarterly_metrics.csv). Premium gross
margin uses the restated (2026-basis) figure where available and the as-reported
figure for earlier quarters; the restatement moved Premium margin by at most
0.1 pt in every quarter where both exist. Ad-Supported revenue uses restated
figures only, because the restatement moved it by up to ~4%; quarters without
a restated figure are left blank.

The numbers in summary.md are computed. The descriptive sentences (seasonality,
mid-2025 ARPU dip, etc.) were checked against data through Q2 2026; recheck
them when new quarters are added.
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS_CSV = ROOT / "data" / "quarterly_metrics.csv"
ASSUMPTIONS_MD = ROOT / "assumptions.md"
OUT_CSV = ROOT / "outputs" / "unit_economics.csv"
OUT_MD = ROOT / "outputs" / "summary.md"

OUTPUT_COLUMNS = [
    "quarter",
    "premium_subscribers_m",
    "premium_arpu_eur",
    "premium_gross_margin_pct",
    "premium_gross_margin_basis",
    "gross_profit_per_sub_month_eur",
    "monthly_churn_pct",
    "lifetime_months",
    "ltv_eur",
    "net_new_subs_m",
    "subs_lost_to_churn_m",
    "gross_new_subs_m",
    "sales_and_marketing_eur_m",
    "cac_eur",
    "ltv_to_cac",
    "payback_months",
    "ad_supported_revenue_restated_eur_m",
    "avg_ad_supported_maus_m",
    "ad_revenue_per_ad_user_month_eur",
]


def read_base_churn(path):
    """Base-case monthly churn (as a fraction) from section 1 of assumptions.md."""
    text = path.read_text()
    section = re.search(r"^## 1\. Monthly Premium churn$(.*?)^## 2\.", text, re.M | re.S)
    if not section:
        sys.exit(f"Couldn't find the churn section in {path}")
    base = re.search(r"^\| Base \| \*\*(\d+(?:\.\d+)?)%\*\* \|", section.group(1), re.M)
    if not base:
        sys.exit(f"Couldn't find the base-case churn row in {path}")
    return float(base.group(1)) / 100


def num(value):
    return float(value) if value not in ("", None) else None


def build_rows(metrics, churn):
    rows = []
    previous = None
    for m in metrics:
        subs = num(m["premium_subscribers_m"])
        arpu = num(m["premium_arpu_eur"])
        if m["premium_gross_margin_restated_pct"]:
            gm, gm_basis = num(m["premium_gross_margin_restated_pct"]), "restated (2026 basis)"
        else:
            gm, gm_basis = num(m["premium_gross_margin_pct"]), "as reported (pre-2026 basis)"
        sm = num(m["sales_and_marketing_eur_m"])

        gp_month = arpu * gm / 100 if None not in (arpu, gm) else None
        lifetime = 1 / churn
        ltv = gp_month * lifetime if gp_month is not None else None

        net_new = lost = gross_new = cac = None
        if previous is not None:
            opening = num(previous["premium_subscribers_m"])
            net_new = subs - opening
            lost = churn * 3 * (opening + subs) / 2
            gross_new = net_new + lost
            cac = sm / gross_new if gross_new > 0 else None

        ltv_cac = ltv / cac if None not in (ltv, cac) else None
        payback = cac / gp_month if None not in (cac, gp_month) else None

        ad_rev = num(m["ad_supported_revenue_restated_eur_m"])
        avg_ad_maus = ad_per_user = None
        if previous is not None:
            avg_ad_maus = (num(previous["ad_supported_maus_m"]) + num(m["ad_supported_maus_m"])) / 2
            if ad_rev is not None:
                ad_per_user = ad_rev / avg_ad_maus / 3

        rows.append({
            "quarter": m["quarter"],
            "premium_subscribers_m": subs,
            "premium_arpu_eur": arpu,
            "premium_gross_margin_pct": gm,
            "premium_gross_margin_basis": gm_basis,
            "gross_profit_per_sub_month_eur": gp_month,
            "monthly_churn_pct": churn * 100,
            "lifetime_months": lifetime,
            "ltv_eur": ltv,
            "net_new_subs_m": net_new,
            "subs_lost_to_churn_m": lost,
            "gross_new_subs_m": gross_new,
            "sales_and_marketing_eur_m": sm,
            "cac_eur": cac,
            "ltv_to_cac": ltv_cac,
            "payback_months": payback,
            "ad_supported_revenue_restated_eur_m": ad_rev,
            "avg_ad_supported_maus_m": avg_ad_maus,
            "ad_revenue_per_ad_user_month_eur": ad_per_user,
        })
        previous = m
    return rows


def fmt(value, places=2):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return f"{value:.{places}f}"


def write_csv(rows):
    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            writer.writerow([fmt(row[c], 3) if isinstance(row[c], float) else row[c] for c in OUTPUT_COLUMNS])


def label(quarter):
    year, q = quarter.split("_")
    return f"{q} {year}"


def first_last(rows, key):
    filled = [r for r in rows if r[key] is not None]
    return filled[0], filled[-1]


def ltm(rows, key):
    """Mean of the last four quarters of a column."""
    values = [r[key] for r in rows[-4:]]
    return sum(values) / len(values) if None not in values else None


def change_word(start, end):
    if abs(end - start) / abs(start) < 0.02:
        return "was roughly flat"
    return "rose" if end > start else "fell"


def write_summary(rows, churn):
    gp_a, gp_b = first_last(rows, "gross_profit_per_sub_month_eur")
    ltv_a, ltv_b = first_last(rows, "ltv_eur")
    cac_a, cac_b = first_last(rows, "cac_eur")
    # Compare ad revenue per user like-for-like: earliest same calendar quarter as the latest.
    _, ad_b = first_last(rows, "ad_revenue_per_ad_user_month_eur")
    ad_a = next(r for r in rows if r["ad_revenue_per_ad_user_month_eur"] is not None
                and r["quarter"][-2:] == ad_b["quarter"][-2:])
    arpu_a, arpu_b = first_last(rows, "premium_arpu_eur")
    gm_a, gm_b = first_last(rows, "premium_gross_margin_pct")

    cac_ltm = sum(r["sales_and_marketing_eur_m"] for r in rows[-4:]) / sum(r["gross_new_subs_m"] for r in rows[-4:])
    ltv_ltm = ltm(rows, "ltv_eur")
    gp_ltm = ltm(rows, "gross_profit_per_sub_month_eur")
    cac_range = [r["cac_eur"] for r in rows if r["cac_eur"] is not None]
    ratio_range = [r["ltv_to_cac"] for r in rows if r["ltv_to_cac"] is not None]
    payback_range = [r["payback_months"] for r in rows if r["payback_months"] is not None]
    lost_share = sum(r["subs_lost_to_churn_m"] for r in rows[-4:]) / sum(r["gross_new_subs_m"] for r in rows[-4:])
    ad_ratio = ltm(rows, "ad_revenue_per_ad_user_month_eur") / ltm(rows, "premium_arpu_eur")
    last = rows[-1]

    md = f"""# Spotify unit economics: key trends

Generated by `scripts/model.py` from `data/quarterly_metrics.csv` and the base-case
assumptions in `assumptions.md`. Full quarterly results are in `outputs/unit_economics.csv`.

**Read this first:** apart from ARPU, gross margin and ad revenue per user, every number
below depends on the assumed monthly churn of **{churn * 100:.1f}%** (base case, an
assumption, not reported data). Lifetime, LTV, acquisition cost, LTV:CAC and payback are
estimates. The trends in them come from reported data; their levels come from the
assumption.

## Premium: profit per subscriber is rising

- **Gross profit per Premium subscriber per month {change_word(gp_a['gross_profit_per_sub_month_eur'], gp_b['gross_profit_per_sub_month_eur'])}**
  from €{gp_a['gross_profit_per_sub_month_eur']:.2f} in {label(gp_a['quarter'])} to
  €{gp_b['gross_profit_per_sub_month_eur']:.2f} in {label(gp_b['quarter'])}.
- Most of that came from **gross margin**, which went from {gm_a['premium_gross_margin_pct']:.1f}% to
  {gm_b['premium_gross_margin_pct']:.1f}%. **ARPU** {change_word(arpu_a['premium_arpu_eur'], arpu_b['premium_arpu_eur'])},
  from €{arpu_a['premium_arpu_eur']:.2f} to €{arpu_b['premium_arpu_eur']:.2f}. It fell for part of 2025 even though
  prices rose; Spotify attributes that to FX and plan/market mix.
- Because lifetime is held at {1 / churn:.1f} months in every quarter, **LTV moves exactly with gross profit
  per subscriber**: €{ltv_a['ltv_eur']:.0f} in {label(ltv_a['quarter'])} to €{ltv_b['ltv_eur']:.0f} in
  {label(ltv_b['quarter'])}. That rise reflects higher margin and ARPU, not any change in retention, which
  we can't observe.

## Acquisition cost is stable, so returns improved

- **Estimated acquisition cost** {change_word(cac_a['cac_eur'], cac_b['cac_eur'])}, from €{cac_a['cac_eur']:.2f} in
  {label(cac_a['quarter'])} to €{cac_b['cac_eur']:.2f} in {label(cac_b['quarter'])}. Across all quarters it ranged
  €{min(cac_range):.2f}–€{max(cac_range):.2f}; over the last four quarters it was
  €{cac_ltm:.2f}. Single quarters are noisy because subscribers are reported in whole millions.
- Acquisition cost fell through 2023–24 and has been roughly level since, because sales and
  marketing spend grew more slowly than the subscriber base.
- **LTV-to-CAC** ranged {min(ratio_range):.1f}x–{max(ratio_range):.1f}x and was
  {last['ltv_to_cac']:.1f}x in {label(last['quarter'])}. **Payback** ranged
  {min(payback_range):.1f}–{max(payback_range):.1f} months and was {last['payback_months']:.1f} months in
  {label(last['quarter'])}. Both improved because acquisition cost fell in 2023–24 and profit per
  subscriber rose throughout. Both dipped in mid-2025 when ARPU fell.
- About {lost_share * 100:.0f}% of estimated gross new subscribers in the last four quarters
  replaced people who churned, so the churn assumption drives the acquisition-cost level more
  than the reported data does.

## Ad-supported: low revenue per user, and uneven

- **Ad-Supported revenue per ad-supported user** {change_word(ad_a['ad_revenue_per_ad_user_month_eur'], ad_b['ad_revenue_per_ad_user_month_eur'])}
  from €{ad_a['ad_revenue_per_ad_user_month_eur']:.2f} a month in {label(ad_a['quarter'])} to
  €{ad_b['ad_revenue_per_ad_user_month_eur']:.2f} in {label(ad_b['quarter'])} (same quarter, to avoid seasonality).
  It is calculated from reported data only (no assumptions)
  on the restated 2026 segment basis, so the series starts in Q1 2024.
- It follows a strong seasonal pattern: Q4 is the high point each year and Q1 the low point,
  matching advertising budgets.
- Ad-supported users grew faster than ad revenue, so revenue per user has drifted down outside the
  seasonal swings.
- Over the last four quarters an ad-supported user brought in about {ad_ratio * 100:.0f}% of the revenue of a Premium
  subscriber per month. Ad-supported users matter mainly as a pipeline into Premium, not as a revenue
  source on their own; their value depends mostly on how many convert.

## Caveats

- **Churn is constant.** We have no data on how retention changed over the period, so lifetime is the
  same in every quarter. If churn actually fell over the period, LTV rose faster than shown and
  acquisition cost fell less (or rose) compared with what's shown.
- **Acquisition cost uses all sales and marketing spend.** Part of it goes to ad-supported growth,
  brand and the ad sales team, so Premium acquisition cost is overstated and LTV:CAC understated.
- **LTV is undiscounted** and assumes today's ARPU and margin hold for the subscriber's whole life.
- **Q3 2023 has no acquisition cost** because the opening subscriber count (Q2 2023) isn't in our
  dataset. **Q3–Q4 2023 have no ad revenue per user** because Spotify hasn't published restated
  figures for them.
- **Premium gross margin** uses restated figures from Q1 2024 and as-reported figures for Q3–Q4 2023.
  The restatement changed Premium margin by at most 0.1 point, so the series is comparable.
- See `assumptions.md` for the low and high cases.
"""
    OUT_MD.write_text(md)


def main():
    with open(METRICS_CSV) as f:
        metrics = list(csv.DictReader(f))
    churn = read_base_churn(ASSUMPTIONS_MD)
    rows = build_rows(metrics, churn)
    write_csv(rows)
    write_summary(rows, churn)

    headers = ["GP/sub/mo", "Life mo", "LTV", "CAC", "LTV:CAC", "Payback", "Ad €/user/mo"]
    keys = ["gross_profit_per_sub_month_eur", "lifetime_months", "ltv_eur", "cac_eur",
            "ltv_to_cac", "payback_months", "ad_revenue_per_ad_user_month_eur"]
    print(f"Base-case monthly churn from assumptions.md: {churn * 100:.1f}%\n")
    print("quarter  " + "  ".join(h.rjust(12) for h in headers))
    for row in rows:
        print(f"{row['quarter']}  " + "  ".join((fmt(row[k]) or "—").rjust(12) for k in keys))
    print(f"\nWrote {OUT_CSV.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
