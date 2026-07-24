#!/usr/bin/env python3
"""
ECMWF IFS global-mean 2m forecast via Open-Meteo (JSON, free, no key, no GRIB).

Samples a 10-degree lat/lon grid (648 points, batched requests), cos-weights to a
global-mean daily t2m (deg C), converts to ERA5-comparable anomaly using the
climatology column already inside era5_daily.csv, and anchors any residual
model/grid offset by matching overlap days against observed ERA5.

Every pull is archived to forecast_log/ so ensemble skill (rho) becomes measurable
from our own history instead of assumed.

Used by update_data.py; runnable standalone: python3 fetch_forecast.py

ponytail: deterministic IFS 0.25 (not the 51-member ensemble) — for a global-mean
predictor the ens-mean gain matters mostly past day ~8; upgrade via
ensemble-api.open-meteo.com if the forecast_log skill fit says it's worth it.
ponytail: 10-degree sampling of a global mean; fine for large-scale anomalies.
"""
import json, math, os, subprocess, time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, 'forecast_log')
API = "https://api.open-meteo.com/v1/forecast"
PAST_DAYS = 5          # overlap with ERA5 (2-day lag) for offset anchoring
FCST_DAYS = 15


def _curl(url):
    r = subprocess.run(['curl', '-s', '--max-time', '120', url], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl failed ({r.returncode})")
    return json.loads(r.stdout)


def fetch_global_mean():
    """-> {date_str: global_mean_t2m_C}; also archives the pull."""
    lats = [l + 0.0 for l in range(-85, 90, 10)]           # 18
    lons = [l + 0.0 for l in range(-180, 180, 10)]         # 36
    pts = [(la, lo) for la in lats for lo in lons]         # 648
    daily_sum, daily_w = {}, {}
    B = 108                                                # 6 batched calls
    for i in range(0, len(pts), B):
        chunk = pts[i:i + B]
        url = (f"{API}?latitude={','.join(str(p[0]) for p in chunk)}"
               f"&longitude={','.join(str(p[1]) for p in chunk)}"
               f"&daily=temperature_2m_mean&models=ecmwf_ifs025"
               f"&past_days={PAST_DAYS}&forecast_days={FCST_DAYS}&timezone=UTC")
        res = _curl(url)
        if isinstance(res, dict):                          # single-location or error shape
            res = [res]
        for loc, (la, _) in zip(res, chunk):
            w = math.cos(math.radians(la))
            d = loc.get('daily', {})
            for t, v in zip(d.get('time', []), d.get('temperature_2m_mean', [])):
                if v is None:
                    continue
                daily_sum[t] = daily_sum.get(t, 0.0) + w * v
                daily_w[t] = daily_w.get(t, 0.0) + w
        time.sleep(0.3)
    gm = {t: daily_sum[t] / daily_w[t] for t in sorted(daily_sum) if daily_w[t] > 0}
    # horizon-edge guard: the final day aggregates incomplete sub-daily steps (diurnal
    # aliasing, seen as a +0.4 jump on 2026-07-24) -> drop it, plus any day after a
    # physically implausible global-mean jump. 0.30C/day: the Jul-10 edge artifact was
    # +0.46; real 3-center surge forecasts hit +0.18/day (Jul 15 lesson: 0.15 cut real signal).
    days = sorted(gm)
    if days:
        days.pop()
        for i in range(1, len(days)):
            if abs(gm[days[i]] - gm[days[i-1]]) > 0.30:
                days = days[:i]
                break
        gm = {t: gm[t] for t in days}
    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    json.dump({'pulled_at_utc': stamp, 'model': 'ecmwf_ifs025', 'global_mean_C': gm},
              open(os.path.join(LOG_DIR, f'fcst_{stamp}.json'), 'w'))
    return gm


def load_cached(max_age_h=6):
    """Most recent archived pull if fresh enough, else None."""
    if not os.path.isdir(LOG_DIR):
        return None
    files = sorted(f for f in os.listdir(LOG_DIR) if f.startswith('fcst_'))
    if not files:
        return None
    p = os.path.join(LOG_DIR, files[-1])
    if time.time() - os.path.getmtime(p) > max_age_h * 3600:
        return None
    return json.load(open(p))['global_mean_C']


def to_anomaly(gm, era5_csv=None):
    """
    Convert global-mean degC -> ERA5-style anomaly (vs 1991-2020), anchored on overlap.
    era5 csv cols: date, absolute, climatology, anomaly  -> clim by day-of-year from col 2.
    Returns ({date: anomaly}, offset, n_overlap).
    """
    era5_csv = era5_csv or os.path.join(HERE, 'era5_daily.csv')
    clim, obs_anom = {}, {}
    for line in open(era5_csv):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            doy = p[0][5:]                       # 'MM-DD'
            clim[doy] = float(p[2])              # 1991-2020 climatology, same for all years
            obs_anom[p[0]] = float(p[3])
    raw = {t: gm[t] - clim[t[5:]] for t in gm if t[5:] in clim}
    overlap = [(obs_anom[t], raw[t]) for t in raw if t in obs_anom]
    offset = (sum(o - r for o, r in overlap) / len(overlap)) if overlap else 0.0
    return {t: v + offset for t, v in raw.items()}, offset, len(overlap)


if __name__ == '__main__':
    gm = load_cached() or fetch_global_mean()
    anom, off, n = to_anomaly(gm)
    print(f"anchor offset={off:+.3f} on {n} overlap day(s)")
    for t in sorted(anom):
        print(f"  {t}  {anom[t]:+.3f}")
    # self-check: offset anchoring must reproduce observed ERA5 on overlap days on average
    assert n >= 1, "no overlap with ERA5 — anchoring impossible"
    assert all(-3 < v < 3 for v in anom.values()), "anomaly out of sane range"
    print("self-check: OK")
