#!/usr/bin/env python3
"""
Dashboard data updater for the Hottest-Month model.
Fetches ERA5 daily + NOAA monthly + Kalshi markets, recomputes the full model,
writes data.js consumed by Dashboard.html.

The target month is whatever calendar month it is now, so the pipeline rolls
over on its own at midnight on the 1st. Override to re-check a settled month:

Usage:
  python3 update_data.py                    # one refresh, current month
  python3 update_data.py --month 2026-07    # pin a month
  python3 update_data.py --loop 900         # refresh forever every 900s
"""
import calendar, json, math, os, subprocess, sys, time
from datetime import datetime, timezone
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ERA5_URL = "https://sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_2t_global.csv"
NOAA_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/1/{m}/1850-{y}/data.json"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
MON = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']

def target_month():
    """(year, month) of the market we are pricing; --month YYYY-MM overrides."""
    if '--month' in sys.argv:
        y, m = sys.argv[sys.argv.index('--month') + 1].split('-')
        return int(y), int(m)
    now = datetime.now()
    return now.year, now.month

def prev_of(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)

def get(url):
    # curl: uses system certs (python.org builds often lack them) and is battle-tested here
    r = subprocess.run(['curl', '-sL', '--max-time', '90', '-A', 'Mozilla/5.0', url],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}")
    return r.stdout

def get_json_file(url, path):
    """Download to a temp file first; only replace target if it parses as JSON."""
    try:
        raw = get(url)
        json.loads(raw)
        open(path, 'wb').write(raw)
    except Exception as e:
        print(f"fetch/validate failed for {path}: {e} (keeping cached)")

def ols(pairs):
    n = len(pairs); sx = sum(x for x,_ in pairs); sy = sum(y for _,y in pairs)
    sxx = sum(x*x for x,_ in pairs); sxy = sum(x*y for x,y in pairs)
    b = (n*sxy - sx*sy)/(n*sxx - sx*sx); a = (sy - b*sx)/n
    sd = math.sqrt(sum((y-a-b*x)**2 for x,y in pairs)/(n-2))
    return a, b, sd

def ols2(X, Y):
    n=len(Y); x1=[x[0] for x in X]; x2=[x[1] for x in X]
    A=[[n,sum(x1),sum(x2)],[sum(x1),sum(a*a for a in x1),sum(a*b for a,b in zip(x1,x2))],
       [sum(x2),sum(a*b for a,b in zip(x1,x2)),sum(a*a for a in x2)]]
    v=[sum(Y),sum(a*y for a,y in zip(x1,Y)),sum(a*y for a,y in zip(x2,Y))]
    for i in range(3):
        for j in range(i+1,3):
            f=A[j][i]/A[i][i]
            for k2 in range(3): A[j][k2]-=f*A[i][k2]
            v[j]-=f*v[i]
    c=[0.0]*3
    for i in (2,1,0): c[i]=(v[i]-sum(A[i][k2]*c[k2] for k2 in range(i+1,3)))/A[i][i]
    sd=math.sqrt(sum((y-c[0]-c[1]*a-c[2]*b)**2 for (a,b),y in zip(X,Y))/(n-3))
    return c, sd

def stale(path, hours=6):
    return not os.path.exists(path) or (time.time() - os.path.getmtime(path)) > hours*3600

def refresh_once():
    YR, TM = target_month()
    PY, PM = prev_of(YR, TM)
    ND = calendar.monthrange(YR, TM)[1]
    FIT_YEARS = list(range(1990, YR))
    cur_key, prev_key = MON[TM-1], MON[PM-1]

    # ---- ERA5 (re-fetch only if >6h old; it updates daily) ----
    csv_path = os.path.join(HERE, 'era5_daily.csv')
    if stale(csv_path):
        try:
            raw = get(ERA5_URL)
            # sanity: complete file reaches the current year and is over 1MB
            if len(raw) > 1_000_000 and str(datetime.now().year).encode() in raw[-6000:]:
                open(csv_path,'wb').write(raw)
            else:
                print("ERA5 download looked truncated -> keeping cached file")
        except Exception as e: print("ERA5 fetch failed, using cached:", e)
    daily = defaultdict(dict)
    for line in open(csv_path):
        if line.startswith('#'): continue
        p = line.strip().split(',')
        if len(p) >= 4 and p[0][:4].isdigit():
            y, m, d = map(int, p[0].split('-'))
            daily[(y,m)][d] = float(p[3])
    mm = lambda y,m: sum(daily[(y,m)].values())/len(daily[(y,m)]) if daily.get((y,m)) else None
    # ERA5 mean of month M in fit-year y, and of its preceding month (Dec rolls back a year)
    pm_of = lambda y: mm(*prev_of(y, TM))

    # ---- NOAA ----
    noaa = {}
    for m in (PM, TM):
        p = os.path.join(HERE, f'noaa_m{m}.json')
        if stale(p): get_json_file(NOAA_URL.format(m=m, y=YR), p)
        noaa[m] = {int(k): v['departure'] for k,v in json.load(open(p))['data'].items()}

    # ---- model ----
    aP,bP,sdP = ols([(mm(y,PM), noaa[PM][y]) for y in FIT_YEARS])
    aC,bC,sdC = ols([(mm(y,TM), noaa[TM][y]) for y in FIT_YEARS])
    prev26 = mm(PY, PM)
    obs = daily.get((YR,TM), {})
    k = len(obs)

    # observed-only view. k=0 (first days of a month, before ERA5's 2-day lag catches
    # up) has no first-k predictor at all, so fall back to the prev-month-only fit
    # expressed in the same 3-coefficient shape -> every downstream consumer is
    # unchanged and nothing divides by zero.
    if k >= 1:
        firstk = sum(obs[d] for d in range(1,k+1))/k
        X = [(pm_of(y), sum(daily[(y,TM)][d] for d in range(1,k+1))/k) for y in FIT_YEARS]
        c, sdf = ols2(X, [mm(y,TM) for y in FIT_YEARS])
    else:
        firstk = 0.0
        a0, b0, sdf = ols([(pm_of(y), mm(y,TM)) for y in FIT_YEARS])
        c = [a0, b0, 0.0]
    curmodel = {'c': c, 'sd_f': sdf, 'k': k, 'firstk': firstk}

    # ---- ECMWF IFS augmentation (Open-Meteo JSON; see fetch_forecast.py) ----
    ens = None
    try:
        import fetch_forecast as ff
        gm = ff.load_cached() or ff.fetch_global_mean()
        anom, off, nov = ff.to_anomaly(gm)
        pre = f'{YR}-{TM:02d}-'
        fdays = {int(t[8:]): v for t, v in anom.items()
                 if t.startswith(pre) and int(t[8:]) > k}
        k_eff = max(fdays) if fdays else 0
        # need contiguous coverage days k+1..k_eff for the first-k_eff regression to apply
        if fdays and len(fdays) == k_eff - k:
            pseudo = (sum(obs[d] for d in range(1, k+1)) + sum(fdays.values())) / k_eff
            X = [(pm_of(y), sum(daily[(y,TM)][d] for d in range(1, k_eff+1))/k_eff) for y in FIT_YEARS]
            ce, sdfe = ols2(X, [mm(y,TM) for y in FIT_YEARS])
            mu_era = ce[0] + ce[1]*prev26 + ce[2]*pseudo
            # ponytail: assumed IFS global-mean daily error 0.015*lead^0.7 C (cap 0.15),
            # 0.6 correlation mix across leads. MEASURED (leakage-free, Jul 2026, n=251):
            # the anchored IFS runs COLD, +0.09 at lead 1 rising to +0.31 at lead 12,
            # 219/251 days positive. That is one month of one regime, so it is not
            # applied here -- but it means mu_era5 skews low, not symmetric. Replace
            # this knob with a forecast_log-fitted skill curve once a 2nd month exists.
            errsum = sum(min(0.015*max(d-k,1)**0.7, 0.15) for d in fdays)
            sd_fe = math.hypot(sdfe, 0.6*errsum/ND)
            rm = [None]*ND            # projected running mean (obs + forecast), for the chart
            cum = sum(obs[d] for d in range(1, k+1))
            if k: rm[k-1] = round(cum/k, 4)
            for dd in range(k+1, k_eff+1):
                cum += fdays[dd]
                rm[dd-1] = round(cum/dd, 4)
            ens = {'k_eff': k_eff, 'n_fcst': len(fdays), 'anchor_offset': round(off,4),
                   'c2': round(ce[2],4), 'pseudo_mean': round(pseudo,4), 'mu_era5': round(mu_era,4),
                   'sd_f': round(sd_fe,4), 'sd_f_hist_only': round(sdfe,4),
                   'fc_rem_mean': round(sum(fdays.values())/len(fdays), 4),
                   'runmean_fcst': rm}
    except Exception as e:
        print("ENS augmentation skipped:", e)

    # ---- 51-member ENS result (July Calibration/ens_spread.py), if fresh (<24h) ----
    ens51 = None
    try:
        cal = os.path.join(HERE, 'July Calibration')
        js = sorted(f for f in os.listdir(cal) if f.startswith('ens_spread_ecmwf_ifs025_'))
        if js:
            p = os.path.join(cal, js[-1])
            if time.time() - os.path.getmtime(p) < 24*3600:
                e5 = json.load(open(p))
                mem = e5.get('member_month_mean_era5', [])
                noaa_blk = e5.get('noaa', {})
                # strict: a file without an explicit matching month is a pre-rollover
                # July artifact, and serving it as this month's P(YES) is exactly the
                # silent-wrong-market failure this guard exists to stop.
                if mem and noaa_blk and e5.get('month') == TM and e5.get('year') == YR:
                    ens51 = {'p_yes_pct': noaa_blk['p_yes_pct'],
                             'n_members': e5['n_members'], 'k_obs': e5['k_obs'],
                             'members_central_breach': noaa_blk['members_central_breach'],
                             'median_era5': sorted(mem)[len(mem)//2],
                             'pulled_at': e5['pulled_at']}
    except Exception as e:
        print("ens51 read skipped:", e)

    collapse = []
    for kk in [x for x in (2,5,10,15,20,26,ND) if x <= ND]:
        X = [(pm_of(y), sum(daily[(y,TM)][d] for d in range(1,kk+1))/kk) for y in FIT_YEARS]
        _, s = ols2(X, [mm(y,TM) for y in FIT_YEARS])
        collapse.append({'k': kk, 'sd_noaa': math.hypot(bC*s, sdC)})

    # audit bias: this year's prints so far vs their own per-month translation
    biases = []
    for m in range(1, 13):
        if (YR, m) not in daily or len(daily[(YR,m)]) < calendar.monthrange(YR,m)[1]: continue
        p = os.path.join(HERE, f'noaa_m{m}.json')
        if stale(p, hours=24*7): get_json_file(NOAA_URL.format(m=m, y=YR), p)
        if not os.path.exists(p): continue
        s = {int(kk): v['departure'] for kk,v in json.load(open(p))['data'].items()}
        if YR not in s: continue
        a_,b_,_ = ols([(mm(y,m), s[y]) for y in FIT_YEARS])
        biases.append(s[YR] - (a_ + b_*mm(YR,m)))
    bias = sum(biases)/len(biases) if biases else 0.0

    # tracking arrays (running means)
    def run_mean(y, m):
        ds = daily.get((y,m), {}); out=[]; c2=0.0
        for d in range(1, 32):
            if d not in ds: break
            c2 += ds[d]; out.append(round(c2/d, 4))
        return out

    # comparison years: the NOAA record holder and the ERA5 record holder for this month
    rec_noaa_y = max((v,y) for y,v in noaa[TM].items() if y < YR)[1]
    rec_era5_y = max((mm(y,TM), y) for y in FIT_YEARS)[1]
    notes = {}
    for ry, note in ((rec_noaa_y,'NOAA record yr'), (rec_era5_y,'ERA5 record yr')):
        notes[ry] = f'{notes[ry]} + {note}' if ry in notes else note
    analog = [{'year': ry, 'series': run_mean(ry, TM), 'note': note} for ry, note in notes.items()]

    # ---- Kalshi ----
    kal = {}
    for tag, tk in ((prev_key.upper(), f'KXHMONTH-{PY%100:02d}{prev_key.upper()}'),
                    (cur_key.upper(),  f'KXHMONTH-{YR%100:02d}{cur_key.upper()}')):
        try:
            mkt = json.loads(get(f"{KALSHI}/markets/{tk}"))['market']
            cd  = json.loads(get(f"{KALSHI}/series/KXHMONTH/markets/{tk}/candlesticks?start_ts=1743465600&end_ts={int(time.time())+86400}&period_interval=1440"))
            candles = [[datetime.fromtimestamp(x['end_period_ts'], tz=timezone.utc).strftime('%b %d'),
                        float(x['price']['close_dollars'])*100 if x['price'].get('close_dollars') else None,
                        float(x.get('volume_fp') or 0)] for x in cd['candlesticks']]
            kal[tag] = {'ticker': tk, 'last': float(mkt['last_price_dollars'])*100,
                        'yes_bid': float(mkt['yes_bid_dollars'])*100, 'yes_ask': float(mkt['yes_ask_dollars'])*100,
                        'no_bid': float(mkt['no_bid_dollars'])*100, 'no_ask': float(mkt['no_ask_dollars'])*100,
                        'volume': float(mkt['volume_fp']), 'oi': float(mkt['open_interest_fp']),
                        'status': mkt['status'], 'close_time': mkt.get('close_time'),
                        'expected_expiration': mkt.get('expected_expiration_time'),
                        'candles': [x for x in candles if x[1] is not None]}
        except Exception as e:
            print(f"Kalshi {tk} fetch failed (keeping previous if any):", e)

    data = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'era5_latest_day': '{}-{:02d}-{:02d}'.format(*max((y,m,d) for (y,m),ds in daily.items() for d in ds)),
        'model': {
            'cur': cur_key, 'prev': prev_key, 'year': YR, 'ndays': ND,
            'cur_label': calendar.month_name[TM], 'prev_label': calendar.month_name[PM],
            prev_key: {'a': aP, 'b': bP, 'sd': sdP, 'era26': prev26,
                       'record': max(v for y,v in noaa[PM].items() if y < PY)},
            cur_key: {'a': aC, 'b': bC, 'sd': sdC, 'era26': mm(YR,TM) if k == ND else None,
                      'record': max(v for y,v in noaa[TM].items() if y<YR),
                      'fc': curmodel, 'ens': ens, 'ens51': ens51},
            'bias': bias, 'collapse': collapse,
            'scatter_prev': [[mm(y,PM), noaa[PM][y], y] for y in FIT_YEARS],
            'scatter_cur': [[mm(y,TM), noaa[TM][y], y] for y in FIT_YEARS],
        },
        'tracking': {'cur': run_mean(YR,TM), 'prev': run_mean(PY,PM), 'analog': analog},
        'noaa_recent': {'prev': {y: noaa[PM][y] for y in range(2015,YR+1) if y in noaa[PM]},
                        'cur':  {y: noaa[TM][y] for y in range(2015,YR+1) if y in noaa[TM]}},
        'kalshi': kal,
    }
    out = os.path.join(HERE, 'data.js')
    prev = {}
    if os.path.exists(out):   # keep last-good kalshi if this fetch failed
        try:
            prev = json.loads(open(out).read().split('=',1)[1].rstrip(';\n'))
            if not kal and prev.get('kalshi'): data['kalshi'] = prev['kalshi']
        except Exception: pass
    open(out,'w').write("window.HM_DATA = " + json.dumps(data) + ";\n")
    print(f"[{data['generated_at']}] data.js written | target {cur_key.upper()} {YR} k={k} "
          f"| ERA5 through {data['era5_latest_day']} | kalshi: {list(data['kalshi'])}")

if __name__ == '__main__':
    if '--loop' in sys.argv:
        n = int(sys.argv[sys.argv.index('--loop')+1])
        while True:
            try: refresh_once()
            except Exception as e: print("refresh failed:", e)
            time.sleep(n)
    else:
        refresh_once()
