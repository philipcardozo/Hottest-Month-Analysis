#!/bin/bash
# Poll NOAA CAG June series until the 2026 print appears (or ~4h timeout), then refresh data.
# ponytail: throwaway event-day script; the generalized release-sniper supersedes it.
URL="https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/1/6/1850-2026/data.json"
DIR="/Users/felipecardozo/Desktop/Stats/Hottest Month"
for i in $(seq 1 240); do
  v=$(curl -sL --max-time 30 -A "Mozilla/5.0" "$URL" | python3 -c "import json,sys
try: print(json.load(sys.stdin)['data'].get('2026',{}).get('departure',''))
except Exception: print('')" 2>/dev/null)
  if [ -n "$v" ]; then
    echo "JUNE 2026 PRINT DETECTED: $v (poll $i, $(date -u '+%H:%M UTC'))"
    cd "$DIR" && rm -f noaa_m6.json && python3 update_data.py
    exit 0
  fi
  sleep 60
done
echo "TIMEOUT: June 2026 print not seen after 4h"
exit 1
