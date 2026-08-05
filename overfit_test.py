#!/usr/bin/env python3
"""
Overfitting / robustness audit of the July ENS-augmented forecast, prompted by the
P(YES) swing ~36% (obs-only) -> ~3.5% (ENS). Separates three possible causes:
  (a) regression overfit          -> LOO-CV + expanding-window OOS of the k-day OLS
  (b) mechanics artifact          -> placebo: persistence-filled pseudo-month
  (c) trust in the NWP forecast   -> sensitivity to forecast bias and trust weight

Run: python3 overfit_test.py
"""
import calendar, json, math, os
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
FIT_YEARS = list(range(1990, 2026))
THR = None   # set from the live record in main(); tie settles NO -> record + 0.005


def load():
    daily = defaultdict(dict)
    for line in open(os.path.join(HERE, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y, m)][d] = float(p[3])
    dj = json.loads(open(os.path.join(HERE, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    fl = sorted(f for f in os.listdir(os.path.join(HERE, 'forecast_log')) if f.startswith('fcst_'))
    import fetch_forecast as ff
    gm = json.load(open(os.path.join(HERE, 'forecast_log', fl[-1])))['global_mean_C']
    anom, _, _ = ff.to_anomaly(gm)
    return daily, dj, anom


def design(daily, k, tm=7):
    """X=(prev-month mean, first-k mean of month tm), Y=full-tm mean, over FIT_YEARS.
    k=0 drops the first-k column entirely -- with no observed days there is no
    such predictor, and the model degenerates to prev-month-only (same fallback
    update_data.py uses on the 1st of a month)."""
    mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])
    pm = lambda y: mm(y - 1, 12) if tm == 1 else mm(y, tm - 1)
    if k == 0:
        X = np.array([[1.0, pm(y)] for y in FIT_YEARS])
    else:
        X = np.array([[1.0, pm(y), sum(daily[(y, tm)][d] for d in range(1, k + 1)) / k]
                      for y in FIT_YEARS])
    Y = np.array([mm(y, tm) for y in FIT_YEARS])
    return X, Y


def fit_sd(X, Y):
    c, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r = Y - X @ c
    return c, math.sqrt(r @ r / (len(Y) - X.shape[1]))


def p_yes(mu_era, sd_f, jul):
    mu = jul['a'] + jul['b'] * mu_era
    sig = math.hypot(jul['b'] * sd_f, jul['sd'])
    return 100 * stats.norm.sf((THR - mu) / sig), mu, sig


def main():
    daily, dj, anom = load()
    global THR
    M = dj['model']
    jul = M[M['cur']]
    TM = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].index(M['cur']) + 1
    YR = M['year']
    PY, PM = (YR - 1, 12) if TM == 1 else (YR, TM - 1)
    THR = round(jul['record'] + 0.005, 3)
    mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])
    jun26 = mm(PY, PM)
    obs = daily.get((YR, TM), {})
    k = len(obs)
    ND = calendar.monthrange(YR, TM)[1]
    # k=0 (first days of a month, ERA5 still 2 days behind): the persistence
    # placebo has no observed days to persist, so persist the previous month --
    # exactly the k=0 fallback update_data.py uses.
    obs_mean = sum(obs.values()) / k if k else jun26
    fdays = sorted((int(t[8:]), v) for t, v in anom.items()
                   if t.startswith('%d-%02d-' % (YR, TM)) and int(t[8:]) > k)
    k_eff = fdays[-1][0]
    fc_mean_rem = sum(v for _, v in fdays) / len(fdays)

    print("=" * 74)
    print("OVERFIT / ROBUSTNESS AUDIT   (k=%d observed, k_eff=%d with forecast)" % (k, k_eff))
    print("=" * 74)

    # ---- (a) is the k-day regression overfit? LOO + expanding-window OOS ----
    print("\n[a] Regression honesty (3 params, %d yrs). Overfit <=> OOS >> in-sample." % len(FIT_YEARS))
    print("    %-6s %10s %10s %12s" % ("k", "in-sample", "LOO-RMSE", "expand-OOS"))
    for kk in (6, 15, 23):
        X, Y = design(daily, kk, TM)
        _, sd_in = fit_sd(X, Y)
        loo = []
        for i in range(len(Y)):
            idx = [j for j in range(len(Y)) if j != i]
            c, _ = fit_sd(X[idx], Y[idx])
            loo.append(Y[i] - X[i] @ c)
        loo_rmse = math.sqrt(np.mean(np.square(loo)))
        oos = []
        for t in range(2005, 2026):
            tr = [i for i, y in enumerate(FIT_YEARS) if y < t]
            te = FIT_YEARS.index(t)
            c, _ = fit_sd(X[tr], Y[tr])
            oos.append(Y[te] - X[te] @ c)
        oos_rmse = math.sqrt(np.mean(np.square(oos)))
        print("    k=%-4d %10.4f %10.4f %12.4f" % (kk, sd_in, loo_rmse, oos_rmse))

    # ---- (b) placebo: does the k_eff machinery alone create the collapse? ----
    print("\n[b] Placebo — fill days %d..%d with PERSISTENCE (first-%d mean), same machinery:"
          % (k + 1, k_eff, k))
    X23, Y23 = design(daily, k_eff, TM)
    c23, sd23 = fit_sd(X23, Y23)
    errsum = sum(min(0.015 * max(d - k, 1) ** 0.7, 0.15) for d, _ in fdays)
    sd_tot = math.hypot(sd23, 0.6 * errsum / ND)

    def pseudo_p(rem_mean):
        pm = (obs_mean * k + rem_mean * (k_eff - k)) / k_eff
        mu_era = c23 @ [1.0, jun26, pm]
        return p_yes(mu_era, sd_tot, jul)

    p_pers, mu_pers, _ = pseudo_p(obs_mean)
    p_fc, mu_fc, sig_fc = pseudo_p(fc_mean_rem)
    X6, Y6 = design(daily, k, TM)
    c6, sd6 = fit_sd(X6, Y6)
    # at k=0 the design has no first-k column, so the row must match its width
    row6 = [1.0, jun26] if k == 0 else [1.0, jun26, obs_mean]
    p_obs, mu_obs, sig_obs = p_yes(c6 @ row6, sd6, jul)
    print("    obs-only (k=%d):        P(YES)=%5.1f%%  mu=%.3f sig=%.3f" % (k, p_obs, mu_obs, sig_obs))
    print("    persistence placebo:    P(YES)=%5.1f%%  mu=%.3f  <- same sigma machinery, no NWP"
          % (p_pers, mu_pers))
    print("    NWP forecast fill:      P(YES)=%5.1f%%  mu=%.3f sig=%.3f" % (p_fc, mu_fc, sig_fc))
    print("    -> if placebo ~= obs-only, the collapse is NOT a mechanics artifact;")
    print("       the drop comes from the forecast CONTENT (remaining-days %+.3f vs persistence %+.3f)"
          % (fc_mean_rem, obs_mean))

    # ---- (c) sensitivity: how wrong can the NWP be before the conclusion flips? ----
    print("\n[c] Sensitivity of P(YES):")
    print("    trust weight w (rem = w*forecast + (1-w)*persistence):")
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        p, _, _ = pseudo_p(w * fc_mean_rem + (1 - w) * obs_mean)
        print("      w=%.2f -> %5.1f%%" % (w, p))
    print("    forecast bias shift (add to every forecast day):")
    for sh in (-0.10, -0.05, 0.0, +0.05, +0.10):
        p, _, _ = pseudo_p(fc_mean_rem + sh)
        print("      shift %+0.2f -> %5.1f%%" % (sh, p))

    # ---- swing decomposition ----
    print("\n[d] 36%% -> 3.5%% decomposition (mu move vs sigma move):")
    p_mu_only = 100 * stats.norm.sf((THR - mu_fc) / sig_obs)
    p_sig_only = 100 * stats.norm.sf((THR - mu_obs) / sig_fc)
    print("    obs-only both:        %5.1f%%   (mu=%.3f sig=%.3f)" % (p_obs, mu_obs, sig_obs))
    print("    new mu, old sigma:    %5.1f%%   -> mu move (forecast content) does this" % p_mu_only)
    print("    old mu, new sigma:    %5.1f%%   -> sigma tightening alone does this" % p_sig_only)
    print("    both (reported):      %5.1f%%" % p_fc)

    assert abs(p_fc - pseudo_p(fc_mean_rem)[0]) < 1e-9
    print("\nself-check: OK")


if __name__ == '__main__':
    main()
