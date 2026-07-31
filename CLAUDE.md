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
      →  NOAA = a + b × ERA5        (per-month OLS, fit 1990–2025)
      →  Normal tail vs threshold  →  fair price  →  edge vs book
```

July: `NOAA = 0.5686 + 0.8891 × ERA5`, σ = 0.0360, n = 36.
June: `NOAA = 0.5871 + 0.9064 × ERA5`, σ = 0.0451.

### Threshold discipline — get this right every time

NOAA prints to **2 decimals**. The July record is **1.18** (2024).

| Outcome | NOAA print | True value | ERA5 equivalent |
|---|---|---|---|
| **WIN** | 1.19 | ≥ **1.185** | **0.69328** |
| TIE — **settles NO** | 1.18 | ≥ 1.175 | 0.68765 |

Always price against **1.185 / ERA5 0.69328**. The tie band is ~10% of the
distribution and it pays NO. Quoting the 1.18 threshold overstates P(YES) by
about 9 points — this mistake has been made here; do not repeat it.

Known cosmetic inconsistency: `daily_check.py` hardcodes `0.694` for its "need"
figure instead of `0.69328`, so its per-day number runs ~0.007 high. Harmless in
the digest, but do not quote it as the precise bar.

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

## Current state — 2026-07-30

**July is effectively decided; only the translation residual is live.**

- k=28, MTD **+0.6684**, 3 days left. Required: **+0.9255/day**.
- Hottest July day ever recorded: **+0.905**. Hottest July 2026 day: **+0.794**.
- **Even three consecutive all-time-record days → 1.1832 → prints 1.18 → tie →
  NO.** The weather path is arithmetically closed.
- P(YES) ≈ **28%**, now ~entirely "does the ERA5→NOAA residual print ≥ +0.021
  warm." No remaining daily data can move it.
- Market YES ≈ 22/23 — model and market within a couple of points, no edge.
- Position per earlier notes: ~741 NO @ ~77¢. **UNVERIFIED** — see Auth below.
- NOAA July print: Kalshi `expected_expiration_time` = **Aug 8, 10:00 ET**
  (older notes said ~Aug 13; trust the API).

### Open questions, ranked by money at risk

1. **Translation slope drift** — full-sample fit says 28%; a 2018–2025 refit says
   ~8%. The slope difference is z ≈ −2. **But out-of-sample testing says do not
   switch**: shorter fit windows do not reduce RMSE and they double-to-triple the
   bias. Keep the full fit; revisit as more high-ERA5 Julys accumulate. ~20 points.
2. **Tie rule** — 10% of the distribution; reads NO, not airtight.
3. **Record revision** — is NOAA still publishing 1.18 for July 2024? Never
   checked. Cheap.

### Validated results worth keeping

- June 2026: model predicted 1.094, NOAA printed **1.09**. Exact.
- Jul 28 2026: bias-anchored ECMWF predicted **+0.742**, actual **+0.742**. Exact.
  Same day, AIFS (warmest AI ensemble) missed by −0.089, confirming its warm bias
  on the first verification datapoint.
- Translation σ is honest: out-of-sample RMSE 0.0364 vs in-sample 0.0360.
- ERA5 `PRELIMINARY` → `FINAL` revisions run **+0.007** (6/6 positive). Small but
  free and well-identified.

### Anti-results — tested and rejected, do not redo

- **EMA / short-window anchor offsets do not beat the flat 4-day mean.** Tested
  May–July on production-validated data (n=60): every bootstrap CI includes zero.
  Leave-one-month-out shows tuning α *loses* to flat in 2 of 3 folds; the
  per-month optimum ranges 0.15–0.99. Linear trend extrapolation is catastrophic
  (RMSE 0.10 vs 0.046).
- The anchor offset is only ~8% of total variance. Perfecting it cannot move
  P(YES) by more than ~3 points. **Translation σ dominates — that is where the
  remaining value is** (roadmap #1).

---

## Files

Every script resolves data via `os.path.join(HERE, …)`. **Do not move `.py`
files, `era5_daily.csv`, `data.js`, `noaa_m*.json`, `gistemp.txt`, or
`forecast_log/` out of the repo root.** `daily_check.py` and `update_data.py`
hardcode the string `'July Calibration'` — that folder cannot be renamed.

| Path | Role |
|---|---|
| `update_data.py` | Data engine: ERA5 + NOAA + Kalshi + IFS → recomputes model → writes `data.js`. Uses `curl` (python.org SSL certs are broken here — keep it). |
| `daily_check.py` | Scheduled job: refresh → ensemble → rebuild → score forecast vs actual → append `track_log.csv` → notify. |
| `fetch_forecast.py` | ECMWF IFS pull via Open-Meteo; `to_anomaly()` computes the anchor offset. |
| `July Calibration/ens_spread.py` | 51-member IFS ensemble → member-level P(YES). Quota-limited; tolerate failure. |
| `July Calibration/calibrate.py` | Kalman/rolling-β drift, HC1, ENSO σ tests, Kelly sizing. |
| `backtest.py`, `overfit_test.py` | Out-of-sample calibration, tail shape, overfit audits. |
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
| Model runs on API | 00z ≈ 01:00–04:00 EDT; 12z ≈ 13:00–16:00 EDT |
| NOAA monthly print | ~day 8–14 of the following month, 10:00 ET |
| GISTEMP | ~mid-month (Polymarket's source, **not** Kalshi's) |

---

## Roadmap, in value order

1. **Reduce translation σ** — replicate NOAAGlobalTemp from GHCN-M v4 + ERSSTv5.
   σ 0.036 → ~0.02. This is now the *only* lever that materially moves a
   probability; everything else is noise around it.
2. **Verify the record value** — is NOAA still publishing 1.18 for July 2024?
3. **Multimodel consensus** (`../Global-Temperature-Model`) — GFS/GEFS/GEPS/GDPS/
   ICON/IFS/AIFS at native resolution. Infrastructure is strong but it has almost
   no verification history. **Anchor each center to ERA5 before using it.** Its
   structural-uncertainty finding matters most mid-month, with 20+ forecast days
   open — not in the final week.
4. Release sniper for the NOAA print (needs an always-on host; the Mac sleeps).
5. Q4 2026: CPC has 63% very-strong El Niño NDJ. Records cluster in such bursts —
   "NO everything" is the losing habit there; YES may be the value side.
