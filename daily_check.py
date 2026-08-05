#!/usr/bin/env python3
"""
Daily scheduled check (launchd: com.hottestmonth.daily, ~07:15 local).

1. Refreshes all data (update_data.py: ERA5 + NOAA + Kalshi + IFS forecast pull).
2. Verifies the forecast: for each ERA5-verified day of the target month, compares actual vs what
   the latest forecast pull made BEFORE that day predicted (leakage-free anchoring:
   each pull is offset-anchored only on days that were observable at pull time).
3. Appends a one-line digest to track_log.csv and fires a macOS notification;
   prefixed with WARN if the last-3-day mean deviation exceeds 0.05 (dip busting /
   forecast blowing up) so it stands out.

Stdlib only (launchd-safe). Run manually: python3 daily_check.py
"""
import json, math, os, subprocess, sys
from datetime import datetime, timezone
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_ALERT = 0.05


def era5():
    daily, clim = {}, {}
    for line in open(os.path.join(HERE, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            daily[p[0]] = float(p[3])
            clim[p[0][5:]] = float(p[2])
    return daily, clim


def pull_anom(path, daily, clim, known_until):
    """Anomaly series for one archived pull, anchored only on days <= known_until."""
    gm = json.load(open(path))['global_mean_C']
    raw = {t: gm[t] - clim[t[5:]] for t in gm if t[5:] in clim}
    ov = [(daily[t], raw[t]) for t in raw if t in daily and t <= known_until]
    off = sum(o - r for o, r in ov) / len(ov) if ov else 0.0
    return {t: v + off for t, v in raw.items()}


def main():
    # Sandwich, and the order matters: ens_spread.py needs BOTH a fresh era5_daily.csv
    # (to anchor members on every observed day) and data.js (for the July a/b/sd), while
    # update_data.py needs ens_spread's JSON to embed ens51 -- so refresh, then members,
    # then rebuild. Running ens_spread first made it anchor on yesterday's ERA5 and
    # forecast days we already had actuals for. Second update_data is cheap: climate
    # files refetch only when >6h stale, so it just recomputes and rewrites data.js.
    r = subprocess.run([sys.executable, os.path.join(HERE, 'update_data.py')],
                       capture_output=True, text=True, timeout=1200)
    try:
        e = subprocess.run([sys.executable,
                            os.path.join(HERE, 'July Calibration', 'ens_spread.py'), 'ecmwf_ifs025'],
                           capture_output=True, timeout=900)
        if e.returncode == 0:            # quota failure -> keep yesterday's ens51, don't rebuild
            r = subprocess.run([sys.executable, os.path.join(HERE, 'update_data.py')],
                               capture_output=True, text=True, timeout=1200)
    except Exception:
        pass
    refresh_note = 'refresh OK' if r.returncode == 0 else f'refresh FAILED rc={r.returncode}'

    daily, clim = era5()
    d = json.loads(open(os.path.join(HERE, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    M = d['model']
    cm, fc, ens = M[M['cur']], M[M['cur']]['fc'], M[M['cur']].get('ens')
    YR, ND = M['year'], M['ndays']
    pre = '%d-%02d-' % (YR, ['jan','feb','mar','apr','may','jun','jul','aug',
                             'sep','oct','nov','dec'].index(M['cur']) + 1)
    thr = round(cm['record'] + 0.005, 3)     # tie is not "the hottest" -> bar is record+0.005

    # forecast-vs-actual on verified days of the target month: latest pull before each day
    pulls = []
    logdir = os.path.join(HERE, 'forecast_log')
    for f in sorted(os.listdir(logdir)):
        if f.startswith('fcst_'):
            pdate = f[5:13]                      # YYYYMMDD
            iso = f'{pdate[:4]}-{pdate[4:6]}-{pdate[6:]}'
            pulls.append((iso, os.path.join(logdir, f)))
    devs = []
    for t in sorted(daily):
        if not t.startswith(pre):
            continue
        prior = [p for p in pulls if p[0] < t]
        if not prior:
            continue
        iso, path = prior[-1]
        known = min(iso, max(dd for dd in daily if dd < t))
        anom = pull_anom(path, daily, clim, known)
        if t in anom:
            devs.append((t, daily[t], anom[t], daily[t] - anom[t]))

    dev3 = sum(x[3] for x in devs[-3:]) / max(len(devs[-3:]), 1) if devs else 0.0
    k = fc['k']
    run_mean = fc['firstk']
    need_era = (thr - cm['a']) / cm['b']                 # full-month ERA5 bar
    need = (need_era * ND - run_mean * k) / (ND - k) if k < ND else float('nan')
    p_ens = None
    if ens:
        mu = cm['a'] + cm['b'] * ens['mu_era5']
        sig = math.hypot(cm['b'] * ens['sd_f'], cm['sd'])
        p_ens = 50 * math.erfc((thr - mu) / sig / math.sqrt(2))
    e51 = cm.get('ens51')
    if e51:                                   # member-based P outranks the det-path view
        p_ens = e51['p_yes_pct']
    mkt = d.get('kalshi', {}).get(M['cur'].upper(), {})

    warn = abs(dev3) > DEV_ALERT
    digest = ('%s %s | k=%d mean %+0.3f need %+0.3f | ENS P(YES) %s | dev3 %+0.3f | mkt YES %s/%s | %s'
              % (datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ'), M['cur'].upper(), k, run_mean, need,
                 f'{p_ens:.1f}%' if p_ens is not None else 'n/a', dev3,
                 mkt.get('yes_bid', '?'), mkt.get('yes_ask', '?'), refresh_note))
    if warn:
        digest = 'WARN dip-check: ' + digest

    # push the same numbers into the decision workbook; refuses (harmlessly) if
    # the file is open in Excel, and builds next month's tab on the 1st
    try:
        x = subprocess.run([sys.executable, os.path.join(HERE, 'xlsx_sync.py'), '--auto'],
                           capture_output=True, text=True, timeout=300)
        print('xlsx_sync:', (x.stdout or x.stderr).strip().splitlines()[-1] if (x.stdout or x.stderr) else 'no output')
    except Exception as e:
        print('xlsx_sync skipped:', e)

    with open(os.path.join(HERE, 'track_log.csv'), 'a') as f:
        f.write(digest + '\n')
    print(digest)
    for t, act, fcv, dv in devs[-3:]:
        print('  %s actual %+0.3f vs fcst %+0.3f -> dev %+0.3f' % (t, act, fcv, dv))

    try:
        title = ('⚠️ Hottest Month' if warn else 'Hottest Month')
        body = '%s k=%d mean %+0.3f | P(YES) %s | dev3 %+0.3f | mkt %s¢' % (
            M['cur'].upper(), k, run_mean, f'{p_ens:.1f}%' if p_ens is not None else 'n/a', dev3,
            mkt.get('yes_ask', '?'))
        subprocess.run(['osascript', '-e',
                        f'display notification "{body}" with title "{title}"'],
                       timeout=15)
    except Exception as e:
        print('notification failed:', e)


if __name__ == '__main__':
    main()
