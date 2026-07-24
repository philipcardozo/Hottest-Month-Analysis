#!/usr/bin/env python3
"""
Market-side evidence for the July KXHMONTH pricing question.

[1] Settled-month calibration: Apr/May/Jun 2026 all settled NO. What YES premium
    did the market carry at the same point-in-month, and how did it decay?
    (cached candles in ../kalshi_data/ + live June candles in data.js)
[2] July VWAP + today's book: is 21-22c real flow or a stale thin quote?
    Authed READ-ONLY orderbook depth via kalshi_client (prod key, no orders).

Run: python3 market_angles.py
"""
import json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def candles(path):
    d = json.load(open(path))
    out = []
    for x in d['candlesticks']:
        ts = datetime.fromtimestamp(x['end_period_ts'], tz=timezone.utc)
        px = x['price'].get('close_dollars')
        out.append((ts, float(px) * 100 if px else None, float(x.get('volume_fp') or 0)))
    return [(t, p, v) for t, p, v in out if p is not None]


def main():
    print("[1] settled-month YES premium at mid-month (all settled NO):")
    for tag, fn in (('APR', 'candles_KXHMONTH-26APR.json'), ('MAY', 'candles_KXHMONTH-26MAY.json'),
                    ('JUN', 'candles_KXHMONTH-26JUN.json')):
        p = os.path.join(ROOT, 'kalshi_data', fn)
        if not os.path.exists(p):
            continue
        cs = candles(p)
        mon = {'APR': 4, 'MAY': 5, 'JUN': 6}[tag]
        mid = [x for x in cs if x[0].month == mon and 12 <= x[0].day <= 16]
        end = [x for x in cs if x[0].month == mon and x[0].day >= 25]
        mid_px = sum(x[1] for x in mid) / len(mid) if mid else None
        end_px = sum(x[1] for x in end) / len(end) if end else None
        last = cs[-1]
        print("  %s: mid-month(12-16th) YES ~%s | day>=25 YES ~%s | final close %s -> settled NO"
              % (tag,
                 f"{mid_px:.0f}c" if mid_px else "n/a",
                 f"{end_px:.0f}c" if end_px else "n/a",
                 f"{last[1]:.0f}c"))
    dj = json.loads(open(os.path.join(ROOT, 'data.js')).read().split('=', 1)[1].rstrip(';\n'))
    KJ = dj['kalshi'].get('JUN')
    if KJ:
        mid = [c for c in KJ['candles'] if c[0] in ('Jun 13', 'Jun 14', 'Jun 15', 'Jun 16')]
        if mid:
            print("  JUN (live cache): mid-month YES ~%.0fc -> settled NO (print 1.09)"
                  % (sum(c[1] for c in mid) / len(mid)))

    KL = dj['kalshi']['JUL']
    tot_v = sum(c[2] for c in KL['candles'])
    vwap = sum(c[1] * c[2] for c in KL['candles']) / tot_v if tot_v else None
    print("\n[2] JULY market: last %.0fc, YES %.0f/%.0f, vol %.0f, OI %.0f, VWAP %.1fc"
          % (KL['last'], KL['yes_bid'], KL['yes_ask'], KL['volume'], KL['oi'], vwap))
    try:
        import requests
        from kalshi_client import Kalshi, HOSTS
        kc = Kalshi()
        base = HOSTS['prod'] + '/trade-api/v2'
        path = '/markets/KXHMONTH-26JUL/orderbook'
        r = requests.get(base + path, headers=kc._headers('GET', path),
                         params={'depth': 10}, timeout=30)
        ob = r.json().get('orderbook', {})
        for side in ('yes', 'no'):
            lv = ob.get(side) or []
            lv2 = sorted(lv, key=lambda x: -float(x[0]))[:5]
            tot = sum(float(q) for _, q in lv)
            print("  book %s: top levels %s | total resting %.0f contracts"
                  % (side.upper(), [(float(px), float(q)) for px, q in lv2], tot))
    except Exception as e:
        print("  orderbook fetch failed:", e)


if __name__ == '__main__':
    main()
