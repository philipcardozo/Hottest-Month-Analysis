#!/usr/bin/env python3
"""
Stress-test of the July ERA5->NOAA translation + Kelly recalibration.

[1] Stationarity of the OLS: 15-yr rolling-window (a,b) + random-walk Kalman
    filter on the coefficients (numpy state-space; a C++ KF for 36 annual points
    is the same arithmetic with a build system).
[2] White HC1 heteroskedasticity-consistent SEs for the July regression.
[3] ENSO regime test: JJA ONI (NOAA CPC, live fetch) vs |residual| — is
    translation noise wider in El Nino years?
[4] Kelly: Student-t(nu=19) tails (nu from the 252-residual OOS backtest —
    measured, unlike an EVT fit on 36 annual points which has garbage CIs),
    quarter-Kelly, capped by live book depth and a hard dollar cap.

Run: python3 calibrate.py [bankroll_dollars]   (default 500)
"""
import json, math, os, subprocess, sys
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIT_YEARS = list(range(1990, 2026))
THR = 1.185
NU = 19.0                # backtest.py MLE on pooled OOS residuals
HARD_CAP = 300.0         # $ per market, absolute


def load():
    daily = defaultdict(dict)
    for line in open(os.path.join(ROOT, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y, m)][d] = float(p[3])
    noaa = {int(k): v['departure'] for k, v in
            json.load(open(os.path.join(ROOT, 'noaa_m7.json')))['data'].items()}
    dj = json.loads(open(os.path.join(ROOT, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    return daily, noaa, dj


def main():
    bankroll = float(sys.argv[1]) if len(sys.argv) > 1 else 500.0
    daily, noaa, dj = load()
    mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])
    yrs = [y for y in FIT_YEARS if y in noaa]
    x = np.array([mm(y, 7) for y in yrs])
    y = np.array([noaa[y] for y in yrs])
    n = len(yrs)

    # ---- [1] rolling window ----
    print("=" * 70)
    print("[1] STATIONARITY — July translation NOAA = a + b*ERA5")
    print("    %-12s %8s %8s" % ("window", "a", "b"))
    W = 15
    for s in range(0, n - W + 1, 5):
        xs, ys = x[s:s + W], y[s:s + W]
        b, a = np.polyfit(xs, ys, 1)
        print("    %d-%d    %8.3f %8.3f" % (yrs[s], yrs[s + W - 1], a, b))
    b_full, a_full = np.polyfit(x, y, 1)
    resid = y - (a_full + b_full * x)
    print("    full 1990-2025 %6.3f %8.3f" % (a_full, b_full))

    # random-walk Kalman on (a,b): state theta_t, theta_t = theta_{t-1} + w,
    # obs y_t = [1 x_t] theta_t + v.  Q small (coeffs drift slowly), R = obs var.
    R = float(resid @ resid / (n - 2))
    Q = np.diag([1e-5, 1e-4])
    theta = np.array([a_full, b_full])          # neutral init at full-sample fit
    P = np.eye(2) * 0.05
    path = []
    for xi, yi in zip(x, y):
        P = P + Q
        H = np.array([1.0, xi])
        S = H @ P @ H + R
        K = P @ H / S
        theta = theta + K * (yi - H @ theta)
        P = P - np.outer(K, H @ P)
        path.append(theta.copy())
    print("\n    Kalman (random-walk coeffs): b 2005=%.3f  2015=%.3f  2020=%.3f  2025=%.3f"
          % (path[yrs.index(2005)][1], path[yrs.index(2015)][1],
             path[yrs.index(2020)][1], path[-1][1]))
    print("    terminal state: a=%.3f b=%.3f  (full-sample: a=%.3f b=%.3f)"
          % (path[-1][0], path[-1][1], a_full, b_full))
    drift = abs(path[-1][1] - b_full)
    print("    VERDICT: beta drift %s (|Δb|=%.3f -> ΔNOAA at ERA5=0.55: %.3f)"
          % ("MATERIAL" if drift > 0.05 else "negligible", drift, drift * 0.55))

    # ---- [2] White HC1 SEs ----
    X = np.column_stack([np.ones(n), x])
    XtXi = np.linalg.inv(X.T @ X)
    e2 = resid ** 2 * (n / (n - 2))              # HC1 dof correction
    cov_hc = XtXi @ (X.T * e2) @ X @ XtXi
    se_cl = np.sqrt(np.diag(XtXi) * R)
    se_hc = np.sqrt(np.diag(cov_hc))
    print("\n[2] WHITE HC1 vs CLASSICAL SEs")
    print("    a: %.4f (classical %.4f)   b: %.4f (classical %.4f)"
          % (se_hc[0], se_cl[0], se_hc[1], se_cl[1]))
    infl = se_hc[1] / se_cl[1]
    print("    b SE inflation x%.2f -> %s" % (infl,
          "heteroskedasticity matters, widen intervals" if infl > 1.2 else "homoskedastic enough"))

    # ---- [3] ENSO regime variance ----
    print("\n[3] ENSO REGIME — |residual| vs JJA ONI (NOAA CPC)")
    try:
        raw = subprocess.run(['curl', '-sL', '--max-time', '60',
                              'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'],
                             capture_output=True).stdout.decode()
        oni = {}
        for line in raw.splitlines():
            p = line.split()
            if len(p) == 4 and p[0] == 'JJA' and p[1].isdigit():
                oni[int(p[1])] = float(p[3])
        nino = [abs(r) for yy, r in zip(yrs, resid) if oni.get(yy, 0) >= 0.5]
        rest = [abs(r) for yy, r in zip(yrs, resid) if oni.get(yy, 0) < 0.5]
        sd_n, sd_r = np.std(nino, ddof=1), np.std(rest, ddof=1)
        rms_n = math.sqrt(np.mean(np.square(nino)))
        rms_r = math.sqrt(np.mean(np.square(rest)))
        _, p_lev = stats.levene(nino, rest)
        print("    El Nino JJA (ONI>=0.5): n=%d rms|e|=%.4f | other: n=%d rms|e|=%.4f"
              % (len(nino), rms_n, len(rest), rms_r))
        print("    Levene p=%.2f -> %s" % (p_lev,
              "variance regime shift NOT significant" if p_lev > 0.1 else
              "WIDEN sigma in El Nino months"))
    except Exception as ex:
        print("    ONI fetch failed (%s) — skipping, rerun later" % ex)

    # ---- [4] Kelly, t-tails, caps ----
    jul, kal = dj['model']['jul'], dj['kalshi']['JUL']
    ens = jul.get('ens')
    mu = jul['a'] + jul['b'] * ens['mu_era5']
    sig = math.hypot(jul['b'] * ens['sd_f'], jul['sd'])
    z = (THR - mu) / sig
    p_yes_n = stats.norm.sf(z)
    p_yes_t = stats.t.sf(z * math.sqrt(NU / (NU - 2)), NU)
    # ensemble-averaged tail if ens_spread output exists (member mixture > any single dist)
    ens_files = sorted(f for f in os.listdir(HERE) if f.startswith('ens_spread_'))
    p_yes_ens = None
    if ens_files:
        js = json.load(open(os.path.join(HERE, ens_files[-1])))
        p_yes_ens = js.get('noaa', {}).get('p_yes_pct', None)
        if p_yes_ens is not None:
            p_yes_ens /= 100.0
    print("\n[4] KELLY — July NO (Kalshi)")
    print("    P(YES): Normal %.4f%% | t(nu=%.0f) %.4f%% | 51-member ENS %s"
          % (100 * p_yes_n, NU, 100 * p_yes_t,
             ("%.2f%%" % (100 * p_yes_ens)) if p_yes_ens is not None else "run ens_spread.py"))
    p_yes = max(p_yes_t, p_yes_ens or 0.0, 0.005)    # conservative: worst tail + 0.5% model-risk floor
    no_ask = kal['no_ask'] / 100.0
    p_no = 1 - p_yes
    edge = p_no - no_ask
    b_odds = (1 - no_ask) / no_ask                   # payoff per $ staked on NO
    f_full = (p_no * b_odds - p_yes) / b_odds
    f_quarter = f_full / 4
    stake_kelly = f_quarter * bankroll
    depth_cap = 0.25 * kal['oi'] * no_ask * 0.05     # ponytail: crude 5%-of-OI depth proxy; replace with book depth via authed API
    stake = min(stake_kelly, depth_cap, HARD_CAP)
    print("    using P(YES)=%.2f%% (max of tails + 0.5%% floor) vs NO ask %.0f cents"
          % (100 * p_yes, 100 * no_ask))
    print("    edge=%.1f cents | quarter-Kelly=%.1f%% of bankroll ($%.0f on $%.0f)"
          % (100 * edge, 100 * f_quarter, stake_kelly, bankroll))
    print("    FINAL STAKE = $%.0f  (min of quarter-Kelly $%.0f, depth-proxy $%.0f, hard cap $%.0f)"
          % (stake, stake_kelly, depth_cap, HARD_CAP))
    print("    NOT financial advice; sizes are model output with stated assumptions.")

    assert 0 < p_yes < 0.5 and 0 < f_quarter < 0.25
    print("\nself-check: OK")


if __name__ == '__main__':
    main()
