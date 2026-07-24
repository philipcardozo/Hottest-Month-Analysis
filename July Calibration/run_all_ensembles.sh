#!/bin/bash
# sequential 4-family run; generous pauses to respect the minutely API quota
cd "/Users/felipecardozo/Desktop/Stats/Hottest Month/July Calibration"
for m in ecmwf_ifs025 gfs025 icon_seamless gem_global; do
  echo "===== $m ====="
  python3 ens_spread.py "$m" 2>&1 | grep -v "retry"
  sleep 75
done
echo "ALL FOUR ENSEMBLES DONE"
