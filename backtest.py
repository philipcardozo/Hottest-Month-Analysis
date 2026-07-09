#!/usr/bin/env python3
"""
Backtest harness for the Hottest-Month translation model (ERA5 monthly mean -> NOAA).

Answers three questions the rest of the roadmap depends on:
  1. Out-of-sample calibration: is the quoted per-month sigma honest, or overconfident?
     (expanding-window: fit 1990..t-1, predict t, for t in 2005..2025, every month)
  2. Tail shape: are the standardized residuals Normal, or fat-tailed (-> Student-t)?
     This is where 100% of the P(YES) lottery-ticket money lives.
  3. Bias drift: is the +0.02 "2026 audit bias" a one-off, or a persistent recent-warm trend?
     (generalizes the dashboard knob across 2015..2025)

Then it re-prices the LIVE June/July markets Normal vs Student-t so the tail verdict is actionable.

Stdlib + numpy + scipy (already installed). No network. Reads era5_daily.csv + noaa_m*.json.
Run: python3 backtest.py

ponytail: this backtests the *translation* layer (complete-month ERA5->NOAA), the cleanest
large-n residual sample. The day-k *forecast* layer (and its ECMWF augmentation) is the next
extension -> that's where the before/after variance-collapse curve gets drawn. Forecast residuals
= translation noise + weather noise, so translation tails are a conservative floor on fatness.
"""
import json, os, math
from collections import defaultdict
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
FIT_START = 1990          # model's fit window start
OOS_START = 2005          # first out-of-sample test year (>=15 fit years behind it)
OOS_END   = 2025          # last complete NOAA year


def era5_monthly_means():
    """(year,month) -> mean of daily anomaly (col 3), matching update_data.py's mm()."""
    daily = defaultdict(dict)
    for line in open(os.path.join(HERE, 'era5_daily.csv')):
        if line.startswith('#'):
            continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y, m)][d] = float(p[3])
    return {k: sum(v.values()) / len(v) for k, v in daily.items() if v}


def noaa_series(m):
    """month m (1..12) -> {year: departure}."""
    d = json.load(open(os.path.join(HERE, f'noaa_m{m}.json')))['data']
    return {int(k): v['departure'] for k, v in d.items()}


def ols_fit(xs, ys):
    """Return (a, b, sd) for y = a + b x, sd = in-sample residual SD (n-2)."""
    b, a = np.polyfit(xs, ys, 1)
    resid = np.array(ys) - (a + b * np.array(xs))
    sd = math.sqrt((resid @ resid) / (len(ys) - 2))
    return a, b, sd


def backtest():
    mm = era5_monthly_means()
    noaa = {m: noaa_series(m) for m in range(1, 13)}
    MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

    per_month = {}                 # m -> dict(n, rmse, sd_in, ratio)
    all_z = []                     # pooled standardized residuals
    year_resid = defaultdict(list) # test_year -> [resid across months]

    for m in range(1, 13):
        zs, resids, sds = [], [], []
        for t in range(OOS_START, OOS_END + 1):
            fit_yrs = [y for y in range(FIT_START, t)
                       if (y, m) in mm and y in noaa[m]]
            if len(fit_yrs) < 12 or (t, m) not in mm or t not in noaa[m]:
                continue
            a, b, sd = ols_fit([mm[(y, m)] for y in fit_yrs],
                               [noaa[m][y] for y in fit_yrs])
            pred = a + b * mm[(t, m)]
            r = noaa[m][t] - pred
            resids.append(r); sds.append(sd); zs.append(r / sd)
            year_resid[t].append(r)
        if not resids:
            continue
        resids = np.array(resids)
        per_month[m] = dict(n=len(resids),
                            rmse=math.sqrt((resids @ resids) / len(resids)),
                            sd_in=float(np.mean(sds)))
        per_month[m]['ratio'] = per_month[m]['rmse'] / per_month[m]['sd_in']
        all_z.extend(zs)

    z = np.array(all_z)
    n = len(z)

    # ---- normality / tail diagnostics on pooled standardized residuals ----
    exkurt = float(stats.kurtosis(z, fisher=True, bias=False))   # 0 = normal
    nu_kurt = 4 + 6 / exkurt if exkurt > 0.05 else float('inf')  # t excess kurtosis = 6/(nu-4)
    # MLE Student-t on standardized residuals (loc/scale free)
    nu_mle, t_loc, t_scale = stats.t.fit(z)

    print("=" * 72)
    print("BACKTEST — ERA5->NOAA translation, expanding-window OOS %d..%d" % (OOS_START, OOS_END))
    print("=" * 72)
    print("\n[1] Per-month OOS calibration (ratio>1 => quoted sigma is OVERCONFIDENT)")
    print("    %-4s %4s %8s %8s %6s" % ("mon", "n", "OOS_RMSE", "sd_in", "ratio"))
    for m in range(1, 13):
        if m in per_month:
            pm = per_month[m]
            star = "  <-- live" if m in (6, 7) else ""
            print("    %-4s %4d %8.4f %8.4f %6.2f%s" %
                  (MONTHS[m-1], pm['n'], pm['rmse'], pm['sd_in'], pm['ratio'], star))
    print("    pooled |z| std = %.3f  (1.00 = quoted sigma perfectly calibrated)" % z.std(ddof=1))

    print("\n[2] Tail shape (pooled standardized residuals, n=%d)" % n)
    print("    mean=%.3f  std=%.3f  excess_kurtosis=%.3f  (0=Normal, >0=fat)" % (z.mean(), z.std(ddof=1), exkurt))
    print("    Student-t nu:  kurtosis-match=%s   MLE=%.1f" %
          (("%.1f" % nu_kurt) if math.isfinite(nu_kurt) else "inf(thin)", nu_mle))
    print("    two-sided |z| exceedance   empirical / Normal / t(nu=%.1f):" % nu_mle)
    for z0, lbl in [(1.2816, "10%"), (1.6449, "5%"), (1.9600, "2.5%"), (2.3263, "1%")]:
        emp = float((np.abs(z) > z0).mean())
        p_norm = 2 * stats.norm.sf(z0)
        p_t = 2 * stats.t.sf(z0, nu_mle, scale=t_scale)
        print("      |z|>%.2f (%-4s):  emp=%.3f  norm=%.3f  t=%.3f" % (z0, lbl, emp, p_norm, p_t))
    verdict = "STUDENT-t (fat tails, YES tickets underpriced by Normal)" if (
        math.isfinite(nu_mle) and nu_mle < 15 and exkurt > 0.2) else "Normal is adequate"
    print("    VERDICT: %s" % verdict)

    print("\n[3] Bias drift — mean OOS residual per test year (NOAA warmer than model = +)")
    recent = []
    for t in range(2015, OOS_END + 1):
        if t in year_resid:
            mr = float(np.mean(year_resid[t]))
            recent.append(mr)
            print("    %d: %+.3f  (n=%d months)" % (t, mr, len(year_resid[t])))
    if recent:
        print("    2015-2025 mean=%+.3f   last-5 mean=%+.3f   dashboard knob=+0.020" %
              (np.mean(recent), np.mean(recent[-5:])))

    # ---- [4] actionable: re-price live June/July markets Normal vs Student-t ----
    print("\n[4] LIVE re-pricing  Normal vs Student-t(nu=%.1f)  (fair YES %%)" % nu_mle)
    dj = json.loads(open(os.path.join(HERE, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    model, kal = dj['model'], dj['kalshi']
    bias = model['bias']
    thr = 1.185  # record 1.18 + 0.005 two-decimal rounding boundary

    def p_yes(mu, sigma, nu):
        zt = (thr - mu) / sigma
        return stats.norm.sf(zt) * 100, stats.t.sf(zt * (math.sqrt(nu / (nu - 2)) if nu > 2 else 1), nu) * 100

    # June: complete-ish translation, mu = a + b*era26
    mu_jun = model['jun']['a'] + model['jun']['b'] * model['jun']['era26']
    sig_jun = model['jun']['sd']
    # July: forecast layer, mu from fc coefficients
    fc = model['jul']['fc']; c = fc['c']
    era_jul_fc = c[0] + c[1] * model['jun']['era26'] + c[2] * fc['firstk']
    mu_jul = model['jul']['a'] + model['jul']['b'] * era_jul_fc
    sig_jul = math.hypot(model['jul']['b'] * fc['sd_f'], model['jul']['sd'])

    for tag, mu, sig in (('JUN', mu_jun, sig_jun), ('JUL', mu_jul, sig_jul)):
        for label, mu_ in (('raw', mu), ('bias-adj', mu + bias)):
            pn, pt = p_yes(mu_, sig, nu_mle)
            print("    %s %-9s mu=%.3f sig=%.3f | Normal YES=%5.1f%%  t YES=%5.1f%%  | mkt YES~%.0f" %
                  (tag, label, mu_, sig, pn, pt, kal[tag]['yes_ask']))

    # ---- self-check ----
    assert n > 50, "too few OOS points"
    assert math.isfinite(per_month[6]['rmse']) and math.isfinite(per_month[7]['rmse'])
    assert 0 <= (np.abs(z) > 1.96).mean() <= 1
    assert nu_mle > 2, "t with nu<=2 has no variance"
    print("\nself-check: OK (n=%d pooled OOS residuals, June/July present)" % n)
    return per_month, z, nu_mle


if __name__ == '__main__':
    backtest()
