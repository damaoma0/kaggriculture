"""KWE thread: compare arms on one world against a base arm (and DSM): money / margin, deaths, midnight deletions, the
wheat and egg unit flows (scripts/wheategg_diag.py hooks), labour by category (unit-steps, moves charged to the next op),
the tier plan's execution counters (skips / waits / unfinished stops) and the product revenue of both players.
usage: wheategg_report.py <team:ep> <BASE> <ARM,ARM,...> [--json out.json]"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import wheategg_diag as D  # noqa: E402
import upkeep_engine as UE  # noqa: E402

PRODS = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')


def tot(L, key):
    c = Counter()
    for day, v in L[key].items():
        if int(day) >= 11:
            c.update(v)
    return c


def summarize(L, res=None):
    W, G, lost = tot(L, 'wheat'), tot(L, 'egg'), tot(L, 'lost')
    ops = tot(L, 'ops')
    lab = Counter()
    for day, v in L['labor'].items():
        if int(day) >= 11:
            for k, n in v.items():
                lab[k.replace('~move', '')] += n
    s = [e for e in L['sales'] if e[1] == 'us']
    out = {'money': L['money'], 'margin': L['money']['us'] - L['money']['opp'],
           'wheat': {'harv_u': W['harv_u'], 'harv_n': W['harv_n'], 'planted': W['planted'], 'water_grow': W['water_grow'],
                     'water_surv': W['water_surv'], 'fert': W['fert'], 'fed': W['fed_SHEEP'] + W['fed_COW'] + W['fed_GOOSE'],
                     'fed_SHEEP': W['fed_SHEEP'], 'fed_COW': W['fed_COW'], 'fed_GOOSE': W['fed_GOOSE'],
                     'sold': sum(1 for e in s if e[3] == 'WHEAT' and e[2] == 'SELL'),
                     'bought': sum(1 for e in s if e[3] == 'WHEAT' and e[2] == 'BUY_PRODUCT'),
                     'rev': round(sum(e[4] for e in s if e[3] == 'WHEAT' and e[2] == 'SELL')),
                     'cost': round(sum(e[4] for e in s if e[3] == 'WHEAT' and e[2] == 'BUY_PRODUCT')),
                     'deleted': lost['WHEAT'], 'died': W['died_unwatered'] + W['decay_dead']},
           'egg': {'goose_days': G['goose_days'], 'feed': G['feed'], 'care': G['care'], 'fed_not_cared': G['fed_not_cared'],
                   'unfed': G['unfed'], 'bonus_paid': G['bonus_paid'], 'bank_wiped': G['bank_wiped'], 'produced': G['produced'],
                   'swallowed': G['swallowed'], 'harv_n': G['harv_n'], 'harv_u': G['harv_u'],
                   'sold': sum(1 for e in s if e[3] == 'EGG' and e[2] == 'SELL'),
                   'rev': round(sum(e[4] for e in s if e[3] == 'EGG' and e[2] == 'SELL')), 'deleted': lost['EGG'],
                   'escaped': G['escaped']},
           'lost': dict(lost), 'ops': dict(ops), 'labor': dict(lab)}
    if res is not None:
        out['died'] = {}
        for d, v in res.get('died', {}).items():
            for k, n in v.items():
                out['died'][k] = out['died'].get(k, 0) + n
        cnt = Counter()
        unf = 0
        for d, x in res.get('tier_days', {}).items():
            if isinstance(x.get('cnt'), dict):
                cnt.update(x['cnt'])
            for u, lst in (x.get('unfinished') or {}).items():
                unf += sum(len(ops_) for _, ops_ in lst)
        out['tier_cnt'] = dict(cnt)
        out['unfinished_ops'] = unf
        out['tier_err'] = res.get('tier_err', {}).get('errors')
    return out


def revenue(team, ep, stream):
    """both players' sales revenue by product (engine replay; SELL only)."""
    got = Counter()
    E = D.E
    orig = D._commit
    w_box = {}

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        r = orig(op, item, price, farm, private, market, shed_capacity)
        w = w_box.get('w')
        if r and w is not None and w.t >= 264 and op == 'SELL':
            side = 'us' if farm is w.farms[w_box['seat']] else 'opp'
            got[f'{side}|{item}|n'] += 1
            got[f'{side}|{item}|$'] += float(price)
        return r
    tape = UE.load_tape(int(team), int(ep))
    saved = E._commit_unit
    E._commit_unit = commit
    try:
        w = UE.World(tape['seed'], tape['shops'])
        seat = tape['seat']
        w_box.update(w=w, seat=seat)
        while w.t < 719:
            t = w.t
            if stream is None or t < 264:
                own = UE.tape_action(tape['actions'], t)
            else:
                a = stream[t] if t < len(stream) else {}
                own = a if isinstance(a, dict) and a else dict(UE.PASS)
            acts = [None, None]
            acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
            w.step(acts)
    finally:
        E._commit_unit = saved
    return dict(got)


def main():
    g, base, arms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    out = {}
    names = ['leader', base] + [a for a in arms if a != base]
    for a in names:
        if a == 'leader':
            L = D.run(tape, None)
            out[a] = summarize(L)
            out[a]['rev'] = revenue(team, ep, None)
            continue
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{a.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / a / f'{ep}.json').read_text(encoding='utf-8'))
        L = D.run(tape, s['actions'])
        out[a] = summarize(L, res)
        out[a]['rev'] = revenue(team, ep, s['actions'])
    b = out[base]
    print(f'world {g}; base {base}')
    hdr = f"{'arm':10s} {'own':>8s} {'rival':>8s} {'margin':>7s} {'dMarg':>6s} {'dOwn':>6s} {'dRiv':>6s} | died | deleted"
    print(hdr)
    for a in names:
        x = out[a]
        m = x['money']
        print(f"{a:10s} {m['us']:8.0f} {m['opp']:8.0f} {x['margin']:7.0f} {x['margin'] - b['margin']:6.0f} "
              f"{m['us'] - b['money']['us']:6.0f} {m['opp'] - b['money']['opp']:6.0f} | {x.get('died', '-')} | "
              f"{sum(x['lost'].values())} {x['lost']}")
    print('EGG   ', ' '.join(f"{k}" for k in b['egg']))
    for a in names:
        print(f"{a:10s}", ' '.join(f"{out[a]['egg'][k]}" for k in b['egg']))
    print('WHEAT ', ' '.join(f"{k}" for k in b['wheat']))
    for a in names:
        print(f"{a:10s}", ' '.join(f"{out[a]['wheat'][k]}" for k in b['wheat']))
    print('tier counters (execution) and unfinished planned ops:')
    for a in names:
        if 'tier_cnt' in out[a]:
            c = out[a]['tier_cnt']
            print(f"{a:10s} unfinished {out[a]['unfinished_ops']} errors {out[a]['tier_err']} "
                  + ' '.join(f"{k}={v}" for k, v in sorted(c.items()) if k.startswith(('skip', 'wait', 'pick', 'fail'))))
    for a in names:
        if a in ('leader', base):
            continue
        print(f'-- {a} vs {base}: labour (unit-steps) changes |d| >= 8:')
        la, lb = out[a]['labor'], b['labor']
        ch = sorted(((la.get(k, 0) - lb.get(k, 0), k) for k in set(la) | set(lb)), key=lambda x: x[0])
        print('   ', ' '.join(f"{k}{d:+d}" for d, k in ch if abs(d) >= 8))
        oa, ob = out[a]['ops'], b['ops']
        ch = sorted(((oa.get(k, 0) - ob.get(k, 0), k) for k in set(oa) | set(ob)), key=lambda x: x[0])
        print('    ops:', ' '.join(f"{k}{d:+d}" for d, k in ch if abs(d) >= 3))
        ra, rb = out[a]['rev'], b['rev']
        line = []
        for p in PRODS:
            for side in ('us', 'opp'):
                dn = ra.get(f'{side}|{p}|n', 0) - rb.get(f'{side}|{p}|n', 0)
                dv = ra.get(f'{side}|{p}|$', 0) - rb.get(f'{side}|{p}|$', 0)
                if abs(dv) >= 150:
                    line.append(f"{side}:{p} {dn:+d}u {dv:+.0f}$")
        print('    revenue:', '; '.join(line))
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), default=str)


if __name__ == '__main__':
    main()
