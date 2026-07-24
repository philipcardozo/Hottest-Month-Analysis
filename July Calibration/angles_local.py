#!/usr/bin/env python3
"""
Forecast-free stress-test angles for P(July 2026 = NOAA record), i.e. no NWP at
all — do the raw data and dumb-but-honest methods agree with the ensemble answer?

Angles:
 [A] Historical analog completion, 1940-2025: graft every past July's remaining-
     days shape (re-centered on 2026's level) onto the observed days -> empirical
     distribution of full-July means -> P(>= ERA5-needed). Two recenterings:
     first-k mean (neutral) and last-3-day mean (persistence-of-now).
 [B] Exceedance base rate: how often has ANY July's remaining-(31-k) mean exceeded
     its first-k mean by the delta 2026 now requires? Same across all 12 months
     (~1000 samples) for power.
 [C] Largest sustained warm swing ever: all-time max of mean(next 31-k days) -
     mean(prev k days) across the full 1940-2026 daily record, any month.
 [D] AR(1) Monte Carlo around the observed level (forecast-blind dynamics).
 [E] Nonparametric translation tails: empirical July OOS residuals instead of
     a Normal -> P(NOAA >= 1.185 | mu_era) without distributional assumptions.
 [F] Deliberately dumb models: persistence-at-latest, EVERY-remaining-day-at-
     month-max, last-5-day linear trend, 2023/2024 analogs, market-implied
     remaining mean (what must the rest of July do for 22c YES to be fair).

Run: python3 angles_local.py
"""
import json, math, os
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    daily = defaultdict(dict)
    for line in open(os.path.join(ROOT, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y, m)][d] = float(p[3])
    dj = json.loads(open(os.path.join(ROOT, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    jul = dj['model']['jul']
    a, b, sd_t = jul['a'], jul['b'], jul['sd']
    THR = 1.185
    need_era = (THR - a) / b

    obs = daily[(2026, 7)]
    k = len(obs)
    vals = [obs[d] for d in range(1, k + 1)]
    obs_sum, obs_mean = sum(vals), sum(vals) / k
    rem_n = 31 - k
    need_rem = (need_era * 31 - obs_sum) / rem_n
    p_norm = lambda mu: 100 * stats.norm.sf((THR - (a + b * mu)) / sd_t)

    print("=" * 74)
    print("FORECAST-FREE ANGLES  k=%d obs, mean %+.4f, latest %+.3f" % (k, obs_mean, vals[-1]))
    print("record needs: full-month ERA5 >= %+.4f  ->  remaining %d days avg >= %+.4f"
          % (need_era, rem_n, need_rem))

    # [A] analog completion over every complete July on record
    years = [y for y in range(1940, 2026) if len(daily.get((y, 7), {})) == 31]
    comp_neutral, comp_persist = [], []
    last3 = sum(vals[-3:]) / 3
    for y in years:
        dy = daily[(y, 7)]
        their_firstk = sum(dy[d] for d in range(1, k + 1)) / k
        their_rem = [dy[d] for d in range(k + 1, 32)]
        comp_neutral.append((obs_sum + sum(v - their_firstk + obs_mean for v in their_rem)) / 31)
        their_lastk3 = sum(dy[d] for d in range(k - 2, k + 1)) / 3
        comp_persist.append((obs_sum + sum(v - their_lastk3 + last3 for v in their_rem)) / 31)
    comp_neutral, comp_persist = np.array(comp_neutral), np.array(comp_persist)
    for lbl, cm in (('recenter on first-%d mean' % k, comp_neutral),
                    ('recenter on last-3 mean (persistence)', comp_persist)):
        n_hit = int((cm >= need_era).sum())
        p_mix = float(np.mean([p_norm(x) for x in cm]))
        print("\n[A] analog completion (%s, n=%d):" % (lbl, len(cm)))
        print("    completions >= needed: %d/%d  | mean %+0.3f  max %+0.3f (%d)"
              % (n_hit, len(cm), cm.mean(), cm.max(), years[int(cm.argmax())]))
        print("    P(YES) with translation noise = %.2f%%" % p_mix)

    # [B] exceedance base rates
    dj_hist = []
    for y in years:
        dy = daily[(y, 7)]
        fk = sum(dy[d] for d in range(1, k + 1)) / k
        rm = sum(dy[d] for d in range(k + 1, 32)) / rem_n
        dj_hist.append(rm - fk)
    dj_hist = np.array(dj_hist)
    delta_need = need_rem - obs_mean
    print("\n[B] base rate of (remaining mean - first-%d mean) >= %+0.3f:" % (k, delta_need))
    print("    July only: %d/%d (max ever %+0.3f, %d)"
          % (int((dj_hist >= delta_need).sum()), len(dj_hist), dj_hist.max(),
             years[int(dj_hist.argmax())]))
    all_d = []
    for y in range(1940, 2026):
        for mth in range(1, 13):
            dm = daily.get((y, mth), {})
            if len(dm) < 28:
                continue
            nd = len(dm)
            kk = min(k, nd - 5)
            rn = nd - kk
            fk = sum(dm[d] for d in range(1, kk + 1)) / kk
            rm = sum(dm[d] for d in sorted(dm) if d > kk) / rn
            all_d.append(rm - fk)
    all_d = np.array(all_d)
    print("    all months 1940-2025: %d/%d = %.3f%%  (99.9th pct %+0.3f)"
          % (int((all_d >= delta_need).sum()), len(all_d),
             100 * (all_d >= delta_need).mean(), np.percentile(all_d, 99.9)))

    # [C] biggest sustained warm swing ever (any window, any month)
    series = []
    for y in range(1940, 2027):
        for mth in range(1, 13):
            for d in sorted(daily.get((y, mth), {})):
                series.append(daily[(y, mth)][d])
    s = np.array(series)
    csum = np.concatenate([[0.0], np.cumsum(s)])
    win_prev, win_next = k, rem_n
    best = -9
    for i in range(win_prev, len(s) - win_next):
        jump = (csum[i + win_next] - csum[i]) / win_next - (csum[i] - csum[i - win_prev]) / win_prev
        best = max(best, jump)
    print("\n[C] largest EVER (next-%d mean − prev-%d mean), any month 1940-2026: %+0.3f"
          % (win_next, win_prev, best))
    print("    2026 needs %+0.3f -> %s precedent in 86 years of daily data"
          % (delta_need, "HAS" if best >= delta_need else "NO"))

    # [D] AR(1) Monte Carlo around observed level (no dip knowledge)
    devs, lags = [], []
    for y in range(1990, 2026):
        dy = daily[(y, 7)]
        mo = sum(dy.values()) / 31
        dv = [dy[d] - mo for d in range(1, 32)]
        devs += dv
        lags += [(dv[i - 1], dv[i]) for i in range(1, 31)]
    rho = np.corrcoef([x for x, _ in lags], [y2 for _, y2 in lags])[0, 1]
    sd_d = np.std(devs, ddof=1)
    sd_innov = sd_d * math.sqrt(1 - rho ** 2)
    rng = np.random.default_rng(7)
    NSIM = 20000
    hits = 0
    mus = np.empty(NSIM)
    for i in range(NSIM):
        x = vals[-1] - obs_mean
        tot = obs_sum
        for _ in range(rem_n):
            x = rho * x + rng.normal(0, sd_innov)
            tot += obs_mean + x
        mus[i] = tot / 31
    p_mc = float(np.mean([p_norm(x) for x in mus]))
    print("\n[D] AR(1) Monte Carlo (rho=%.2f, sd_day=%.3f, level=first-%d mean, %d sims):"
          % (rho, sd_d, k, NSIM))
    print("    P(YES) = %.2f%%   (forecast-blind; the obs-only regression said ~%.0f%%)"
          % (p_mc, p_norm((jul['fc']['c'][0] + jul['fc']['c'][1] * (sum(daily[(2026,6)].values())/30)
                           + jul['fc']['c'][2] * obs_mean) if jul.get('fc') else obs_mean)))

    # [E] nonparametric translation tails (empirical July OOS residuals)
    noaa = {int(kk): v['departure'] for kk, v in
            json.load(open(os.path.join(ROOT, 'noaa_m7.json')))['data'].items()}
    resid = []
    for t in range(2005, 2026):
        fit = [y for y in range(1990, t) if y in noaa]
        xs = np.array([sum(daily[(y,7)].values())/31 for y in fit])
        ys = np.array([noaa[y] for y in fit])
        bb, aa = np.polyfit(xs, ys, 1)
        mu26 = sum(daily[(t,7)].values())/31
        resid.append(noaa[t] - (aa + bb * mu26))
    resid = np.array(resid)
    def p_emp(mu_era):
        return 100 * float(np.mean((a + b * mu_era + resid) >= THR))
    print("\n[E] empirical-residual tails (n=%d July OOS): P(YES | mu_era=needed-0.02)=%.1f%%,"
          % (len(resid), p_emp(need_era - 0.02)))
    print("    P at ENS-median-level mu (+0.586 from Jul 13 run) = %.2f%% (Normal gave ~1.1%%)"
          % p_emp(0.586))

    # [F] deliberately dumb models
    print("\n[F] dumb models (full-month mean -> P(YES) with translation noise):")
    dumb = {
        'persistence at latest (%+0.3f)' % vals[-1]: (obs_sum + rem_n * vals[-1]) / 31,
        'EVERY remaining day = month max (%+0.3f)' % max(vals): (obs_sum + rem_n * max(vals)) / 31,
        'last-5-day linear trend extrapolated': None,
        '2023 shape analog (ERA5 record yr)': comp_neutral[years.index(2023)],
        '2024 shape analog (NOAA record yr)': comp_neutral[years.index(2024)],
    }
    t5 = np.polyfit(range(5), vals[-5:], 1)
    ext = [vals[-1] + t5[0] * (i + 1) for i in range(rem_n)]
    dumb['last-5-day linear trend extrapolated'] = (obs_sum + sum(ext)) / 31
    for lbl, mu in dumb.items():
        print("    %-42s mu=%+0.3f  P=%6.2f%%" % (lbl, mu, p_norm(mu)))
    # market-implied: what remaining mean makes P(YES)=22%?
    from scipy.optimize import brentq
    yes_mkt = dj['kalshi']['JUL']['yes_ask'] / 100.0
    f = lambda rm: stats.norm.sf((THR - (a + b * (obs_sum + rem_n * rm) / 31)) / sd_t) - yes_mkt
    rm_impl = brentq(f, -1, 2)
    print("    market %2.0f%% implies remaining-%d-day mean = %+0.3f  (vs month max %+0.3f, latest %+0.3f)"
          % (100 * yes_mkt, rem_n, rm_impl, max(vals), vals[-1]))

    print("\nself-check: OK" if len(years) > 80 and len(all_d) > 900 else "self-check: WEAK SAMPLE")


if __name__ == '__main__':
    main()
