# Hottest Month — global temperature forecasting and KXHMONTH market pricing

Two connected systems built around one question: **what will the global mean temperature print at, and what is that worth?**

| Part | System | Purpose |
| --- | --- | --- |
| **I** | **Hottest Month** (this repository) | Prices Kalshi's `KXHMONTH` markets — *"Will \<month\> 2026 be the hottest \<month\> on record?"* — from ERA5 daily anomalies plus NWP forward paths. |
| **II** | **Global Temperature Forecast and Verification** (`../Global-Temperature-Model`) | Computes area-weighted whole-Earth mean 2-meter temperature from seven operational forecast systems, builds a multimodel consensus, and verifies against ERA5T. |

Part I is a live trading model with realized P&L. Part II is the rigorous forecast engine intended to replace Part I's forward path — a calibrated seven-center consensus in place of a hand-blended set of deterministic runs and one ensemble family.

The two use ERA5 differently, and the distinction matters:

- Part I uses **ERA5 daily global-mean *anomaly*** (Climate Pulse CSV), because Kalshi settles on an anomaly versus the 1901–2000 baseline.
- Part II uses **ERA5T absolute 2-meter temperature** (Copernicus CDS, hourly fields), because forecast verification needs the same physical quantity the models produce.

---

# Part I — Hottest Month (Kalshi KXHMONTH)

Markets settle on the **NOAA NCEI Climate-at-a-Glance** global land+ocean temperature anomaly (2 decimals, baseline 1901–2000). Contract rules are in [HMONTH.pdf](HMONTH.pdf).

## The edge

NOAA publishes the settlement number around day 9–14 of the *following* month. ERA5 publishes daily global-mean anomalies with only a ~2-day lag. The model translates the fast signal into the slow settlement number before the print, and turns that into a fair price to compare against the book.

Capacity is bounded by book depth (~$1–3k per event, ~12 events/year). This is scheduled-event latency arbitrage, not HFT.

## How the model works

```
ERA5 daily anomalies
  └─ month-to-date mean
       └─ incomplete month: OLS  full = c0 + c1·prev_month + c2·first_k_days
            └─ per-month OLS     NOAA = a + b·ERA5      (fit 1990–2025)
                 └─ Normal tail vs (record + 0.005)     (2-decimal rounding)
                      └─ fair price  →  edge vs book  →  ¼-Kelly, depth- and cap-limited
```

Refinements layered on top:

- **NWP forward path** — remaining-days mean from ECMWF HRES, GFS, ICON and GEM replaces the pure-climatology tail, collapsing variance ~10 days earlier in the month.
- **51-member ECMWF ENS** (`July Calibration/ens_spread.py`) — member-level global means via the Open-Meteo ensemble API. Probability is averaged over members rather than taken from the deterministic path, which otherwise hides real tail mass.
- **Bias knob** — a rolling correction for NOAA prints running warm or cool against the historical ERA5→NOAA mapping. Reported as a bracket (raw vs biased), not a point.
- **`dev3` tripwire** — 3-day mean forecast-vs-actual deviation on verified days, leakage-free anchored. Beyond ±0.05 °C the forward path is not trusted.
- **Calibration checks** (`July Calibration/calibrate.py`) — Kalman/rolling-β drift, White HC1 heteroskedasticity, El Niño σ-expansion (Levene). All three came back negligible; kept as regression guards.

Sizing takes the **worst-tail** probability across methods (t-distribution, ENS, floor), then ¼-Kelly, then a depth proxy, then a hard dollar cap.

## Repository layout

| Path | What it is |
| --- | --- |
| `Model_Analysis.ipynb` | Full documented model: data → OLS translation → normal tail → EV/Kelly. Set `REFRESH=True`, Run All. |
| `Kalshi.ipynb` | Market analytics: series history, taker-flow decomposition (contracts vs dollars), NOAA record base rates, fees/depth, hedging, position sizing. |
| `update_data.py` | Data engine. Fetches ERA5 + NOAA CAG + Kalshi public API, recomputes the model, writes `data.js`. |
| `daily_check.py` | Scheduled run: full refresh → forecast-vs-actual deviation → appends `track_log.csv` → macOS notification (⚠️-prefixed when `dev3` breaches). |
| `fetch_forecast.py` | NWP forward-path retrieval (ECMWF / GFS / ICON / GEM deterministic runs). |
| `kalshi_client.py` | Authenticated Kalshi client — RSA-PSS-SHA256 request signing. **Read-only** (balance, positions, fills); no order placement. |
| `Dashboard.html` | Live dashboard; reloads `data.js` every 5 minutes. |
| `backtest.py`, `overfit_test.py`, `variance_collapse.py` | Validation harnesses: historical replay, overfit checks, variance-collapse curve. |
| `July Calibration/` | Multi-angle stress test of the July 2026 market — ensemble spread, calibration, market angles, playbook and analysis writeups. |
| `era5_daily.csv`, `noaa_m*.json`, `gistemp.txt`, `kalshi_data/` | Cached source data. `gistemp.txt` is NASA GISTEMP (Polymarket's settlement source, *not* NOAA's). |
| `forecast_log/`, `track_log.csv` | Append-only forecast and deviation history. |
| `CLAUDE.md` | Working research log — dated model states, decisions, open questions, lessons. |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Kalshi credentials are optional — everything except `kalshi_client.py` runs on public data.

```bash
cp .env.example .env
```

Then create an API key in Kalshi settings, save the private key **outside this repository**, and point `KALSHI_PRIVATE_KEY_PATH` at it. `.env` and `*.pem` are gitignored; keep them that way.

## Running

```bash
python3 update_data.py
```

Continuous refresh (24/7 mode, 900-second interval):

```bash
python3 update_data.py --loop 900
```

Serve the dashboard from the repository root, then open `http://localhost:8000/Dashboard.html`:

```bash
python3 -m http.server 8000
```

Ensemble spread for one model family (`ecmwf_ifs025`, `gfs025`, `icon_seamless`, `gem_global`):

```bash
python3 "July Calibration/ens_spread.py" ecmwf_ifs025
```

All four families sequentially, with pauses that respect the Open-Meteo minutely quota — note the script contains an absolute `cd` path and needs editing for another machine:

```bash
bash "July Calibration/run_all_ensembles.sh"
```

## Automation

`daily_check.py` runs at 07:15 local via launchd (`com.hottestmonth.daily`, plist at `~/Library/LaunchAgents/`), and fires on wake if the machine slept through the window.

```bash
launchctl kickstart gui/$UID/com.hottestmonth.daily
```

The launchd plist is machine-local and not tracked here.

## Data schedule (empirically verified)

| Source | Timing |
| --- | --- |
| ERA5 daily | 2-day lag, updates ~06:00–12:35 UTC |
| NWP 00z runs | on API ~05:00–08:00 UTC |
| NWP 12z runs | on API ~17:00–20:00 UTC |
| NOAA monthly print | ~day 9–14 of the following month, ~11:00 ET — settles the market |
| NASA GISTEMP | ~mid-month following |

## Known constraints and gotchas

- **SSL** — python.org's certificate store fails against several of these endpoints. `update_data.py` shells out to `curl` on purpose; don't "fix" it back to `requests`.
- **Download validation** — climate files refetch only when >6h stale and are validated on arrival; silent truncation has happened before.
- **Ensemble quota** — the Open-Meteo ensemble endpoint is rate-limited. `ens_spread.py` retries, but a busy period still returns partial member sets; retry off-peak.
- **Verify sources literally** — fetched-page summaries have relabelled months in the past. Check the archive URL, not the summary.
- **Cross-platform basis risk** — Polymarket's equivalent brackets settle on NASA GISTEMP, where ties count *into* brackets. Different dataset, different record, not a clean hedge.
- **Record clustering** — record months cluster inside El Niño bursts, which correlates outcomes across months. A standing "NO everything" habit is the losing one during a strong-Niño stretch.
- **Report brackets, not points** — deterministic paths, ensemble medians and forecast-free methods routinely disagree by 0.15 °C on remaining-days mean. When they do, that spread *is* the answer.
- **Fit sample is small** — the per-month ERA5→NOAA regression fits ~36 observations. Extreme-value refinements on that sample were evaluated and declined as unsupportable.

## Roadmap

1. **Replace the forward path with the Part II consensus** — the seven-center, area-weighted, ERA5T-verified system below, instead of a hand-blend of deterministic runs plus one ensemble family. Biggest bang, and the reason Part II exists.
2. **NOAA-input replication** — GHCN-M v4 plus preliminary ERSSTv5 (~day 3–5) to reconstruct NOAAGlobalTemp directly, targeting translation σ 0.047 → ~0.02.
3. Kalshi authenticated trading — websocket book depth, flow surveillance, order placement. Paper mode first, hard risk caps.
4. Rolling Kalman-style bias recalibration each print; Student-t fat-tail option; backtest harness over 2015–2025.
5. Climate Reanalyzer / CFS as a lag-killer input; NMME and C3S seasonal for pricing Sep–Dec.

## Status

Research code, single-operator. It reads markets and prices them; it does not place orders. Only public data sources are used, and Kalshi permits API trading.

Current model state, position history and open questions live in [CLAUDE.md](CLAUDE.md) — it is dated and updated per print, and it is the file to read before trusting any number here.

---

# Part II — Global Temperature Forecast and Verification System

Code lives in the companion project `Global-Temperature-Model/` (repository: `Global-Temperature-Forecast-initial-model-and-data`). All paths in this part are relative to that root, not to this one.

## Overview

A reproducible multi-model system for estimating the daily whole-Earth mean 2-meter air temperature from operational numerical weather prediction and AI forecast systems.

It retrieves global 2-meter temperature fields, converts each field into an area-weighted global mean, aggregates six-hourly values into UTC daily means, summarizes ensemble uncertainty, builds a multimodel consensus, and verifies against ERA5T as observations arrive.

Seven forecast systems are supported:

- NOAA Global Forecast System (**GFS**)
- NOAA Global Ensemble Forecast System (**GEFS**)
- ECCC Global Deterministic Prediction System (**GDPS**)
- Deutscher Wetterdienst **ICON Global**
- ECCC Global Ensemble Prediction System (**GEPS**)
- ECMWF Integrated Forecasting System Ensemble (**IFS ENS**)
- ECMWF Artificial Intelligence Forecasting System Ensemble (**AIFS ENS**)

ERA5T is the realized reference for verification.

The design is built on immutable run identifiers, explicit provenance, run-scoped paths, cloud archival, integrity validation and repeatable verification. It is **not** a climate reanalysis, a surface-station product, or a replacement for an official global-temperature index. Its primary statistic is the spatially area-weighted whole-Earth mean of gridded 2-meter air temperature.

## Objectives

1. **Produce a reproducible global forecast statistic** — one physically interpretable scalar per field: the area-weighted whole-Earth mean in °C.
2. **Compare structurally different systems** — deterministic, physics ensemble, and AI ensemble on a common temporal and spatial framework.
3. **Separate internal ensemble uncertainty from inter-model structural disagreement.**
4. **Verify against realized conditions** — match forecast-valid dates to complete ERA5T days; compute model, member and calibration errors.
5. **Build an auditable pipeline** — run identity, manifests, file counts, checksums, cloud paths, validation results, machine-readable catalog.

## Current status

Reference cycle:

```text
Initialization: 2026-07-28 00Z
Run ID:         20260728_00z
```

| System | Type | Forecast coverage | Effective members |
|---|---:|---:|---:|
| GFS | Deterministic | 10 complete UTC days through +240 h | 1 |
| GEFS | Ensemble | 10 complete UTC days through +240 h | 31 |
| GDPS | Deterministic | 10 complete UTC days through +240 h | 1 |
| ICON Global | Deterministic | 7 complete UTC days through +180 h | 1 |
| GEPS | Ensemble | 10 complete UTC days through +240 h | 21 |
| IFS ENS | Ensemble | 10 complete UTC days through +240 h | 51 |
| AIFS ENS | AI ensemble | 10 complete UTC days through +240 h | 51 |

Multi-cycle readiness audit — clean:

```text
Errors:   0
Warnings: 0
Passes:   22
```

Cloud validation of the reference raw archive:

```text
Cloud objects: 1,652
Cloud bytes:   3,896,758,158
Restore test:  SHA-256 match
GRIB test:     restored file readable by ecCodes
```

Verification is not yet populated for the reference cycle: the available ERA5T archive has not reached the forecast-valid period. Operational status is therefore `WAITING_FOR_ERA5T` — an expected state, not a failure.

## System architecture

```text
Official forecast providers
        |
        v
Model-specific downloaders
        |
        v
Run-scoped raw GRIB storage
data/<model>/<run_id>/
        |
        v
Model-specific global processors
        |
        +---------------------------+
        |                           |
        v                           v
Six-hourly global means      Member-level global means
        |                           |
        +-------------+-------------+
                      |
                      v
UTC daily aggregation and ensemble summaries
                      |
                      v
Cross-model comparisons and multimodel consensus
                      |
                      v
ERA5T matching and verification
                      |
                      v
Run snapshot, manifest, catalog, readiness audit
                      |
                      v
Google Cloud Storage archive and restore validation
```

### Run identity

```text
RUN_ID = YYYYMMDD_CCz      e.g. 20260728_00z, 20260728_06z, 20260729_00z
```

A run ID must appear in raw directories, processed and verification filenames, snapshot directories, cloud object prefixes, manifest and catalog records, and log directories. Run scoping is what stops one cycle overwriting another; it is a core reproducibility requirement, not a naming convention.

## Data retrieved

### Common variable

Every downloader targets **2-meter air temperature**, which providers label variously:

```text
2t   t2m   TMP at 2 m above ground   AirTemp_AGL-2m   T_2M
```

The processing layer resolves the field, converts Kelvin to Celsius, and computes the whole-Earth spatial mean.

### Temporal sampling

Six-hourly: `f000, f006, f012, …, f240` — 41 forecast times for a +240 h system. A complete UTC day holds four snapshots (00, 06, 12, 18 UTC) and a daily row is marked complete only when all four are present.

### Per-model acquisition

**GFS** — deterministic NOAA. Global domain, 2-meter temperature, 0.25°, six-hourly, f000–f240, explicit initialization date and cycle, via NOAA NOMADS filtering.

```text
data/gfs/<run_id>/gfs_<run_id>_fHHH.grib2
```

Interface: `--date`, `--cycle`, `--max-hour`, `--overwrite`. Downloads write to a temporary `.part` file and atomically rename on completion; existing nonempty files are skipped, so interrupted runs resume.

**GEFS** — NOAA ensemble. One control plus 30 perturbed members (31 total), six-hourly through +240 h. Members are separated on disk:

```text
data/gefs/<run_id>/c00/
data/gefs/<run_id>/p01/
...
data/gefs/<run_id>/p30/
```

Each member's global mean is computed before ensemble summaries are constructed.

**GDPS** — deterministic Canadian global. Global 2-meter air temperature, six-hourly, f000–f240, 41 GRIB files, under `data/gdps/<run_id>/`.

**ICON Global** — deterministic DWD. ICON distributes temperature on an unstructured icosahedral grid; CCSDS packing support and invalid intermediate files were both resolved during development. The reference archive holds 93 ICON raw objects across 31 lead times from +0 h to +180 h, yielding seven complete UTC days. Native unstructured-grid handling is harder than regular lat-lon, so **ICON is the model most in need of production hardening and independent spatial-integration validation.**

**GEPS** — Canadian ensemble. 21 members, 41 forecast files, six-hourly through +240 h. A single GEPS file can carry all members for one lead time; the processor extracts member-level global means and builds daily ensemble statistics.

**IFS ENS** — ECMWF physics ensemble. One control plus 50 perturbed (51 total), six-hourly through +240 h, 41 control files and 41 perturbed-member files. Each perturbed file contains 50 ensemble messages; each control file contains one.

```text
data/ecmwf_ens/<run_id>/control/
data/ecmwf_ens/<run_id>/perturbed/
```

**AIFS ENS** — ECMWF AI ensemble. Same shape as IFS ENS (51 members, 41 + 41 files, six-hourly through +240 h):

```text
data/aifs_ens/<run_id>/control/
data/aifs_ens/<run_id>/perturbed/
```

AIFS is kept as a **distinct model center** and is never merged into IFS before the multimodel calculations — the AI-versus-physics comparison is one of the project's reasons for existing.

**ERA5T** — near-real-time reanalysis reference. Global 2-meter temperature, 24 hourly fields per complete UTC day, one file per date, under `data/era5t/YYYYMMDD/`.

The ERA5T processor computes two daily estimates:

1. the mean of all 24 hourly fields, and
2. the mean of the four forecast-matched six-hourly fields,

which makes the sampling difference between a true hourly daily mean and the forecast-compatible four-snapshot mean directly measurable rather than assumed.

At the reference snapshot, complete ERA5T existed for `2026-07-22` and `2026-07-23`; the forecast cycle starts `2026-07-28`, hence no overlap yet.

## Mathematical processing

### Area-weighted whole-Earth mean

On a regular latitude-longitude grid, grid cells are not equal-area — longitude spacing is near-uniform but cell area shrinks toward the poles. The global mean therefore uses latitude weights:

$$w_i = \cos(\phi_i)$$

where $\phi_i$ is latitude. For a temperature field $T_{ij}$:

$$\bar{T} = \frac{\sum_i \sum_j T_{ij}\cos(\phi_i)}{\sum_i \sum_j \cos(\phi_i)}$$

The processor also drops a duplicated longitude endpoint when both 0° and 360° are present, and converts Kelvin to Celsius:

$$T_{^\circ C} = T_K - 273.15$$

### Six-hourly output

Deterministic records carry:

```text
file, initialization_utc, valid_time_utc, forecast_hour,
global_temperature_c, date_utc
```

Ensemble records additionally carry:

```text
member, control_or_perturbed, members_available
```

### Daily aggregation

$$\bar{T}_d = \frac{1}{n_d}\sum_{k=1}^{n_d} T_{d,k}$$

where $n_d$ is the number of available six-hourly snapshots for date $d$. A day is complete when $n_d = 4$. Daily deterministic output includes:

```text
global_temperature_c, snapshots, minimum_snapshot_c,
maximum_snapshot_c, complete_day
```

### Ensemble summaries

```text
ensemble_mean_c, ensemble_std_c, p05_c, p95_c, members_available
```

Member-level daily values are preserved so member errors can be computed once ERA5T arrives.

## Multimodel consensus

Currently combines four ensemble centers: **GEFS, GEPS, IFS ENS, AIFS ENS**.

### Equal-center consensus

Each system gets equal weight regardless of member count, so a 51-member ensemble cannot dominate a 21-member one on member count alone:

$$\mu_{\text{equal}} = \frac{1}{4}\sum_{m=1}^{4}\mu_m$$

### Physics consensus

Excludes AIFS:

$$\mu_{\text{physics}} = \frac{\mu_{\text{GEFS}} + \mu_{\text{GEPS}} + \mu_{\text{IFS}}}{3}$$

The system then measures `AIFS − IFS` and `AIFS − physics consensus`.

### Structural disagreement

Minimum and maximum model-center mean, center-mean range, between-center standard deviation, warmest system, coolest system, disagreement rank.

### Variance decomposition

Average within-center ensemble variance:

$$\sigma^2_{\text{within}} = \frac{1}{M}\sum_{m=1}^{M}\sigma_m^2$$

Between-center variance (population variance of the center means):

$$\sigma^2_{\text{between}} = \operatorname{Var}(\mu_1,\ldots,\mu_M)$$

Equal-weight mixture variance and structural fraction:

$$\sigma^2_{\text{total}} = \sigma^2_{\text{within}} + \sigma^2_{\text{between}}
\qquad
f_{\text{structural}} = \frac{\sigma^2_{\text{between}}}{\sigma^2_{\text{total}}}$$

This single statistic answers whether forecast uncertainty comes mainly from disagreement *inside* ensembles or *between* forecasting systems — and it is the number Part I most needs, because a market model fed by one ensemble family sees only $\sigma^2_{\text{within}}$.

### Interval diagnostics

Normal-approximation multimodel 5th and 95th percentiles; intersection and union of the four reported central 90% intervals; common-to-union overlap fraction. These are **diagnostics, not calibrated forecast intervals.**

## Reference-run results (`20260728_00z`)

```text
Equal-center period mean:              16.934039 °C
Physics-consensus period mean:         16.888760 °C
Average AIFS minus IFS:                +0.106438 °C
Average AIFS minus physics consensus:  +0.181115 °C
Average center-mean range:              0.250378 °C
Average internal RMS spread:            0.050642 °C
Average total mixture spread:           0.107425 °C
Average structural variance fraction:  77.97%
Common central-90% overlap:             0 of 10 dates
Greatest disagreement date:             2026-08-03
Greatest center-mean range:              0.297486 °C
```

Reading:

- AIFS ran consistently warmer than IFS and than the physics-only consensus in this cycle.
- Inter-model disagreement **dominated** total mixture variance (78%).
- Internal ensemble spread alone materially understated total cross-system uncertainty — roughly a factor of two on spread.
- The four central 90% intervals shared **no** common overlap on any of the ten dates.

These are one initialization cycle. They are not evidence of stable model bias; bias and calibration conclusions need many verified historical cycles.

## Verification architecture

```text
verify_forecasts.py            verify_ecmwf_ens.py
verify_gdps.py                 verify_aifs_ens.py
verify_icon.py                 verify_multimodel_consensus.py
verify_geps.py                 verification_status.py
```

Output under `output/verification/`:

```text
<model>_<run_id>_vs_era5t.csv
<ensemble>_<run_id>_member_errors.csv
multimodel_consensus_<run_id>_vs_era5t.csv
```

Intended metrics: forecast − ERA5T error, ERA5T − forecast error, absolute error, squared error, member-level error, ensemble-mean error, interval coverage, lead-time error, model-center ranking, cross-cycle calibration.

Reference-run verification tables currently hold headers and no rows, because ERA5T has not reached the forecast dates.

## Repository structure (`Global-Temperature-Model/`)

```text
.
├── README.md
├── .gitignore
├── gcs_lifecycle.json
│
├── download_gfs.py                  ├── calculate_gfs_global.py
├── download_gefs.py                 ├── calculate_gefs_global.py
├── download_gdps.py                 ├── calculate_gdps_global.py
├── download_icon.py                 ├── calculate_icon_global.py
├── download_geps.py                 ├── calculate_geps_global.py
├── download_ecmwf_ens.py            ├── calculate_ecmwf_ens_global.py
├── download_aifs_ens.py             ├── calculate_aifs_ens_global.py
├── download_era5t.py                └── calculate_era5t_global.py
│
├── compare_all_global_models.py
├── compare_ensemble_systems.py
├── compare_three_ensemble_systems.py
├── build_multimodel_consensus.py
│
├── verify_forecasts.py              ├── verify_ecmwf_ens.py
├── verify_gdps.py                   ├── verify_aifs_ens.py
├── verify_icon.py                   ├── verify_multimodel_consensus.py
├── verify_geps.py                   └── verification_status.py
│
├── snapshot_run.py
├── build_run_catalog.py
├── audit_multicycle_readiness.py
│
├── archive/
│   ├── run_catalog.csv / .json
│   ├── multicycle_readiness.csv / .json
│   └── runs/<run_id>/
│       ├── manifest.json
│       ├── output_index.csv
│       ├── cloud_validation.json
│       └── cloud_validation_complete.json
│
├── data/      # raw GRIB; gitignored
│   └── gfs/ gefs/ gdps/ icon/ geps/ ecmwf_ens/ aifs_ens/ era5t/
├── output/    # generated products; gitignored
│   └── verification/
└── logs/      # runtime and transfer logs; gitignored
```

### File responsibilities

**Download**

| File | Responsibility |
|---|---|
| `download_gfs.py` | Run-scoped GFS 2-meter temperature GRIB files, with resumption. |
| `download_gefs.py` | GEFS control and perturbed members. |
| `download_gdps.py` | Deterministic GDPS 2-meter air temperature. |
| `download_icon.py` | ICON Global 2-meter temperature and supporting grid products. |
| `download_geps.py` | GEPS files containing all expected members. |
| `download_ecmwf_ens.py` | IFS ENS control and perturbed products. |
| `download_aifs_ens.py` | AIFS ENS control and perturbed products. |
| `download_era5t.py` | Complete hourly ERA5T 2-meter temperature days. |

**Processing**

| File | Responsibility |
|---|---|
| `calculate_gfs_global.py` | Run-scoped six-hourly, daily, complete-daily and JSON GFS outputs. |
| `calculate_gefs_global.py` | Member-level and ensemble-level GEFS global summaries. |
| `calculate_gdps_global.py` | Deterministic GDPS global summaries. |
| `calculate_icon_global.py` | ICON processing and deterministic global summaries. |
| `calculate_geps_global.py` | Member-level and ensemble-level GEPS summaries. |
| `calculate_ecmwf_ens_global.py` | IFS ENS member and ensemble summaries. |
| `calculate_aifs_ens_global.py` | AIFS ENS member and ensemble summaries. |
| `calculate_era5t_global.py` | Hourly and daily ERA5T global means, plus matched-six-hour diagnostics. |

**Comparison and consensus**

| File | Responsibility |
|---|---|
| `compare_all_global_models.py` | Joins deterministic and ensemble products for cross-model inspection. |
| `compare_ensemble_systems.py` | Compares ensemble systems on common dates. |
| `compare_three_ensemble_systems.py` | Earlier, narrower ensemble comparison workflow. |
| `build_multimodel_consensus.py` | Four-center consensus and structural-disagreement diagnostics. |

**Verification**

| File | Responsibility |
|---|---|
| `verify_forecasts.py` | GFS and GEFS against ERA5T. |
| `verify_gdps.py` | GDPS. |
| `verify_icon.py` | ICON. |
| `verify_geps.py` | GEPS, including member-level errors. |
| `verify_ecmwf_ens.py` | IFS ENS, including member-level errors. |
| `verify_aifs_ens.py` | AIFS ENS, including member-level errors. |
| `verify_multimodel_consensus.py` | Consensus output. |
| `verification_status.py` | Whether ERA5T overlap exists for each system. |

**Reproducibility and audit**

| File | Responsibility |
|---|---|
| `snapshot_run.py` | Immutable run snapshot and output index. |
| `build_run_catalog.py` | CSV and JSON catalogs across run manifests. |
| `audit_multicycle_readiness.py` | Enforces run-scoped data, output naming, script interfaces and clean Git state. |

## Raw and processed data policy

Raw GRIB and generated output stay out of Git. Ignored:

```text
data/   output/   logs/   .venv/   .env.gcp.local
.DS_Store   __pycache__/   *.py[cod]
```

Because GRIB archives are too large for ordinary Git history, generated CSV/JSON can be recreated from raw data, logs are operational artifacts, virtual environments are platform-specific, cloud configuration may carry local identifiers, and bytecode and macOS metadata are not source.

Manifests, catalogs, validation records and readiness reports **do** belong in Git — small, auditable metadata.

## Google Cloud Storage architecture

```text
Google Cloud project:  gtf-forecast-20260729-a7c9
Cloud Storage bucket:  gtf-forecast-20260729-a7c9-data
Location:              US-EAST1
```

Created with Standard default storage, uniform bucket-level access, public-access prevention, and seven-day soft delete.

### Object layout

```text
gs://gtf-forecast-20260729-a7c9-data/
├── raw/<run_id>/<model>/
├── processed/<run_id>/
├── verification/<run_id>/
├── manifests/<run_id>/
├── catalogs/
└── logs/<run_id>/
```

| Prefix | Purpose |
|---|---|
| `raw/` | Original provider GRIB files and model-specific supporting files. |
| `processed/` | Run-scoped CSV and JSON forecast products. |
| `verification/` | ERA5T comparison products. |
| `manifests/` | Snapshot manifests, output indexes, cloud-validation records. |
| `catalogs/` | Cross-run CSV and JSON catalogs. |
| `logs/` | Download, processing and cloud-transfer logs. |

### Lifecycle policy

```text
STANDARD -> NEARLINE  after  30 days
NEARLINE -> COLDLINE  after  90 days
COLDLINE -> ARCHIVE   after 365 days
```

Applies only under `raw/` — small processed products, manifests and catalogs stay immediately accessible.

### Common gcloud commands

```bash
export PROJECT_ID="gtf-forecast-20260729-a7c9"
export BUCKET="${PROJECT_ID}-data"
export RUN_ID="20260728_00z"

gcloud config set project "$PROJECT_ID"
```

Inspect the bucket:

```bash
gcloud storage buckets describe "gs://${BUCKET}"
```

List run objects:

```bash
gcloud storage ls --recursive "gs://${BUCKET}/raw/${RUN_ID}/**"
```

Calculate run size:

```bash
gcloud storage du --summarize "gs://${BUCKET}/raw/${RUN_ID}"
```

Synchronize a raw model directory:

```bash
gcloud storage rsync --recursive "data/gfs/${RUN_ID}" "gs://${BUCKET}/raw/${RUN_ID}/gfs"
```

Synchronize processed output:

```bash
gcloud storage rsync --recursive output "gs://${BUCKET}/processed/${RUN_ID}"
```

Restore one object:

```bash
gcloud storage cp "gs://${BUCKET}/raw/${RUN_ID}/gfs/gfs_${RUN_ID}_f000.grib2" "/tmp/gfs_${RUN_ID}_f000.grib2"
```

### Cloud integrity validation

Reference archive object counts:

```text
aifs_ens:   82      geps:       41
ecmwf_ens:  82      gfs:        41
gdps:       41      icon:       93
gefs:     1272      total:    1652
```

A GFS file was pulled back from Cloud Storage and compared against the local source:

```text
Local SHA-256:    f4d4a26ee37a3a55009634bd30fd6d5e615c7ac2a4d7a792d8eee96d8d357582
Restored SHA-256: f4d4a26ee37a3a55009634bd30fd6d5e615c7ac2a4d7a792d8eee96d8d357582
grib_count = 1
```

That demonstrates restoration and content integrity **for the tested file**. Production needs automated checksum validation across a statistically meaningful sample, or every object.

## Local environment

Reference environment is macOS with Python 3.13.

Python packages used in the processing code:

```text
requests   numpy   pandas   xarray   cfgrib
```

System requirements:

```text
ecCodes command-line tools
Google Cloud CLI
```

ERA5T retrieval also needs valid Copernicus Climate Data Store credentials.

A pinned dependency file is still missing for this part. Until one is committed:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install requests numpy pandas xarray cfgrib
```

Install ecCodes via the platform package manager — Homebrew provides the utilities on macOS.

## Manual execution

Options differ slightly per model; every operational script must accept explicit run parameters.

GFS:

```bash
python download_gfs.py --date 20260728 --cycle 00 --max-hour 240
python calculate_gfs_global.py --date 20260728 --cycle 00 --max-hour 240
```

Consensus:

```bash
python build_multimodel_consensus.py --date 20260728 --cycle 00
```

Readiness audit — a run is automation-ready only at zero errors and zero warnings:

```bash
python audit_multicycle_readiness.py --run-id 20260728_00z
```

Snapshot and catalog:

```bash
python snapshot_run.py --run-id 20260728_00z
python build_run_catalog.py
```

The snapshot records code, output, raw-directory, file-count, size and result metadata without duplicating raw GRIB into Git.

## Reproducibility controls completed

1. Run-scoped GFS raw paths
2. Run-scoped GFS output filenames
3. Explicit `--date`, `--cycle` and horizon parameters
4. Hardcoded consensus dates removed
5. Atomic and resumable GFS downloads
6. Immutable run snapshot
7. Output index
8. Machine-readable run catalog
9. Multi-cycle readiness audit
10. Git exclusion of generated and binary data
11. Cloud archive organized by run and model
12. Cloud object-count validation
13. Cloud size validation
14. SHA-256 restore test
15. GRIB readability test after restore
16. Clean repository state
17. Deterministic audit output

## Work completed

**Forecast ingestion** — GFS, GEFS, GDPS, GEPS, IFS ENS and AIFS ENS complete; ICON complete through +180 h; ERA5T ingestion operational for available complete dates.

**Processing** — whole-Earth weighted means, duplicate-longitude handling, Kelvin→Celsius, six-hourly outputs, UTC daily aggregation, complete-day flags, ensemble member processing, ensemble mean / standard deviation / percentile summaries.

**Analysis** — deterministic model comparison, ensemble-system comparison, equal-center consensus, physics-only consensus, AI-versus-physics diagnostics, within- and between-center variance decomposition, structural variance fraction, interval-overlap diagnostics, disagreement ranking.

**Verification** — ERA5T hourly and matched-six-hour processing, verification files for all seven systems, ensemble member-error outputs, verification-status reporting, and correct handling of the current no-overlap state as a status rather than a failure.

**Reproducibility and operations** — reference run snapshot, run catalog, cloud archive, validated raw object counts, validated GFS cloud restore, generated files untracked, hardened gitignore, and a readiness audit passing with zero errors and zero warnings.

## Missing work

Operational for a manually executed reference cycle; **not** yet an unattended production system.

### Highest priority: the orchestrator

One resumable run orchestrator that will: resolve the initialization date and cycle → acquire a filesystem lock → run model downloads independently → resume partial downloads → validate expected files and message counts → process each available model → build comparisons and consensus → update ERA5T → run verification → snapshot and manifest → update the catalog → upload raw and processed artifacts → validate cloud counts and checksums → write a machine-readable run status → release the lock → exit nonzero on any incomplete mandatory stage.

### Dependency management

`requirements.txt` or `pyproject.toml`, exact version pins, a lock file, a declared supported Python version, and an automated installation test.

### Testing

Unit tests for spatial weighting, daily completeness, member parsing, filename parsing, run IDs and consensus variance decomposition; tests for empty or delayed ERA5T overlap; integration tests against small fixture GRIB files; cloud-upload dry-run tests; restore-validation tests; regression tests for the reference cycle.

### Historical verification

One cycle cannot support skill conclusions. Needs: historical forecast-cycle backfill, ERA5T backfill, lead-time verification, seasonal stratification, rolling bias estimates, MAE, RMSE, CRPS, interval coverage, rank histograms, spread-error analysis, ensemble reliability, cross-model error correlation, out-of-sample calibration.

### Calibrated consensus

Equal-center weighting is transparent but uncalibrated. Future versions should compare it against inverse-error weighting, constrained linear stacking, Bayesian model averaging, lead-dependent weights, season-dependent weights, regime-dependent weights, robust median or trimmed consensus, and correlation-adjusted weighting.

**All weights must be estimated only from information available before the forecast being evaluated.** This is also the hard constraint on feeding the consensus into Part I: a market model calibrated on hindsight prices nothing.

### ICON hardening

Independent cell-area weighting validation, regridding-conservation tests, CCSDS packing compatibility checks, detection of zero-byte and invalid intermediate files, native-grid metadata preservation, and a repeatable containerized regridding environment.

### Data provenance

Each raw object should carry or reference: provider, source URL or request parameters, retrieval timestamp, initialization time, forecast lead, member, variable, level, grid, message count, file size, checksum, downloader version, processing-code commit.

### Cloud operations

Dedicated service account, least-privilege IAM, an Application Default Credentials strategy for automation, budget alerts, cost monitoring, retention review, automated lifecycle-policy tests, a cross-region recovery decision, automated catalog upload, automated log retention, and an object-versioning review.

### Monitoring

Missing model cycles, missing forecast hours, missing ensemble members, invalid GRIB messages, slow downloads, ERA5T lag, processing exceptions, cloud transfer failures, checksum mismatches, disk-space thresholds, forecast completion status, verification completion status.

### Documentation and governance

License selection, `CONTRIBUTING.md`, a code of conduct if outside collaboration is expected, maintainer and ownership information, release policy, data-provider attribution review, citation instructions, security policy, changelog.

## Target architecture

```text
Scheduler
   |
   v
Run resolver and lock manager
   |
   +--> GFS acquisition
   +--> GEFS acquisition
   +--> GDPS acquisition
   +--> ICON acquisition
   +--> GEPS acquisition
   +--> IFS ENS acquisition
   +--> AIFS ENS acquisition
   |
   v
Integrity gate
   |
   v
Parallel model processing
   |
   v
Daily products and member summaries
   |
   v
Consensus and diagnostics
   |
   v
ERA5T update and verification
   |
   v
Snapshot, manifest, and catalog
   |
   v
GCS upload and checksum validation
   |
   v
Run-status database and monitoring
```

Target capabilities: multiple cycles without overwrite risk, restart after interruption, independent model failures, explicit partial-completion status, historical backfill, verification by lead time, calibrated multimodel distributions, programmatic query across all runs, reproducible restoration from cloud storage, automated reports, and optional API or dashboard access.

## Scientific limitations

1. 2-meter air temperature is not surface skin temperature.
2. A gridded forecast is not a direct observation.
3. The global mean depends on spatial weighting and grid representation.
4. Four six-hourly samples approximate a 24-hour mean.
5. Model initializations are not independent observations.
6. Ensemble members within one system are correlated.
7. Different systems can share observations, assimilation inputs and model assumptions.
8. One forecast cycle cannot establish persistent bias.
9. Normal approximations may misrepresent multimodal or skewed mixtures.
10. ERA5T is near-real-time and may later differ from finalized reanalysis.
11. The current statistic is an absolute global mean temperature, **not** an anomaly against a climatological baseline — Part I needs an anomaly, so a baseline conversion is required before the two systems connect.
12. The system has not been calibrated across historical out-of-sample cycles.

---

# Shared concerns

## Data sources and attribution

| Source | Used by | For |
| --- | --- | --- |
| NOAA NCEI Climate at a Glance | Part I | Settlement anomaly; the number the market resolves on. |
| Copernicus ERA5 (Climate Pulse) | Part I | Daily global-mean anomaly, ~2-day lag. |
| Copernicus ERA5T (CDS) | Part II | Hourly absolute 2-meter temperature; verification reference. |
| NASA GISTEMP | Part I | Cross-platform basis check (Polymarket's settlement source). |
| Open-Meteo ensemble API | Part I | 51-member member-level global means. |
| NOAA NOMADS | Part II | GFS and GEFS GRIB. |
| ECCC | Part II | GDPS and GEPS. |
| Deutscher Wetterdienst | Part II | ICON Global. |
| ECMWF open data | Part II | IFS ENS and AIFS ENS. |
| Kalshi public and authenticated API | Part I | Market prices, depth, positions, fills. |

All forecast and climate inputs are public data. Provider terms and attribution requirements should be reviewed before any public redistribution of derived products.

## Security and secret handling

Never commit:

```text
.env                        Google service-account keys
*.pem private keys          Copernicus CDS credentials
.env.gcp.local              Application Default Credential files
Kalshi API keys             Cloud billing information
```

Both `.gitignore` files exclude these. The GCS bucket has public-access prevention enabled — publishing source code does not publish the raw forecast archive.

Before publishing any repository archive:

```bash
git status --short
git ls-files data output logs
git grep -n -I -E 'BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY|API_KEY=|PASSWORD='
```

Build release archives from committed Git files, never by zipping the working directory:

```bash
git archive --format=zip -o dist/hottest-month.zip HEAD
```

`git archive` only sees tracked files, so it cannot leak an ignored secret or a multi-gigabyte GRIB tree.

## Release procedure

1. Review project name, ownership and license.
2. Commit a pinned dependency file for both parts.
3. Commit all source and metadata changes; confirm a clean working tree.
4. Run the Part II multi-cycle readiness audit.
5. Confirm `data/`, `output/` and `logs/` contain no tracked files.
6. Run the secret scan above.
7. Generate the release ZIP with `git archive` and a SHA-256 checksum.
8. Inspect the ZIP listing before publishing.
9. Push source to GitHub; keep raw data in Cloud Storage.

## Progress summary

Part I is a working, settled-and-scored market model: it called the June 2026 NOAA print to the third decimal, and its documented failures — a censoring jump-guard, an over-tight forecast-error knob, a deterministic path that hid real ensemble tail mass — are what motivated Part II.

Part II has moved from a single-cycle experiment to a run-scoped, cloud-archived, reproducibility-oriented forecast system. The milestone that matters is not that seven systems produced output; it is that the reference run can be identified, audited, restored and compared without relying on untracked assumptions.

Next milestones, in order: unattended orchestration for Part II, then accumulated verified historical cycles, then replacing equal weighting with out-of-sample calibrated probabilistic forecasts — and only then wiring that calibrated distribution into Part I's pricing in place of the current hand-blended forward path.

## License

No license has been selected. Until one is added, normal copyright applies — a public repository is not open-source merely because its source is visible. Select and add an explicit license before inviting external reuse or contributions.

## Disclaimer

Personal research. Not investment advice, not a recommendation to trade. Event contracts can lose their full value.
