#!/usr/bin/env python3
"""
Full 51-member ECMWF ENS spread for the July hottest-month markets.

Fetches member-level IFS ENS (ensemble-api.open-meteo.com, models=ecmwf_ifs025 —
the real ECMWF ensemble regridded to points; member-level is the ONLY way to get
the distribution of the GLOBAL MEAN, since per-gridpoint spread fields don't
aggregate into global-mean spread). 15-deg cos-weighted grid, anchored to ERA5
overlap, horizon-edge day dropped (diurnal-aliasing artifact, measured Jul 10).

Per member m: full-July ERA5 mean estimate via the historical first-k_eff OLS
-> NOAA + GISTEMP translations -> P(record) per member -> P(YES) = member average.
Directly answers: "do >=5% of members produce a late heat spike that breaks the
record?" — with members, not assumptions.

Writes ens_spread_<UTC>.json next to this file. Run: python3 ens_spread.py
ponytail: ENS is underdispersive at long leads; the historical sd_f(k_eff) term
in each member's sigma carries that slack. Grid 15 deg: global-mean sampling
error << signal (validated vs the 10-deg deterministic feed).
"""
import json, math, os, subprocess, sys, time
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'ecmwf_ifs025'   # gfs025 / icon_seamless / gem_global
FIT_YEARS = list(range(1990, 2026))
THR_NOAA = 1.185          # NOAA record 1.18 + rounding
THR_GIS = 1.195           # GISTEMP record 1.20 (2024) + rounding; ties count INTO bracket


def era5():
    daily, clim = defaultdict(dict), {}
    for line in open(os.path.join(ROOT, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y, m)][d] = float(p[3])
            clim[p[0][5:]] = float(p[2])
    return daily, clim


def fetch_members():
    """-> {date: np.array(51) of cos-weighted global-mean t2m degC}"""
    lats = [l + 7.5 for l in range(-90, 90, 15)]     # 12
    lons = [l + 0.0 for l in range(-180, 180, 15)]   # 24
    pts = [(la, lo) for la in lats for lo in lons]   # 288
    keys = None
    sums, wcnt = {}, {}
    B = 24
    for i in range(0, len(pts), B):
        ch = pts[i:i + B]
        url = (f"{API}?latitude={','.join(str(p[0]) for p in ch)}"
               f"&longitude={','.join(str(p[1]) for p in ch)}"
               f"&daily=temperature_2m_mean&models={MODEL}"
               f"&past_days=5&forecast_days=15&timezone=UTC")
        res = None
        for attempt in range(3):
            r = subprocess.run(['curl', '-s', '--max-time', '180', url], capture_output=True)
            res = json.loads(r.stdout)
            if isinstance(res, dict) and res.get('error'):
                print(f"  batch {i//B}: API error '{res.get('reason')}' — retry {attempt+1}", file=sys.stderr)
                time.sleep(15 * (attempt + 1))
                continue
            break
        if isinstance(res, dict):
            if res.get('error'):
                raise RuntimeError(f"ensemble API refused batch {i//B}: {res.get('reason')}")
            res = [res]
        for loc, (la, _) in zip(res, ch):
            w = math.cos(math.radians(la))
            d = loc['daily']
            if keys is None:
                keys = sorted((k for k in d if k.startswith('temperature_2m_mean')),
                              key=lambda s: int(s.rsplit('member', 1)[1]) if 'member' in s else 0)
            for mi, key in enumerate(keys):
                vals = d.get(key)
                if not vals:
                    continue
                for t, v in zip(d['time'], vals):
                    if v is not None:
                        sums.setdefault(t, np.zeros(len(keys)))[mi] += w * v
                        wcnt.setdefault(t, np.zeros(len(keys)))[mi] += w
        time.sleep(1.0)
    full_w = max(w.max() for w in wcnt.values())
    gm = {}
    for t in sorted(sums):
        cov = wcnt[t] / full_w
        if cov.min() >= 0.99:                        # keep only days ALL members fully cover
            gm[t] = sums[t] / wcnt[t]
    days = sorted(gm)
    if days:
        days.pop()                                   # horizon-edge artifact guard
        em = {t: gm[t].mean() for t in days}
        for i in range(1, len(days)):
            if abs(em[days[i]] - em[days[i - 1]]) > 0.15:
                days = days[:i]
                break
        gm = {t: gm[t] for t in days}
    return gm


def ols2(X, Y):
    A = np.column_stack([np.ones(len(Y)), [x[0] for x in X], [x[1] for x in X]])
    c, *_ = np.linalg.lstsq(A, np.array(Y), rcond=None)
    r = np.array(Y) - A @ c
    return c, math.sqrt(r @ r / (len(Y) - 3))


def main():
    daily, clim = era5()
    mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])
    obs = daily[(2026, 7)]
    k = len(obs)
    jun26 = mm(2026, 6)

    gm = fetch_members()                             # {date: array(51)}
    # anchor: ensemble-mean anomaly vs observed ERA5 on overlap days
    anom = {t: gm[t] - clim[t[5:]] for t in gm if t[5:] in clim}
    ov = [(obs[int(t[8:])], anom[t].mean()) for t in anom
          if t.startswith('2026-07-') and int(t[8:]) in obs]
    off = sum(o - a for o, a in ov) / len(ov) if ov else 0.0
    fdays = {int(t[8:]): anom[t] + off for t in anom
             if t.startswith('2026-07-') and int(t[8:]) > k}
    k_eff = max(fdays)
    assert len(fdays) == k_eff - k, "non-contiguous forecast coverage"

    # historical regression at k_eff (same machinery as update_data.py)
    X = [(mm(y, 6), sum(daily[(y, 7)][d] for d in range(1, k_eff + 1)) / k_eff) for y in FIT_YEARS]
    c, sd_f = ols2(X, [mm(y, 7) for y in FIT_YEARS])

    obs_sum = sum(obs[d] for d in range(1, k + 1))
    n_memb = len(next(iter(fdays.values())))
    member_first = np.array([(obs_sum + sum(fdays[d][m] for d in fdays)) / k_eff
                             for m in range(n_memb)])
    mu_era = c[0] + c[1] * jun26 + c[2] * member_first          # per member

    # translations (NOAA for Kalshi; GISTEMP for Polymarket)
    dj = json.loads(open(os.path.join(ROOT, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    jul = dj['model']['jul']
    gis = {}
    for line in open(os.path.join(ROOT, 'gistemp.txt')):
        p = line.split()
        if p and p[0].isdigit() and len(p) >= 8 and p[7].replace('-', '').isdigit():
            gis[int(p[0])] = int(p[7]) / 100.0
    yrs = [y for y in FIT_YEARS if y in gis]
    bg, ag = np.polyfit([mm(y, 7) for y in yrs], [gis[y] for y in yrs], 1)
    rg = np.array([gis[y] for y in yrs]) - (ag + bg * np.array([mm(y, 7) for y in yrs]))
    sd_g = math.sqrt(rg @ rg / (len(yrs) - 2))

    out = {'pulled_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'k_obs': k, 'k_eff': k_eff, 'model': MODEL, 'n_members': n_memb, 'anchor_offset': round(off, 4),
           'member_july_mean_era5': [round(float(x), 4) for x in mu_era]}

    print("%s | %d members | k=%d obs, members fill days %d..%d, anchor %+.3f on %d overlap days"
          % (MODEL, n_memb, k, k + 1, k_eff, off, len(ov)))
    print("member full-July ERA5 mean: min %+.3f  p05 %+.3f  median %+.3f  p95 %+.3f  MAX %+.3f"
          % (mu_era.min(), np.percentile(mu_era, 5), np.median(mu_era),
             np.percentile(mu_era, 95), mu_era.max()))
    print("ensemble spread of July mean: sd=%.4f  (pipeline's assumed fcst-error knob: compare!)"
          % mu_era.std(ddof=1))
    for name, a_, b_, sd_t, thr in (('NOAA/Kalshi', jul['a'], jul['b'], jul['sd'], THR_NOAA),
                                    ('GISTEMP/Polymarket-1st', ag, bg, sd_g, THR_GIS)):
        mu_m = a_ + b_ * mu_era
        sig = math.hypot(b_ * sd_f, sd_t)            # per-member residual (beyond-horizon + translation)
        p_m = stats.norm.sf((thr - mu_m) / sig)
        p = float(p_m.mean())
        n_hot = int((p_m > 0.01).sum())
        need = (thr - a_) / b_
        n_breach = int((mu_era >= need).sum())
        print("\n[%s] threshold %.3f (ERA5-equiv %+.3f)" % (name, thr, need))
        print("  P(YES) ensemble-averaged = %.3f%%   (was Normal-point ~0.00%%)" % (100 * p))
        print("  members with P>1%%: %d/51 · members whose CENTRAL path breaks record: %d/51"
              % (n_hot, n_breach))
        print("  hottest member: mu=%.3f -> P=%.2f%%" % ((a_ + b_ * mu_era.max()), 100 * float(p_m.max())))
        out[name.split('/')[0].lower()] = {'p_yes_pct': round(100 * p, 4),
                                           'members_p_gt_1pct': n_hot,
                                           'members_central_breach': n_breach,
                                           'hottest_member_p_pct': round(100 * float(p_m.max()), 3)}

    path = os.path.join(HERE, 'ens_spread_' + MODEL + '_%s.json'
                        % datetime.now(timezone.utc).strftime('%Y%m%d_%H%M'))
    json.dump(out, open(path, 'w'), indent=1)
    print("\nwrote", os.path.basename(path))

    assert mu_era.std(ddof=1) > 0.001, "degenerate ensemble"
    assert len(ov) >= 1 and abs(off) < 0.5, "anchoring failed"
    print("self-check: OK")


if __name__ == '__main__':
    main()
