# Hottest-Month-Analysis — Kalshi KXHMONTH pricing model

## Purpose

Produce an honest, defensible probability that a given month sets a global
temperature record, and trade the gap against Kalshi's KXHMONTH market
("Will ‹month› ‹year› be the hottest ‹month› ever?").

The edge is **timing**: ERA5 publishes a global daily temperature with a ~2-day
lag; NOAA — which actually settles the contract — publishes ~day 8–14 of the
following month. This project converts the fast daily signal into the slow
settlement number weeks before the print.

The deliverable is **a calibrated probability, not a forecast**. Being
directionally right while overstating confidence is a failure, not a win.

---

## How to communicate in this project

The user is quantitatively fluent and time-constrained. Optimize for decisions,
not for demonstrating work.

**Lead with the answer.** Number first, evidence second, methodology only if
asked or if it changes the number.

**Only surface information that can change a decision.** Cache states, byte
counts, file mtimes, "I verified X matches Y" — that is internal plumbing. Do
not narrate it. If a check matters, report only its *consequence* ("data was 2
days stale, so that 40.8% was computed on the wrong day count").

**Never let prose outrun the model.** If the model says 14%, do not write
"mathematically settled" or "no scenario where YES wins." Calibrate language to
the number. This has been a real, repeated failure in this project.

**Report brackets, not false precision.** When engines disagree (deterministic
vs ensemble vs multimodel), quote the range and name which is which. A single
number hiding a 3%–40% spread is a lie.

**Own errors in one line and move on.** State the correction, fix it, continue.
No apology paragraphs, no re-litigating.

**Formats that work here:** scenario tables with an explicit verdict column;
"what would change my mind" trigger tables with thresholds; arrival calendars
with exact local times. Prefer these to prose.

**Do not act on the market unasked.** Report fair value, market price, and the
arithmetic. The position decision is the user's. There is no order-placement
code in this repo by design — keep it that way unless explicitly instructed.

---

## The model

```
ERA5 daily anomalies  →  month-to-date mean
      + forecast for remaining days (ECMWF IFS, anchored to ERA5)
      →  full-month ERA5 estimate
      →  NOAA = a + b × ERA5        (per-month OLS, fit 1990–…)
      →  Normal tail vs threshold  →  fair price  →  edge vs book
```

August: `NOAA = 0.5892 + 0.9619 × ERA5`, σ = 0.0357, n = 36.
July:   `NOAA = 0.5686 + 0.8891 × ERA5`, σ = 0.0360, n = 36.
June:   `NOAA = 0.5871 + 0.9064 × ERA5`, σ = 0.0451.

**The pipeline is month-generic (rolled over 2026-07-31).** `update_data.py`,
`ens_spread.py` and `daily_check.py` target `datetime.now().month` and roll at
midnight on the 1st; `--month YYYY-MM` pins any month. Coefficients, thresholds,
record values and day counts are all derived from the data — **nothing is
hardcoded to a month any more.** `data.js` exposes `model.cur` / `model.prev`
(3-letter keys) and the per-month blocks live under those names.

### Threshold discipline — get this right every time

NOAA prints to **2 decimals**, so the bar is always **record + 0.005**, never the
record. A tie is not "the hottest" and **pays NO**.

| Month | Record | WIN needs print | True value | ERA5 equivalent |
|---|---|---|---|---|
| **August** | **1.25** (2023) | 1.26 | ≥ **1.255** | **0.69216** |
| July | 1.18 (2024) | 1.19 | ≥ 1.185 | 0.69328 |

Both records **verified live and unrevised 2026-07-31** (roadmap #2 closed).
Quoting the record itself instead of record+0.005 overstates P(YES) by ~7–9
points — this mistake has been made here; do not repeat it.

Every script now derives the threshold from `record + 0.005` and the ERA5 bar
from `(thr − a) / b`. The old hardcoded `0.694` in `daily_check.py` is gone.
Note the near-coincidence: July needed ERA5 0.69328, August needs 0.69216 —
almost the same bar for a record 0.07 higher, because August's slope is steeper.

### Contract rules (verified against `docs/HMONTH.pdf`, Jul 2026)

- Payout criterion: *"…is the hottest ‹month› recorded."* **There is no numeric
  strike in the contract** — it is a comparison to the record, not a threshold.
- A tie is not "the hottest." Base case: **tie = NO**. Not airtight; there is no
  explicit tie clause and Kalshi retains a Market Outcome Review Process.
- *"Revisions made after Expiration will not be accounted for"* → revisions
  **before** expiration **do** count. **The record itself can move.** If NOAA
  revises July 2024 down off 1.18, a 1.18 print in 2026 wins. Unmodeled.
- The PDF says last trading = last day of month. **Superseded by the live market
  config** (`close_time` ≈ 2 weeks after month end; June traded through its Jul 9
  settlement). Verify via the API, not the PDF.

---

## Non-negotiable invariants

**Anchor every forecast to ERA5 before use.** Raw model global means carry
per-center absolute biases of ±0.12 °C. Anchoring removes them. An unanchored
multi-center spread is mostly calibration offset, not predictive uncertainty —
measured: ~57% of the maximum between-center spread is already present at zero
forecast lead.

**Sanity-guard the anchor.** A valid offset is ~±0.15. `ens_spread.py` asserts
`abs(off) < 0.5`. Any throwaway analysis script must do the same — an unguarded
script once produced a plausible-looking "ICON = 63.8%" from a −5.9 °C offset.
**Never report a number from a script lacking this assert.**

**Anchor forecast-skill measurements only on days observable at pull time.**
Scoring an archived pull while anchoring it on days that were still unpublished
then leaks the answer into the offset and shrinks the apparent error ~3×. The
correct cutoff is `pull_date − 2` (ERA5's lag) — `daily_check.pull_anom` does
this; ad-hoc skill scripts usually do not. This produced a wrong lead-error
table here on 2026-07-31.

**Verify a new calculation against the production pipeline before trusting it.**
The reconstruction that reproduced production exactly (r = 1.0000) was
trustworthy; a coarser-grid version was noise dressed as signal and gave the
opposite answer.

**Decompose taker flow before believing a price move.** Contracts ≠ dollars. A
20-point YES crash on "4,630 volume" was ~$180 of two-way flow in a thin book,
fully retraced within the hour.

**Check data freshness explicitly.** `update_data.py` refetches only when files
are >6h stale (`stale()`, ~line 60). If a refetch fires minutes before ERA5
publishes, the guard serves stale data through the next run. Symptom: `k` does
not advance. Fix: `touch -t <yesterday> era5_daily.csv`, then re-run.

---

## Current state — 2026-07-31 (rolled over to August)

**July is settled bar the print. August is a coin flip and it is the live book.**

### July (settles Aug 8, 10:00 ET)
- k=29, MTD **+0.6698**. Required over the last 2 days: **+1.033/day** —
  impossible (hottest July day ever recorded: +0.905). Weather path closed.
- P(YES) ≈ **29%**, entirely the ERA5→NOAA translation residual. Market YES 21/22.
- Position per earlier notes: ~741 NO @ ~77¢. **UNVERIFIED** — see Auth below.

### August (settles Sep 8, 10:00 ET · `KXHMONTH-26AUG`)
- Record **1.25** (2023); needs a **1.26** print → ERA5 ≥ **+0.69216**.
- **Central estimate ~30%. Bracket 20–45%.** Market YES **41/46** — so the market
  is at or above fair, and buying YES here is *not* supported.
- Built from the ERA5-anchored native multimodel (`20260730_12z`, Aug 1–8):
  physics-only equal-center **27.4%**, all-4 equal-center 31.9%, per-center
  23.2% (GEFS) → 46.6% (AIFS). Newest Open-Meteo deterministic (00z Jul 31)
  reads 20.5% on the same window.
- **`data.js` / the dashboard will show ~55% until the next `ens_spread.py` run.**
  That number came from the pre-fix 3-day anchor and reads ~10–20 points warm —
  see "The ensemble feed reads warm" below. The Open-Meteo daily API quota was
  exhausted on 2026-07-31, so the corrected run lands with the 07:15 job.
- Window matters as well as feed: the same Open-Meteo ensemble gives 44.6% on
  Aug 1–8 but 55.4% on Aug 1–12, because days 9–12 sit at leads 10–13 where the
  measured cold-bias/noise is largest. Prefer the shorter, better-verified window.

### August-specific structure worth knowing
- **σ does not collapse the way July's did.** Translation σ = 0.0357 is a hard
  floor: even with all 31 days observed and ERA5 landing exactly on +0.694, fair
  value is ~52¢. Weather data moves the *mean*, not the *spread*. To price above
  85¢ this needs ERA5 ≈ +0.731. **Do not plan to "wait for the data to prove it."**
- The two Augusts anywhere near this ERA5 level both printed **below** the line:
  2023 resid −0.023, 2024 resid −0.035. Across the 8 warmest Augusts the mean
  residual is −0.002, so it is not a general high-end bias — but those two define
  the threshold. Curvature is not significant (quadratic sd 0.0358 vs linear
  0.0357) yet drags the estimate −0.012.
- **Measured IFS cold bias, leakage-free (Jul 2026, n=251):** anchored IFS runs
  cold +0.09 at lead 1 rising to +0.31 at lead 12, **219/251 days positive**.
  Regime-split it survives (plateau/decline pulls: +0.079). One month, ~2
  effective independent samples — sets the *direction* of skew, not the center.
  My first pass at this table was wrong because it anchored on days unobserved at
  pull time; always anchor on days ≤ pull−2 (`daily_check.pull_anom`).

### Open questions, ranked by money at risk
1. **Is the translation line flatter at the top?** Three quasi-independent reads
   (2018–25 refit, 2023/24 residuals, quadratic) all land 1.232–1.245. OOS RMSE
   cannot separate fit windows (0.032–0.035 for every window 8y→expanding), so it
   stays unresolved. Note it matters *less* now that the feed fix pulled the
   central ERA5 down to ~+0.664 (NOAA ~1.228) — the fit variants and the
   production fit now cluster instead of straddling the threshold. **~10 points**,
   and it becomes the dominant question again if August verifies warm.
2. **Residual persistence** — lag-1 month ρ = 0.49 (t = 11.4), Aug-on-Jan–Jul
   slope 0.63 (t = 2.5); 2026 is running +0.022 warm. But applying it *raises*
   OOS RMSE (0.0341 → 0.0364) while cutting bias. Do not run it as the center.
3. **Tie rule** — ~6 points of the August distribution; reads NO, not airtight.

### Validated results worth keeping

- June 2026: model predicted 1.094, NOAA printed **1.09**. Exact.
- Jul 28 2026: bias-anchored ECMWF predicted **+0.742**, actual **+0.742**. Exact.
  Same day, AIFS (warmest AI ensemble) missed by −0.089, confirming its warm bias
  on the first verification datapoint.
- Translation σ is honest: out-of-sample RMSE 0.0364 vs in-sample 0.0360.
- ERA5 `PRELIMINARY` → `FINAL` revisions run **+0.007** (6/6 positive, and Jul 28
  made it 7/7 at +0.006). Small but free and well-identified.
- The month-generic rewrite reproduces the pinned July fit exactly
  (`--month 2026-07` → 0.5686 + 0.8891, σ 0.0360, bias +0.0224). Any future
  refactor should be checked the same way before it is trusted.
- Deriving thresholds from data instead of hardcoding immediately caught a wrong
  guess: the GISTEMP August record is **1.30 (2024)**, not 1.31.

### The ensemble feed reads warm — measured 2026-07-31, act on this

Roadmap #3 was run for the first time (GEFS + GEPS + IFS ENS, native GRIB,
`20260730_12z`, all ERA5-anchored). It did **not** find big structural
disagreement. It found a problem with our own primary feed.

| Feed (identical days, Aug 1–8, `20260730_12z`) | Aug 1–8 anchored | 1-day-out error | P(YES) |
|---|---|---|---|
| GEFS native | +0.6630 | −0.005 | 23.2% |
| GEPS native | +0.6721 | **+0.001** | 25.6% |
| IFS ENS native GRIB | +0.7006 | +0.034 | 33.9% |
| AIFS ENS native GRIB | +0.7397 | — | 46.6% |
| **IFS ENS Open-Meteo (`ens_spread.py`)** | **+0.7339** | **+0.092** | **44.6%** |
| physics-only equal-center (GEFS+GEPS+IFS) | +0.6786 | — | **27.4%** |
| all-4 equal-center (incl. AIFS) | +0.6939 | — | 31.9% |

AIFS runs **+0.101 °C warmer than IFS** across the period (consensus diagnostic),
which matches its one prior verification miss of −0.089. Prefer the physics-only
consensus as the center and treat AIFS as the warm edge of the bracket.

- **Raw between-center offsets span 0.123 °C** — anchoring is not optional, and
  the invariant is confirmed rather than merely asserted.
- **After anchoring the centers agree closely**: Aug 1–6 daily spread 0.007–0.047,
  widening to 0.13 only by day 8. Between-center spread contributes 0.019 °C to
  the full-August ERA5 estimate against a σ/b of 0.060 — **structural uncertainty
  is ~1/3 of σ and is not what is driving this market.**
- **`ens_spread.py`'s 288-point 15° grid is the least accurate feed tested.** It
  read +0.033 warm vs native IFS on identical days and missed the only 1-day-out
  verification by +0.092. Its anchor offset moved −0.179 → −0.109 depending on
  which days were used, i.e. the "offset" is partly grid sampling noise, not a
  calibration constant. Worth **10–20 points of P(YES)**.
- **Fix applied**: `past_days` 5 → 14, so the offset averages over ~13 days
  instead of 3. Zero extra API calls. Effective from the next run.
- **Do not trust an `ens_spread.py` number produced before 2026-07-31 to better
  than ±0.03 °C on the global mean** (≈ ±10 points of P).

### Anti-results — tested and rejected, do not redo

- **EMA / short-window anchor offsets do not beat the flat 4-day mean.** Tested
  May–July on production-validated data (n=60): every bootstrap CI includes zero.
  Leave-one-month-out shows tuning α *loses* to flat in 2 of 3 folds; the
  per-month optimum ranges 0.15–0.99. Linear trend extrapolation is catastrophic
  (RMSE 0.10 vs 0.046).
- ~~The anchor offset is only ~8% of total variance; perfecting it cannot move
  P(YES) by more than ~3 points.~~ **Superseded 2026-07-31.** That held for the
  *deterministic* 10° feed's day-to-day offset. The 15° ensemble grid's offset
  carries sampling noise worth ~0.03 °C ≈ 10–20 points — see above.
- **Translation σ still dominates once the feed is fixed** — 0.0357 is a hard
  floor no amount of weather data removes (roadmap #1).

---

## Files

Every script resolves data via `os.path.join(HERE, …)`. **Do not move `.py`
files, `era5_daily.csv`, `data.js`, `noaa_m*.json`, `gistemp.txt`, or
`forecast_log/` out of the repo root.** `daily_check.py` and `update_data.py`
hardcode the string `'July Calibration'` — that folder cannot be renamed (the
name is now historical; it holds the live ensemble engine for every month).

| Path | Role |
|---|---|
| `update_data.py` | Data engine: ERA5 + NOAA + Kalshi + IFS → recomputes model → writes `data.js`. Month-generic; `--month YYYY-MM` pins. Uses `curl` (python.org SSL certs are broken here — keep it). |
| `daily_check.py` | Scheduled job: refresh → ensemble → rebuild → score forecast vs actual → append `track_log.csv` → notify. Threshold and per-day "need" derived from the record; digest is month-tagged. |
| `fetch_forecast.py` | ECMWF IFS pull via Open-Meteo; `to_anomaly()` computes the anchor offset. |
| `July Calibration/ens_spread.py` | 51-member IFS ensemble → member-level P(YES). Month-generic (`--month`); NOAA **and** GISTEMP thresholds derived from the data. Writes `year`/`month` into its JSON — `update_data.py` **rejects** an ens file whose month ≠ target, so a stale July file can never be served as August. Quota-limited (per-minute); retries back off 65 s. |
| `July Calibration/calibrate.py` | Kalman/rolling-β drift, HC1, ENSO σ tests, Kelly sizing. **Pinned to July on purpose** (campaign audit); skips its live-repricing block unless `data.js` targets July. |
| `xlsx_sync.py` | Keeps `KXHMONTH_2026 (decision).xlsx` in sync in place. `--auto` (used by `daily_check.py`) builds the month tab if missing then refreshes; bare run refreshes input cells only; `--charts` rebuilds charts. **Refuses to write while the workbook is open in Excel** (`~$` lock). Layout constants at the top must match the sheet — HDR 18, pre-month 19–22, month starts row 23. |
| `multimodel_check.py` | ERA5-anchored GEFS/GEPS/IFS/AIFS cross-check against `../Global-Temperature-Model` outputs. `python3 multimodel_check.py <anchor_run> <live_run>` — the anchor run must overlap observed ERA5. Reports per-center P(YES), physics-only vs all-center consensus, and the native-vs-Open-Meteo pipeline gap. |
| `backtest.py`, `overfit_test.py` | Out-of-sample calibration, tail shape, overfit audits. Month-generic. |
| `kalshi_client.py` | **Read-only** (balance/positions/fills). No order code by design. |
| `era5_watch.sh` | Polls for a given ERA5 day; logs publish time to `era5_release_times.csv`. Uses `caffeinate`. |
| `Dashboard.html` | Live dashboard; reads `data.js`. Serve with `python3 -m http.server`. |
| `Model_Analysis.ipynb`, `Kalshi.ipynb` | Documented model + market analytics. |
| `docs/` | `HMONTH.pdf` (contract rules), spreadsheets, notes. Not read by code. |
| `archive/` | Retired: June sniper, `variance_collapse.*`, legacy `noaa_june/july.json`. Zero references. |

### Automation

launchd `com.hottestmonth.daily`, 07:15 local, runs `daily_check.py`.

```bash
launchctl kickstart -p gui/$UID/com.hottestmonth.daily
```

Logs to `~/Library/Logs/hottestmonth-daily.log`. **The log path must stay outside
`~/Desktop`** — launchd opens it before exec, and a TCC-protected path makes the
job die with `EX_CONFIG (78)` without running a line. That silently killed the
job for 8 days.

### Auth

`.env` + `kalshi_demo.pem` — the file is **misnamed; it is a production key**.
`KALSHI_ENV` must be `prod`; with `demo` the API returns 401 and positions cannot
be read. Never commit `.env` or `*.pem` (both gitignored).

---

## Data schedule (empirically measured)

| Source | Timing |
|---|---|
| ERA5 daily | 2-day lag. Publishes **00:14–01:47 EDT** (n=5; the older "06:00–12:35 UTC" note was too late). Newest day is always `PRELIMINARY`. |
| Open-Meteo ensemble API | Per-**minute** request cap. `ens_spread.py` sleeps 5 s between batches and backs off 65 s on refusal; a sub-60 s retry ladder just burns attempts inside the same window. |
| Model runs on API | 00z ≈ 01:00–04:00 EDT; 12z ≈ 13:00–16:00 EDT |
| NOAA monthly print | ~day 8–14 of the following month, 10:00 ET |
| GISTEMP | ~mid-month (Polymarket's source, **not** Kalshi's) |

---

## Roadmap, in value order

1. **Reduce translation σ** — replicate NOAAGlobalTemp from GHCN-M v4 + ERSSTv5.
   σ 0.036 → ~0.02. This is now the *only* lever that materially moves a
   probability; everything else is noise around it.
2. ~~Verify the record value~~ — **done 2026-07-31**: NOAA still publishes 1.18
   for July 2024 and 1.25 for August 2023. Re-check before each settlement.
3. **Multimodel consensus** (`../Global-Temperature-Model`) — GFS/GEFS/GEPS/GDPS/
   ICON/IFS/AIFS at native resolution. Infrastructure is strong but it has almost
   no verification history. **Anchor each center to ERA5 before using it.** Its
   structural-uncertainty finding matters most mid-month, with 20+ forecast days
   open — which is exactly August's situation now. Note runs at `--max-hour 240`
   reach only ~day 10, so it cross-checks the first-third window rather than
   extending the horizon; anchoring needs a prior run that overlaps observed ERA5
   (a fresh 12z init has **zero** overlap — ERA5 lags 2 days).
4. Release sniper for the NOAA print (needs an always-on host; the Mac sleeps).
5. Q4 2026: CPC has 63% very-strong El Niño NDJ. Records cluster in such bursts —
   "NO everything" is the losing habit there; YES may be the value side.
