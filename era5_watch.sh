#!/bin/bash
# era5_watch.sh [YYYY-MM-DD]  — poll for one ERA5 day; on arrival print the value,
# what we had forecast for it, and where the month now stands.
# Re-runnable on an already-published day: the loop exits immediately and just reports.
URL="https://sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_2t_global.csv"
TARGET="${1:-$(date -v-2d +%Y-%m-%d)}"
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/era5_release_times.csv"

if [ -z "$TARGET" ]; then echo "no target date"; exit 1; fi
caffeinate -i -w $$ &
echo "watching for $TARGET ..."

while true; do
    ROW=$(curl -fsSL -r -3000 "$URL" | grep "^${TARGET},")
    if [ -n "$ROW" ]; then
        LM=$(curl -sI "$URL" | grep -i '^last-modified' | cut -d' ' -f2-)
        PUB=$(date -jf "%a, %d %b %Y %H:%M:%S %Z" "$LM" "+%Y-%m-%d %H:%M:%S %Z" 2>/dev/null)
        VAL=$(echo "$ROW" | cut -d, -f4)
        echo "OUT: $ROW"
        echo "     anomaly $VAL | published $PUB"
        grep -q "^$TARGET," "$LOG" 2>/dev/null || echo "$TARGET,$VAL,$PUB" >> "$LOG"
        say "report is out. $VAL"

        # --- context: forecast-vs-actual + month standing (never fatal) ---
        python3 - "$TARGET" "$VAL" "$DIR" <<'PY' || echo "     (context unavailable)"
import sys, os, json, calendar
target, val, DIR = sys.argv[1], float(sys.argv[2]), sys.argv[3]
sys.path.insert(0, DIR)
import daily_check as dc                      # reuse the anchoring that feeds track_log

daily, clim = dc.era5()
daily[target] = val                           # just-published day isn't in the csv yet
mon, ndays = target[:7], calendar.monthrange(int(target[:4]), int(target[5:7]))[1]

# what we forecast for this day, using the latest pull made BEFORE it (leakage-free)
logdir = os.path.join(DIR, 'forecast_log')
pulls = sorted(f for f in os.listdir(logdir) if f.startswith('fcst_'))
prior = [f for f in pulls if f'{f[5:9]}-{f[9:11]}-{f[11:13]}' < target]
if prior:
    path = os.path.join(logdir, prior[-1])
    iso = f'{prior[-1][5:9]}-{prior[-1][9:11]}-{prior[-1][11:13]}'
    known = min(iso, max(d for d in daily if d < target))
    anom = dc.pull_anom(path, daily, clim, known)
    if target in anom:
        gm = json.load(open(path))['global_mean_C']
        raw, corr = gm[target] - clim[target[5:]], anom[target]
        print('     forecast for this day: ECMWF raw %+.3f | model (bias-corr) %+.3f | dev %+.3f'
              % (raw, corr, val - corr))

days = sorted(d for d in daily if d.startswith(mon))
s, k = sum(daily[d] for d in days), len(days)
prev = f'  (was {(s-val)/(k-1):+.4f} over {k-1})' if k > 1 else ''
print('     month to date:        %+.4f over %d days%s' % (s/k, k, prev))

# projection + record bar, if this month has fitted translation coefficients
try:
    M = json.loads(open(os.path.join(DIR, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))['model']
    cf = M[['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'][int(target[5:7])-1]]
    a, b, rec = cf['a'], cf['b'], cf['record']
    thr = (rec + 0.005 - a) / b                       # print must round UP past the record
    if k < ndays:
        latest = json.load(open(os.path.join(logdir, pulls[-1])))['global_mean_C']
        fa = dc.pull_anom(os.path.join(logdir, pulls[-1]), daily, clim, max(daily))
        rem = [fa[f'{mon}-{d:02d}'] for d in range(1, ndays+1) if f'{mon}-{d:02d}' in fa
               and f'{mon}-{d:02d}' > target]
        if rem:
            full = (s + sum(rem) + (sum(rem)/len(rem)) * (ndays - k - len(rem))) / ndays
            print('     projected full month: %+.4f  ->  NOAA %.3f  (record %.2f)' % (full, a + b*full, rec))
        print('     to WIN (print %.2f):   needs %+.4f/day over the remaining %d days'
              % (rec + 0.01, (thr*ndays - s)/(ndays - k), ndays - k))
    else:
        print('     month complete:       %+.4f  ->  NOAA %.3f  (record %.2f)' % (s/k, a + b*(s/k), rec))
except (KeyError, IndexError, ValueError, FileNotFoundError):
    pass
PY
        break
    fi
    echo "[$(date +%H:%M:%S)] not yet"
    sleep 60
done
