#!/usr/bin/env python3
"""
Daily scheduled check (launchd: com.hottestmonth.daily, ~07:15 local).

1. Refreshes all data (update_data.py: ERA5 + NOAA + Kalshi + IFS forecast pull).
2. Verifies the forecast: for each ERA5-verified July day, compares actual vs what
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
    jul, fc, ens = d['model']['jul'], d['model']['jul']['fc'], d['model']['jul'].get('ens')

    # forecast-vs-actual on verified July days: latest pull strictly before each day
    pulls = []
    logdir = os.path.join(HERE, 'forecast_log')
    for f in sorted(os.listdir(logdir)):
        if f.startswith('fcst_'):
            pdate = f[5:13]                      # YYYYMMDD
            iso = f'{pdate[:4]}-{pdate[4:6]}-{pdate[6:]}'
            pulls.append((iso, os.path.join(logdir, f)))
    devs = []
    for t in sorted(daily):
        if not t.startswith('2026-07-'):
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
    need = (0.694 * 31 - run_mean * k) / (31 - k)
    p_ens = None
    if ens:
        mu = jul['a'] + jul['b'] * ens['mu_era5']
        sig = math.hypot(jul['b'] * ens['sd_f'], jul['sd'])
        p_ens = 50 * math.erfc((1.185 - mu) / sig / math.sqrt(2))
    e51 = jul.get('ens51')
    if e51:                                   # member-based P outranks the det-path view
        p_ens = e51['p_yes_pct']
    mkt = d.get('kalshi', {}).get('JUL', {})

    warn = abs(dev3) > DEV_ALERT
    digest = ('%s | k=%d mean %+0.3f need %+0.3f | ENS P(YES) %s | dev3 %+0.3f | mkt YES %s/%s | %s'
              % (datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ'), k, run_mean, need,
                 f'{p_ens:.1f}%' if p_ens is not None else 'n/a', dev3,
                 mkt.get('yes_bid', '?'), mkt.get('yes_ask', '?'), refresh_note))
    if warn:
        digest = 'WARN dip-check: ' + digest

    with open(os.path.join(HERE, 'track_log.csv'), 'a') as f:
        f.write(digest + '\n')
    print(digest)
    for t, act, fcv, dv in devs[-3:]:
        print('  %s actual %+0.3f vs fcst %+0.3f -> dev %+0.3f' % (t, act, fcv, dv))

    try:
        title = ('⚠️ Hottest Month' if warn else 'Hottest Month')
        body = 'k=%d mean %+0.3f | P(YES) %s | dev3 %+0.3f | mkt %s¢' % (
            k, run_mean, f'{p_ens:.1f}%' if p_ens is not None else 'n/a', dev3,
            mkt.get('yes_ask', '?'))
        subprocess.run(['osascript', '-e',
                        f'display notification "{body}" with title "{title}"'],
                       timeout=15)
    except Exception as e:
        print('notification failed:', e)


if __name__ == '__main__':
    main()
