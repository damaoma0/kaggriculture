"""Report on leader upkeep skips from results/fresh/upkeep_20260925/skips/*.json.gz (scripts/upkeep_skips.py).

usage: upkeep_skip_report.py [d0=12] [d1=29] > results/fresh/upkeep_20260925/skips_report.txt
Module job classes: RP = required and production-affecting (units lost if skipped today > 0, optimal from tomorrow),
RZ = required with no unit at stake (scheduling / visit-saving), OH = optional harvest (can wait), CF = collect
fertilizer. A job is DONE when the leader performed the same command on that tile that day (effective).
Realized output loss of an asset-day: L0 = V0(d) - harvested(d) - V0(d+1) (no new fertilizer), LF the same with free
fertilizer; both telescope to the asset's life loss vs its hour-0 potential.
"""
import gzip
import json
import statistics as stt
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / 'results/fresh/upkeep_20260925/skips'
TEAM = {'16732748': 'DSM', '16770421': 'Vadim', '16730612': 'UMG'}
BASE = {'WHEAT': 25, 'CARROT': 35, 'TOMATO': 60, 'STRAWBERRY': 120, 'MELON': 250, 'EGG': 50, 'MILK': 160, 'WOOL': 200,
        'FERTILIZER': 100}
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
ANIM = set(PROD)


def pbucket(r):
    if r is None:
        return '?'
    for lim, name in ((0.25, '<.25'), (0.5, '.25-.5'), (0.8, '.5-.8'), (1.2, '.8-1.2')):
        if r < lim:
            return name
    return '>1.2'


def plbucket(n):
    return str(n) if n < 3 else '3+'


def dbucket(n):
    return '1-2' if n <= 2 else '3-4' if n <= 4 else '5-6' if n <= 6 else '7+'


def dwin(d):
    return '12-17' if d <= 17 else '18-23' if d <= 23 else '24-29'


def plant_b(n):
    return '0' if n == 0 else '1-5' if n <= 5 else '6-15' if n <= 15 else '16+'


def main():
    args = dict(a.split('=') for a in sys.argv[1:] if '=' in a)
    d0, d1 = int(args.get('d0', 12)), int(args.get('d1', 29))
    files = sorted(SK.glob('*.json.gz'))
    ngames = Counter()
    job = defaultdict(lambda: [0, 0, 0.0, 0.0])      # key -> [n, done, units lost (skipped), value lost (skipped)]
    ctx = defaultdict(lambda: [0, 0])                 # (feature, bucket, class) -> [n RP, skipped]
    extra = Counter()
    extra_n_assetdays = Counter()
    chk = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])   # key -> [asset-days, module units of skips, L0, LF, value]
    day_rows = []
    eol = defaultdict(list)
    fert_extra_gain = Counter()
    team_skip = defaultdict(lambda: [0, 0, 0.0])
    bad = 0
    for f in files:
        try:
            r = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        except Exception:
            bad += 1
            continue
        if not r.get('cash_match'):
            bad += 1
            continue
        tm = TEAM.get(r['team'], r['team'])
        ngames[tm] += 1
        ngames['all'] += 1
        days = {dd['d']: dd for dd in r['days']}
        umax = max(dd['units'] for dd in r['days'])
        per_day = defaultdict(lambda: Counter())
        for a in r['assets']:
            d = a['d']
            if not (d0 <= d <= d1):
                continue
            kind = a['k']
            grp = kind if kind in ANIM else 'crop:' + kind
            prod = PROD.get(kind, kind)
            pr = (a['p'] / BASE[prod]) if a.get('p') else None
            ops = Counter(o[0] for o in a['ops'])
            dd = days[d]
            listed = set()
            skipped_units = 0.0
            skipped_value = 0.0
            skipped_cmds = []
            for cmd, val, u, jk, dl, opt, held in a['mj']:
                listed.add(cmd)
                if opt:
                    cls = 'OH'
                elif cmd == 'COLLECT_FERTILIZER':
                    cls = 'CF'
                elif u > 0:
                    cls = 'RP'
                else:
                    cls = 'RZ'
                done = ops.get(cmd, 0) > 0
                for key in ((grp, cmd, jk, cls), ('ALL', cmd, '*', cls), ('ALL', '*', '*', cls)):
                    job[key][0] += 1
                    job[key][1] += int(done)
                    if not done:
                        job[key][2] += u
                        job[key][3] += max(0.0, val)
                if cls == 'RP':
                    per_day[d]['rp'] += 1
                    per_day[d]['rp_skip'] += int(not done)
                    team_skip[tm][0] += 1
                    team_skip[tm][1] += int(not done)
                    if not done:
                        team_skip[tm][2] += max(0.0, val)
                        per_day[d]['rp_skip_value'] += max(0.0, val)
                        skipped_units += u
                        skipped_value += max(0.0, val)
                        skipped_cmds.append(cmd)
                    cc = f'{grp}:{cmd}'
                    for feat, b in (('price/base', pbucket(pr)), ('prods_left', plbucket(a['pl'])),
                                    ('shed_dist', dbucket(a['dist'])), ('days', dwin(d)),
                                    ('plantings that day', plant_b(dd.get('planted', 0))),
                                    ('units at game max', 'yes' if dd['units'] >= umax else 'no')):
                        ctx[(cc, feat, b)][0] += 1
                        ctx[(cc, feat, b)][1] += int(not done)
            for cmd, n in ops.items():
                if cmd in ('WATER', 'FEED', 'CARE', 'FERTILIZE', 'HARVEST', 'COLLECT_FERTILIZER') and cmd not in listed:
                    extra[(grp, cmd)] += 1
                    if cmd == 'FERTILIZE':
                        fert_extra_gain[grp] += (a.get('VF_1', 0) or 0) - (a['VF'] - a['hv'])   # not a clean gain; see L check
            # realized-loss check (asset-days alive at hour 0 of d, day < 29)
            if d < 29 and 'V0_1' in a:
                L0 = a['V0'] - a['hv'] - a['V0_1']
                LF = a['VF'] - a['hv'] - a['VF_1']
                key = (grp, 'skip:' + ('+'.join(sorted(set(skipped_cmds))) if skipped_cmds else 'none'))
                c = chk[key]
                c[0] += 1
                c[1] += skipped_units
                c[2] += L0
                c[3] += LF
                c[4] += skipped_value
                # end of life
                dug = ops.get('DIG', 0) > 0
                if not a.get('alive1', 1) and not (kind in ('WHEAT', 'CARROT', 'MELON') and a['hv'] > 0):
                    why = 'dug live' if dug else ('escaped (unfed)' if kind in ANIM else 'died (unwatered) or decayed')
                    eol[(grp, why)].append(dict(V0=a['V0'], pl=a['pl'], pr=pr, d=d, age=d - a['s'], hv=a['hv']))
        for d, c in per_day.items():
            dd = days[d]
            day_rows.append(dict(tm=tm, g=r['game'], d=d, rp=c['rp'], skip=c['rp_skip'], skip_value=c['rp_skip_value'],
                                 units=dd['units'], planted=dd.get('planted', 0), ops=dd['ops'], moves=dd['moves'],
                                 passes=dd['passes'], noeff=sum(dd['noeff'].values())))
    G = ngames['all']
    print(f'Leader upkeep skips, days {d0}-{d1}: {G} games ({dict(ngames)}), {bad} files unreadable / cash mismatch')
    print()
    print('== A. Module jobs vs what the leader did (per game; RP = production-affecting, RZ = no unit at stake, OH = optional harvest, CF = collect fertilizer)')
    print('| asset | cmd | job kind | class | jobs / game | done by leader | skipped / game | units lost / game (module) | coins lost / game (module, net of inputs) |')
    print('|---|---|---|---|---|---|---|---|---|')
    for key in sorted(job, key=lambda k: (k[0] != 'ALL', k[0], k[3], k[1], k[2])):
        n, dn, u, v = job[key]
        if n < G:          # rarer than once a game: skip the row
            continue
        print(f'| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {n / G:.1f} | {dn / n:.0%} | {(n - dn) / G:.1f} | {u / G:.1f} | {v / G:,.0f} |')
    print()
    print('== A2. RP skips by team: skip rate, module value of the skipped jobs per game')
    for tm, (n, s, v) in sorted(team_skip.items()):
        print(f'  {tm}: {n / ngames[tm]:.0f} RP jobs / game, skipped {s / n:.1%} ({s / ngames[tm]:.1f} / game), module value {v / ngames[tm]:,.0f} / game')
    print()
    print('== B. Leader ops NOT on the module list (per game)')
    print('| asset | cmd | per game |')
    print('|---|---|---|')
    for (grp, cmd), n in sorted(extra.items(), key=lambda kv: -kv[1]):
        if n >= G:
            print(f'| {grp} | {cmd} | {n / G:.1f} |')
    print()
    print('== C. RP skip rate by context (rows with >= 200 jobs)')
    feats = ['price/base', 'prods_left', 'shed_dist', 'days', 'plantings that day', 'units at game max']
    ccs = sorted({k[0] for k in ctx})
    for cc in ccs:
        tot = sum(ctx[k][0] for k in ctx if k[0] == cc and k[1] == 'days')
        if tot < 3 * G:
            continue
        print(f'  {cc} ({tot / G:.1f} RP jobs / game)')
        for feat in feats:
            cells = [(k[2], ctx[k]) for k in ctx if k[0] == cc and k[1] == feat]
            cells.sort()
            print('    %-20s ' % feat + '  '.join(f'{b}: {s / n:.0%} (n={n})' for b, (n, s) in cells if n >= 200))
    print()
    print('== D. Realized output loss per asset-day (days < 29) vs the module\'s estimate for the skipped jobs')
    print('| asset | skipped RP jobs that day | asset-days / game | module units lost / asset-day | realized L0 / asset-day | realized LF / asset-day |')
    print('|---|---|---|---|---|---|')
    for key in sorted(chk, key=lambda k: (k[0], -chk[k][0])):
        c = chk[key]
        if c[0] < G:
            continue
        print(f'| {key[0]} | {key[1]} | {c[0] / G:.1f} | {c[1] / c[0]:.2f} | {c[2] / c[0]:.2f} | {c[3] / c[0]:.2f} |')
    print()
    print('== E. End of life: assets that end without a completed harvest (dug live / neglected)')
    print('| asset | how | per game | median day | median age | median units forfeited (V0) | median productions left | median price/base |')
    print('|---|---|---|---|---|---|---|---|')
    for key in sorted(eol, key=lambda k: -len(eol[k])):
        L = eol[key]
        if len(L) < G / 3:
            continue
        prs = [x['pr'] for x in L if x['pr'] is not None]
        print(f"| {key[0]} | {key[1]} | {len(L) / G:.2f} | {stt.median(x['d'] for x in L):.0f} | {stt.median(x['age'] for x in L):.0f} | "
              f"{stt.median(x['V0'] for x in L):.0f} | {stt.median(x['pl'] for x in L):.0f} | {(stt.median(prs) if prs else float('nan')):.2f} |")
    print()
    print('== F. What the labour did on high- vs low-skip days (terciles of skipped RP jobs within each game; days 12-23)')
    rows = [x for x in day_rows if x['d'] <= 23]
    byg = defaultdict(list)
    for x in rows:
        byg[x['g']].append(x)
    groups = defaultdict(list)
    for g, L in byg.items():
        L.sort(key=lambda x: (x['skip'], x['d']))
        k = len(L)
        for i, x in enumerate(L):
            groups['low' if i < k / 3 else 'mid' if i < 2 * k / 3 else 'high'].append(x)
    cols = ['PLANT', 'HARVEST', 'WATER', 'FERTILIZE', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'PICKUP', 'DIG']
    print('| skip tercile | day-games | RP jobs | skipped | skipped value | units | plantings | ' + ' | '.join(cols) + ' | moves | PASS | no-effect |')
    print('|---|---|---|---|---|---|---|' + '---|' * len(cols) + '---|---|---|')
    for gname in ('low', 'mid', 'high'):
        L = groups[gname]
        m = lambda f: stt.mean(f(x) for x in L)
        print(f"| {gname} | {len(L)} | {m(lambda x: x['rp']):.1f} | {m(lambda x: x['skip']):.1f} | {m(lambda x: x['skip_value']):,.0f} | {m(lambda x: x['units']):.1f} | {m(lambda x: x['planted']):.1f} | "
              + ' | '.join(f"{m(lambda x, c=c: x['ops'].get(c, 0)):.1f}" for c in cols)
              + f" | {m(lambda x: x['moves']):.0f} | {m(lambda x: x['passes']):.1f} | {m(lambda x: x['noeff']):.1f} |")


if __name__ == '__main__':
    main()
