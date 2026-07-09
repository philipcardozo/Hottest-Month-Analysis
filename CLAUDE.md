# Hottest Month — Kalshi KXHMONTH trading model

## What this project is
Quantitative model + dashboard for Kalshi's "Will <month> 2026 be the hottest <month> ever?" markets (settle on NOAA NCEI Climate-at-a-Glance global land+ocean anomaly, 2 decimals, vs 1901–2000; rules in `HMONTH.pdf`). Core edge: ERA5 publishes daily with ~2-day lag; NOAA publishes ~day 9–14 of the next month. The model converts the fast signal into the slow settlement number ahead of the print.

## Files
- `Model_Analysis.ipynb` — full documented model (data → OLS translation → normal tail → EV/Kelly). Set `REFRESH=True` + Run All to update.
- `Kalshi.ipynb` — market analytics: series history (Apr/May settled NO), flow decomposition (contracts vs dollars), NOAA record base rates (records cluster in El Niño bursts → cross-month NO correlation risk), fees/depth, hedging playbook, position calculator.
- `Dashboard.html` — live dashboard. Serve: `python3 -m http.server 8000` here; auto-reloads `data.js` every 5 min.
- `update_data.py` — data engine: fetches ERA5 (Climate Pulse CSV) + NOAA CAG JSONs + Kalshi public API (curl-based; python.org SSL certs are broken → keep using curl), recomputes model, writes `data.js`. Run `--loop 900` for 24/7. Climate files refetch only when >6h stale; validates downloads (truncation bugs happened).
- `era5_daily.csv`, `noaa_m*.json`, `kalshi_data/` — cached source data. `gistemp.txt` — NASA GISTEMP (Polymarket's settlement source, different from NOAA).

## Model (v1) in one line
ERA5 daily → monthly mean → (incomplete month: OLS `full = c0 + c1·prev_month + c2·first_k_days`) → per-month OLS `NOAA = a + b·ERA5` (June: 0.585+0.903x, σ=0.046; July: 0.566+0.892x, σ=0.036; fit 1990–2025) → Normal tail vs record+0.005 (2-decimal rounding; 1.18 tie band tracked separately, no tie clause in Kalshi rules) → fair price → edge vs book → ¼-Kelly max, capped by depth (~$1–3k book).
**2026 audit bias**: NOAA's Jan–May 2026 prints ran +0.020 warm vs historical mapping (Feb–Apr; Jan/May ≈ 0) → toggle in dashboard; honest fair = bracket between raw and biased.

## State as of 2026-07-08 evening
- **Records to beat: June +1.18 (2024), July +1.18 (2024).** June 2026 ERA5 = +0.559 (2nd warmest, −0.116 below record) → predicted NOAA print 1.09–1.11, P(YES) ≈ 2–8% (central ~5%). NOAA June print: **Jul 9, 11:00 ET** — settles the June market.
- **July 2026 running HOT**: July 1–6 mean +0.648 (days 5–6 ≈ +0.70, above the +0.694 full-month record pace) → model P(YES July) ≈ 36% raw / 46% bias-adjusted vs market YES ~21–23¢. Day-15 exit rule (≥ +0.64) effectively fired.
- **User positions/decisions**: HOLDING 300 June NO @ 91¢ (settles Jul 9–10, model 94–97% to pay). SELLING 421.89 July NO @ 79¢ basis into ~78¢ bid (limits, 2–3 clips — thin book).
- **Lessons logged**: (1) markets = contracts ≠ dollars — decompose taker flow before believing a price move; (2) WebFetch summaries can relabel months (moyhu May post was misreported as June — always verify archive/URL literally); (3) my own residual audit moved fair June YES from 2.2%→~5%; report brackets, not points.
- Cross-platform: Polymarket June brackets settle on **NASA GISTEMP** (record 124; ties count INTO brackets) — different dataset, basis risk; NOAA's record is "softer" in σ terms so Kalshi YES should trade richer than Polymarket 1st.
- **Q4 2026 warning**: CPC 63% very-strong El Niño NDJ; record months cluster in such bursts → Sep–Dec "NO everything" is the losing habit; YES may be the value side there.

## Calendar
Jul 9 11:00 ET NOAA June print · Jul 17–18 day-15 July checkpoint (σ halves) · Jul 28 day-26 (σ≈0.017, market still open) · ~Aug 13 NOAA July print · monthly thereafter.

## Improvement roadmap (agreed direction)
1. **ECMWF open-data 15-day ensemble** (free, no key): add ensemble-mean of remaining days as 3rd predictor in the forecast OLS → shifts variance collapse ~10 days left. Biggest bang first.
2. **NOAA-input replication**: GHCN-M v4 (`ncei.noaa.gov/pub/data/ghcn/v4/`) + ERSSTv5 prelim (~day 3–5) → replicate NOAAGlobalTemp; translation σ 0.047 → ~0.02. Regression skeleton stays, refit as NOAA ~ replication.
3. **Kalshi authenticated API** (user creates key in Kalshi settings; store in local `.env`, never in chat): websocket book depth + flow surveillance + order placement. Paper-mode first, hard risk caps.
4. **Rolling bias recalibration** (update the +0.02 knob each print, Kalman-style) · fat-tail (Student-t) option · backtest harness over 2015–2025 months.
5. Climate Reanalyzer (CFS, no 2-day lag) as lag-killer input; NMME/C3S seasonal for pricing Sep–Dec before the crowd.

## Speed/“HFT” reality (answered 2026-07-08)
Not HFT — scheduled-event latency arbitrage. NOAA release time is known; a release-sniper (poll CAG JSON from ~10:59:50 ET, parse, fire Kalshi limit orders) wins by seconds with ~95–99% directional confidence when the gap is big. BUT capacity ≈ book depth ≈ $1–3k/event, ~12 events/yr → hundreds of dollars per event max. Build it as a cheap cron script, not infrastructure. Kalshi permits API trading; only public data used.
