"""Quarterly Premium unit economics and ad-supported monetization.

Reads data/quarterly_metrics.csv (reported data) and the low/base/high monthly
churn from assumptions.md. Writes outputs/unit_economics.csv and
outputs/summary.md.

Two kinds of output, kept apart:

Reported-data only (no assumptions):
  gross profit per sub/month    = Premium ARPU × Premium gross margin
  Premium gross profit          = Premium revenue × Premium gross margin
  Premium gross profit / S&M    = how many times Premium gross profit covers all S&M
  S&M per Premium sub/month     = S&M / average Premium subs / 3
  ad revenue per ad user/month  = Ad-Supported revenue / average Ad-Supported MAUs / 3

Estimates (depend on assumed churn; computed for each churn case):
  lifetime (months)             = 1 / monthly churn
  LTV                           = gross profit per sub/month × lifetime
  subs lost to churn            = churn × 3 × average Premium subs in the quarter
  gross new subs                = net subscriber growth + subs lost to churn
  CAC                           = S&M / gross new subs
  LTV:CAC                       = LTV / CAC
  payback (months)              = CAC / gross profit per sub/month

Why LTV:CAC is mostly not about churn: substituting the formulas,
  LTV:CAC = 3 × GP/sub/month × avg subs / S&M  +  GP/sub/month × net adds / (churn × S&M)
          ≈ Premium gross profit / S&M          +  a growth term
The first term is reported data and doesn't depend on churn; the churn
assumption only affects the smaller second term. Payback, by contrast, moves
almost in proportion to churn.

Segment basis: Spotify reclassified some revenue from Ad-Supported to Premium
effective 2026. Premium gross margin uses the restated (2026-basis) figure where
available and the as-reported figure for Q3-Q4 2023; the restatement moved
Premium margin by at most 0.1 pt wherever both exist. Ad-Supported revenue uses
restated figures only, because the restatement moved it by up to ~4%.

The numbers in summary.md are computed. The descriptive sentences were checked
against data through Q2 2026; recheck them when new quarters are added.
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

CASES = ("low", "base", "high")  # churn cases from assumptions.md

# Operating-expense one-offs stated in the decks that distort S&M in a quarter.
# Social Charges come from the CSV; this covers charges the CSV doesn't hold.
ONE_OFF_OPEX = {
    "2023_Q4": "€143M net severance and real-estate charges in operating expenses (Q4 2023 deck); split by line not disclosed",
}
SOCIAL_CHARGE_FLAG_EUR_M = 50  # flag quarters where |Social Charges in opex| is at least this


def read_churn_cases(path):
    """Low/base/high monthly churn (fractions) from section 1 of assumptions.md."""
    text = path.read_text()
    section = re.search(r"^## 1\. Monthly Premium churn$(.*?)^## 2\.", text, re.M | re.S)
    if not section:
        sys.exit(f"Couldn't find the churn section in {path}")
    cases = {}
    for case in CASES:
        m = re.search(rf"^\| {case.capitalize()} \| \*\*(\d+(?:\.\d+)?)%\*\* \|", section.group(1), re.M)
        if not m:
            sys.exit(f"Couldn't find the {case}-case churn row in {path}")
        cases[case] = float(m.group(1)) / 100
    return cases


def num(value):
    return float(value) if value not in ("", None) else None


def divide(a, b):
    return a / b if None not in (a, b) and b != 0 else None


def build_rows(metrics, churn):
    rows = []
    previous = None
    for m in metrics:
        subs = num(m["premium_subscribers_m"])
        arpu = num(m["premium_arpu_eur"])
        sm = num(m["sales_and_marketing_eur_m"])
        if m["premium_gross_margin_restated_pct"]:
            gm, gm_basis = num(m["premium_gross_margin_restated_pct"]), "restated (2026 basis)"
            prem_rev = num(m["premium_revenue_restated_eur_m"])
        else:
            gm, gm_basis = num(m["premium_gross_margin_pct"]), "as reported (pre-2026 basis)"
            prem_rev = num(m["premium_revenue_eur_m"])

        gp_month = arpu * gm / 100 if None not in (arpu, gm) else None
        prem_gp = prem_rev * gm / 100 if None not in (prem_rev, gm) else None

        opening = num(previous["premium_subscribers_m"]) if previous else None
        avg_subs = (opening + subs) / 2 if opening is not None else None
        net_new = subs - opening if opening is not None else None

        ad_rev = num(m["ad_supported_revenue_restated_eur_m"])
        avg_ad_maus = None
        if previous:
            avg_ad_maus = (num(previous["ad_supported_maus_m"]) + num(m["ad_supported_maus_m"])) / 2

        social = num(m["opex_social_charges_eur_m"])
        flags = []
        if m["quarter"] in ONE_OFF_OPEX:
            flags.append(ONE_OFF_OPEX[m["quarter"]])
        if social is not None and abs(social) >= SOCIAL_CHARGE_FLAG_EUR_M:
            kind = "credit" if social < 0 else "charge"
            flags.append(f"Social Charges {kind} of €{abs(social):.0f}M in operating expenses (line split not disclosed)")

        row = {
            "quarter": m["quarter"],
            "premium_subscribers_m": subs,
            "avg_premium_subscribers_m": avg_subs,
            "net_new_subs_m": net_new,
            "premium_arpu_eur": arpu,
            "premium_arpu_yoy_constant_currency_pct": num(m["premium_arpu_yoy_constant_currency_pct"]),
            "premium_gross_margin_pct": gm,
            "premium_gross_margin_basis": gm_basis,
            "gross_profit_per_sub_month_eur": gp_month,
            "premium_gross_profit_eur_m": prem_gp,
            "sales_and_marketing_eur_m": sm,
            "opex_social_charges_eur_m": social,
            "sm_distortion_flag": "; ".join(flags),
            "premium_gp_to_sm": divide(prem_gp, sm),
            "sm_per_avg_sub_month_eur": divide(sm, avg_subs * 3) if avg_subs else None,
            "ad_supported_revenue_restated_eur_m": ad_rev,
            "avg_ad_supported_maus_m": avg_ad_maus,
            "ad_revenue_per_ad_user_month_eur": divide(ad_rev, avg_ad_maus * 3) if avg_ad_maus else None,
        }
        for case, c in churn.items():
            ltv = gp_month / c if gp_month is not None else None
            cac = None
            if avg_subs is not None:
                gross_new = net_new + c * 3 * avg_subs
                cac = sm / gross_new if gross_new > 0 else None
            row[f"monthly_churn_pct_{case}"] = c * 100
            row[f"lifetime_months_{case}"] = 1 / c
            row[f"ltv_eur_{case}"] = ltv
            row[f"cac_eur_{case}"] = cac
            row[f"ltv_to_cac_{case}"] = divide(ltv, cac)
            row[f"payback_months_{case}"] = divide(cac, gp_month)
        rows.append(row)
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
    columns = list(rows[0])
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([fmt(row[c], 3) for c in columns])


def label(quarter):
    year, q = quarter.split("_")
    return f"{q} {year}"


def window_label(rows):
    return f"{label(rows[0]['quarter'])}–{label(rows[-1]['quarter'])}"


def mean(rows, key):
    values = [r[key] for r in rows]
    return sum(values) / len(values) if values and None not in values else None


def total(rows, key):
    values = [r[key] for r in rows]
    return sum(values) if values and None not in values else None


def window_estimates(window, c):
    """CAC, LTV, LTV:CAC and payback over a multi-quarter window for monthly churn c."""
    sm = total(window, "sales_and_marketing_eur_m")
    net_new = total(window, "net_new_subs_m")
    gross_new = net_new + sum(c * 3 * r["avg_premium_subscribers_m"] for r in window)
    gp = mean(window, "gross_profit_per_sub_month_eur")
    cac = sm / gross_new
    ltv = gp / c
    return {"cac": cac, "ltv": ltv, "ratio": ltv / cac, "payback": cac / gp,
            "gross_new": gross_new, "net_new": net_new}


def write_summary(rows, churn):
    latest, prior = rows[-4:], rows[-8:-4]
    lw, pw = window_label(latest), window_label(prior)

    gp_l, gp_p = mean(latest, "gross_profit_per_sub_month_eur"), mean(prior, "gross_profit_per_sub_month_eur")
    gm_l, gm_p = mean(latest, "premium_gross_margin_pct"), mean(prior, "premium_gross_margin_pct")
    arpu_l, arpu_p = mean(latest, "premium_arpu_eur"), mean(prior, "premium_arpu_eur")
    arpu_cc_l = mean(latest, "premium_arpu_yoy_constant_currency_pct")
    arpu_eur_change = (arpu_l / arpu_p - 1) * 100
    pgp_l, pgp_p = total(latest, "premium_gross_profit_eur_m"), total(prior, "premium_gross_profit_eur_m")
    sm_l, sm_p = total(latest, "sales_and_marketing_eur_m"), total(prior, "sales_and_marketing_eur_m")
    sc_l, sc_p = total(latest, "opex_social_charges_eur_m"), total(prior, "opex_social_charges_eur_m")
    smps_l, smps_p = mean(latest, "sm_per_avg_sub_month_eur"), mean(prior, "sm_per_avg_sub_month_eur")
    est = {case: window_estimates(latest, churn[case]) for case in CASES}
    est_prior = window_estimates(prior, churn["base"])
    replace_share = 1 - est["base"]["net_new"] / est["base"]["gross_new"]

    # Ad-supported: compare the latest quarter with the earliest same calendar quarter.
    ad_key = "ad_revenue_per_ad_user_month_eur"
    ad_b = rows[-1]
    ad_a = next(r for r in rows if r[ad_key] is not None and r["quarter"][-2:] == ad_b["quarter"][-2:])
    ad_ratio = mean(latest, ad_key) / arpu_l
    q4s = [r for r in rows if r["quarter"].endswith("Q4") and r[ad_key] is not None]
    q1s = [r for r in rows if r["quarter"].endswith("Q1") and r[ad_key] is not None]

    flag_lines = "\n".join(f"- **{label(q)}:** {note}." for q, note in ONE_OFF_OPEX.items())
    sc_rows = "\n".join(
        f"| {label(r['quarter'])} | {r['sales_and_marketing_eur_m']:.0f} | {r['opex_social_charges_eur_m']:+.0f} |"
        for r in rows
    )
    q4_2023 = next(r for r in rows if r["quarter"] == "2023_Q4")

    def est_row(case):
        e = est[case]
        return (f"| {case.capitalize()} ({churn[case] * 100:.1f}%) | €{e['cac']:.2f} | €{e['ltv']:.0f} | "
                f"{e['ratio']:.1f}x | {e['payback']:.1f} |")

    md = f"""# Spotify unit economics: key findings

Generated by `scripts/model.py` from `data/quarterly_metrics.csv` and `assumptions.md`.
Quarterly detail is in `outputs/unit_economics.csv`. Data runs through {label(rows[-1]['quarter'])}.

Comparisons use the latest four quarters ({lw}) against the four before ({pw}), not
single quarters, to smooth out seasonality, rounding and one-off charges.

## Bottom line

1. **Premium is more profitable per subscriber. This is reported data.** Gross profit per
   subscriber per month averaged €{gp_l:.2f} over {lw}, up from €{gp_p:.2f}, because Premium
   gross margin rose from {gm_p:.1f}% to {gm_l:.1f}%.
2. **Premium gross profit covered all sales and marketing spend {pgp_l / sm_l:.1f}x** over {lw},
   up from {pgp_p / sm_p:.1f}x. Also reported data, and it's most of what the LTV:CAC figure below
   is really measuring.
3. **LTV:CAC of {est['high']['ratio']:.1f}x–{est['low']['ratio']:.1f}x and payback of
   {est['high']['payback']:.1f}–{est['low']['payback']:.1f} months are estimates.** Payback depends heavily on the
   churn assumption; LTV:CAC hardly does (see section 2).
4. **Marketing efficiency didn't clearly improve, and reported S&M likely understates the latest
   year.** Reported S&M rose {(sm_l / sm_p - 1) * 100:.1f}% while subscribers grew, so S&M per subscriber
   edged down. But Social Charges (payroll taxes on stock compensation, driven by the share price)
   added €{sc_p:.0f}M to operating expenses over {pw} and were a net credit of €{-sc_l:.0f}M
   over {lw}. Spotify doesn't say how much of that sits in S&M; whatever share does means
   underlying S&M grew faster than reported.

## 1. Premium profitability (reported data)

| | {pw} | {lw} |
|---|---|---|
| Premium gross margin (avg) | {gm_p:.1f}% | {gm_l:.1f}% |
| Premium ARPU (avg) | €{arpu_p:.2f} | €{arpu_l:.2f} |
| Gross profit per subscriber per month (avg) | €{gp_p:.2f} | €{gp_l:.2f} |
| Premium gross profit (total) | €{pgp_p:,.0f}M | €{pgp_l:,.0f}M |
| Sales and marketing (total) | €{sm_p:,.0f}M | €{sm_l:,.0f}M |

- The gain came from **margin**. Euro ARPU {'fell' if arpu_eur_change < 0 else 'rose'} {abs(arpu_eur_change):.1f}% between the two
  periods, while constant-currency ARPU growth averaged {arpu_cc_l:+.1f}% Y/Y over {lw}
  (as stated in the decks). The euro weakness in 2025 was mostly exchange rates, not pricing.
- Premium gross profit here is revenue × the margin rounded to one decimal, so it can differ from
  Spotify's own segment gross profit by a few million euros.

## 2. Acquisition cost, LTV and payback (estimates)

These depend on assumed monthly churn, which Spotify doesn't report (see `assumptions.md`).
Over {lw}:

| Churn case | CAC | LTV | LTV:CAC | Payback (months) |
|---|---|---|---|---|
{est_row('low')}
{est_row('base')}
{est_row('high')}

How to read this:

- **LTV:CAC barely moves with churn because it's mostly a reported ratio in disguise.** With our
  formulas, LTV:CAC ≈ Premium gross profit ÷ S&M ({pgp_l / sm_l:.1f}x) plus a term for net subscriber
  growth. Higher churn shortens lifetime but raises the implied number of gross adds, and the two
  almost cancel. The base-case {est['base']['ratio']:.1f}x is no more precise than "Premium gross profit covers
  S&M about {pgp_l / sm_l:.0f} times, plus credit for growth".
- **Payback is where churn matters.** It ranges {est['high']['payback']:.1f}–{est['low']['payback']:.1f} months across the cases.
- **A falling CAC is mostly arithmetic.** In the base case {replace_share * 100:.0f}% of estimated gross adds are
  replacements for assumed churn, and assumed churn grows with the subscriber base. If S&M is flat,
  CAC falls automatically as the base grows. Base-case CAC went from €{est_prior['cac']:.2f} ({pw}) to
  €{est['base']['cac']:.2f} ({lw}). The assumption-free equivalent is **S&M per average Premium
  subscriber per month: €{smps_p:.2f}, then €{smps_l:.2f}**.
- **LTV is undiscounted** and assumes today's ARPU and margin for the whole lifetime. With constant
  churn, LTV is just gross profit per subscriber × {1 / churn['base']:.0f} months; its trend adds no
  information beyond section 1.

### Sales and marketing is distorted in several quarters

Reported S&M includes one-off and share-price-driven charges that aren't acquisition spend.
Spotify discloses them only for operating expenses as a whole, so we can't remove them from S&M
without guessing. We leave S&M as reported and flag the quarters instead.

Social Charges by quarter (negative = credit). The `sm_distortion_flag` column in the CSV marks
quarters where they're €{SOCIAL_CHARGE_FLAG_EUR_M}M or more either way.

| Quarter | S&M (€M) | Social Charges in all operating expenses (€M) |
|---|---|---|
{sc_rows}

One-off charges:
{flag_lines}

Consequences:
- Trends that start at Q4 2023 (base-case CAC €{q4_2023['cac_eur_base']:.2f}, the highest in the series) overstate the
  improvement, because that quarter carries severance charges.
- Comparing {lw} with {pw} flatters the latest period: operating expenses swung by
  €{sc_p - sc_l:.0f}M from Social Charges alone. Any share of that in S&M means underlying S&M,
  CAC and payback are higher in the latest period than shown.

## 3. Ad-supported (reported data)

- **Ad-Supported revenue per ad-supported user per month was €{ad_b[ad_key]:.2f} in {label(ad_b['quarter'])},
  down from €{ad_a[ad_key]:.2f} in {label(ad_a['quarter'])}** (same quarter, to avoid seasonality). Ad-supported
  users grew faster than ad revenue.
- It's about {ad_ratio * 100:.0f}% of Premium ARPU (average over {lw}).
- Seasonal: Q4 was the highest quarter ({', '.join(f"€{r[ad_key]:.2f}" for r in q4s)}) and Q1 the lowest
  ({', '.join(f"€{r[ad_key]:.2f}" for r in q1s)}) in each year we have. Only {len(q4s)} Q4s are on the restated
  basis, so treat the pattern as indicative.
- **This overstates revenue per ad-supported user.** The Ad-Supported segment includes podcast
  advertising, and podcast ads also reach Premium subscribers, but we divide by ad-supported
  users only.
- We have no data on how many ad-supported users convert to Premium, so this analysis can't
  value the free tier as a pipeline.

## What this analysis can't tell you

- **Whether retention improved or worsened.** Churn is an assumption held constant.
- **True Premium acquisition cost.** S&M also funds ad-supported growth, brand and the ad sales team,
  and includes the charges above. Our CAC overstates Premium CAC, on a noisy base.
- **Q3 2023 acquisition cost**, because the Q2 2023 subscriber count isn't in our data, and **2023
  ad revenue per user**, because Spotify hasn't published restated 2023 segment figures.
- Subscriber counts are reported in whole millions, so single-quarter net adds (3–11M) carry up to
  ±1M of rounding.
"""
    OUT_MD.write_text(md)


def main():
    with open(METRICS_CSV) as f:
        metrics = list(csv.DictReader(f))
    churn = read_churn_cases(ASSUMPTIONS_MD)
    rows = build_rows(metrics, churn)
    write_csv(rows)
    write_summary(rows, churn)

    headers = ["GP/sub/mo", "GP/S&M", "S&M/sub/mo", "CAC", "LTV:CAC", "Payback", "Ad €/user/mo"]
    keys = ["gross_profit_per_sub_month_eur", "premium_gp_to_sm", "sm_per_avg_sub_month_eur", "cac_eur_base",
            "ltv_to_cac_base", "payback_months_base", "ad_revenue_per_ad_user_month_eur"]
    print("Churn cases from assumptions.md: " + ", ".join(f"{k} {v * 100:.1f}%" for k, v in churn.items()))
    print("CAC, LTV:CAC and payback below are base case.\n")
    print("quarter  " + "  ".join(h.rjust(12) for h in headers) + "  flag")
    for row in rows:
        flag = "*" if row["sm_distortion_flag"] else ""
        print(f"{row['quarter']}  " + "  ".join((fmt(row[k]) or "—").rjust(12) for k in keys) + f"  {flag}")
    print("\n* S&M distorted by one-off or Social Charges; see summary.md")
    print(f"\nWrote {OUT_CSV.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
