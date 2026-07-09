#!/usr/bin/env python3
"""
Dashboard data updater for the Hottest-Month model.
Fetches ERA5 daily + NOAA monthly + Kalshi markets, recomputes the full model,
writes data.js consumed by Dashboard.html.

Usage:
  python3 update_data.py              # one refresh
  python3 update_data.py --loop 900   # refresh forever every 900s (24/7 mode)
"""
import json, math, os, subprocess, sys, time
from datetime import datetime, timezone
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ERA5_URL = "https://sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_2t_global.csv"
NOAA_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/1/{m}/1850-2026/data.json"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
FIT_YEARS = list(range(1990, 2026))

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

    # ---- NOAA ----
    noaa = {}
    for m in (6,7):
        p = os.path.join(HERE, f'noaa_m{m}.json')
        if stale(p): get_json_file(NOAA_URL.format(m=m), p)
        noaa[m] = {int(k): v['departure'] for k,v in json.load(open(p))['data'].items()}

    # ---- model ----
    aJ,bJ,sdJ = ols([(mm(y,6), noaa[6][y]) for y in FIT_YEARS])
    aL,bL,sdL = ols([(mm(y,7), noaa[7][y]) for y in FIT_YEARS])
    jun26 = mm(2026,6)
    k = len(daily.get((2026,7), {}))
    firstk_26 = sum(daily[(2026,7)][d] for d in range(1,k+1))/k if k else None
    julmodel = None
    if k >= 1:
        X = [(mm(y,6), sum(daily[(y,7)][d] for d in range(1,k+1))/k) for y in FIT_YEARS]
        c, sdf = ols2(X, [mm(y,7) for y in FIT_YEARS])
        julmodel = {'c': c, 'sd_f': sdf, 'k': k, 'firstk': firstk_26}
    collapse = []
    for kk in (2,5,10,15,20,26,31):
        X = [(mm(y,6), sum(daily[(y,7)][d] for d in range(1,kk+1))/kk) for y in FIT_YEARS]
        _, s = ols2(X, [mm(y,7) for y in FIT_YEARS])
        collapse.append({'k': kk, 'sd_noaa': math.hypot(bL*s, sdL)})
    # audit bias (Jan-May 2026)
    biases = []
    for m in range(1,6):
        p = os.path.join(HERE, f'noaa_m{m}.json')
        if stale(p, hours=24*7): get_json_file(NOAA_URL.format(m=m), p)
        if not os.path.exists(p): continue
        s = {int(kk): v['departure'] for kk,v in json.load(open(p))['data'].items()}
        a_,b_,_ = ols([(mm(y,m), s[y]) for y in FIT_YEARS])
        if 2026 in s: biases.append(s[2026] - (a_ + b_*mm(2026,m)))
    bias = sum(biases)/len(biases) if biases else 0.0

    # tracking arrays (running means)
    def run_mean(y, m):
        ds = daily.get((y,m), {}); out=[]; c2=0.0
        for d in range(1, 32):
            if d not in ds: break
            c2 += ds[d]; out.append(round(c2/d, 4))
        return out

    # ---- Kalshi ----
    kal = {}
    for tag, tk in (('JUN','KXHMONTH-26JUN'), ('JUL','KXHMONTH-26JUL')):
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
                        'status': mkt['status'], 'candles': [x for x in candles if x[1] is not None]}
        except Exception as e:
            print(f"Kalshi {tk} fetch failed (keeping previous if any):", e)

    data = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'era5_latest_day': '{}-{:02d}-{:02d}'.format(*max((y,m,d) for (y,m),ds in daily.items() for d in ds)),
        'model': {
            'jun': {'a': aJ, 'b': bJ, 'sd': sdJ, 'era26': jun26,
                    'record': max(v for y,v in noaa[6].items() if y<2026)},
            'jul': {'a': aL, 'b': bL, 'sd': sdL, 'record': max(v for y,v in noaa[7].items() if y<2026),
                    'fc': julmodel},
            'bias': bias, 'collapse': collapse,
            'scatter_jun': [[mm(y,6), noaa[6][y], y] for y in FIT_YEARS],
        },
        'tracking': {'jul26': run_mean(2026,7), 'jul24': run_mean(2024,7), 'jul23': run_mean(2023,7),
                     'jun26': run_mean(2026,6), 'jun24': run_mean(2024,6)},
        'noaa_recent': {'june': {y: noaa[6][y] for y in range(2015,2027) if y in noaa[6]},
                        'july': {y: noaa[7][y] for y in range(2015,2027) if y in noaa[7]}},
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
    print(f"[{data['generated_at']}] data.js written | ERA5 through {data['era5_latest_day']} | kalshi: {list(data['kalshi'])}")

if __name__ == '__main__':
    if '--loop' in sys.argv:
        n = int(sys.argv[sys.argv.index('--loop')+1])
        while True:
            try: refresh_once()
            except Exception as e: print("refresh failed:", e)
            time.sleep(n)
    else:
        refresh_once()
