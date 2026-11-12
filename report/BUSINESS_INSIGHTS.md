# OLA Rides — Business Insights

Four business use cases, each answered with the actual numbers from the cleaned
dataset (103,024 bookings, July 2024, Bengaluru). Every figure below is
reproducible from `data/ola_cleaned.csv`, `sql/queries.sql` or `eda/eda_summary.json`.

---

## Use case 1 — Peak demand hours & driver allocation

### What the data says

| Window | Bookings | Share |
|---|---|---|
| Late Night (00–05) | 21,416 | 20.8% |
| Afternoon (12–16) | 17,301 | 16.8% |
| Early Morning (05–09) | 17,213 | 16.7% |
| Night (20–24) | 17,080 | 16.6% |
| Evening Peak (16–20) | 17,061 | 16.6% |
| Morning (09–12) | 12,953 | 12.6% |

Top three hours by volume: **12:00 (4,408)**, **15:00 (4,376)**, **08:00 (4,374)**.
Hourly volume ranges only from **4,176 to 4,408** — a spread of just 5.6%.

### The insight

**Demand is remarkably flat.** There is no sharp commuter peak to exploit: the
busiest hour is only 5.6% above the quietest. The one genuine structural
pattern is that the **00:00–05:00 window carries the single largest share
(20.8%)** — late-night demand is the largest block, not the smallest.

### Recommendation

- **Do not build a surge-driven driver schedule around a "rush hour" that does
  not exist.** Instead, staff for a flat baseline with a modest uplift in the
  late-night window.
- **Late-night is the highest-value allocation target**: 20.8% of demand with
  typically thinner driver supply. A late-night incentive (e.g. +₹50/ride
  between 00:00–05:00) targets the largest demand block at the lowest marginal
  cost.
- **Reallocate, don't add.** Because volume is flat, the lever is *distribution*
  of existing drivers across the 24 hours, not headcount growth.

---

## Use case 2 — Customer behaviour for personalised marketing

### What the data says

| Metric | Value |
|---|---|
| Distinct customers | ~94,000 (near one booking each) |
| Repeat-customer rate | **8.41%** |
| Max bookings by one customer | **5** |
| Top customer | CID954071 — 5 bookings, ₹1,796 spend |
| Highest-spend top-5 customer | CID836942 — 4 bookings, ₹6,019 spend |

### The insight

**This is a broad, low-frequency customer base, not a loyalist base.** No
customer books more than 5 times in the month, and only 8.41% book more than
once. "Top customers" are therefore only marginally above average — there is no
concentrated whale segment to protect.

That is the strategic point: **loyalty is a growth opportunity, not an existing
moat.** The revenue base is wide and shallow, which means retention economics
are unusually favourable — a small lift in repeat rate moves a large number of
customers.

### Recommendation

- **Target the 8.41% repeat cohort first.** They have already demonstrated
  intent; a second-ride incentive (e.g. 20% off ride #3) has the highest
  conversion probability per rupee spent.
- **Segment by vehicle type, not by spend.** Since spend is flat, the
  differentiating signal is *what* a customer books. Auto riders (10 km average)
  and Prime riders (25 km average) are different products with different
  messaging.
- **Personalise on payment method.** Cash and UPI riders (95.2%) respond to
  instant-discount mechanics; the 4.8% card cohort responds to points and
  cashback. Two campaigns, not one.
- **Set a realistic target:** lifting repeat rate from 8.41% to 12% would add
  roughly 3,400 returning customers per month at near-zero acquisition cost.

---

## Use case 3 — Pricing patterns & surge effectiveness

### What the data says

| Metric | Value |
|---|---|
| Average fare | ₹548.42 |
| Median fare | ₹385 |
| 95th-percentile fare | ₹1,899 |
| Max fare | ₹2,999 |
| **Fare ↔ distance correlation** | **r = 0.002** |
| Median fare per km | ₹20.35 |
| Avg fare range across vehicle types | ₹540.72 (Mini) – ₹556.99 (Prime Sedan) |

### The insight

**Fare is statistically independent of distance (r = 0.002).** A 5 km ride and a
45 km ride have, on average, the same fare. This is the single most important
structural finding in the dataset, and it has three consequences:

1. **Revenue is not a function of distance travelled** — so "more km" is not a
   revenue lever. Distance optimisation and revenue optimisation are separate
   problems here.
2. **Fare is also flat across vehicle types** (₹541–₹557, a 3% spread). Premium
   positioning (Prime Sedan vs Mini) is *not* being monetised.
3. **Surge, as conventionally understood, cannot be measured from this data** —
   there is no fare-to-demand or fare-to-distance elasticity to estimate. Any
   surge claim would be unsupported.

### Recommendation

- **Treat this as a pricing-integrity finding, not a pricing-optimisation
  finding.** Before building surge logic, confirm whether fare is genuinely
  distance-independent or whether the fare field is a synthetic/rounded value.
  This is a data-governance question that must be resolved first.
- **If fare is genuine:** introduce distance-based pricing. The median ₹20.35/km
  is a defensible anchor; long trips (31–50 km, 21,325 rides) are currently
  under-monetised relative to short ones.
- **If fare is synthetic:** do not build pricing strategy on it. Use the dataset
  for demand, cancellation and quality analysis (where it is sound) and source a
  real fare table for pricing work.
- **Monetise the premium tier.** A 3% fare spread between Mini and Prime Sedan
  is too thin to justify a premium product. A 15–20% premium is the norm.

---

## Use case 4 — Anomaly / fraud detection

### What the data says

| Check | Result | Verdict |
|---|---|---|
| Duplicate `Booking_ID` | **0** | Clean |
| Same customer + same timestamp | **0** | Clean |
| Ratings outside 3.0–5.0 | **0** | Clean |
| Zero-distance rides with a fare | **39,057 (37.9%)** | **Structural, not fraud** |
| Extreme fares (IQR flag) | 8,468 (8.2%) | Expected tail |
| Fare per km > ₹200 | **3,591** | Review candidates |
| Fare per km > ₹500 | **889** | High-priority review |
| Cancellation-cluster days (> mean + 2σ) | **1 day** (2024-07-29, 29.67%) | Mild |

### The insight

**The dataset is clean on the classic fraud signals** — no duplicate bookings, no
impossible timestamps, no out-of-band ratings. The 39,057 zero-distance rides
are **not fraud**: they are exactly the 39,057 non-successful bookings, where no
trip occurred and distance is correctly recorded as 0. This is a structural
property of the data, and treating it as an anomaly would be a false positive.

The genuine review queue is **fare-per-km outliers**: 3,591 rides above ₹200/km
and 889 above ₹500/km. Given the median is ₹20.35/km, a ₹500/km ride is 25× the
norm — these are the rides worth auditing for meter tampering or manual fare
overrides.

### Recommendation

- **Do not flag zero-distance rides as fraud.** Add a rule that excludes
  non-successful bookings from distance-integrity checks; otherwise 37.9% of the
  dataset generates false alerts and the real signal is buried.
- **Build a fare-per-km audit queue** on the 889 rides above ₹500/km. At the
  average fare of ₹548, the maximum exposure is ~₹0.5M — small in absolute
  terms, but a strong control signal.
- **Monitor cancellation clusters weekly.** Only one day (29 July) exceeded
  mean + 2σ, and only by 1.6 points — the process is stable. A weekly control
  chart is sufficient; no real-time alerting is warranted.
- **Add a duplicate-booking guard at ingestion** even though none exist today —
  the check is cheap and the failure mode (double-billing) is expensive.

---

## Cross-cutting: the one number to act on

**Driver cancellations are the largest controllable revenue leak.**

- 18,434 driver cancellations vs 10,499 customer cancellations.
- 6,542 of them are *"Personal & Car related issue"* — a supply-reliability
  problem, not a demand problem.
- At the average fare of ₹548.42, recovering **half** of driver-cancelled rides
  is worth roughly **₹5.0M per month**.

That is the highest-impact, lowest-cost intervention available in this dataset,
and it is the recommendation the analysis leads with.
