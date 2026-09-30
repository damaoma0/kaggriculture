"""Reports for the search-dispatch tests (stored results only, no games).

  search_dispatch_report.py lead [--arms SDoff,SDsh,SDa12,SDall] [--base SDoff] [--suffix X] [--out FILE]
      leader worlds (results/fresh/search_dispatch_20260925/lead_worlds/<arm><suffix>/<ep>.json, written by
      scripts/search_dispatch_run.py through lead_sem4.play): shadow check (final, opponent and every day-start cash
      equal to the base), then per arm vs the base: gap to the leader, own / opponent cash, paired difference (t and
      bootstrap 95% CI, better / worse), effective maintenance ops (all days / days 12-23, by type), moves per tile op,
      harvested units, deaths (unwatered plants, escaped animals), decay (rotted plants, units lost to rot), shed-cap
      discards, planner timing / fallbacks (agent_log sd_*) and the harness step times; then the market side (v2):
      revenue vs the base split into volume and price by product, the share of each product sold on the day it was
      harvested (FIFO over the daily ledger), in-day deposits, units carried at midnight, thirsty plants still dry at
      23h, forced hard insertions / idle deliveries (v2 counters), and a per-game table (paired difference, planner
      time, minimum time bank left).
"""
import json
import math
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/fresh/search_dispatch_20260925'
MAINT = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER')
TILE_OPS = MAINT + ('PLANT', 'DIG', 'BUILD_COOP', 'BUILD_PASTURE', 'PLACE_ANIMAL')
T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18,
        13: 2.16, 14: 2.14, 15: 2.13, 16: 2.12, 17: 2.11, 18: 2.10, 19: 2.09, 20: 2.09, 25: 2.06, 30: 2.04, 40: 2.02,
        47: 2.01, 60: 2.00}


def tcrit(df):
    ks = sorted(T975)
    for k in ks:
        if df <= k:
            return T975[k]
    return 1.96


def paired(d, n_boot=10000, seed=7):
    n = len(d)
    if n == 0:
        return dict(n=0)
    m = st.mean(d)
    sd = st.stdev(d) if n > 1 else 0.0
    h = tcrit(n - 1) * sd / math.sqrt(n) if n > 1 else 0.0
    rng = random.Random(seed)
    bs = sorted(st.mean(rng.choices(d, k=n)) for _ in range(n_boot))
    return dict(n=n, mean=m, t_lo=m - h, t_hi=m + h, b_lo=bs[int(0.025 * n_boot)], b_hi=bs[int(0.975 * n_boot) - 1],
                better=sum(1 for x in d if x > 0), worse=sum(1 for x in d if x < 0), same=sum(1 for x in d if x == 0))


def load(arm, suffix=''):
    d = BASE / 'lead_worlds' / f'{arm}{suffix}'
    return {int(f.stem): json.loads(f.read_text(encoding='utf-8')) for f in sorted(d.glob('1*.json'))}


def metrics(r):
    tot = r['totals']
    eff = Counter(tot.get('eff_ops', {}))
    days = r['days']
    m = {}
    m['final'] = r['final']
    m['opp'] = r['opp_final']
    m['gap'] = r['target'] - r['final']
    m['ratio'] = r['ratio']
    m['maint'] = sum(eff.get(k, 0) for k in MAINT)
    m['maint_12_23'] = sum(dd.get('maint', 0) for dd in days[12:24])
    m['tile_ops'] = sum(eff.get(k, 0) for k in TILE_OPS)
    m['moves'] = tot.get('moves', 0)
    m['moves_per_op'] = m['moves'] / max(1, m['tile_ops'])
    for k in MAINT:
        m['op_' + k] = eff.get(k, 0)
    dth = Counter(tot.get('deaths', {}))
    m['unwatered'] = sum(v for k, v in dth.items() if k.startswith('unwatered_'))
    m['escaped'] = sum(v for k, v in dth.items() if k.startswith('escaped_'))
    m['rotted'] = sum(v for k, v in dth.items() if k.startswith('rotted_'))
    m['rot_units'] = sum(v for k, v in dth.items() if k.startswith('rot_units_'))
    m['harvested'] = sum(tot.get('harvested', {}).values())
    m['discards'] = tot.get('discards_total', 0)
    m['passes'] = tot.get('passes', 0)
    m['unit_steps'] = tot.get('unit_steps', 0)
    m['tmax'] = r.get('tmax', 0)
    m['tsum'] = r.get('tsum', 0)
    lg = r.get('agent_log') or {}
    for k in ('sd_plan_ms_max', 'sd_plan_ms_mean', 'sd_plan_ms_p95', 'sd_plan_ms_first_max', 'sd_step_ms_max',
              'sd_step_ms_p95', 'sd_bank_min_remaining', 'sd_fb_unit', 'sd_fb_step', 'sd_errors', 'sd_time_capped',
              'sd_idle_unit', 'sd_planned_unit', 'sd_switch_steps', 'sd_deliv_deferred', 'sd_steps',
              'sd_planned_drop_first', 'sd_planned_drop_first_value', 'sd_dropped_jobs', 'sd_dropped_value',
              'sd_dropped_prod_jobs', 'sd_dropped_prod_value', 'sd_dropped_hard', 'sd_plants_lost',
              'sd_plants_lost_thirst', 'sd_animals_lost', 'sd_shed_arrivals', 'sd_agree', 'sd_agree_n',
              'sd_walk_after_last', 'sd_fb_pickup', 'sd_fb_noop', 'sd_fb_notask', 'sd_pred_wait', 'sd_forced_hard',
              'sd_idle_deliver'):
        m[k] = lg.get(k)
    return m


def fmt(x, nd=0):
    if x is None:
        return '-'
    if isinstance(x, float):
        return f'{x:,.{nd}f}'
    return f'{x:,}'


SALE_P = ('STRAWBERRY', 'MELON', 'MILK', 'WOOL', 'EGG', 'TOMATO', 'CARROT', 'FERTILIZER')


def same_day(r, p):
    """(units sold, units sold on their harvest day) of product p, FIFO over the daily ledger."""
    from collections import deque
    q = deque()
    n = n0 = 0
    for d in range(30):
        dd = r['days'][d]
        h = dd['harv'].get(p, 0)
        if h:
            q.append([d, h])
        s_ = dd['sold'].get(p, 0)
        while s_ > 0 and q:
            k = min(s_, q[0][1])
            n += k
            n0 += k if q[0][0] == d else 0
            q[0][1] -= k
            s_ -= k
            if q[0][1] == 0:
                q.popleft()
    return n, n0


def market_tables(R, base, arms):
    L = ['', '### Market side: revenue vs the base = volume / price (per game), same-day sale share, deliveries']
    B = R[base]
    prods = ('WHEAT',) + SALE_P
    L.append('| arm | ' + ' | '.join(p.lower() for p in prods) + ' | volume | price |')
    L.append('|---|' + '---|' * (len(prods) + 2))
    for a in arms:
        if a == base:
            continue
        common = sorted(set(R[a]) & set(B))
        if not common:
            continue
        n = len(common)
        cells, tv, tp = [], 0.0, 0.0
        for p in prods:
            dv = dp = 0.0
            for e in common:
                ta, tb = R[a][e]['totals'], B[e]['totals']
                ua, ub = ta['sold'].get(p, 0), tb['sold'].get(p, 0)
                pa, pb = ta['avg_price'].get(p, 0) or 0, tb['avg_price'].get(p, 0) or 0
                dv += (ua - ub) * pb
                dp += ua * (pa - pb)
            tv += dv
            tp += dp
            cells.append(f'{dv / n:+,.0f} / {dp / n:+,.0f}')
        L.append(f'| {a} | ' + ' | '.join(cells) + f' | {tv / n:+,.0f} | {tp / n:+,.0f} |')
    L.append('')
    L.append('| arm | ' + ' | '.join(f'{p.lower()} same-day' for p in SALE_P) + ' | in-day deposits (units) | '
             'carried at midnight d12-23 | dry at 23h | unfed unassigned 23h | forced hard | idle deliveries |')
    L.append('|---|' + '---:|' * (len(SALE_P) + 6))
    for a in arms:
        Ra = R[a]
        if not Ra:
            continue
        cells = []
        for p in SALE_P:
            n = n0 = 0
            for r in Ra.values():
                x, y = same_day(r, p)
                n += x
                n0 += y
            cells.append(f'{n0 / max(1, n):.0%}')
        dep = st.mean(sum(r['totals'].get('deposited', {}).get(p, 0) for p in SALE_P) for r in Ra.values())
        cm = st.mean(st.mean(r['days'][d].get('carried_mid') or 0 for d in range(12, 24)) for r in Ra.values())
        lg = lambda k: st.mean((r.get('agent_log') or {}).get(k, 0) or 0 for r in Ra.values())
        L.append(f'| {a} | ' + ' | '.join(cells) + f' | {dep:.1f} | {cm:.1f} | {lg("dying_water_task"):.1f} | '
                 f'{lg("unfed_unassigned"):.1f} | {lg("sd_forced_hard"):.1f} | {lg("sd_idle_deliver"):.1f} |')
    L.append('')
    L.append('### Per game: own cash vs the base, planner time (ms) and minimum time bank left (s)')
    act = [a for a in arms if a != base]
    L.append('| world | ' + ' | '.join(f'{a} diff' for a in act) + ' | '
             + ' | '.join(f'{a} plan mean / p95 / max, bank min' for a in act) + ' |')
    L.append('|---|' + '---:|' * len(act) + '---|' * len(act))
    for e in sorted(B):
        c1, c2 = [], []
        for a in act:
            r = R[a].get(e)
            if r is None:
                c1.append('-')
                c2.append('-')
                continue
            c1.append(f"{r['final'] - B[e]['final']:+,.0f}")
            lg = r.get('agent_log') or {}
            if lg.get('sd_plan_ms_max') is not None:
                c2.append(f"{lg.get('sd_plan_ms_mean', 0):.0f} / {lg.get('sd_plan_ms_p95', 0):.0f} / "
                          f"{lg.get('sd_plan_ms_max', 0):.0f}, {lg.get('sd_bank_min_remaining', 0):.2f}")
            else:
                c2.append('-')
        L.append(f'| {e} | ' + ' | '.join(c1) + ' | ' + ' | '.join(c2) + ' |')
    return L


def lead(argv):
    arms, base, suffix, out = ['SDoff', 'SDsh', 'SDa12', 'SDall'], 'SDoff', '', None
    i = 0
    while i < len(argv):
        if argv[i] == '--arms':
            arms = argv[i + 1].split(','); i += 2
        elif argv[i] == '--base':
            base = argv[i + 1]; i += 2
        elif argv[i] == '--suffix':
            suffix = argv[i + 1]; i += 2
        elif argv[i] == '--out':
            out = argv[i + 1]; i += 2
        else:
            i += 1
    R = {a: load(a, suffix) for a in set(arms) | {base}}
    B = R[base]
    L = []
    L.append(f'base {base}: {len(B)} worlds' + (f' (suffix {suffix})' if suffix else ''))
    # shadow / reproduction check
    for a in arms:
        if a == base or not a.endswith('sh'):
            continue
        common = sorted(set(R[a]) & set(B))
        same_final = sum(1 for e in common if round(R[a][e]['final'], 2) == round(B[e]['final'], 2)
                         and round(R[a][e]['opp_final'], 2) == round(B[e]['opp_final'], 2))
        same_days = sum(1 for e in common if all(x['cash'] == y['cash'] for x, y in zip(R[a][e]['days'], B[e]['days'])))
        L.append(f'SHADOW CHECK {a} vs {base}: final + opponent identical in {same_final}/{len(common)} worlds, every '
                 f'day-start cash identical in {same_days}/{len(common)}')
        for e in common:
            if round(R[a][e]['final'], 2) != round(B[e]['final'], 2):
                L.append(f'   DIFF {e}: {R[a][e]["final"]:.0f} vs {B[e]["final"]:.0f}')
    Mb = {e: metrics(r) for e, r in B.items()}
    rows = []
    for a in arms:
        Ra = R[a]
        common = sorted(set(Ra) & set(B))
        if not common:
            continue
        Ma = {e: metrics(Ra[e]) for e in common}
        mean = lambda k, M=Ma: st.mean(M[e][k] for e in common) if all(M[e].get(k) is not None for e in common) else None
        row = dict(arm=a, n=len(common), final=mean('final'), gap=mean('gap'), ratio=mean('ratio'), opp=mean('opp'),
                   maint=mean('maint'), maint_12_23=mean('maint_12_23'), tile_ops=mean('tile_ops'), moves=mean('moves'),
                   mpo=st.mean(Ma[e]['moves'] for e in common) / max(1e-9, st.mean(Ma[e]['tile_ops'] for e in common)),
                   unwatered=mean('unwatered'), escaped=mean('escaped'), rotted=mean('rotted'), rot_units=mean('rot_units'),
                   harvested=mean('harvested'), discards=mean('discards'), tmax=max(Ma[e]['tmax'] for e in common))
        for k in MAINT:
            row['op_' + k] = mean('op_' + k)
        if a != base:
            row['d_final'] = paired([Ma[e]['final'] - Mb[e]['final'] for e in common])
            row['d_margin'] = paired([(Ma[e]['final'] - Ma[e]['opp']) - (Mb[e]['final'] - Mb[e]['opp']) for e in common])
            row['d_opp'] = st.mean(Ma[e]['opp'] - Mb[e]['opp'] for e in common)
            row['d_ratio'] = st.mean(Ma[e]['ratio'] - Mb[e]['ratio'] for e in common)
        for k in ('sd_plan_ms_max', 'sd_plan_ms_mean', 'sd_plan_ms_p95', 'sd_plan_ms_first_max', 'sd_step_ms_max',
                  'sd_step_ms_p95', 'sd_bank_min_remaining', 'sd_fb_unit', 'sd_fb_step', 'sd_errors', 'sd_time_capped',
                  'sd_idle_unit', 'sd_planned_unit', 'sd_switch_steps', 'sd_deliv_deferred', 'sd_dropped_jobs',
                  'sd_dropped_value', 'sd_dropped_prod_jobs', 'sd_dropped_hard', 'sd_plants_lost', 'sd_animals_lost',
                  'sd_shed_arrivals', 'sd_walk_after_last', 'sd_agree', 'sd_agree_n'):
            vals = [Ma[e][k] for e in common if Ma[e].get(k) is not None]
            if vals:
                row[k] = (max(vals) if k.endswith('_max') else min(vals) if k == 'sd_bank_min_remaining'
                          else st.mean(vals))
        rows.append(row)
    L.append('')
    L.append('| arm | n | own cash | gap to leader | ratio | opponent | vs base: own (t 95% CI; bootstrap) better/worse | '
             'margin diff (t CI) | maint ops (d12-23) | tile ops | moves / tile op | harvested units | unwatered / '
             'escaped | rotted plants / rot units | discards |')
    L.append('|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|')
    for r in rows:
        d = r.get('d_final')
        dm = r.get('d_margin')
        dtxt = (f"{d['mean']:+,.0f} ({d['t_lo']:+,.0f}..{d['t_hi']:+,.0f}; {d['b_lo']:+,.0f}..{d['b_hi']:+,.0f}) "
                f"{d['better']}/{d['worse']}") if d else ''
        mtxt = f"{dm['mean']:+,.0f} ({dm['t_lo']:+,.0f}..{dm['t_hi']:+,.0f})" if dm else ''
        L.append(f"| {r['arm']} | {r['n']} | {fmt(r['final'])} | {fmt(r['gap'])} | {r['ratio']:.3f} | {fmt(r['opp'])} | "
                 f"{dtxt} | {mtxt} | {fmt(r['maint'])} ({fmt(r['maint_12_23'])}) | {fmt(r['tile_ops'])} | {r['mpo']:.3f} | "
                 f"{fmt(r['harvested'])} | {r['unwatered']:.1f} / {r['escaped']:.1f} | {r['rotted']:.1f} / "
                 f"{r['rot_units']:.1f} | {r['discards']:.1f} |")
    L.append('')
    L.append('| arm | ' + ' | '.join(MAINT) + ' |')
    L.append('|---|' + '---:|' * len(MAINT))
    for r in rows:
        L.append(f"| {r['arm']} | " + ' | '.join(fmt(r['op_' + k]) for k in MAINT) + ' |')
    L.append('')
    L.append('| arm | plan ms mean / p95 / max (first plan max) | whole step ms p95 / max | harness tmax s | min bank s | '
             'time-capped steps | fallbacks unit / step / errors | idle unit-steps | switch steps | deliveries deferred | '
             'dropped jobs at 23h (prod.; value) | survival dropped | plants / animals lost | shadow agreement |')
    L.append('|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---|---|')
    for r in rows:
        g = lambda k, nd=0: fmt(r.get(k), nd) if r.get(k) is not None else '-'
        agree = (f"{r['sd_agree'] / max(1, r['sd_agree_n']):.0%}" if r.get('sd_agree_n') else '-')
        L.append(f"| {r['arm']} | {g('sd_plan_ms_mean', 1)} / {g('sd_plan_ms_p95', 1)} / {g('sd_plan_ms_max', 1)} "
                 f"({g('sd_plan_ms_first_max', 1)}) | {g('sd_step_ms_p95', 1)} / {g('sd_step_ms_max', 1)} | "
                 f"{r['tmax']:.3f} | {g('sd_bank_min_remaining', 2)} | {g('sd_time_capped', 1)} | {g('sd_fb_unit', 1)} / "
                 f"{g('sd_fb_step', 1)} / {g('sd_errors', 1)} | {g('sd_idle_unit', 1)} | {g('sd_switch_steps', 1)} | "
                 f"{g('sd_deliv_deferred', 1)} | {g('sd_dropped_jobs', 1)} ({g('sd_dropped_prod_jobs', 1)}; "
                 f"{g('sd_dropped_value', 0)}) | {g('sd_dropped_hard', 2)} | {g('sd_plants_lost', 1)} / "
                 f"{g('sd_animals_lost', 2)} | {agree} |")
    L += market_tables(R, base, arms)
    txt = '\n'.join(L)
    print(txt)
    if out:
        Path(out).write_text(txt + '\n', encoding='utf-8')
    return rows


if __name__ == '__main__':
    if sys.argv[1] == 'lead':
        lead(sys.argv[2:])
