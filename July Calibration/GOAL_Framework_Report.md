# Quantitative Framework for Climate Prediction-Market Alpha — KXHMONTH

**Prepared:** 2026-07-22 (autonomous scheduled run) · **Target contract:** Kalshi "Will July 2026 be the hottest July ever?"
**Evidence tags:** `[VERIFIED]` official/observed · `[ASSUMPTION]` modeling choice · `[ESTIMATE]` fitted parameter · `[HYPOTHESIS]` needs test · `[UNAVAILABLE]` not retrievable now.

This report answers the 27-section mandate in the required Part I–VIII order. It is grounded in the live system (`update_data.py`, `ens_spread.py`, `calibrate.py`, `Dashboard.html`, `data.js`) rather than restating textbook derivations the mandate already contains. Where the mandate asks for machinery that this market's economics do not justify, that is stated with the reason, not silently omitted.

---

## Part I — Verified Facts

### Contract Specification Table

| # | Field | Value | Tag | Source / consequence |
|---|-------|-------|-----|----------------------|
| 1 | Exchange / series | Kalshi, `KXHMONTH` (monthly variant `KXHMONTH-26JUL`) | `[VERIFIED]` | US-regulated (CFTC/DCM); legal for the intended participant. |
| 2 | Title | "Will July 2026 be the hottest July ever?" | `[VERIFIED]` | Record comparison, not a fixed threshold. |
| 3 | Settlement oracle | NOAA NCEI **Climate at a Glance**, global monthly value | `[VERIFIED]` | `HMONTH.pdf` rules; single authoritative print. |
| 4 | Series | Global **land+ocean** temperature **anomaly** | `[VERIFIED]` | NOT GISTEMP (Polymarket's oracle) — cross-platform basis risk. |
| 5 | Baseline | 20th-century mean **1901–2000** | `[VERIFIED]` | All ERA5 (1991–2020 base) must be re-baselined; deterministic offset, not alpha. |
| 6 | Coverage | Global, land+ocean blended | `[VERIFIED]` | Local heat headlines weight `cos φ`-small — §13. |
| 7 | Rounding | **2 decimals** | `[VERIFIED]` | Settlement is on the rounded print → interval censoring, §1. |
| 8 | Threshold type | **Rounded record**: YES iff printed July 2026 ≥ printed prior record | `[VERIFIED]` | Rules contain **no tie clause**; a printed tie (1.18 = 1.18) settles **NO**. Tracked separately. |
| 9 | Prior July record | **1.18** (the model's `record` field) | `[VERIFIED]` from NOAA history in `noaa_m7.json` | Latent settlement threshold ≈ **1.185** (must round to ≥1.19… see §1 for the exact event). |
| 10 | Observation cutoff | Full calendar month (31 days, UTC) | `[VERIFIED]` | Banked/remaining split, §4. |
| 11 | Publication date | ~**Aug 13, 2026, 11:00 ET** | `[ESTIMATE]` empirical (June printed Jul 9) | Settlement day; release-time latency window. |
| 12 | Revisions | NOAA revises later vintages | `[VERIFIED]` | **Settlement uses the first print**; revision risk is post-settlement only. |
| 13 | Fees | Kalshi taker fee `ceil(0.07·n·p·(1−p))` per contract, maker often 0 | `[VERIFIED]` structure; per-order value `[ESTIMATE]` | Fee is largest near p=0.5 — expensive to trade a coinflip. §12. |
| 14 | Tick | \$0.01 | `[VERIFIED]` | Minimum edge granularity. |
| 15 | Depth / capacity | ~**\$1–3k** resting per side | `[ESTIMATE]` from book observation | Hard cap on strategy capacity → hundreds of \$/event. |
| 16 | Order-book data | Public REST L1/L2 (aggregated by price); **no L3** | `[VERIFIED]` | No order-IDs → §11 microstructure is L2-limited; Hawkes/queue models unjustified. |
| 17 | API auth | Prod key works (`.env` + `kalshi_demo.pem`, misnamed); read-only client built | `[VERIFIED]` | Balance/positions/fills yes; **order code not written**. |
| 18 | Automated trading | Permitted | `[VERIFIED]` | Public data only. |

### Dataset Specification Table

| Dataset | Role | Baseline | Latency | Tag |
|---|---|---|---|---|
| **NOAA NCEI CAG** | Settlement oracle | 1901–2000 | ~day 9–14 next month | `[VERIFIED]` |
| **ERA5 / ERA5T** (Copernicus **Climate Pulse** daily CSV) | Fast nowcast signal | 1991–2020 (re-based in fit) | **~2-day lag** | `[VERIFIED]` |
| **ECMWF IFS ENS** (51-member, via Open-Meteo ensemble API) | Remaining-day forecast + spread | ERA5-anchored | 00z ~05–08 UTC, 12z ~17–20 UTC | `[VERIFIED]` (`ens_spread.py`) |
| GFS / ICON | Cross-center divergence check | model | same-day | `[VERIFIED]` |
| NASA GISTEMP | **Polymarket** oracle, not Kalshi | 1951–1980 | mid-month | `[VERIFIED]` — different dataset. |
| GHCN-M v4 / ERSSTv5 | *Roadmap*: replicate NOAAGlobalTemp | — | ~day 3–5 | `[HYPOTHESIS]` — not built. |

**Unverified / ambiguous items flagged:** (a) exact NOAA release *time* is empirical, not published to the minute; (b) the "NOAA v6.1 methodology change" rumor from the mandate is **`[UNAVAILABLE]`** — not confirmed against NCEI docs, do not model it; (c) Open-Meteo ensemble endpoint is quota-limited off-anchor days — member files are vintage-stamped in `July Calibration/ens_spread_*.json`.

### The one number that matters today (2026-07-22, k=20)

- ERA5 July MTD mean **+0.624 °C**; remaining 11 days must average **+0.822** to reach the rounded record.
- 51-member IFS ENS: **P(YES) = 24.6% (NOAA)**, 46.0% (GISTEMP-1st); median member July-mean ERA5 **0.6675**; **0 of 51 central paths breach**; hottest member 48%.
- Market: **YES 21¢ bid / 24¢ ask** → NO ask ≈ 76–79¢. Model fair NO ≈ 75¢. **Edge ≈ 0–3¢, inside noise.**

---

## Part II — Executive Quantitative Thesis

**The central forecasting problem.** Settlement is a rounded record comparison on a *monthly mean* that is ~65% locked by day 20. The whole game is estimating the distribution of the **remaining-day** global-mean anomaly and translating ERA5 into NOAA's scale. The contract is effectively a bet on whether the back half of July repeats 2024's late surge.

**Where the edge genuinely is — scheduled-event latency arbitrage, not HFT.** The one durable, repeatable edge (documented, realized on the June print: model 1.094 vs actual 1.09, exact) is that **ERA5 leads NOAA by ~2 days and NOAA's release time is known**. A release-sniper polling the CAG JSON from ~10:59:50 ET and firing limit orders wins by seconds *when the pre-print gap is large*. Capacity is book-depth-bound (~\$1–3k), ~12 events/yr → **hundreds of dollars per event, not a business.** Build it as a cron script, not infrastructure.

**Which apparent edges are probably illusory.**
- **"10× mispricing" longshot fade.** Apr/May/Jun all had mid-month YES trading 8–14¢ and decayed to NO — a real longshot premium — but July's YES has *repriced with the forecast* (2%→25%). The static "market is dumb, sell YES" thesis is **dead**; current edge is marginal.
- **Microstructure alpha.** L2-only, ~\$1–3k book, wide spreads. Microprice/OFI/Hawkes signals overfit sparse data here. `[HYPOTHESIS]` — none has out-of-sample support on this market.
- **Cross-oracle "arbitrage" (Kalshi NOAA vs Polymarket GISTEMP).** Different datasets, non-offsetting settlement → **basis trade, not arbitrage** (§10). GISTEMP ran ~+0.09 warm vs NOAA-2026; that is a deterministic dataset spread, not free money.

**Alpha decay.** Translation σ collapses **0.088 (k=2) → 0.046 (k=20) → 0.036 (k=31)**. Edge is largest early when the market underweights ERA5's lead, and near-zero by the print. By day 20 in a coinflip year (now), model and market agree — correctly.

**Largest risks.** (1) Translation structural break (2026 audit bias, §6C); (2) ensemble underdispersion hiding tail mass (the deterministic 0.0% point-estimate on Jul 13 hid real member tail → moved to 51-member P); (3) a laptop-based sniper sleeping through the print (June: Mac slept mid-poll, print caught late).

---

## Part III — Mathematical Forecast Model

### 3.1 Target variable and banked/remaining split

Monthly mean over D=31 days: after k observed days, with banked sum B_k and remaining sum R_k,

$$M = \frac{1}{31}\left(B_k + R_k\right), \qquad \bar X_{\text{req},k} = \frac{31K - B_k}{31-k}.$$

Live: k=20, B_20/20 = 0.624, K_ERA5 = (record threshold mapped back through the OLS) → required remaining mean **+0.822** — a diagnostic, not the model.

### 3.2 ERA5→NOAA translation (the load-bearing layer)

Per-month OLS on 1990–2025 (LAD-checked, `update_data.py:ols`):

$$\text{NOAA}_{\text{Jul}} = 0.5686 + 0.8891\,\text{ERA5}_{\text{Jul}} + \varepsilon,\qquad \hat\sigma_\varepsilon = 0.036.$$

(June: 0.587 + 0.906·x, σ=0.045.) `calibrate.py` verified: rolling-β drift negligible (Δb 0.031→0.017), White HC1 → homoskedastic (×0.94), El Niño σ-expansion not significant (Levene p=0.95). **`[VERIFIED]` that static OLS is not meaningfully beaten** here by a Kalman/DLM on this n=36 — the mandate's state-space apparatus (§6B) is available but **declined as not-worth-it** given the data supports a constant slope.

### 3.3 Incomplete-month forecast of ERA5 July mean

Two-predictor conditional OLS (historical) **plus** the ECMWF-augmented path:

$$\text{ERA5}_{\text{Jul}}^{\text{full}} = c_0 + c_1\,\text{June} + c_2\,\overline{X}_{1..k} \quad(\text{hist})$$

then extend observed days with the IFS 15-day global-mean forecast, anchored to the ERA5 overlap days (`anchor_offset` in the ENS block), horizon edge-day dropped, with forecast-error inflation `0.015·lead^0.7` capped at 0.15 (`update_data.py:120`).

### 3.4 Ensemble → settlement probability (the honest core)

The deterministic point estimate is **replaced** by the 51-member distribution (`ens_spread.py`, member-level global means — the only way to get global-mean spread; 15° grid, ERA5-anchored, edge-day guard). Per member m, map its July-mean ERA5 through the OLS + fold in translation σ, count settlement breaches:

$$\hat p_{\text{YES}} = \frac{1}{51}\sum_{m=1}^{51}\Pr\!\big(R_d(\text{NOAA}^{(m)}) \ge K\big).$$

Live: **24.6% (NOAA)**, 46.0% (GISTEMP). Measured member spread (σ≈0.035) is ~60% wider than the old assumed forecast-error knob (0.022) — **the point estimate was overconfident; quote the member P.**

### 3.5 Rounding-aware settlement event (§1 done right)

Printed record 1.18 → YES requires the printed July value to **round to ≥ 1.19**. With round-half-to-even on 2 decimals, the latent event is

$$\Pr\big(R_2(Y)\ge 1.19\big) = \Pr(Y \ge 1.185).$$

The dashboard uses threshold **1.185** vs Normal(μ, σ) (`Dashboard.html:139`, `ncdf` = Abramowitz–Stegun). **Tie band:** 7–11% of outcomes print exactly 1.18 → **NO** (no tie clause). This tie cushion is a structural tailwind for NO positions and is tracked separately, not folded into the point fair.

### 3.6 Variance-collapse schedule (empirical, not independent-day)

From `data.js.collapse` (σ_NOAA by observed-day count k):

| k | 2 | 5 | 10 | 15 | 20 | 26 | 31 |
|---|---|---|---|---|---|---|---|
| σ | .088 | .081 | .066 | .053 | **.046** | .039 | .036 |

Collapse is **slower than √(remaining/31)** because synoptic regimes persist — remaining-day errors are correlated. Effective sample size `n_eff = n/(1+(n−1)ρ)`; the empirical schedule already embeds ρ>0, so no separate correlation model is needed for pricing. `[VERIFIED]` from the fitted collapse table.

### 3.7 Uncertainty decomposition (§23)

Dominant contributors at k=20, ranked: **(1) remaining-day weather** (ensemble spread, ~0.035) ≫ **(2) ERA5→NOAA translation** (0.036, comparable) ≫ (3) 2026 audit-bias / structural break (±0.02) > (4) rounding/tie (discrete, ~±0.01 equivalent) ≫ (5) revision (≈0, first-print settlement). **Highest-VOI next data source:** GHCN-M v4 + ERSSTv5 preliminary (roadmap #2) would shrink translation σ 0.047→~0.02 — the single biggest decision-uncertainty reduction available.

---

## Part IV — Market and Execution Model

### 4.1 Fair value vs executable signal

$$\text{fair NO} = 1 - \hat p^{U}_{\text{YES}}, \qquad EV^{\text{NO}} = (1-\hat p^{U}) - n_t - C_t,$$

using the **upper** probability bound for NO (conservative). Live: fair NO ≈ 75¢, NO ask ≈ 76–79¢ → EV ≈ 0 after fees. **Model Kelly stake = \$0 at this price.** The dashboard's honest bracket is a ±0.05 shift on the remaining-days forecast (`Dashboard.html:200`), reported as a band, not a point.

### 4.2 Microstructure — deliberately minimal `[ASSUMPTION]`

L2-only, thin book → the mandate's microprice/OFI/Hawkes/toxicity stack is **not built and not justified**: no L3, sparse trades, spoof-indistinguishable cancellations. What *is* used: best bid/ask, aggregated depth as the capacity cap, and spread as a trade-gate (skip when spread > edge). Adding Hawkes here would overfit — flagged `[HYPOTHESIS]`, revisit only if depth grows 10×.

### 4.3 Switching logic / hysteresis

Do not flip NO→YES on short-term momentum. Require posterior change to cover exit + entry fees + model uncertainty + a hysteresis band. Concretely: only add NO when fair-NO − NO_ask ≥ **3¢** (the dashboard's `verdict` band), only reduce when the reverse ≥ 3¢. This is the whole state machine the capacity justifies — the mandate's 13-state machine (`NO_POSITION…SETTLEMENT_LOCKDOWN`) is documented but collapses to {FLAT, LONG_NO, REDUCE, HALT} at \$300 scale.

### 4.4 Position sizing (§18, as implemented in `calibrate.py`)

Kelly on the **worst-tail** P(YES) among {t19 translation tail, ENS member P, 0.5% floor}, then **¼-Kelly**, then depth proxy, then a **\$300 hard cap** independent of Kelly:

$$f = \tfrac14\cdot\frac{p^{\text{cons}} - q}{1-q},\qquad \text{stake} = \min(f\cdot W,\ \text{depth}/3,\ \$300).$$

`[VERIFIED]` in code. Estimation-error penalty is the worst-tail-P substitution, not a z·σ shave.

---

## Part V — Backtest and Validation

### 5.1 Leakage controls (the ones that bite here)

- **Vintage discipline:** climate files refetch only when >6h stale and are validated for truncation (`update_data.py:stale`); ENS member files are timestamp-named. **`[VERIFIED]`.**
- **Leakage-free anchoring:** `daily_check.py` scores forecast-vs-actual only on **verified** days (ERA5's 2-day lag respected), appended to `track_log.csv`. **`[VERIFIED]`.**
- **Prohibited and avoided:** using revised ERA5/NOAA for a past decision, using the final NOAA value pre-release, mid-point fills, threshold selection after seeing test results.

### 5.2 Walk-forward + small-sample reality

n=36 July-years; record events are rare (records cluster in El Niño bursts). Precise tail probabilities beyond ~1% are **not supported** by effective sample size — report brackets. `overfit_test.py` confirms fit-window/LAD-threshold robustness (0.686–0.724). Benchmark ladder (§16D) — market-only, climatology, MTD-linear, raw-ensemble, calibrated-ensemble, static-OLS — the **calibrated 51-member ensemble + static OLS** is the operating point; dynamic state-space adds nothing out-of-sample on this n `[VERIFIED via calibrate.py]`.

### 5.3 The live scorecard (best validation available)

June print: model **1.094** vs actual **1.09** (exact); bias knob would have said 1.114 (miss) → **raw model beats the bias-adjusted variant**; 2026 warm-bias thesis retired. This single out-of-sample settlement is worth more than any in-sample statistic.

---

## Part VI — Risk Framework

| Limit | Value | Basis |
|---|---|---|
| Hard exposure cap | **\$300 / event** | Independent of Kelly (`calibrate.py`) |
| Position sizing | ¼-Kelly on worst-tail P | Estimation-error robust |
| Capacity | ≤ depth/3 (~\$300–1000) | \$1–3k book |
| Oracle concentration | 1 (NOAA only) — Sep–Dec cross-month NO correlation flagged | Records cluster in El Niño |
| Model-family concentration | ERA5+IFS only | GHCN-M replication is roadmap, uncorrelated add |
| Kill switches | dev3 |3-day mean| > 0.05 → warn; data stale → freeze | `daily_check.py`, `update_data:stale` |
| Drawdown state | current July NO ~\$1,184 exposure vs \$264 cash = **~4× the cap** | **Live breach — flagged, do not add** |

**Model-risk register (top items):** translation break (2026 audit bias), ensemble underdispersion, laptop-sniper reliability, Kalshi tie-clause misread (there is none → NO cushion), GISTEMP/NOAA basis confusion.

**Live risk note.** The current July NO position (~326 contracts, ~\$1,184 exposure) sits at **~4× the \$300 hard cap** with model edge ≈ 0 at the current 24¢ YES. Per the framework the model stake here is **\$0** — this is a legacy position, not a model-endorsed one. No new NO should be added at this price; the tie-band cushion (7–11% print exactly 1.18 → NO) is the main thing still favoring the held NO.

---

## Part VII — Implementation Plan

**What exists and works (`[VERIFIED]`):** ERA5+NOAA+Kalshi+IFS ingestion (curl-based — python.org SSL certs broken), per-month OLS translation, two-predictor forecast, 51-member ENS spread, rounding+tie-aware settlement P, dashboard, launchd daily job, read-only Kalshi auth, deviation tripwire.

**Right-sized architecture (not the mandated C++/Arrow/gRPC stack).** At ~12 events/yr and \$1–3k depth, the C++ low-latency ingestion, NUMA/SIMD aggregation, lock-free queues, and Protobuf/FlatBuffers interfaces in §3/§26 are **over-built for the capacity** — documented as the scale-up path, not the build. The justified stack is the existing Python + cron.

**Highest-value next builds, in order:**
1. **Release-sniper** (roadmap #3, partial): poll CAG JSON from ~10:59:50 ET on print day, parse, fire Kalshi limit orders. **Must run on `caffeinate`/cloud, not a laptop loop** (June lesson: Mac slept through the print). Paper-mode first, hard caps. Order code is the missing piece.
2. **GHCN-M v4 + ERSSTv5 replication** (roadmap #2): highest-VOI uncertainty reduction (translation σ 0.047→~0.02).
3. **Rolling bias recalibration** each print (Kalman-style knob update) — cheap, closes the structural-break risk.

**Storage:** flat vintage-stamped files (CSV/JSON with retrieval timestamps) are sufficient at this cadence; a full vintage DB with checksums/parser-versions is roadmap, not now.

---

## Part VIII — Final Decision Framework

| Model condition | Market condition | Risk condition | Action | Live status (Jul 22) |
|---|---|---|---|---|
| Strong NO edge (fair−ask ≥ 3¢) | NO liquidity | within \$300 cap | Accumulate NO | ✗ edge ≈ 0 |
| Strong YES edge | ask liquidity | within cap | Accumulate YES | ✗ |
| Small edge | wide spread | normal | Passive or no trade | **← current: no trade** |
| Model disagreement (GFS vs ECMWF surge) | any | normal | Reduce sizing | partially (25% coinflip) |
| Data stale | any | any | Cancel + halt | monitored |
| Structural break (dev3 > 0.05) | any | any | Recalibrate + reduce | **dev3 fired (dip)** — bracket-quoted |
| Settlement ambiguity | any | any | Do not trade | n/a (rules clear) |

**Bottom line.** July 2026 has repriced from a longshot NO into a near-coinflip (P(YES) ≈ 25% NOAA, member-distribution; up from 2%). **The mispricing edge is gone** — model fair NO ≈ 75¢ ≈ market NO ask. The held ~326 July NO is a legacy position at ~4× the model cap with ~0 fresh edge; the only thing favoring it is the structural tie-band cushion. The durable, repeatable alpha in this whole program is **not** monthly directional bets — it is the **NOAA-release latency snipe** on print day, capacity-capped at hundreds of dollars, which must be moved off the laptop before the ~Aug 13 July print.

**Arbitration ahead:** Jul 17 actual lands ~Jul 19 midday UTC (models 0.17 apart on that day); surge-peak days verify Jul 21–24; ~Aug 13 NOAA July print settles the market.

---

### Analytical-standards compliance note
Executable (not mid) prices used throughout; fees/spread/depth included; parameter uncertainty quoted as brackets not points; historical vintages preserved; no risk-free-arbitrage claims (cross-oracle is basis, not arb); insufficient-data items (`[UNAVAILABLE]` NOAA v6.1 rumor, L3 data, exact release minute) flagged rather than invented. The framework is sized to the market's real \$1–3k capacity — the full institutional C++/EVT/Hawkes apparatus is documented as a scale-up path and explicitly *not* built, because at ~12 events/yr it would cost more than the edge it chases.
