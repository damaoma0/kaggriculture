"""Skeptic re-check (1/3) of the sem4 gap analysis: pairing, ledgers, LEADER control, collapse, headline gaps.

Independent of gap_analysis.py / lead_sem4.py: reads only the raw per-(arm, game) JSONs, worlds.json and the leader
semantics files (data/leader_semantics/<team>/<ep>.json.gz meta.final_cash). One process, no games.
"""
import gzip
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
OURS = ARMS[1:]


def tci(x):
    x = np.asarray(x, float)
    n = len(x)
    m = x.mean()
    h = stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / math.sqrt(n)
    return m, m - h, m + h


RNG = np.random.default_rng(7)


def bci(x, nb=10000):
    x = np.asarray(x, float)
    idx = RNG.integers(0, len(x), size=(nb, len(x)))
    ms = x[idx].mean(axis=1)
    return np.percentile(ms, 2.5), np.percentile(ms, 97.5)


def fmt(x):
    m, lo, hi = tci(x)
    bl, bh = bci(x)
    return f'{m:+9,.0f}  t[{lo:+,.0f}..{hi:+,.0f}]  b[{bl:+,.0f}..{bh:+,.0f}]'


W = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))
worlds = {w['episode']: w for w in W['worlds']}
R = {}
bad_files = []
for a in ARMS:
    R[a] = {}
    for f in sorted((OUT / a).glob('*.json')):
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception as ex:  # noqa: BLE001
            bad_files.append((a, f.name, repr(ex)))
            continue
        R[a][r['episode']] = r
print('files per arm:', {a: len(R[a]) for a in ARMS}, 'unreadable:', bad_files)

# ---------------------------------------------------------------- pairing
sets = {a: set(R[a]) for a in ARMS}
common = sorted(set(worlds).intersection(*sets.values()))
print('worlds.json n =', len(worlds), '| common to all arms =', len(common),
      '| arms missing a world:', {a: sorted(set(worlds) - sets[a]) for a in ARMS if set(worlds) - sets[a]},
      '| extra:', {a: sorted(sets[a] - set(worlds)) for a in ARMS if sets[a] - set(worlds)})
problems = Counter()
for e in common:
    w = worlds[e]
    for a in ARMS:
        r = R[a][e]
        if r['game'] != w['game'] or r['team'] != w['team'] or r['seat'] != w['seat']:
            problems['id/seat mismatch'] += 1
        if list(r['statuses']) != ['DONE', 'DONE']:
            problems[f'status {a} {r["statuses"]}'] += 1
        if r['target'] != w['leader_final'] or r['target_opp'] != w['opp_final_recorded']:
            problems[f'target mismatch {a}'] += 1
        if r['arm'] != a:
            problems[f'arm label {a}'] += 1
        if abs(r['gap'] - (r['target'] - r['final'])) > 1e-6 or abs(r['ratio'] - r['final'] / r['target']) > 1e-9:
            problems[f'stored gap/ratio inconsistent {a}'] += 1
print('pairing / status problems:', dict(problems) or 'none')
print('teams:', Counter(worlds[e]['team'] for e in common))
print('seats:', Counter(worlds[e]['seat'] for e in common))

# ---------------------------------------------------------------- ledger identity
led_bad = []
for a in ARMS:
    for e in common:
        t = R[a][e]['totals']
        calc = 3000 + sum(t['rev'].values()) - sum(t['spend'].values()) - t['wages'] - t['land_spend']
        if abs(calc - R[a][e]['final']) > 0.5:
            led_bad.append((a, e, calc, R[a][e]['final']))
print('ledger identity failures (final = 3000 + rev - spend - wages - land):', len(led_bad), led_bad[:5])
# daily cash series ends at final?  (day 29 cash is day-start; just report the day-29 cash vs final spread)

# ---------------------------------------------------------------- LEADER control vs the raw semantics files
ctl_bad = []
for e in common:
    w = worlds[e]
    m = json.load(gzip.open(ROOT / w['semantics']))['meta']
    s = w['seat']
    lf, of = m['final_cash'][s], m['final_cash'][1 - s]
    r = R['LEADER'][e]
    if round(r['final']) != round(lf) or round(r['opp_final']) != round(of) or m['episode'] != e:
        ctl_bad.append((e, r['final'], lf, r['opp_final'], of))
    if round(lf) != round(w['leader_final']) or round(of) != round(w['opp_final_recorded']):
        ctl_bad.append(('worlds.json vs semantics', e))
print(f'LEADER arm = recorded leader AND opponent cash (semantics meta.final_cash): {len(common) - len(ctl_bad)}/{len(common)}',
      ctl_bad[:5])

# ---------------------------------------------------------------- collapse
print('\nreplayed-opponent final / recorded (per arm): worlds < 0.8, 0.8..0.95, > 1.05')
coll = {}
for a in ARMS:
    rat = {e: R[a][e]['opp_final'] / R[a][e]['target_opp'] for e in common}
    lo = sorted(e for e in common if rat[e] < 0.8)
    mid = sorted((e, round(rat[e], 3)) for e in common if 0.8 <= rat[e] < 0.95)
    hi = sorted((e, round(rat[e], 3)) for e in common if rat[e] > 1.05)
    flag = sorted(e for e in common if R[a][e]['opp_collapse'])
    coll[a] = set(lo)
    print(f'  {a:6s} <0.8: {lo}  flag==mine: {flag == lo}  | 0.8-0.95: {mid} | >1.05: {hi}')
known = sorted(e for e in common if worlds[e]['flags'])
union = sorted(set().union(*coll.values()) | set(known))
clean = [e for e in common if e not in union]
print('known-collapse flags:', known, '| union:', union, '| clean n =', len(clean))
for e in union:
    print('   ', e, worlds[e]['team'], {a: round(R[a][e]['opp_final'] / R[a][e]['target_opp'], 3) for a in ARMS})

# ---------------------------------------------------------------- headline
fin = {a: {e: R[a][e]['final'] for e in common} for a in ARMS}
print('\nLeader mean final all %.0f  clean %.0f' % (np.mean([fin['LEADER'][e] for e in common]),
                                                    np.mean([fin['LEADER'][e] for e in clean])))
print('arm   mean final   gap all (t / boot CI)                         ratio  ahead | gap clean (t / boot)                          ratio')
for a in OURS:
    g = [fin['LEADER'][e] - fin[a][e] for e in common]
    gc = [fin['LEADER'][e] - fin[a][e] for e in clean]
    rt = np.mean([fin[a][e] / fin['LEADER'][e] for e in common])
    rtc = np.mean([fin[a][e] / fin['LEADER'][e] for e in clean])
    ahead = [e for e in common if fin[a][e] > fin['LEADER'][e]]
    print(f'{a:5s} {np.mean([fin[a][e] for e in common]):10,.0f}  {fmt(g)}  {rt:.3f}  {len(ahead)} | {fmt(gc)}  {rtc:.3f}'
          f'   ahead-in-union: {[e for e in ahead if e in union]}')
    # ratio of means (alternative definition)
    print(f'        ratio of means all {np.mean([fin[a][e] for e in common]) / np.mean([fin["LEADER"][e] for e in common]):.3f}'
          f'  median gap {np.median(g):,.0f}  Wilcoxon p {stats.wilcoxon(g).pvalue:.2g}')

# ---------------------------------------------------------------- paired steps
print('\npaired steps (second - first; positive = second arm ahead)')
for a, b in (('LEADER', 'T'), ('LEADER', 'T0'), ('T0', 'T'), ('T', 'S'), ('S0', 'S'), ('T', 'S0'), ('S', 'D'),
             ('D', 'Dp'), ('LEADER', 'Dp')):
    d = [fin[b][e] - fin[a][e] for e in common]
    dc = [fin[b][e] - fin[a][e] for e in clean]
    print(f'  {a:>6s} -> {b:3s}: all {fmt(d)} W={sum(x > 0 for x in d):2d} | clean {fmt(dc)} W={sum(x > 0 for x in dc):2d}')

# per team T - T0 and per-team gaps
teams = sorted({worlds[e]['team'] for e in common})
print('\nT - T0 per team:', {t: tuple(round(v) for v in tci([fin['T'][e] - fin['T0'][e] for e in common if worlds[e]['team'] == t])) for t in teams})
for a in OURS:
    row = []
    for t in teams:
        es = [e for e in common if worlds[e]['team'] == t]
        m, lo, hi = tci([fin['LEADER'][e] - fin[a][e] for e in es])
        cl = [e for e in es if e in clean]
        row.append(f'{t} {m:+,.0f} ({lo:+,.0f}..{hi:+,.0f}) clean {np.mean([fin["LEADER"][e] - fin[a][e] for e in cl]):+,.0f} [{len(cl)}]')
    print(f'  {a:4s}', ' | '.join(row))
print('leader final by team:', {t: round(np.mean([fin['LEADER'][e] for e in common if worlds[e]['team'] == t])) for t in teams})

# ---------------------------------------------------------------- land purchase days vs the leader
print('\nland purchase day (arm vs leader): worlds where any quadrant is bought on a different day / not bought')
for a in OURS:
    diff = Counter()
    for e in common:
        Ld = {q: d for q, d, *_ in R['LEADER'][e]['land']}
        Xd = {q: d for q, d, *_ in R[a][e]['land']}
        for q in ('NE', 'SW', 'SE'):
            if q not in Xd:
                diff[f'{q} missing'] += 1
            elif Xd[q] != Ld.get(q):
                diff[f'{q} {Xd[q] - Ld[q]:+d}d'] += 1
    print(f'  {a:4s}', dict(sorted(diff.items())))
# hand-days
for a in ARMS:
    hd = np.mean([sum(dd['hands'] for dd in R[a][e]['days']) for e in common])
    thd = np.mean([sum(dd['target_hands'] for dd in R[a][e]['days']) for e in common])
    print(f'  hand-days {a:6s} {hd:.1f}  (target_hands {thd:.1f})')
