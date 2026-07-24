#!/bin/bash
# era5_watch.sh [YYYY-MM-DD]  — poll for one ERA5 day, print value + publish time.
URL="https://sites.ecmwf.int/data/climatepulse/data/series/era5_daily_series_2t_global.csv"
TARGET="${1:-$(date -v-2d +%Y-%m-%d)}"
LOG="$(dirname "$0")/era5_release_times.csv"

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
        echo "$TARGET,$VAL,$PUB" >> "$LOG"
        say "report is out. $VAL"
        break
    fi
    echo "[$(date +%H:%M:%S)] not yet"
    sleep 60
done
