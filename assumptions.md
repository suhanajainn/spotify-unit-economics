# Model assumptions

Spotify doesn't report three of the inputs our unit-economics model needs. This file
records what each one means, how we estimate it, the range we use, and why.

Every number is tagged:

| Tag | Meaning |
|---|---|
| **[REPORTED]** | Taken directly from a Spotify shareholder deck, via `data/quarterly_metrics.csv` |
| **[EXTERNAL]** | Published by a third party, not by Spotify. Cited, not verified against a primary source |
| **[ASSUMPTION]** | Our judgment. Not reported by anyone |
| **[DERIVED]** | Calculated from reported data **plus at least one assumption**. Only as good as the assumption |

Anything tagged [ASSUMPTION] or [DERIVED] is an estimate, not data.

---

## 1. Monthly Premium churn

### What it means
The share of Premium subscribers at the start of a month who cancel or lapse during
that month. This is gross churn: people who leave, before counting new sign-ups.
Spotify reports subscriber totals but not how many people leave.

### How we'll estimate it
Spotify last published churn in its 2018 IPO filing, and the data never shows gross
adds and cancellations separately, so we can't derive churn from it. We set a range
based on the external reference points below and apply it to all quarters at once.

Reference points:
- Q4 2015 **7.5%**, Q4 2016 **6.0%**, Q4 2017 **5.1%** monthly Premium churn **[EXTERNAL]**.
  These come from Spotify's 2018 F-1 filing, as quoted by
  [Statista](https://de.statista.com/statistik/daten/studie/812548/umfrage/churn-rate-von-spotify-premium-weltweit),
  [ChartMogul](https://chartmogul.com/blog/metrics-behind-spotifys-ipo/) and
  [Music Business Worldwide](https://musicbusinessworldwide.com/spotify-really-doesnt-want-you-to-stop-subscribing-and-its-handing-out-google-home-minis-to-help-ensure-you-dont).
  We haven't checked them against the filing itself. Spotify attributed the decline to
  Family and Student plans, which retain better.
- About **2%** average monthly churn for US Spotify subscribers in 2024, per Antenna **[EXTERNAL]**
  ([Mezha, June 2024](https://mezha.ua/en/2024/06/03/spotify-demonstrates-record-breaking-loyalty-rates-the-service-practically-does-not-lose-users/)).
  This covers the US only, and the US is one of Spotify's most mature markets.

### Range

| Case | Monthly churn | Tag |
|---|---|---|
| Low | **2.0%** | [ASSUMPTION] |
| Base | **3.0%** | [ASSUMPTION] |
| High | **4.0%** | [ASSUMPTION] |

### Why
- **Low 2.0%:** Antenna's US figure. A global average can't plausibly be lower than
  the most mature major market, because the subscriber base increasingly comes from
  emerging markets, which usually churn more.
- **High 4.0%:** Below the last disclosed figure of 5.1% (2017). Churn was falling
  about one point a year then, and the subscriber mix has since moved further toward
  Family and Student plans, which Spotify said retain better.
- **Base 3.0%:** The midpoint. We have no source pinning the global figure, so we
  don't claim more precision than that.

We hold churn constant across quarters. We have no data to model how it changes over time.

---

## 2. Cost to acquire a Premium subscriber (CAC)

### What it means
Sales and marketing spend per gross new Premium subscriber, i.e. what it costs to
win one paying subscriber.

### How we'll estimate it

```
subscribers lost to churn (quarter) = monthly churn × 3 × average Premium subscribers in the quarter
average Premium subscribers         = (opening subscribers + closing subscribers) / 2
gross new subscribers               = net subscriber growth + subscribers lost to churn
CAC                                 = sales and marketing expense / gross new subscribers
```

Inputs:
- Premium subscribers and sales and marketing expense **[REPORTED]**: columns
  `premium_subscribers_m` and `sales_and_marketing_eur_m`
- Monthly churn **[ASSUMPTION]**: section 1

Multiplying monthly churn by 3 slightly overstates quarterly losses compared with
compounding. At these churn levels the difference is small, and the simple version
is easier to audit.

### Range
We use the trailing twelve months, Q3 2025–Q2 2026. Single quarters are noisy (see caveats).

| Case | Churn used | S&M, LTM **[REPORTED]** | Gross new subs, LTM **[DERIVED]** | CAC **[DERIVED]** |
|---|---|---|---|---|
| Low CAC | 4.0% (high churn) | €1,480M | 162.2M | **€9.12** |
| Base | 3.0% | €1,480M | 127.7M | **€11.59** |
| High CAC | 2.0% (low churn) | €1,480M | 93.1M | **€15.89** |

Net subscriber growth over the same period was 24M **[REPORTED]** (276M → 300M).

By quarter, base case (3.0% churn). Every CAC value is **[DERIVED]**:

| Quarter | Opening subs | Closing subs | Net adds | S&M (€M) | Lost to churn (M) | Gross adds (M) | CAC (€) |
|---|---|---|---|---|---|---|---|
| Q4 2023 | 226 | 236 | 10 | 432 | 20.8 | 30.8 | 14.03 |
| Q1 2024 | 236 | 239 | 3 | 324 | 21.4 | 24.4 | 13.29 |
| Q2 2024 | 239 | 246 | 7 | 343 | 21.8 | 28.8 | 11.90 |
| Q3 2024 | 246 | 252 | 6 | 332 | 22.4 | 28.4 | 11.69 |
| Q4 2024 | 252 | 263 | 11 | 393 | 23.2 | 34.2 | 11.50 |
| Q1 2025 | 263 | 268 | 5 | 314 | 23.9 | 28.9 | 10.87 |
| Q2 2025 | 268 | 276 | 8 | 364 | 24.5 | 32.5 | 11.21 |
| Q3 2025 | 276 | 281 | 5 | 349 | 25.1 | 30.1 | 11.61 |
| Q4 2025 | 281 | 290 | 9 | 399 | 25.7 | 34.7 | 11.50 |
| Q1 2026 | 290 | 293 | 3 | 342 | 26.2 | 29.2 | 11.70 |
| Q2 2026 | 293 | 300 | 7 | 390 | 26.7 | 33.7 | 11.58 |

Subscriber and S&M columns are **[REPORTED]**. Net adds is arithmetic on reported data.
Q3 2023 is left out because its opening subscriber count (Q2 2023) isn't in our dataset.

### Why, and caveats
- **CAC moves opposite to churn.** Higher churn means more gross adds are needed for
  the same net growth, so the same spend is spread over more people. Scenarios must
  pair them consistently: high churn goes with low CAC. Never combine low churn with
  low CAC.
- **Churn drives the result.** In the base case about 80% of gross adds are
  replacements for churned subscribers, so the churn assumption matters more than the
  reported data.
- **S&M isn't only for Premium.** Reported sales and marketing also covers
  ad-supported user growth, brand marketing and the advertising sales team. Charging
  all of it to Premium gross adds overstates Premium CAC. We keep the full figure
  because it's the definition we chose, and it's a conservative (high) CAC.
- **Rounding.** Spotify reports subscribers in whole millions. Quarterly net adds of
  3–11M can therefore be off by up to ±1M, which is why we use the LTM figure rather
  than a single quarter.
- **Free trials.** Some gross adds are trial conversions that cost little marketing
  spend. We don't adjust for this.

---

## 3. Price elasticity of Premium demand

### What it means
The percentage change in Premium subscribers for a 1% change in Premium price, all
else equal. An elasticity of −0.5 means a 10% price increase loses about 5% of
subscribers relative to where they would otherwise have been, through more
cancellations, fewer sign-ups, or both. Values closer to zero mean subscribers are
less sensitive to price.

### How we'll estimate it
Spotify doesn't publish one, and its quarterly data can't identify one. Prices rose
market by market while subscribers kept growing for other reasons: new markets,
product changes and marketing. Aggregate totals can't separate those effects. So
elasticity is a pure assumption, checked for consistency against what was reported:

- The Q3 2023 deck mentions "price increases we began implementing late in the
  quarter". Every deck from Q4 2023 to Q2 2026 says ARPU (excluding FX) was "driven
  by price increase benefits" **[REPORTED]**. This means price increases were rolled
  out throughout the period.
- Over the same period Premium subscribers grew 9–16% Y/Y in every quarter **[REPORTED]**.
  Subscriber growth slowed from 16% (Q3 2023) to 9% (Q1–Q2 2026) **[REPORTED]**,
  but we can't tell how much of that slowdown was caused by price.
- No deck reports churn, or subscriber losses, linked to a price increase.

### Range

| Case | Elasticity | Tag |
|---|---|---|
| Low sensitivity | **−0.2** | [ASSUMPTION] |
| Base | **−0.5** | [ASSUMPTION] |
| High sensitivity | **−1.0** | [ASSUMPTION] |

### Why
- **The base −0.5 is inelastic** because subscribers kept growing at high single digits
  or better through three years of repeated price increases. Strongly elastic demand
  would have been hard to square with that.
- **Low sensitivity −0.2** reflects Spotify's position in mature markets, where
  playlists, libraries and Family plans make switching costly.
- **High sensitivity −1.0** allows for the possibility that the subscriber slowdown
  since 2023 was mostly caused by price, and for more price-sensitive emerging
  markets, which are a growing share of the base.
- These values come from no study or dataset. They are judgment calls bounded by the
  reported data above. Treat the model's price scenarios as sensitivity analysis, not
  forecasts.
- **Premium ARPU isn't price.** ARPU also moves with FX, plan mix (Family, Duo,
  Student) and market mix. Spotify says in every deck that mix partly offset price
  increases. Don't use ARPU changes as a stand-in for price changes when applying
  this elasticity.
