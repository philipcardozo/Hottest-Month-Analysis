#!/usr/bin/env python3
"""
Full 51-member ECMWF ENS spread for the live hottest-month market.

Fetches member-level IFS ENS (ensemble-api.open-meteo.com, models=ecmwf_ifs025 —
the real ECMWF ensemble regridded to points; member-level is the ONLY way to get
the distribution of the GLOBAL MEAN, since per-gridpoint spread fields don't
aggregate into global-mean spread). 15-deg cos-weighted grid, anchored to ERA5
overlap, horizon-edge day dropped (diurnal-aliasing artifact, measured Jul 10).

KNOWN WARM BIAS, NOT YET FIXED. The 288-point 15-deg grid carries real
global-mean sampling noise. Measured 2026-07-31/08-01 against native-resolution
GRIB (../Global-Temperature-Model, see ../multimodel_check.py): this feed reads
+0.026..+0.033 C warm vs both native IFS ENS and our own 10-deg deterministic on
identical days/cycles, and missed a 1-day-out verification by +0.092 (native IFS
+0.034, GEFS -0.005, GEPS +0.001). That is 10-20 points of P(YES).

Raising past_days does NOT fix it and was reverted: the ensemble API only serves
member data back to ~3 days before the run initialisation (older past_days come
back all-null), so the anchor is structurally capped at 2-3 overlap days against
ERA5's 2-day lag. Real fixes, in order of cost:
  1. take the SPREAD from here but re-centre the mean on the 10-deg deterministic
     or on native GRIB (cheapest, no extra quota) -- see multimodel_check.py;
  2. 10-deg grid here (648 pts, 2.25x quota, and the daily cap already binds).
Until one is done, treat this P(YES) as the WARM END of the bracket.

Per member m: full-month ERA5 mean estimate via the historical first-k_eff OLS
-> NOAA + GISTEMP translations -> P(record) per member -> P(YES) = member average.
Directly answers: "do >=5% of members produce a late heat spike that breaks the
record?" — with members, not assumptions.

Targets the current calendar month; --month YYYY-MM pins another one.
Writes ens_spread_<UTC>.json next to this file. Run: python3 ens_spread.py
ponytail: ENS is underdispersive at long leads; the historical sd_f(k_eff) term
in each member's sigma carries that slack. The old claim here -- "grid 15 deg:
sampling error << signal" -- was WRONG: it had only ever been checked against the
10-deg feed, which shares the same point-sampling weakness. Native-resolution
GRIB is the arbiter. See the warm-bias note above for the fixes.
"""
import calendar, json, math, os, subprocess, sys, time
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://ensemble-api.open-meteo.com/v1/ensemble"
args = [a for a in sys.argv[1:] if not a.startswith('--')]
MODEL = args[0] if args else 'ecmwf_ifs025'   # gfs025 / icon_seamless / gem_global
if '--month' in sys.argv:
    _y, _m = sys.argv[sys.argv.index('--month') + 1].split('-')
    YR, TM = int(_y), int(_m)
else:
    YR, TM = datetime.now().year, datetime.now().month
PY, PM = (YR - 1, 12) if TM == 1 else (YR, TM - 1)
ND = calendar.monthrange(YR, TM)[1]
FIT_YEARS = list(range(1990, YR))
# Thresholds are the record + 0.005: the print must round UP past it. A tie is not
# "the hottest" -> tie settles NO, so the bar is record+0.005, never the record.
# Both records are read from the data, never hardcoded (Aug: NOAA 1.25, GISTEMP 1.31).


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
        for attempt in range(5):
            r = subprocess.run(['curl', '-s', '--max-time', '180', url], capture_output=True)
            res = json.loads(r.stdout)
            if isinstance(res, dict) and res.get('error'):
                # Open-Meteo's limit is per-MINUTE, so back off past a full window;
                # the old 15/30/45s ladder retried inside the same window and burned
                # all three attempts for nothing.
                print(f"  batch {i//B}: API error '{res.get('reason')}' — retry {attempt+1}", file=sys.stderr)
                time.sleep(65)
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
        time.sleep(5.0)
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
    obs = daily.get((YR, TM), {})
    k = len(obs)
    prev26 = mm(PY, PM)
    pm_of = lambda y: mm(y - 1, 12) if TM == 1 else mm(y, TM - 1)

    gm = fetch_members()                             # {date: array(51)}
    # anchor: ensemble-mean anomaly vs observed ERA5 on overlap days
    anom = {t: gm[t] - clim[t[5:]] for t in gm if t[5:] in clim}
    pre = f'{YR}-{TM:02d}-'
    # anchor on every day of the target month already observed; if the month just
    # started, fall back to the tail of the previous month so day-1 still anchors
    ov = [(daily[(int(t[:4]), int(t[5:7]))][int(t[8:])], anom[t].mean()) for t in anom
          if int(t[8:]) in daily.get((int(t[:4]), int(t[5:7])), {})]
    off = sum(o - a for o, a in ov) / len(ov) if ov else 0.0
    fdays = {int(t[8:]): anom[t] + off for t in anom
             if t.startswith(pre) and int(t[8:]) > k}
    k_eff = max(fdays)
    assert len(fdays) == k_eff - k, "non-contiguous forecast coverage"

    # historical regression at k_eff (same machinery as update_data.py)
    X = [(pm_of(y), sum(daily[(y, TM)][d] for d in range(1, k_eff + 1)) / k_eff) for y in FIT_YEARS]
    c, sd_f = ols2(X, [mm(y, TM) for y in FIT_YEARS])

    obs_sum = sum(obs[d] for d in range(1, k + 1))
    n_memb = len(next(iter(fdays.values())))
    member_first = np.array([(obs_sum + sum(fdays[d][m] for d in fdays)) / k_eff
                             for m in range(n_memb)])
    mu_era = c[0] + c[1] * prev26 + c[2] * member_first         # per member

    # translations (NOAA for Kalshi; GISTEMP for Polymarket)
    dj = json.loads(open(os.path.join(ROOT, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    cm = dj['model'][dj['model']['cur']]
    assert dj['model']['year'] == YR and dj['model']['cur'] == \
        ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'][TM-1], \
        "data.js is built for a different month -- run update_data.py first"
    THR_NOAA = round(cm['record'] + 0.005, 3)
    gis = {}   # gistemp.txt: p[0]=year, p[1..12]=Jan..Dec, in 0.01 C
    for line in open(os.path.join(ROOT, 'gistemp.txt')):
        p = line.split()
        if p and p[0].isdigit() and len(p) > TM and p[TM].replace('-', '').isdigit():
            gis[int(p[0])] = int(p[TM]) / 100.0
    yrs = [y for y in FIT_YEARS if y in gis]
    bg, ag = np.polyfit([mm(y, TM) for y in yrs], [gis[y] for y in yrs], 1)
    rg = np.array([gis[y] for y in yrs]) - (ag + bg * np.array([mm(y, TM) for y in yrs]))
    sd_g = math.sqrt(rg @ rg / (len(yrs) - 2))
    THR_GIS = round(max(v for y, v in gis.items() if y < YR) + 0.005, 3)

    out = {'pulled_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'year': YR, 'month': TM,
           'k_obs': k, 'k_eff': k_eff, 'model': MODEL, 'n_members': n_memb, 'anchor_offset': round(off, 4),
           'thr_noaa': THR_NOAA, 'thr_gistemp': THR_GIS,
           'member_month_mean_era5': [round(float(x), 4) for x in mu_era]}

    print("%s %d-%02d | %d members | k=%d obs, members fill days %d..%d, anchor %+.3f on %d overlap days"
          % (MODEL, YR, TM, n_memb, k, k + 1, k_eff, off, len(ov)))
    print("member full-month ERA5 mean: min %+.3f  p05 %+.3f  median %+.3f  p95 %+.3f  MAX %+.3f"
          % (mu_era.min(), np.percentile(mu_era, 5), np.median(mu_era),
             np.percentile(mu_era, 95), mu_era.max()))
    print("ensemble spread of month mean: sd=%.4f  (pipeline's assumed fcst-error knob: compare!)"
          % mu_era.std(ddof=1))
    for name, a_, b_, sd_t, thr in (('NOAA/Kalshi', cm['a'], cm['b'], cm['sd'], THR_NOAA),
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
