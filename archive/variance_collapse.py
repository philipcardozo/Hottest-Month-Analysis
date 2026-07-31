#!/usr/bin/env python3
"""
Before/after variance-collapse curve for the July NOAA forecast.

BEFORE = current model: predict full-July ERA5 from (June mean, first-k observed days).
         Forecast sigma shrinks only as real days accumulate.
AFTER  = add an ECMWF/ENS forecast of the *remaining* (31-k) days as a 3rd predictor.
         The unobserved-days uncertainty shrinks by sqrt(1 - rho^2), where rho is the
         ensemble's *partial* skill for the remaining-days global-mean anomaly (given
         June + first-k already known). We don't have live ENS here, so we bracket rho
         in {0.4, 0.6, 0.8} and show the perfect-foresight floor (rho=1 -> just the
         translation sigma). This says how many days LEFT the collapse shifts, i.e.
         whether the GRIB pipeline is worth building before we build it.

Reads era5_daily.csv + data.js (live July translation params). Stdlib + numpy + matplotlib.
Run: python3 variance_collapse.py   ->  prints table, writes variance_collapse.png

ponytail: rho is an assumed ENS partial-skill, not measured. Once the forecast feed is
wired, replace the rho scenarios with the harness-measured partial correlation.
"""
import json, os, math
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIT_YEARS = list(range(1990, 2026))


def daily_era5():
    daily = defaultdict(dict)
    for line in open(os.path.join(HERE, "era5_daily.csv")):
        if line.startswith("#"):
            continue
        p = line.strip().split(",")
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split("-"))
            daily[(y, m)][d] = float(p[3])
    return daily


def ols2_sd(X, Y):
    """residual SD (n-3) of Y ~ 1 + x1 + x2, via numpy least squares."""
    A = np.column_stack([np.ones(len(Y)), [x[0] for x in X], [x[1] for x in X]])
    coef, *_ = np.linalg.lstsq(A, np.array(Y), rcond=None)
    resid = np.array(Y) - A @ coef
    return math.sqrt((resid @ resid) / (len(Y) - 3))


def main():
    daily = daily_era5()
    mm = lambda y, m: sum(daily[(y, m)].values()) / len(daily[(y, m)])
    dj = json.loads(open(os.path.join(HERE, "data.js")).read().split("=", 1)[1].rstrip(";\n"))
    bL, sdL = dj["model"]["jul"]["b"], dj["model"]["jul"]["sd"]   # translation slope + sigma

    ks = list(range(1, 31))
    sd_f = {}   # forecast-layer residual SD of full-July ERA5 given first-k days
    for k in ks:
        X = [(mm(y, 6), sum(daily[(y, 7)][d] for d in range(1, k + 1)) / k) for y in FIT_YEARS]
        Y = [mm(y, 7) for y in FIT_YEARS]
        sd_f[k] = ols2_sd(X, Y)

    # NOAA-space forecast sigma: translation slope * forecast-layer sd, in quadrature with translation sigma
    before = {k: math.hypot(bL * sd_f[k], sdL) for k in ks}
    rhos = [0.4, 0.6, 0.8, 1.0]
    after = {rho: {k: math.hypot(bL * sd_f[k] * math.sqrt(1 - rho**2), sdL) for k in ks} for rho in rhos}

    # "days-left shift": at each k, find the earliest k' whose BEFORE sigma the ENS-AFTER already beats
    def days_saved(rho, k):
        target = after[rho][k]
        for kk in ks:
            if before[kk] <= target:
                return kk - k   # BEFORE needs kk days to reach what AFTER has at day k
        return ks[-1] - k

    print("July forecast sigma (NOAA space) vs day-of-month k")
    print("%3s  %8s | %s" % ("k", "BEFORE", "  ".join("rho=%.1f" % r for r in rhos)))
    for k in (2, 5, 10, 15, 20, 26):
        row = "  ".join("%6.4f" % after[r][k] for r in rhos)
        print("%3d  %8.4f | %s   [rho=0.6 saves ~%d days]" % (k, before[k], row, days_saved(0.6, k)))
    print("\nfloor (perfect foresight rho=1) = translation sigma = %.4f at every k" % sdL)
    print("Read: at day k, ENS with partial-skill rho gives the sigma the observed-only")
    print("model only reaches ~'saves' days later. That left-shift is the whole value of ECMWF.")

    # ---- figure ----
    plt.figure(figsize=(9, 5.2))
    plt.plot(ks, [before[k] for k in ks], "o-", lw=2.4, color="#c0392b", label="BEFORE (observed days only)")
    for rho, c in zip([0.4, 0.6, 0.8], ["#e67e22", "#2980b9", "#27ae60"]):
        plt.plot(ks, [after[rho][k] for k in ks], "--", lw=1.8, color=c, label=f"AFTER +ENS (rho={rho})")
    plt.axhline(sdL, color="#7f8c8d", ls=":", lw=1.5, label=f"floor = translation sigma ({sdL:.3f})")
    plt.xlabel("day of July observed (k)"); plt.ylabel("NOAA July forecast sigma")
    plt.title("Variance collapse: before vs after adding an ENS remaining-days predictor")
    plt.legend(fontsize=9); plt.grid(alpha=0.3); plt.tight_layout()
    out = os.path.join(HERE, "variance_collapse.png")
    plt.savefig(out, dpi=130)
    print("\nwrote", out)

    # self-check
    assert all(sd_f[k] >= sd_f[k + 1] - 1e-6 for k in ks[:-1]), "sd_f should shrink as k grows"
    assert all(after[0.6][k] < before[k] for k in ks), "ENS must reduce sigma"
    assert abs(after[1.0][ks[0]] - sdL) < 1e-9, "perfect foresight floor must equal translation sigma"
    print("self-check: OK")


if __name__ == "__main__":
    main()
