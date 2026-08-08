#!/usr/bin/env python3
"""
Corpus + adversarial tests for the decision engine.  No network, no key.

The corpus is free: every (year, month) NOAA has ever published is a labelled
decision with known ground truth.  If decide() does not score 100% on it, the
executor does not ship.

Run: python3 test_sniper.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sniper import parse_asc, load_cag, decide, fit_offset, boundary_distance, HERE

BASE = open(os.path.join(HERE, 'baseline.asc')).read()
ARC = parse_asc(BASE)
CAG = load_cag()
fails = []

# the corpus scores the COMPARISON logic, so the July-specific safety gates are
# widened out of the way; live callers use the strict defaults.
WIDE = dict(plausible=(-10, 10), sigma_limit=None, check_boundary=False,
            max_outlier_rate=0.05)   # live gate stays 0.02; this scores months 4/8 too


def check(name, cond, detail=''):
    if cond:
        print(f'  ok   {name}')
    else:
        print(f'  FAIL {name}  {detail}')
        fails.append(name)


print('== 1. offset fits for every month ==')
for m in range(1, 13):
    off, half, n, bad = fit_offset(ARC, CAG[m], m)
    check(f'month {m:02d} fits (off {off:+.6f} +/-{half:.6f}, {bad}/{n} outliers)',
          off is not None and half is not None and bad / n < 0.05)

print('\n== 2. THE CORPUS: every published (year, month) decision ==')
total = yes_n = tie_n = skipped = 0
for m in range(1, 13):
    cag_m = CAG[m]
    years = sorted(y for y in cag_m if (y, m) in ARC)
    for i, y in enumerate(years):
        if i == 0:
            continue
        truth_new = round(cag_m[y], 2)
        truth_rec = max(round(cag_m[p], 2) for p in years[:i])
        truth = 'YES' if truth_new > truth_rec else 'NO'
        v = decide(ARC, CAG, year=y, month=m, **WIDE)
        if not v.get('trade'):
            skipped += 1
            continue
        total += 1
        yes_n += (truth == 'YES')
        tie_n += (truth_new == truth_rec)
        if v['verdict'] != truth:
            fails.append(f'corpus {y}-{m:02d}')
            if len([f for f in fails if f.startswith('corpus')]) <= 6:
                print(f'  FAIL {y}-{m:02d}: engine {v["verdict"]} '
                      f'({v["new_print"]:.2f} vs {v["record_print"]:.2f}) '
                      f'!= truth {truth} ({truth_new:.2f} vs {truth_rec:.2f})')
n_corpus_fail = len([f for f in fails if f.startswith('corpus')])
print(f'  scored {total} decisions · {yes_n} record-settings · {tie_n} exact ties '
      f'· {skipped} refused by gates')
check(f'corpus {total - n_corpus_fail}/{total} correct', n_corpus_fail == 0)
check('corpus is large enough to mean something', total > 2000, f'only {total}')
check('corpus exercised real ties', tie_n >= 20, f'only {tie_n}')

print('\n== 3. ties must resolve NO (the trap that already cost this project) ==')
tie_seen = 0
for m in range(1, 13):
    cag_m = CAG[m]
    years = sorted(y for y in cag_m if (y, m) in ARC)
    for i, y in enumerate(years):
        if i and round(cag_m[y], 2) == max(round(cag_m[p], 2) for p in years[:i]):
            v = decide(ARC, CAG, year=y, month=m, **WIDE)
            if v.get('trade'):
                tie_seen += 1
                if v['verdict'] != 'NO' or not v['tie']:
                    check(f'tie {y}-{m:02d} -> NO', False, str(v.get('verdict')))
check(f'all {tie_seen} exact ties resolved NO', tie_seen >= 20 and
      not [f for f in fails if f.startswith('tie ')])

print('\n== 4. malformed input must never trade ==')
for name, txt in {
    'empty': '',
    'html_503': '<!DOCTYPE HTML><html><head><title>503</title></head></html>',
    'truncated': '\n'.join(BASE.splitlines()[:40]),
    'all_nodata': '\n'.join(f'{y} 7 -999.000000' for y in range(1850, 2027)),
    'target_missing': '\n'.join(l for l in BASE.splitlines() if not l.startswith('2026  6')),
    'garbage': 'not a data file at all\nnope\n',
    'nul_bytes': BASE[:5000] + '\x00\x00\x00',
}.items():
    v = decide(parse_asc(txt), CAG, year=2026, month=6)
    check(f'{name} -> no trade', not v['trade'], v.get('reason'))

print('\n== 5. implausible values must never trade ==')
for label, val in [('zero', 0.0), ('sentinel', -999.0), ('absurd_high', 5.0),
                   ('absurd_low', -2.0), ('just_outside_band', 0.95)]:
    a = dict(ARC); a[(2026, 6)] = val
    v = decide(a, CAG, year=2026, month=6)
    check(f'{label} ({val}) -> no trade', not v['trade'], v.get('reason'))

print('\n== 6. broken offset (base period moved) must never trade ==')
shifted = {k: (val + 0.25 if k[0] < 2020 else val) for k, val in ARC.items()}
v = decide(shifted, CAG, year=2026, month=6)
check('inconsistent history -> no trade', not v['trade'], v.get('reason'))

print('\n== 7. verdict must be stable under offset uncertainty ==')
off7, half7, _, _ = fit_offset(ARC, CAG[7], 7, exclude_year=2026)
a = dict(ARC)
a[(2026, 7)] = 1.185 - off7            # exactly ON the YES/NO knife edge
v = decide(a, CAG, year=2026, month=7)
check('value on the DECISION boundary -> no trade', not v['trade'], v.get('reason'))
check('  reason cites verdict instability', 'flips the verdict' in (v.get('reason') or ''),
      str(v.get('reason'))[:80])
a[(2026, 7)] = 1.21 - off7             # clear of it
v = decide(a, CAG, year=2026, month=7)
check('value clear of the edge -> trades, YES', v['trade'] and v['verdict'] == 'YES',
      f"{v.get('reason')} {v.get('verdict')}")
a[(2026, 7)] = 1.095 - off7            # near a 2dp boundary but 9 cents from the record
v = decide(a, CAG, year=2026, month=7)
check('near a boundary but verdict cannot flip -> STILL TRADES (NO)',
      v['trade'] and v['verdict'] == 'NO', f"{v.get('reason')} {v.get('verdict')}")

print('\n== 8. record revision is picked up from the same fetch ==')
base = dict(ARC)
a = dict(ARC)
a[(2026, 7)] = ARC[(2024, 7)] - 0.002             # just under the standing record
v = decide(a, CAG, year=2026, month=7, baseline=base)
check('below record -> NO', v.get('verdict') == 'NO',
      f"{v.get('verdict')} / {v.get('reason')}")
a[(2024, 7)] = 0.50                                # NOAA revises the record DOWN
v2 = decide(a, CAG, year=2026, month=7, baseline=base)
check('revision detected', v2.get('gates', {}).get('G5_series') == 'REVISED_TARGET_MONTH',
      str(v2.get('gates', {}).get('G5_series')))
check('same value now WINS after the record moved',
      v2.get('trade') and v2.get('verdict') == 'YES' and v2.get('record_year') != 2024,
      f"trade={v2.get('trade')} verdict={v2.get('verdict')} "
      f"rec_yr={v2.get('record_year')} reason={v2.get('reason')}")

print('\n== 9. live target sanity (July 2026, not yet published) ==')
v = decide(ARC, CAG, year=2026, month=7)
check('July 2026 absent -> no trade', not v['trade'], v.get('reason'))
off, half, n, bad = fit_offset(ARC, CAG[7], 7, exclude_year=2026)
check(f'July offset exact (+{off:.6f} +/-{half:.6f}, n={n}, outliers={bad})',
      bad == 0 and half < 0.0002)
rec = max((round(ARC[(y, 7)] + off, 2), y) for y in range(1850, 2026) if (y, 7) in ARC)
check(f'record reads {rec[0]:.2f} ({rec[1]}) — expect 1.18 (2024)',
      rec[0] == 1.18 and rec[1] == 2024)
need = 1.185 - off
print(f'  -> archive value >= {need:.6f} prints 1.19 (YES); below prints <=1.18 (NO)')
print(f'  -> ambiguous zone (G8 refuses): {need-0.0005:.6f} .. {need+0.0005:.6f}')

print('\n' + '=' * 62)
if fails:
    print(f'FAILED: {len(fails)} check(s)')
    for f in fails[:12]:
        print('   -', f)
    sys.exit(1)
print('ALL CHECKS PASSED')
