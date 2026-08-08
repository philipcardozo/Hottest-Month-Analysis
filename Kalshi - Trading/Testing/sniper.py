#!/usr/bin/env python3
"""
NOAA release detector + decision engine for KXHMONTH.  READ-ONLY: there is no
order path in this file and no Kalshi credentials are loaded.  Kalshi market
data is public, so this whole tree runs without a key -- a directory with no
credentials cannot place an order no matter what bug it contains.

What it proves:
    T0  the NOAAGlobalTemp file for the target month appears (404 -> 200)
    T1  we have parsed it, passed the gates, and know YES/NO
    T2  the Kalshi book first reprices
  edge = T2 - T1.  That is the whole thesis, measured instead of argued.

Run:  python3 sniper.py --watch          # live, polls until the file lands
      python3 sniper.py --replay         # decide against the on-disk baseline
      python3 sniper.py --market         # one-shot book snapshot
"""
import argparse, datetime as dt, hashlib, http.client, json, os, ssl, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))       # …/Hottest Month
LOG = os.path.join(HERE, 'audit.log')

NCEI = 'www.ncei.noaa.gov'
TS_DIR = '/data/noaa-global-surface-temperature/v6.1/access/timeseries/'
GRID_DIR = '/data/noaa-global-surface-temperature/v6.1/access/gridded/'
ASC = TS_DIR + 'aravg.mon.land_ocean.90S.90N.v6.1.0.{ym}.asc'
KALSHI = 'api.elections.kalshi.com'
CAG = ('/access/monitoring/climate-at-a-glance/global/time-series/'
       'globe/land_ocean/1/{m}/1850-{y}/data.json')

TARGET_Y, TARGET_M = 2026, 7
TICKER = 'KXHMONTH-26JUL'

# gate G2: July archive anomalies have run 0.55-0.61 recently; band is deliberately
# wide enough to admit a genuine surprise and narrow enough to reject -999 / 0.0
PLAUSIBLE = (0.40, 0.80)
# gate G6: model central estimate in CAG space, and how far we let reality differ
MODEL_MU, MODEL_SIGMA = 1.1660, 0.0360
SIGMA_LIMIT = 4.0

_CTX = None


def ctx():
    """python.org's CA bundle is broken on this Mac -- certifi, not the default."""
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            _CTX = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
    return _CTX


def audit(event, **kw):
    """Append-only.  Never rewritten, never truncated."""
    rec = {'ts': dt.datetime.now(dt.timezone.utc).isoformat(), 'event': event}
    rec.update(kw)
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    return rec


class Conn:
    """One kept-warm TLS connection.  Cold connect to NCEI has been measured at
    64.8 s on a bad morning; the whole point is to never pay it in the window."""

    def __init__(self, host):
        self.host = host
        self.c = None

    def _dial(self):
        self.c = http.client.HTTPSConnection(self.host, 443, context=ctx(), timeout=15)

    def req(self, method, path):
        for attempt in (1, 2):
            try:
                if self.c is None:
                    self._dial()
                self.c.request(method, path, headers={
                    'User-Agent': 'Mozilla/5.0', 'Connection': 'keep-alive'})
                r = self.c.getresponse()
                return r.status, r.read()
            except Exception:
                try:
                    self.c.close()
                except Exception:
                    pass
                self.c = None
                if attempt == 2:
                    return None, b''
        return None, b''


# ---------------------------------------------------------------- decision ---

def parse_asc(text):
    """year, month -> anomaly (1971-2000 base).  Rejects the -999 no-data rows."""
    out = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 3:
            try:
                y, m, v = int(p[0]), int(p[1]), float(p[2])
            except ValueError:
                continue
            if v > -900:
                out[(y, m)] = v
    return out


def load_cag(refresh=False, conn=None):
    """CAG departures (1901-2000 base) per month.

    A stale cache silently breaks the offset fit: the repo's month-10 and -11
    JSONs were 31 days old and 45 of their rows had since been revised, which
    emptied the feasible interval and would have refused a good trade.  So the
    test tree keeps its OWN copy and refreshes it rather than trusting the repo.
    """
    cag = {}
    own = os.path.join(HERE, 'cag')
    os.makedirs(own, exist_ok=True)
    if refresh:
        c = conn or Conn(NCEI)
        for m in range(1, 13):
            st, body = c.req('GET', CAG.format(m=m, y=TARGET_Y))
            if st == 200 and len(body) > 1000:
                try:
                    json.loads(body)
                    open(os.path.join(own, f'm{m}.json'), 'wb').write(body)
                except Exception:
                    pass
        audit('cag_refresh', files=len(os.listdir(own)))
    for m in range(1, 13):
        for p in (os.path.join(own, f'm{m}.json'), os.path.join(REPO, f'noaa_m{m}.json')):
            if os.path.exists(p):
                try:
                    cag[m] = {int(y): v['departure']
                              for y, v in json.load(open(p))['data'].items()}
                    break
                except Exception:
                    continue
    return cag


def offset_interval(arc, cag_m, month, exclude_year=None, exclude=()):
    """Widest offset that reproduces EVERY published 2dp CAG print for `month`.

    round(a+off, 2) == c  <=>  c-0.005 <= a+off < c+0.005.
    Kept for diagnostics; fit_offset() is what the engine uses.
    """
    lo, hi = -9.0, 9.0
    n = 0
    for y, c in cag_m.items():
        if y == exclude_year or y in exclude or (y, month) not in arc:
            continue
        a = arc[(y, month)]
        lo = max(lo, c - 0.005 - a)
        hi = min(hi, c + 0.005 - a)
        n += 1
    return lo, hi, n


def fit_offset(arc, cag_m, month, exclude_year=None, exclude=()):
    """Robust offset fit.

    A strict all-years interval is too brittle: a handful of historical years sit
    exactly on a 2dp rounding boundary, where NOAA's internal full-precision value
    and the 6dp number in the .asc round to different cents.  Measured: months 4,
    8 and 12 each have 1-3 such years, which empties a strict interval even though
    the mapping is otherwise perfect.

    So: take the median offset, identify the years it cannot reproduce, then
    re-derive a tight interval from the years that agree.  Returns the estimate,
    its half-width, and the outlier count -- the caller gates on the last two.
    """
    pts = [(y, cag_m[y], arc[(y, month)]) for y in cag_m
           if y != exclude_year and y not in exclude and (y, month) in arc]
    if len(pts) < 50:
        return None, None, len(pts), len(pts)

    # exact first: if one offset reproduces every published print, that is the
    # answer and it is far tighter than any robust estimator.
    lo = max(c - 0.005 - a for _, c, a in pts)
    hi = min(c + 0.005 - a for _, c, a in pts)
    if lo < hi:
        return (lo + hi) / 2, (hi - lo) / 2, len(pts), 0

    # otherwise a few years sit on a rounding boundary; drop them and re-derive.
    offs = sorted(c - a for _, c, a in pts)
    med = offs[len(offs) // 2]
    good = [(y, c, a) for y, c, a in pts if round(a + med, 2) == round(c, 2)]
    bad = len(pts) - len(good)
    if not good:
        return None, None, len(pts), bad
    lo = max(c - 0.005 - a for _, c, a in good)
    hi = min(c + 0.005 - a for _, c, a in good)
    if lo >= hi:
        return med, None, len(pts), bad
    return (lo + hi) / 2, (hi - lo) / 2, len(pts), bad


def boundary_distance(value_cag):
    """Distance from the nearest 2dp rounding boundary, in CAG units.

    A value at .xx5 is one offset-wobble away from printing a different cent, and
    one cent is the entire contract.  ~12% of historical July years sit within
    0.0005 of a boundary, so this is not a hypothetical.
    """
    cents = value_cag * 100.0
    return abs((cents - int(cents)) - (0.5 if cents >= 0 else -0.5)) / 100.0


def decide(arc, cag, year=TARGET_Y, month=TARGET_M, baseline=None,
           plausible=PLAUSIBLE, sigma_limit=SIGMA_LIMIT, min_rows=2000,
           check_boundary=True, max_outlier_rate=0.02):
    """Pure. Returns a verdict dict.  Every failure mode returns trade=False.

    The threshold is never computed.  We derive both PRINTED values from the
    same bytes and compare them -- so `record + 0.005` arithmetic cannot be got
    wrong, ties fail correctly via `>`, and a revised record is picked up
    automatically because the record is recomputed from this same fetch.

    The keyword gates are widened by the corpus test so the comparison logic can
    be scored on all 2100+ historical decisions; live callers use the defaults.
    """
    v = {'target': f'{year}-{month:02d}', 'trade': False, 'gates': {}, 'reason': None}

    def fail(gate, reason):
        v['gates'][gate] = False
        v['reason'] = reason
        return v

    # G1 presence
    if (year, month) not in arc:
        return fail('G1_present', f'no row for {year}-{month:02d}')
    raw = arc[(year, month)]
    v['archive_value'] = raw
    v['gates']['G1_present'] = True

    # G2 plausibility band
    if not (plausible[0] <= raw <= plausible[1]):
        return fail('G2_plausible', f'{raw} outside {plausible}')
    v['gates']['G2_plausible'] = True

    # G3 structure
    if len(arc) < min_rows:
        return fail('G3_structure', f'only {len(arc)} rows parsed')
    v['rows'] = len(arc)
    v['gates']['G3_structure'] = True

    # G5 first: find revised years BEFORE fitting, so a revision cannot poison
    # the offset.  This is the scenario with the largest payoff -- the record
    # moving -- and a naive fit would refuse exactly there.
    revised = set()
    if baseline:
        changed = [k for k, b in baseline.items()
                   if k in arc and k != (year, month) and abs(arc[k] - b) > 1e-6]
        revised = {k[0] for k in changed if k[1] == month}
        v['revised_rows'] = len(changed)
        v['revised_target_month'] = sorted(revised)
        v['gates']['G5_series'] = 'REVISED_TARGET_MONTH' if revised else True
    else:
        v['gates']['G5_series'] = 'no baseline'

    # G4 offset self-consistency -- an independent proof we understand the file.
    # Revised years are excluded from the fit, then the offset is applied to them.
    cag_m = cag.get(month) or {}
    off, half, n, bad = fit_offset(arc, cag_m, month, exclude_year=year, exclude=revised)
    if off is None or half is None:
        return fail('G4_offset', f'offset unfittable (n={n}, outliers={bad})')
    if n < 50:
        return fail('G4_offset', f'only {n} reference years')
    if bad / n > max_outlier_rate:
        return fail('G4_offset', f'{bad}/{n} years unreproducible ({bad/n:.1%})')
    if half > 0.0005:
        return fail('G4_offset', f'offset half-width too wide: {half:.6f}')
    v.update(offset=off, offset_halfwidth=half, offset_n=n, offset_outliers=bad)
    v['gates']['G4_offset'] = True

    # the decision itself: two printed values out of one fetch
    new_cag = raw + off
    new_print = round(new_cag, 2)
    prior = [(y, round(arc[(y, month)] + off, 2))
             for y in range(1850, year) if (y, month) in arc]
    if not prior:
        return fail('G1_present', 'no prior years to compare')
    record_year, record_print = max(prior, key=lambda t: (t[1], t[0]))
    v['new_cag_value'] = new_cag
    v['new_print'] = new_print
    v['record_print'] = record_print
    v['record_year'] = record_year
    v['margin_cents'] = round((new_print - record_print) * 100)

    # G6 model circuit breaker -- catches a catastrophic upstream error, not a
    # forecast miss.  4 sigma is deliberately loose.
    z = abs(new_print - MODEL_MU) / MODEL_SIGMA
    v['model_z'] = z
    if sigma_limit is not None and z > sigma_limit:
        return fail('G6_model', f'print {new_print} is {z:.1f} sigma from model {MODEL_MU}')
    v['gates']['G6_model'] = True

    # G8 verdict stability under offset uncertainty.
    #
    # The offset is an estimate with a known half-width, so re-run the ENTIRE
    # decision at both ends of that interval.  Refuse only if the answer differs
    # -- which is the question that actually matters.  An earlier version refused
    # whenever the value sat near any 2dp boundary; that blocked June 2026, whose
    # print was 9 cents clear of the record and could not have flipped.
    dist = boundary_distance(new_cag)
    v['boundary_distance'] = dist
    verdicts = {}
    for tag, o in (('lo', off - (half or 0)), ('mid', off), ('hi', off + (half or 0))):
        np_ = round(raw + o, 2)
        rp_ = max(round(arc[(y, month)] + o, 2)
                  for y in range(1850, year) if (y, month) in arc)
        verdicts[tag] = ('YES' if np_ > rp_ else 'NO', np_, rp_)
    v['verdict_under_offset_bounds'] = {k: w[0] for k, w in verdicts.items()}
    if check_boundary and len({w[0] for w in verdicts.values()}) > 1:
        return fail('G8_stability',
                    f'offset uncertainty +/-{half:.6f} flips the verdict '
                    f'({verdicts["lo"][0]} .. {verdicts["hi"][0]}); '
                    f'value {new_cag:.6f} sits {dist:.6f} from a 2dp boundary')
    v['gates']['G8_stability'] = True

    v['verdict'] = 'YES' if new_print > record_print else 'NO'
    v['tie'] = (new_print == record_print)
    v['trade'] = True
    v['reason'] = 'all gates passed'
    return v


def cross_check_cag(body, verdict):
    """G7: the settlement-authoritative source must agree on the printed value."""
    try:
        d = json.loads(body)['data']
    except Exception as e:
        return {'G7_cag': 'unavailable', 'detail': str(e)}
    key = str(TARGET_Y)
    if key not in d:
        return {'G7_cag': 'not_published_yet'}
    cag_print = round(float(d[key]['departure']), 2)
    return {'G7_cag': cag_print == verdict.get('new_print'),
            'cag_print': cag_print, 'ours': verdict.get('new_print')}


# ------------------------------------------------------------------ market ---

def book(conn):
    st, b = conn.req('GET', f'/trade-api/v2/markets/{TICKER}/orderbook?depth=100')
    if st != 200:
        return None
    try:
        ob = json.loads(b)['orderbook_fp']
    except Exception:
        return None
    yes = [(float(p), float(s)) for p, s in (ob.get('yes_dollars') or [])]
    no = [(float(p), float(s)) for p, s in (ob.get('no_dollars') or [])]
    return {
        'yes_bid': max((p for p, _ in yes), default=None),
        'yes_ask': (1 - max((p for p, _ in no), default=1)) if no else None,
        'yes_depth': sum(s for _, s in yes),
        'no_depth': sum(s for _, s in no),
    }


# ------------------------------------------------------------------- watch ---

def watch(interval=0.25, ym=None, max_hours=30):
    ym = ym or f'{TARGET_Y}{TARGET_M:02d}'
    asc_path = ASC.format(ym=ym)
    baseline = None
    bp = os.path.join(HERE, 'baseline.asc')
    if os.path.exists(bp):
        baseline = parse_asc(open(bp).read())

    ncei, kal = Conn(NCEI), Conn(KALSHI)
    print(f'watching {asc_path}')
    print(f'  cadence {interval}s · baseline {len(baseline or {})} rows · '
          f'ticker {TICKER} · NO ORDER PATH IN THIS PROCESS')
    audit('watch_start', target=ym, interval=interval,
          baseline_rows=len(baseline or {}), ticker=TICKER)

    # pre-warm both connections now so the window never pays a cold handshake
    for c, m, p in ((ncei, 'HEAD', asc_path), (kal, 'GET', '/trade-api/v2/exchange/status')):
        t = time.perf_counter()
        st, _ = c.req(m, p)
        print(f'  warmed {c.host}: {st} in {(time.perf_counter()-t)*1000:.0f} ms')

    b0 = book(kal)
    print(f'  book at start: {b0}')
    audit('book_start', **(b0 or {}))

    polls, t_start, last_beat = 0, time.time(), 0.0
    grid_seen = None
    while time.time() - t_start < max_hours * 3600:
        polls += 1
        t_poll = time.perf_counter()
        st, _ = ncei.req('HEAD', asc_path)

        if st == 200:
            t0 = time.time()
            audit('DETECT', source='asc_head', http=st, polls=polls)
            print(f'\n*** {dt.datetime.now():%H:%M:%S.%f} FILE IS LIVE after {polls} polls ***')

            st2, body = ncei.req('GET', asc_path)
            t_fetch = time.time()
            sha = hashlib.sha256(body).hexdigest()
            open(os.path.join(HERE, f'{ym}.asc'), 'wb').write(body)
            audit('FETCH', http=st2, bytes=len(body), sha256=sha,
                  fetch_ms=round((t_fetch - t0) * 1000))

            arc = parse_asc(body.decode('utf-8', 'replace'))
            v = decide(arc, load_cag(), baseline=baseline)
            t1 = time.time()
            v['decide_ms'] = round((t1 - t0) * 1000)
            v['sha256'] = sha
            audit('DECIDE', **v)

            print(json.dumps(v, indent=2, default=str))
            print('\n  T1-T0 = %s ms  (detect -> verdict)' % v['decide_ms'])

            # G7 cross-check, best effort -- the archive is expected to lead CAG
            sc, cb = ncei.req('GET', CAG.format(m=TARGET_M, y=TARGET_Y))
            g7 = cross_check_cag(cb, v) if sc == 200 else {'G7_cag': f'http {sc}'}
            print(f'  G7 cross-check: {g7}')
            audit('CROSSCHECK', **g7)

            # now the number that decides the thesis: when does the book move?
            print('\n  watching for the market to reprice…')
            for _ in range(2400):                       # ~20 min at 0.5s
                b = book(kal)
                if b and b0 and (b['yes_bid'] != b0['yes_bid'] or b['yes_ask'] != b0['yes_ask']):
                    t2 = time.time()
                    print(f'  *** MARKET MOVED at +{t2-t0:.1f}s : {b0} -> {b}')
                    audit('MARKET_MOVED', lag_s=round(t2 - t0, 2), before=b0, after=b)
                    print(f'\n  EDGE = {t2-t1:.1f} s between our verdict and the reprice')
                    return v
                time.sleep(0.5)
            audit('MARKET_STILL_STALE', after_s=1200)
            print('  market still had not moved after 20 min')
            return v

        # cheap secondary detector: the gridded .nc was written 34 s BEFORE the
        # .asc in June, but its filename embeds a build timestamp we cannot guess
        if polls % 20 == 0:
            gs, gb = ncei.req('GET', GRID_DIR)
            if gs == 200:
                import re
                got = sorted(set(re.findall(rb'_e(\d{6})_c([0-9T]+)', gb)))
                if got and got != grid_seen:
                    if grid_seen is not None and got[-1][0].decode() == ym:
                        print(f'\n*** GRIDDED FILE FOR {ym} APPEARED FIRST: {got[-1]}')
                        audit('DETECT', source='gridded_dir', file=str(got[-1]))
                    grid_seen = got

        if time.time() - last_beat > 300:
            last_beat = time.time()
            el = (time.time() - t_start) / 3600
            print(f'  [{dt.datetime.now():%H:%M:%S}] {polls} polls · {el:.1f} h · '
                  f'last {(time.perf_counter()-t_poll)*1000:.0f} ms · http {st}')
            audit('heartbeat', polls=polls, hours=round(el, 2), http=st)

        time.sleep(interval)

    audit('watch_timeout', polls=polls)
    print('watch window expired without a release')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--replay', action='store_true')
    ap.add_argument('--market', action='store_true')
    ap.add_argument('--interval', type=float, default=0.25)
    ap.add_argument('--month', default=None, help='YYYYMM override, e.g. 202606')
    a = ap.parse_args()

    if a.replay:
        # decide against a file we already have, as if it had just landed
        path = os.path.join(HERE, f'{a.month}.asc') if a.month else os.path.join(HERE, 'baseline.asc')
        arc = parse_asc(open(path).read())
        y, m = (int(a.month[:4]), int(a.month[4:])) if a.month else (2026, 6)
        v = decide(arc, load_cag(), year=y, month=m)
        print(json.dumps(v, indent=2, default=str))
    elif a.market:
        print(json.dumps(book(Conn(KALSHI)), indent=2))
    elif a.watch:
        watch(interval=a.interval, ym=a.month)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
