# The Hottest-Month System, Explained From Zero

*A complete beginner's walkthrough of the model, the math, the data, and the code.*
*Written 2026-07-22. Every number in the worked examples is from the live system on that date (k = 20 observed July days).*

If you know nothing about trading, statistics, or climate data, start here and read straight through. Each part builds on the one before it. Nothing is assumed.

---

## Part 0 — The whole thing in one paragraph

There is a betting market where you can bet **yes** or **no** on the question *"Will July 2026 be the hottest July ever recorded?"* The bet is settled by a single official number that a US government agency (NOAA) publishes around **August 13**. We don't want to wait until August 13 to know the answer — we want to know it **now**, in July, while the bet is still cheap or mispriced. We can, because a *different* temperature dataset (ERA5) publishes **every day** with only a 2-day delay. So the entire system is a machine that (1) reads the fast daily data, (2) forecasts the rest of the month, (3) **translates** that into what the slow official number will probably say, (4) turns that into a **probability** the bet pays, and (5) compares that probability to the **price** in the market to decide whether there's money to be made. That's it. Everything below is the detail of those five steps.

---

## Part 1 — The bet itself (the market)

### 1.1 What a prediction market is

**Kalshi** is a US-regulated exchange where each contract pays out **exactly \$1 if some real-world event happens, and \$0 if it doesn't.** You buy the side you believe in:

- A **YES** contract pays \$1 if the event happens.
- A **NO** contract pays \$1 if the event does *not* happen.

Because the payout is always \$0 or \$1, the **price is a probability**. If a YES contract costs **24¢**, the market is collectively saying "we think there's about a 24% chance this happens." (24¢ to maybe win \$1.) A NO contract on the same event would cost about **76¢** (because YES + NO ≈ \$1; whoever's right splits the dollar).

> **Key mental model:** price in cents ≈ the market's probability in percent. 24¢ ↔ 24%.

### 1.2 The specific contract

- **Exchange / ticker:** Kalshi, series `KXHMONTH`, this month's contract `KXHMONTH-26JUL`.
- **Question:** "Will July 2026 be the hottest July ever?"
- **Who decides:** the **settlement oracle** = NOAA's *Climate at a Glance* global monthly temperature value. An "oracle" is just the agreed-upon source of truth that the exchange uses to settle the bet.
- **What "hottest ever" means numerically:** NOAA reports each month as an **anomaly** (how much warmer than a long-term average — see Part 3). July's all-time record anomaly is **+1.18 °C** (set in 2024). July 2026 settles **YES** if NOAA's printed July 2026 number is **higher than 1.18**.

### 1.3 How the money works (payoff math)

Say you buy a NO contract at price `n` (in dollars, so 76¢ = 0.76). Two outcomes:

- Event does **not** happen (NO wins): you paid `n`, you receive \$1 → **profit = 1 − n**.
- Event **happens** (NO loses): you paid `n`, you receive \$0 → **profit = −n**.

Your **expected profit** (probability-weighted average) if the true chance of YES is `p`:

$$\mathbb{E}[\text{profit on NO}] = (1-p)\cdot(1-n) + p\cdot(-n) = (1-p) - n$$

So a NO bet is worth making when **(1 − p) > n**, i.e. when the true probability of NO winning is bigger than the price you pay for NO. The whole model exists to estimate that `p` better than the market does.

There are also **fees**. Kalshi's taker fee is roughly `ceil(0.07 · n · p · (1−p))` per contract — notice it's **largest when p is near 0.5** (a coin-flip is the most expensive thing to trade) and near-zero when p is near 0 or 1. Fees, plus the gap between the buy price and sell price (the **spread**), plus **slippage** (the price moving as you buy), all eat into that expected profit. A gap between your model and the market is **not** real profit ("alpha") until it survives all of those costs.

### 1.4 The rounding subtlety (this matters more than it looks)

NOAA prints the number rounded to **2 decimal places**. The record is **1.18**. There is **no "tie" rule** in the contract — a printed tie (1.18 = 1.18) settles **NO**, not YES. So to win, July 2026 must print **1.19 or higher**.

A printed value of 1.19 means the *true, unrounded* value was at least **1.185** (anything from 1.185 up rounds to 1.19). So the real event we're pricing is:

$$\text{YES} \iff \text{true July anomaly} \ge 1.185$$

That's why **1.185** — not 1.18 — is the threshold used everywhere in the code (`THR = 1.185`). And because roughly **7–11%** of plausible outcomes land *exactly* on a printed 1.18 (a tie → NO), there's a small built-in tailwind for NO bets. We track that "tie band" separately.

---

## Part 2 — The core idea (where the edge comes from)

Two datasets measure the same thing (global temperature) on different clocks:

| Dataset | How fast | Role |
|---|---|---|
| **NOAA** (the oracle) | Slow — prints ~day 9–14 of the *next* month (so July's value ≈ **Aug 13**) | This is what settles the bet |
| **ERA5** | Fast — a new day appears with only a **~2-day lag** | This is our early-warning signal |

The market settles on the slow number, but the fast number tells us almost everything about it *weeks early*. If we can reliably **translate ERA5 → NOAA**, we effectively know the answer before the market does.

This is **not** high-frequency trading (HFT). It's **scheduled-event latency arbitrage**: the release time is on a known calendar, and we read a leading indicator. The single most durable, repeatable edge in this whole project is the **release snipe**: on print day (~Aug 13) poll NOAA's feed the instant it updates and fire orders seconds before everyone else reprices. That worked on the June print (model predicted 1.094, actual was 1.09 — an exact hit). But the capacity is tiny (the order book is only ~\$1–3k deep), so this earns **hundreds of dollars per event, not a fortune.** That's a feature, not a bug — build it cheap.

---

## Part 3 — The data (what every number actually is)

### 3.1 Temperature *anomaly* — the concept everything rests on

Nobody reports "the Earth was 17.001 °C today" as the headline, because that number is meaningless without context (of course July is warmer than January). Instead climate science reports the **anomaly**: how far above or below a long-term *average for that same calendar day/month* the temperature was.

$$\text{anomaly} = \text{actual temperature} - \text{climatology}$$

- **climatology** = the long-term average for that specific day-of-year, computed over a fixed **baseline period**.
- A positive anomaly means "warmer than the historical norm for this date."

**The catch: the two datasets use different baselines.**
- **ERA5** anomalies are vs the **1991–2020** average.
- **NOAA** anomalies are vs the **1901–2000** average.

The 20th century (NOAA's baseline) was colder than 1991–2020 (ERA5's baseline), so **NOAA's anomalies are systematically bigger** for the same weather. This is a fixed, known offset — a *deterministic* difference, not free money. The translation step (Part 4.4) absorbs it automatically.

### 3.2 ERA5 — the fast daily file (`era5_daily.csv`)

This is a plain text CSV from Copernicus (Europe's climate service). Real lines from the file:

```
# ...header comment lines start with #...
2026-07-18,16.836,16.237,0.599,FINAL
2026-07-19,16.911,16.241,0.671,FINAL
2026-07-20,17.001,16.244,0.757,PRELIMINARY
```

The four columns that matter:

| Column | Example | Meaning |
|---|---|---|
| date | `2026-07-20` | the day |
| absolute | `17.001` | actual global-mean 2m air temperature (°C) |
| climatology | `16.244` | the 1991–2020 average for this day-of-year |
| **anomaly** | `0.757` | absolute − climatology (this is the number we use) |
| status | `PRELIMINARY` | `FINAL` days are settled; the newest day is often preliminary and may tick slightly |

The code reads this file, splits each line on commas, and stores the **anomaly** (column index 3) keyed by `(year, month) → {day: anomaly}`. Every script starts this way — for example in `update_data.py`:

```python
daily[(y,m)][d] = float(p[3])       # p[3] is the anomaly column
```

"2m air temperature" means measured 2 meters above the surface — the standard height for "surface" temperature.

### 3.3 NOAA — the slow monthly file (`noaa_m7.json`)

One JSON file per month (`noaa_m7.json` = July). Structure:

```json
{"description":{"title":"...July...","units":"Degrees Celsius","base_period":"1901-2000"},
 "data":{"1850":{"departure":0.03}, "1851":{"departure":0.13}, ... }}
```

Each year maps to a `departure` (NOAA's word for anomaly). The code pulls it into `{year: anomaly}`:

```python
noaa[7] = {int(k): v['departure'] for k,v in json.load(open(p))['data'].items()}
```

This gives us the full history of July anomalies (1850–present) — the raw material for learning the ERA5→NOAA relationship, and for finding the record (`max` over years before 2026 = **1.18**).

### 3.4 ECMWF ensemble forecast — the "what happens next" data

ERA5 only tells us the past (through ~2 days ago). For the *rest* of July we need a **forecast**. We use the **ECMWF IFS ensemble** (Europe's flagship weather model) via a free API (Open-Meteo).

**What "ensemble" means:** weather is chaotic, so instead of running the model once, ECMWF runs it **51 times** with slightly different starting conditions. Each run is a **member**. The 51 members spread out over time — that spread *is* the forecast uncertainty. If all 51 agree, we're confident; if they're all over the place, we're not.

**Why we need member-level data (subtle but important):** we care about the **global mean** temperature. You cannot get the uncertainty of a global mean from per-location uncertainty fields — the errors at different places partly cancel. The only correct way is to compute each member's *own* global mean, then look at the spread across those 51 global means. That's exactly what `ens_spread.py` does: for each of 51 members it builds a full-July global-mean estimate, giving 51 possible answers.

A raw member file (`ens_spread_ecmwf_ifs025_*.json`) looks like:

```json
{"k_obs":20, "n_members":51,
 "member_july_mean_era5":[0.6435, 0.6721, 0.6541, ... 51 numbers ...],
 "noaa":{"p_yes_pct":24.569, "members_central_breach":0, "hottest_member_p_pct":48.44}}
```

Those 51 numbers are 51 guesses at "what will July's ERA5 mean end up being." Today they range from ~0.63 to ~0.69, median **0.6675**.

### 3.5 Kalshi market data — the prices

From Kalshi's public API we pull the live order book for the July contract:

```
yes_bid: 21   yes_ask: 24   no_bid: 76   no_ask: 79   volume: 42945   oi: 19306
```

- **bid** = highest price someone will *pay* (you sell into it).
- **ask** = lowest price someone will *sell* at (you buy at it).
- The gap (ask − bid) is the **spread** — a cost you pay to cross.
- **oi** (open interest) = number of live contracts; **volume** = total traded. Both proxy how much size the market can absorb (~\$1–3k here — thin).

**L1 / L2 / L3** is jargon for how much order-book detail an exchange shows:
- **L1** = just best bid and ask.
- **L2** = total quantity at each price level (what Kalshi gives).
- **L3** = every individual order with IDs (Kalshi does *not* give this).
No L3 means fancy microstructure models (tracking individual orders) are impossible here — and unjustified anyway on a book this thin.

### 3.6 GISTEMP — the *other* oracle (`gistemp.txt`)

NASA's **GISTEMP** is a third temperature dataset. It's **not** what Kalshi uses — but it *is* what **Polymarket** (a different betting platform) uses for its version of this bet. GISTEMP uses yet another baseline (1951–1980) and runs about **+0.09 warmer** than NOAA in 2026. So the two platforms can show different prices for "the same" bet — that's **basis risk** (Part 5.5), not an arbitrage.

---

## Part 4 — The math, built from the ground up

We'll go from raw daily numbers to a final probability, one small step at a time.

### 4.1 The monthly mean is just an average

July has D = 31 days. NOAA's July value is (essentially) the average of the month. In anomaly terms:

$$M = \frac{1}{31}\sum_{d=1}^{31} X_d$$

where $X_d$ is day *d*'s anomaly. Simple average. The whole difficulty is that partway through the month we only know *some* of the $X_d$.

### 4.2 Banked + remaining (the split that drives everything)

After **k** observed days, split the month into what's locked in and what's still unknown:

$$M = \frac{1}{31}\Big(\underbrace{\sum_{d=1}^{k} X_d}_{\text{banked } B_k} + \underbrace{\sum_{d=k+1}^{31} X_d}_{\text{remaining } R_k}\Big)$$

- **Banked** $B_k$ = the days we've already observed. Fixed. No uncertainty.
- **Remaining** $R_k$ = the future days. Uncertain — this is the *only* thing we forecast.

As the month goes on, k grows, banked grows, remaining shrinks — so uncertainty shrinks. That's the "variance collapse" (Part 4.11).

**Worked example (today, k = 20):** the mean of the first 20 days is **0.624** (call it $\bar B = B_{20}/20$). So $B_{20} = 20 \times 0.624 = 12.48$.

### 4.3 The "required remaining average" diagnostic

Ask: *how hot would the remaining days have to be, on average, for the record to fall?* Set the whole-month mean equal to the ERA5-equivalent of the threshold, $K$:

$$\bar X_{\text{req}} = \frac{31K - B_k}{31 - k}$$

**Worked example:** The threshold on NOAA's scale is 1.185. Translated back to ERA5's scale (using the line from 4.5, inverted): $K = (1.185 - 0.5686)/0.8891 = 0.693$. Then:

$$\bar X_{\text{req}} = \frac{31(0.693) - 12.48}{31 - 20} = \frac{21.49 - 12.48}{11} = \frac{9.01}{11} \approx 0.82$$

So the last 11 days of July must **average +0.82 °C anomaly** to break the record. Recent observed days have been running ~0.56–0.76. +0.82 is a stretch but not impossible (2024 did exactly that with a late-month surge). This one number is a great gut-check — but it's a **diagnostic, not the model**, because it says nothing about *how likely* +0.82 is. For that we need the probability machinery.

### 4.4 The translation problem: ERA5 ≠ NOAA

ERA5 and NOAA measure the same planet but with different methods, coverage, and baselines. They are *related but not identical*. We need a converter that takes an ERA5 monthly mean and predicts the NOAA monthly value. We *learn* that converter from history: for each past July we have both the ERA5 mean and the NOAA value; we fit a line through those points.

### 4.5 Ordinary Least Squares (OLS) — the line of best fit, from scratch

Plot every year from 1990–2025 as a point: x = that July's ERA5 mean, y = that July's NOAA value. The points fall almost on a straight line. **OLS** finds the line $y = a + bx$ that minimizes the total squared vertical distance from the points to the line. "Least squares" = smallest sum of (error)². The formulas (this is literally the code in `update_data.py:ols`):

$$b = \frac{n\sum xy - \sum x \sum y}{n\sum x^2 - (\sum x)^2}, \qquad a = \frac{\sum y - b\sum x}{n}$$

- **b (slope)** = how many units NOAA rises per unit of ERA5.
- **a (intercept)** = the offset (this is where NOAA's warmer baseline gets absorbed).

We also measure how tightly the points hug the line — the **residual standard deviation** σ, the typical miss:

$$\sigma = \sqrt{\frac{1}{n-2}\sum_{\text{years}} (y - a - bx)^2}$$

**The fitted July line (live):**

$$\text{NOAA}_{\text{Jul}} = 0.5686 + 0.8891 \times \text{ERA5}_{\text{Jul}}, \qquad \sigma = 0.036$$

Read it as: "NOAA ≈ 0.57 + 0.89 × (ERA5 mean), and even with the right ERA5 mean we're typically off by ±0.036." (June has its own line: 0.587 + 0.906·x, σ = 0.045.) The **σ = 0.036 is the translation uncertainty** — it never goes away, even on the last day of the month, because it's about the ERA5↔NOAA gap, not about unknown weather.

**Why a plain line and nothing fancier?** `calibrate.py` stress-tested this: the slope barely drifts over time (a rolling-window and a Kalman filter both say b is stable), the scatter is even across the range (no heteroskedasticity), and El Niño years aren't noisier (a Levene test says the variance doesn't shift). With only 36 data points, a fancier model would just fit noise. So a constant-slope line is the honest choice. **Lazy, and correct.**

### 4.6 Forecasting the ERA5 monthly mean from a partial month

Mid-month we don't yet have July's full ERA5 mean — that's the x we need. So we predict *it* too, from two things we *do* know: last month's value and the month-to-date average. Another OLS, now with **two predictors** (`update_data.py:ols2`):

$$\text{ERA5}_{\text{Jul}}^{\text{full}} = c_0 + c_1 \cdot \text{June}_{\text{ERA5}} + c_2 \cdot \overline{X}_{1..k}$$

We fit $c_0, c_1, c_2$ on history (for every past year: June mean and first-k-days mean → full July mean). Live coefficients: `c = [-0.0025, 0.110, 0.934]`. So the full-July mean ≈ 0.934 × (first-k mean) + 0.110 × (June) − small. The big weight (0.934) on the month-to-date makes sense — the days you've already seen are the best predictor of the whole month.

**Worked example:** with June = 0.5593 and first-20 = 0.62385:
$$\text{ERA5}_{\text{Jul}}^{\text{full}} = -0.0025 + 0.110(0.5593) + 0.934(0.62385) = 0.641$$

### 4.7 Upgrading the forecast with the actual weather model (ECMWF)

The two-predictor OLS is a *statistical* guess (based only on the past). We can do better by injecting the **actual weather forecast** for the remaining days. `fetch_forecast.py` pulls ECMWF's global-mean forecast for the next 15 days and **anchors** it: it compares the forecast against observed ERA5 on the overlapping recent days and shifts the whole forecast so those overlap days match (correcting any constant model bias). Then it fills in the not-yet-observed days with anchored forecast values, and re-runs the same regression at the now-longer horizon $k_{\text{eff}}$ (effective days = observed + forecast, up to all 31).

Live, this ECMWF-augmented path gives an ERA5 full-July mean of **0.6559** (higher than the statistics-only 0.641, because the model forecasts a warm back-half). Feeding *that* through the translation line (4.5):

$$\mu = 0.5686 + 0.8891 \times 0.6559 = 1.152$$

So our central estimate for NOAA's July print is **≈ 1.15** — just *below* the 1.185 needed. Close. Hence "coin-flip-ish."

### 4.8 Turning one prediction into a probability (the Normal tail)

We have a central estimate μ ≈ 1.15 and we know we're uncertain. Model the true outcome as a **bell curve (Normal distribution)** centered at μ with a spread σ. The chance of YES is the area of the bell curve **above the threshold 1.185** — the shaded right tail.

The total uncertainty σ combines two independent pieces (added "in quadrature," i.e. via the Pythagorean theorem because independent errors combine as squares):

$$\sigma_{\text{total}} = \sqrt{(b \cdot \sigma_f)^2 + \sigma_{\text{translation}}^2}$$

- $\sigma_f$ = uncertainty in the remaining-day forecast (shrinks as the month fills in).
- $\sigma_{\text{translation}} = 0.036$ = the permanent ERA5→NOAA scatter from 4.5.
- $b\cdot\sigma_f$ scales the forecast error onto NOAA's units.

**Worked example (ECMWF path):** $\sigma_f = 0.0108$, so
$$\sigma_{\text{total}} = \sqrt{(0.8891 \times 0.0108)^2 + 0.036^2} = \sqrt{0.0096^2 + 0.036^2} = 0.0373$$

The probability of YES is the tail area. In standardized form, compute the **z-score** (how many σ the threshold sits above μ) and read off the Normal tail:

$$z = \frac{1.185 - \mu}{\sigma_{\text{total}}} = \frac{1.185 - 1.152}{0.0373} = 0.89, \qquad P(\text{YES}) = 1 - \Phi(0.89) \approx 0.19$$

$\Phi$ is the Normal cumulative function ("what fraction of the bell is below z"). The dashboard computes $\Phi$ with the **Abramowitz–Stegun approximation** — a short polynomial that matches the true Normal curve to ~7 decimals without needing a stats library (`Dashboard.html:ncdf`):

```javascript
function ncdf(x){
  const t = 1/(1+0.2316419*Math.abs(x));
  const d = 0.3989423*Math.exp(-x*x/2);
  let p = d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));
  return x > 0 ? 1-p : p;
}
```

So the single-path model says **P(YES) ≈ 19%**. Fair NO = 1 − 0.19 = **81¢**... but this single-path number is *overconfident*, which brings us to the honest version.

### 4.9 The honest version: average over all 51 members

The single-path calculation uses one forecast (the ensemble *mean*) and one σ. But the tail is **curved** (convex): being lucky helps you more than being unlucky hurts you near a threshold. Mathematically, the average of the probabilities across the 51 members is **higher** than the probability computed at their average (this is *Jensen's inequality*). So the right thing is to run the tail calculation **per member** and average:

$$\hat p_{\text{YES}} = \frac{1}{51}\sum_{m=1}^{51} P\big(\text{NOAA}^{(m)} \ge 1.185\big)$$

Each member m has its own July-mean ERA5 → its own μ via the translation line → its own tail probability (using a per-member σ that keeps the beyond-horizon + translation uncertainty). This is exactly `ens_spread.py`'s loop:

```python
mu_m = a + b * mu_era          # one mu per member (51-vector)
sig  = hypot(b*sd_f, sd_t)     # residual uncertainty
p_m  = stats.norm.sf((thr - mu_m)/sig)   # tail prob per member
p    = p_m.mean()              # average across members = P(YES)
```

**Live result: P(YES) = 24.6% (NOAA).** Notice it's higher than the 19% single-path number — that gap *is* the tail mass the point estimate was hiding. Also reported:
- **0 of 51** members' *central* paths actually break the record (all 51 medians land below 1.185)...
- ...but the hottest single member sits at **48%**, and the spread gives a 24.6% blended chance. The tail is real even when the center isn't there.
- The same machinery with GISTEMP's threshold gives **46%** — that's why Polymarket (GISTEMP) trades much higher than Kalshi (NOAA) on "the same" bet.

> **The lesson that reshaped the model (July 13):** the old code reported a single-path **0.0%** and looked like free money on the NO side. The 51-member version revealed real tail mass (2–3% then, 24.6% now). A point estimate near a threshold *lies*; you must carry the whole distribution.

### 4.10 Rounding and the tie band (revisited precisely)

We use threshold **1.185** (not 1.18) because NOAA must *print* ≥ 1.19 to settle YES (4.14). Separately, the chunk of the bell curve that rounds to *exactly* 1.18 (roughly the slice from 1.175 to 1.185) is a **tie → NO**. That's ~7–11% of outcomes, a structural cushion for NO positions, tracked on its own rather than blended into the point estimate.

### 4.11 Variance collapse — why uncertainty shrinks (but slowly)

As observed days pile up, the forecast uncertainty falls. The code computes the total NOAA-scale σ at each stage of the month (`update_data.py`, the `collapse` table):

| k (days observed) | 2 | 5 | 10 | 15 | **20** | 26 | 31 |
|---|---|---|---|---|---|---|---|
| σ (NOAA units) | .088 | .081 | .066 | .053 | **.046** | .039 | .036 |

Two things to notice:
1. It **shrinks** (early month = wild uncertainty, end of month = only the translation σ of 0.036 remains).
2. It shrinks **slower than you'd naively expect.** If each day's error were independent, uncertainty would fall like $1/\sqrt{\text{days left}}$. It doesn't, because weather comes in **persistent regimes** — a hot spell tends to continue, so consecutive days' errors are *correlated*. Correlated errors don't cancel as fast. The "effective number of independent days" is smaller than the calendar count:

$$n_{\text{eff}} = \frac{n}{1 + (n-1)\rho}$$

where ρ is the day-to-day correlation. The fitted collapse table already bakes this in, so we don't need a separate correlation model for pricing. **This is why the edge decays over the month:** early on, the market underweights ERA5's lead and we know more than the price; by k = 20 (now) our σ and the market have converged and the edge is gone.

### 4.12 The bias knob (the hardware-calibration of this system)

Any translation learned from 1990–2025 might be slightly off for 2026 specifically (methodology tweaks, a warm run of prints, etc.). So there's a **bias** term: the average amount by which 2026's actual NOAA prints (Jan–June) have exceeded what the translation line predicted. Live: **+0.022**. The dashboard has a toggle to add it or not, and the honest answer is quoted as a **bracket** between the raw and bias-adjusted numbers — never a single false-precision point.

Crucially, this knob is *empirical and updated each print*. When June printed 1.09 (vs the raw model's 1.094 — nearly exact, and the +0.02-biased version's 1.114 would have been a *miss*), that was evidence the warm-bias had faded, and the knob came down. This is the "leave a calibration knob for the real world" principle: no fixed model captures a drifting reality, so you keep one tunable dial and re-tune it on every new data point.

---

## Part 5 — From a probability to an actual trade

Having a good P(YES) is only half the job. The mandate is explicit: **maximize risk-adjusted expected value, not forecast accuracy.** A correct probability with no price gap is worth \$0.

### 5.1 Fair value vs the market

- Model says P(YES) = 24.6% → **fair NO price = 1 − 0.246 = 75.4¢**.
- Market NO ask = **79¢** (what you'd pay to buy NO), NO bid = 76¢ (what you'd sell at).
- To *buy* NO you pay 79¢ for something worth 75¢ → you'd be **overpaying**. To *sell* NO you get 76¢ for something worth 75¢ → roughly fair.

The **edge** is fair − price. Here it's ≈ **0–3¢**, inside the noise and smaller than fees+spread. **Verdict: no trade.** (For the conservative version we actually use the *upper* probability bound for NO decisions, which shrinks the edge further — never trade on the optimistic tail.)

### 5.2 The trade gate (hysteresis)

The dashboard only flags a trade when |edge| ≥ **3¢** (`verdict()`), and the switching logic requires the same 3¢ to *flip* a position, so you don't churn in and out on noise (each flip costs two spreads + two fees). This is the entire "state machine" the market's tiny capacity justifies — it collapses the mandate's elaborate 13-state execution engine down to `{FLAT, LONG_NO, REDUCE, HALT}`.

### 5.3 Kelly sizing — how much to bet (from zero)

Suppose you *do* have an edge. How much of your bankroll do you stake? Betting too little wastes the edge; betting too much risks ruin even when you're right on average. The **Kelly criterion** gives the growth-optimal fraction. For a bet where you risk your stake to win net odds `b` per dollar, with win probability `p_win`:

$$f^\star = \frac{p_{\text{win}} \cdot b - (1 - p_{\text{win}})}{b}$$

For a NO bet at price `n`: you risk `n` to win `(1−n)`, so odds `b = (1−n)/n`, and `p_win = 1 − p_YES`. That's exactly `calibrate.py`:

```python
b_odds  = (1 - no_ask)/no_ask           # payoff per $ staked
f_full  = (p_no*b_odds - p_yes)/b_odds  # full Kelly fraction
f_quarter = f_full/4                     # quarter-Kelly
```

We then apply three safety reductions, taking the smallest:

1. **Quarter-Kelly** (÷4) — full Kelly is famously too aggressive when `p` itself is uncertain (and ours is). Betting a fraction of Kelly trades a little growth for a lot less volatility.
2. **Depth cap** — never bet more than the thin book can absorb (~depth/3).
3. **Hard dollar cap** — a flat **\$300 per market**, independent of everything else.

$$\text{stake} = \min\!\big(\tfrac14 f^\star \cdot W,\; \text{depth}/3,\; \$300\big)$$

And the probability plugged in is the **worst-case** among {Student-t tail, 51-member ENS, a 0.5% floor} — deliberately pessimistic, because Kelly is very sensitive to overestimating your edge. Today, with edge ≈ 0, **Kelly says stake \$0.** (The existing ~326 NO contracts are a legacy position from when the edge was real; the model does not endorse adding to them now.)

### 5.4 Why "t-tails" instead of Normal for sizing

`calibrate.py` sizes using a **Student-t distribution** (ν = 19) rather than a Normal. The t-distribution has **fatter tails** — it assigns more probability to extreme outcomes. For *sizing* (a risk decision) you want to respect fat tails so you don't get blown up by a surprise; ν = 19 was measured from the out-of-sample residuals, not guessed.

### 5.5 What is *not* an edge (traps)

- **"Sell the longshot" (dead).** April/May/June all had mid-month YES at 8–14¢ and decayed to NO — a real longshot-premium pattern. But July's YES **repriced with the forecast** (2% → 25%), so the static "market is dumb" bet no longer exists.
- **Microstructure alpha (unjustified here).** Order-flow/microprice/Hawkes-process signals need L3 data and deep books. We have neither. Building them would overfit sparse data.
- **Cross-oracle "arbitrage" (it's basis, not arb).** Kalshi settles on NOAA, Polymarket on GISTEMP. They can't offset each other exactly (different datasets, +0.09 gap), so holding both is a **basis trade** with real risk — calling it arbitrage would be wrong. A true arbitrage requires *guaranteed* offsetting payoffs under **every** outcome; that condition isn't met.

---

## Part 6 — The code, file by file

The system is deliberately small: a handful of Python scripts + one HTML dashboard. No C++, no databases, no message queues — because at ~12 events/year and \$1–3k depth, that infrastructure would cost more than the edge it chases. (The full institutional stack is documented as a *scale-up path*, not built.)

### 6.1 `update_data.py` — the engine (run this to refresh everything)

The heart. One function, `refresh_once()`, does the whole pipeline:
1. **Fetch ERA5** (only if the cached file is >6h stale), and *validate* it (must be >1 MB and reach the current year — truncated downloads have burned us before).
2. **Fetch NOAA** for June & July (again, only if stale).
3. **Fit the translation lines** (`ols`) for June and July.
4. **Fit the incomplete-month forecast** (`ols2`, two predictors).
5. **Augment with ECMWF** (imports `fetch_forecast`, fills remaining days).
6. **Embed the 51-member result** (reads the freshest `ens_spread_*.json` if <24h old).
7. **Compute the variance-collapse table** and the **bias** knob.
8. **Fetch Kalshi** prices and candlesticks.
9. **Write `data.js`** — a single line `window.HM_DATA = {...};` that the dashboard reads.

Two ponytail-style engineering notes worth understanding:
- **Why `curl` instead of Python's `requests`?** The comment says it: Python.org's Mac builds often ship broken SSL certificates, so `subprocess.run(['curl', ...])` is the battle-tested path here.
- **Fail-safe writes:** if a Kalshi fetch fails, it keeps the previous good prices rather than blanking them (`if not kal and prev.get('kalshi')`). Data staleness never silently corrupts the file.

Run it: `python3 update_data.py` (once) or `python3 update_data.py --loop 900` (forever, every 15 min).

### 6.2 `fetch_forecast.py` — the ECMWF puller (deterministic, single forecast)

Samples a 10°×10° grid (648 points) of ECMWF's global-mean forecast, cos-latitude-weights them into one global-mean number per day (cells near the equator cover more area, so they weigh more: weight = cos(latitude)), converts to ERA5-style anomaly, and **anchors** the offset on overlap days. Archives every pull to `forecast_log/` so we can later *measure* forecast skill instead of assuming it. Has a **horizon-edge guard**: the last forecast day and any day after an implausible >0.30 °C/day jump are dropped (a known artifact where the final day aggregates incomplete sub-daily steps).

### 6.3 `ens_spread.py` — the 51-member ensemble (the honest core)

Same idea as `fetch_forecast` but pulls **all 51 members** (from Open-Meteo's ensemble API) on a 15° grid, and — critically — computes **each member's own global mean** so we get the *distribution*. Produces the per-member July means, then the averaged P(YES) for both NOAA and GISTEMP thresholds. This is what turned the model from a lying point estimate into an honest distribution. Ends with `assert` self-checks (spread must be non-degenerate, anchoring must succeed).

### 6.4 `calibrate.py` — stress-test + position sizing

Four checks in one script:
1. **Stationarity** — rolling-window + Kalman filter on the translation coefficients (is the slope drifting? No.).
2. **Heteroskedasticity** — White HC1 standard errors (is the scatter uneven? No.).
3. **ENSO regime** — fetches live El Niño index, Levene test (are El Niño years noisier? Not significantly.).
4. **Kelly** — the full sizing calc from 5.3, using the worst-case tail probability.

Run it with your bankroll: `python3 calibrate.py 500`. Every branch it checks concludes "the simple model holds" — which is *why* the model stays simple.

### 6.5 `daily_check.py` + launchd — the automation

Runs automatically every day at **07:15 local** (via macOS `launchd`, job `com.hottestmonth.daily`). It:
1. Refreshes all data → runs `ens_spread.py` → refreshes again (the order matters: members need fresh ERA5 to anchor, and `update_data` needs the member file to embed — a careful sandwich, explained in the code comment).
2. **Scores the forecast** leakage-free: for each verified July day, it compares the actual ERA5 to what the latest forecast *made before that day* predicted. "Leakage-free" means it only ever anchors a forecast on days that were observable *at forecast time* — never peeking at the answer.
3. Appends a one-line digest to `track_log.csv` and fires a **macOS notification**, prefixed **⚠️** if the 3-day mean forecast error exceeds **0.05** (the "dip-check" tripwire — it fires when the forecast is diverging from reality, telling you to look).

This tripwire is the model's smoke alarm. It fired on July 15 (actuals ran warmer than forecast three days straight), which is *how we caught* the late-month surge repricing the market in real time.

### 6.6 `Dashboard.html` + `data.js` — the live view

Pure static HTML + Chart.js. Serve it (`python3 -m http.server 8000`) and it reads `data.js`, recomputes the probability in-browser (`model()` / `ncdf()`, exactly the math of Part 4.8), and draws the bell curves, the tracking chart, and the fair-vs-market bar. It re-reads `data.js` every 5 minutes, so if `update_data.py --loop` is running, the dashboard is always live. The bias toggle switches the knob (4.12) on/off.

### 6.7 `kalshi_client.py` — authenticated account access (read-only)

Uses your production API key (`.env` + `kalshi_demo.pem` — misnamed, it's really a prod key) to read **balance, positions, and fills**. It is **read-only** — there is **no order-placement code yet**. That's the deliberate missing piece before any live automated trading (paper-mode and hard caps first).

---

## Part 7 — Every case (the decision table)

This is the full "if X then do Y" the whole system reduces to:

| Model says | Market says | Risk says | Action | Today (Jul 22) |
|---|---|---|---|---|
| Strong NO edge (fair − ask ≥ 3¢) | NO liquidity there | within \$300 cap | **Accumulate NO** | ✗ edge ≈ 0 |
| Strong YES edge | ask liquidity there | within cap | **Accumulate YES** | ✗ |
| Small edge | wide spread | normal | **Passive / no trade** | **← current** |
| Model disagreement (GFS vs ECMWF surge) | any | normal | **Reduce sizing** | partial (coin-flip) |
| Data stale | any | any | **Cancel + halt** | monitored |
| Structural break (dev3 > 0.05) | any | any | **Recalibrate + reduce** | dev3 fired on the dip |
| Settlement ambiguity | any | any | **Do not trade** | n/a (rules clear) |

**The bottom line, in plain words:** July 2026 went from a longshot NO (the model once said ~2% YES) to a near-coin-flip (~25% YES). The mispricing that made this interesting is **gone** — model fair NO (≈75¢) ≈ market NO ask. The durable, repeatable money in this whole project isn't monthly directional bets; it's the **NOAA-release snipe** on print day (~Aug 13), which must be moved off a sleeping laptop onto a reliable always-on runner before then.

---

## Part 8 — What can go wrong (risk register) + glossary

### 8.1 The main risks

1. **Translation break** — the ERA5→NOAA line shifts (methodology change, warm run). Mitigation: the bias knob + the dev3 tripwire.
2. **Ensemble underdispersion** — the 51 members are *too confident* (they share model errors), hiding real tail mass. This already bit us once (the 0.0% point estimate). Mitigation: carry the member distribution + a translation-σ floor.
3. **The sniper sleeps** — a laptop-based release poller missing the print (the Mac literally slept through the June poll and caught the print late). Mitigation: run it on `caffeinate` or the cloud.
4. **Overtrading a thin book** — the ~\$1–3k depth means large orders move the price against you. Mitigation: depth cap + \$300 hard cap.
5. **Q4 El Niño cluster** — records cluster in El Niño bursts, so "always bet NO" becomes the *losing* habit in Sep–Dec. YES may be the value side then.

### 8.2 Glossary (every term, one line each)

- **Anomaly** — temperature minus its long-term average for that date.
- **Baseline / climatology** — the reference period the anomaly is measured against (ERA5: 1991–2020; NOAA: 1901–2000; GISTEMP: 1951–1980).
- **Oracle** — the official data source the exchange uses to settle (Kalshi → NOAA).
- **YES/NO contract** — pays \$1 if the event does/doesn't happen; its price ≈ probability.
- **Bid / ask / spread** — best sell price / best buy price / the gap between them (a cost).
- **Depth / open interest** — how much size the book can absorb / how many live contracts.
- **ERA5** — fast daily reanalysis temperature dataset (~2-day lag), our signal.
- **NOAA GlobalTemp** — slow monthly official dataset (~2-week lag), the settlement number.
- **Ensemble / member** — 51 slightly-different forecast runs; their spread = uncertainty.
- **OLS (least squares)** — the line $y = a+bx$ minimizing squared errors; our translation.
- **Residual σ** — the typical miss of the line; the irreducible translation uncertainty (0.036).
- **Banked / remaining** — observed days (fixed) vs future days (forecast).
- **z-score** — how many σ a value sits from the mean.
- **Normal / Student-t tail** — the bell-curve area above the threshold = P(YES); t has fatter tails, used for cautious sizing.
- **Variance collapse** — uncertainty shrinking as the month fills in (slower than √ because weather persists).
- **Jensen's inequality** — why averaging probabilities across members > probability at the average (the tail is curved).
- **Kelly criterion** — growth-optimal bet fraction; we use ¼-Kelly + caps.
- **Edge / alpha** — model probability minus market price, *after* all costs.
- **Basis risk** — two related-but-not-identical instruments (NOAA vs GISTEMP) that don't perfectly offset.
- **Latency arbitrage** — profiting from knowing a scheduled number seconds/days before the market reprices.
- **dev3 tripwire** — the 3-day mean forecast-error alarm (>0.05 → warn).

---

*Everything in this primer maps to real files: `era5_daily.csv`, `noaa_m*.json`, `gistemp.txt`, `update_data.py`, `fetch_forecast.py`, `July Calibration/ens_spread.py`, `July Calibration/calibrate.py`, `daily_check.py`, `Dashboard.html`, `data.js`, `kalshi_client.py`. Open any of them next to the matching section above and the code will read like prose.*
