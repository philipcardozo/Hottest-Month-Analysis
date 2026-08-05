#!/usr/bin/env python3
"""ERA5-anchored multimodel view of the live month, per CLAUDE.md's invariant:
anchor EVERY center to ERA5 before using it, or the spread you measure is mostly
per-center calibration offset rather than predictive disagreement.

A fresh 12z init has no overlap with observed ERA5 (2-day lag), so each center's
absolute offset is measured on an older run and carried to the live one. Offsets
are per-center calibration constants -- exactly the quantity the README calls
stable, and measured at 0.19 C spread across centers on 2026-07-31.

Usage:  python3 multimodel_check.py <anchor_run> <live_run> [--month YYYY-MM]
  e.g.  python3 multimodel_check.py 20260728_00z 20260730_12z

<anchor_run> must be an older run that still OVERLAPS observed ERA5; it supplies
each center's offset. <live_run> is the newest run you actually want to price.
Both must already be processed into ../Global-Temperature-Model/output/.
"""
import calendar, csv, json, math, os, sys
from datetime import datetime
from collections import defaultdict

HM = os.path.dirname(os.path.abspath(__file__))
GTM = os.path.join(os.path.dirname(HM), 'Global-Temperature-Model')
CENTERS = ['gefs', 'geps', 'ecmwf_ens', 'aifs_ens']
PHYSICS = ['gefs', 'geps', 'ecmwf_ens']          # AIFS runs ~+0.10 warm; keep it out of the center
_pos = [a for a in sys.argv[1:] if not a.startswith('--')]
ANCHOR_RUN, LIVE_RUN = (_pos + ['20260728_00z', '20260730_12z'])[:2]
if '--month' in sys.argv:
    _y, _m = sys.argv[sys.argv.index('--month') + 1].split('-')
    YR, TM = int(_y), int(_m)
else:
    YR, TM = datetime.now().year, datetime.now().month
PY, PM = (YR - 1, 12) if TM == 1 else (YR, TM - 1)
FIT = list(range(1990, YR))

daily, clim = defaultdict(dict), {}
obs = {}
for line in open(os.path.join(HM, 'era5_daily.csv')):
    if line.startswith('#'):
        continue
    p = line.strip().split(',')
    if len(p) >= 4 and p[0][:4].isdigit():
        y, m, d = map(int, p[0].split('-'))
        daily[(y, m)][d] = float(p[3])
        clim[p[0][5:]] = float(p[2])
        obs[p[0]] = float(p[3])
mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])


def load(center, run):
    out = {}
    path = os.path.join(GTM, 'output', f'{center}_{run}_daily_summary.csv')
    for row in csv.DictReader(open(path)):
        out[row['date_utc'][:10]] = {k: float(row[k]) for k in
                                     ('ensemble_mean_c', 'ensemble_std_c', 'p05_c', 'p95_c')}
    return out


def ols2(X, Y):
    n = len(Y); x1 = [x[0] for x in X]; x2 = [x[1] for x in X]
    A = [[n, sum(x1), sum(x2)],
         [sum(x1), sum(a * a for a in x1), sum(a * b for a, b in zip(x1, x2))],
         [sum(x2), sum(a * b for a, b in zip(x1, x2)), sum(a * a for a in x2)]]
    v = [sum(Y), sum(a * y for a, y in zip(x1, Y)), sum(a * y for a, y in zip(x2, Y))]
    for i in range(3):
        for j in range(i + 1, 3):
            f = A[j][i] / A[i][i]
            for k in range(3): A[j][k] -= f * A[i][k]
            v[j] -= f * v[i]
    c = [0.0] * 3
    for i in (2, 1, 0):
        c[i] = (v[i] - sum(A[i][k] * c[k] for k in range(i + 1, 3))) / A[i][i]
    return c, math.sqrt(sum((y - c[0] - c[1] * a - c[2] * b) ** 2
                            for (a, b), y in zip(X, Y)) / (n - 3))


def ols(pairs):
    n = len(pairs); sx = sum(x for x, _ in pairs); sy = sum(y for _, y in pairs)
    sxx = sum(x * x for x, _ in pairs); sxy = sum(x * y for x, y in pairs)
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx); a = (sy - b * sx) / n
    return a, b, math.sqrt(sum((y - a - b * x) ** 2 for x, y in pairs) / (n - 2))


sf = lambda z: 0.5 * math.erfc(z / math.sqrt(2))
noaa8 = {int(k): v['departure'] for k, v in
         json.load(open(os.path.join(HM, f'noaa_m{TM}.json')))['data'].items()}
aA, bA, sdA = ols([(mm(y, TM), noaa8[y]) for y in FIT])
THR = round(max(v for y, v in noaa8.items() if y < YR) + 0.005, 3)
need = (THR - aA) / bA
pm_of = lambda y: mm(y - 1, 12) if TM == 1 else mm(y, TM - 1)
prev26 = mm(PY, PM)

print(f"{calendar.month_name[TM]} translation NOAA = {aA:.4f} + {bA:.4f} x ERA5, sigma {sdA:.4f}")
print(f"record {THR-0.005:.2f} -> need ERA5 >= {need:+.5f} | prev month {prev26:+.4f} "
      f"({len(daily[(PY,PM)])} days)\n")

# ---- 1. per-center offset from the anchor run ----
print("per-center ERA5 anchoring (offset = observed ERA5 - center anomaly), "
      f"run {ANCHOR_RUN}:")
offs = {}
for c in CENTERS:
    a = load(c, ANCHOR_RUN)
    pairs = [(obs[d], a[d]['ensemble_mean_c'] - clim[d[5:]]) for d in sorted(a) if d in obs]
    assert pairs, f"{c}: no ERA5 overlap in anchor run"
    off = sum(o - r for o, r in pairs) / len(pairs)
    assert abs(off) < 0.5, f"{c}: anchor offset {off:+.3f} insane -- refusing to use it"
    offs[c] = off
    detail = " ".join(f"{d[5:]}:{o - r:+.3f}" for d, (o, r) in zip(
        [d for d in sorted(a) if d in obs], pairs))
    print(f"  {c:11s} offset {off:+.4f}  on {len(pairs)} day(s)  [{detail}]")
print(f"  spread of raw center offsets: {max(offs.values()) - min(offs.values()):.4f} C "
      f"-- this is calibration, NOT forecast disagreement\n")

# ---- 2. anchored August daily anomalies from the live run ----
live = {c: load(c, LIVE_RUN) for c in CENTERS}
augdays = sorted({int(d[8:]) for c in CENTERS for d in live[c] if d.startswith(f'{YR}-{TM:02d}')})
k_eff = max(augdays)
assert augdays == list(range(1, k_eff + 1)), f"non-contiguous August coverage: {augdays}"
print(f"anchored daily anomalies, Aug 1-{k_eff} ({LIVE_RUN}):")
print("  day  " + "  ".join(f"{c:>10s}" for c in CENTERS) + "   spread   ens-sd(IFS)")
for d in augdays:
    key = f'{YR}-{TM:02d}-{d:02d}'
    vals = {c: live[c][key]['ensemble_mean_c'] - clim[key[5:]] + offs[c] for c in CENTERS}
    sp = max(vals.values()) - min(vals.values())
    print(f"  {d:3d}  " + "  ".join(f"{vals[c]:+10.3f}" for c in CENTERS)
          + f"  {sp:7.3f}      {live['ecmwf_ens'][key]['ensemble_std_c']:.3f}")

means = {c: sum(live[c][f'{YR}-{TM:02d}-{d:02d}']['ensemble_mean_c'] - clim[f'{TM:02d}-{d:02d}'] + offs[c]
                for d in augdays) / k_eff for c in CENTERS}
print("\n  Aug 1-%d mean: " % k_eff
      + "  ".join(f"{c} {means[c]:+.4f}" for c in CENTERS)
      + f"   |  between-center spread {max(means.values())-min(means.values()):.4f}")

# ---- 3. each center through the August two-stage regression ----
X = [(pm_of(y), sum(daily[(y, TM)][d] for d in range(1, k_eff + 1)) / k_eff) for y in FIT]
c2, sd_f = ols2(X, [mm(y, TM) for y in FIT])
print(f"\nregression at k_eff={k_eff}: ERA5_aug = {c2[0]:.4f} + {c2[1]:.4f}*Jul "
      f"+ {c2[2]:.4f}*first{k_eff}, sd_f={sd_f:.4f}")
sig = math.hypot(bA * sd_f, sdA)
print(f"per-center sigma {sig:.4f} (regression {bA*sd_f:.4f} + translation {sdA:.4f})\n")
print("  center        Aug1-%d    full-Aug ERA5   NOAA    P(YES)" % k_eff)
ps = {}
for c in CENTERS:
    mu_e = c2[0] + c2[1] * prev26 + c2[2] * means[c]
    mu_n = aA + bA * mu_e
    ps[c] = 100 * sf((THR - mu_n) / sig)
    print(f"  {c:11s} {means[c]:+8.4f} {mu_e:+12.4f} {mu_n:9.4f} {ps[c]:8.1f}%")
for lab, grp in (('PHYSICS', PHYSICS), ('ALL-CENTER', CENTERS)):
    eq = sum(means[c] for c in grp) / len(grp)
    mu_e = c2[0] + c2[1] * prev26 + c2[2] * eq
    mu_n = aA + bA * mu_e
    print(f"  {lab:11s} {eq:+8.4f} {mu_e:+12.4f} {mu_n:9.4f} "
          f"{100*sf((THR-mu_n)/sig):8.1f}%")
print(f"\n  structural spread in P(YES) across centers: "
      f"{min(ps.values()):.1f}% - {max(ps.values()):.1f}%")

# ---- 4. cross-check: native-GRIB IFS ENS vs the Open-Meteo IFS ENS feed ----
cal = os.path.join(HM, 'July Calibration')
js = sorted(f for f in os.listdir(cal) if f.startswith('ens_spread_ecmwf_ifs025_'))
om = json.load(open(os.path.join(cal, js[-1])))
print(f"\ncross-check, same center two pipelines (native GRIB vs Open-Meteo points):")
print(f"  native ecmwf_ens day1-{k_eff} anchored mean : {means['ecmwf_ens']:+.4f}")
print(f"  Open-Meteo ifs025 run {om['pulled_at'][:16]}, k_eff={om['k_eff']}, "
      f"P(YES)={om['noaa']['p_yes_pct']:.1f}%")
