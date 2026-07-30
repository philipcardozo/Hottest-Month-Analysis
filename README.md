# Hottest Month — Kalshi KXHMONTH forecast model

Probability model and live dashboard for Kalshi's `KXHMONTH` markets: *"Will \<month\> 2026 be the hottest \<month\> on record?"*

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

1. Ensemble mean of remaining days as a third predictor in the forward OLS.
2. **NOAA-input replication** — GHCN-M v4 plus preliminary ERSSTv5 (~day 3–5) to reconstruct NOAAGlobalTemp directly, targeting translation σ 0.047 → ~0.02.
3. Kalshi authenticated trading — websocket book depth, flow surveillance, order placement. Paper mode first, hard risk caps.
4. Rolling Kalman-style bias recalibration each print; Student-t fat-tail option; backtest harness over 2015–2025.
5. Climate Reanalyzer / CFS as a lag-killer input; NMME and C3S seasonal for pricing Sep–Dec.

## Status

Research code, single-operator. It reads markets and prices them; it does not place orders. Only public data sources are used, and Kalshi permits API trading.

Current model state, position history and open questions live in [CLAUDE.md](CLAUDE.md) — it is dated and updated per print, and it is the file to read before trusting any number here.

## Disclaimer

Personal research. Not investment advice, not a recommendation to trade. Event contracts can lose their full value.
