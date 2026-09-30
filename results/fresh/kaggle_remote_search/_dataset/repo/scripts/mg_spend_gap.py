"""Where does Mother-Goose's spending gap to her peers come from? Exact ledgers by re-running her 72 public replays.

Every replay is re-simulated in the local engine from its seed with both sides' RECORDED actions, inside the same
transaction ledger the panel harness uses (successful fills only, by category). The re-run must reproduce the
recorded final cash on both sides, otherwise the game is dropped. Wheat is bought and sold as a position by both
sides, so it is reported three ways: gross purchases, gross sales, and the round-trip volume (units bought back
and sold again) separated from genuine consumption (feed) and genuine production.

Output: results/fresh/mg_watch/spend_gap.json
"""
import glob
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replay(path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from evaluate_boards import Ledger
    r = json.load(open(path))
    names = r['info'].get('TeamNames') or []
    if not any('Mother' in (x or '') for x in names):
        return None
    seat = next(i for i, x in enumerate(names) if 'Mother' in (x or ''))
    steps = r['steps']

    def player(i):
        state = {'t': 0}

        def act(obs, cfg=None):
            state['t'] += 1
            a = steps[state['t']][i].get('action') if state['t'] < len(steps) else None
            return a if isinstance(a, dict) else {'farmer': ['PASS'], 'hands': [], 'market': []}
        return act

    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': r['info']['seed']})
    bought = [Counter(), Counter()]
    flows = [Counter(), Counter()]          # physical wheat: fed to animals, cut from fields
    cur = {'seat': -1}
    apply_orig = E._apply_unit_action

    def apply(farm, private, idx, action, *args, **kw):
        # the interpreter calls seat 0's farmer and hands, then seat 1's: a farmer call (idx 0) starts a seat
        if idx == 0:
            cur['seat'] = (cur['seat'] + 1) % 2
        invs = private['inventories']
        before = int((invs[idx] if idx < len(invs) else {}).get('WHEAT', 0) or 0)
        out = apply_orig(farm, private, idx, action, *args, **kw)
        invs = private['inventories']
        after = int((invs[idx] if idx < len(invs) else {}).get('WHEAT', 0) or 0)
        op = action[0] if isinstance(action, list) and action else None
        if op == 'FEED' and after < before:
            flows[cur['seat']]['fed'] += before - after
        elif op == 'HARVEST' and after > before:
            flows[cur['seat']]['cut'] += after - before
        return out
    E._apply_unit_action = apply
    with Ledger(E) as ledger:
        orig = E._commit_unit

        def commit(op, item, price, farm, private, market, shed_capacity=100):
            ok = orig(op, item, price, farm, private, market, shed_capacity)
            if ok and op != 'SELL':
                bought[ledger.seats[id(farm)]][op + ':' + item] += 1
            return ok
        E._commit_unit = commit
        try:
            env.run([player(0), player(1)])
        finally:
            E._commit_unit = orig
            E._apply_unit_action = apply_orig
        final = [env.state[i].reward for i in (0, 1)]
        if [round(x or 0) for x in final] != [round(x or 0) for x in r['rewards']]:
            return dict(id=r['info']['EpisodeId'], mismatch=[final, r['rewards']])
        out = {}
        for who, i in (('her', seat), ('opp', 1 - seat)):
            d = ledger.data[i]
            out[who] = dict(revenue=dict(d['revenue']), sold=dict(d['sold_units']), spend=dict(d['spend']), bought=dict(bought[i]), cash=final[i],
                            fed=flows[i]['fed'], cut=flows[i]['cut'])
    return dict(id=r['info']['EpisodeId'], opp_name=names[1 - seat], **out)


def main():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    rows = {'old': [], 'new': []}
    bad = 0
    for d, era in (('data/leaders_20260917', 'old'), ('data/leaders_20260919', 'new')):
        for path in sorted(glob.glob(str(ROOT / d / '*.json'))):
            g = replay(path)
            if g is None:
                continue
            if 'mismatch' in g:
                bad += 1
                print('MISMATCH', g['id'], g['mismatch'], flush=True)
                continue
            rows[era].append(g)
            print(era, g['id'], 'ok', flush=True)
    (ROOT / 'results/fresh/mg_watch/spend_gap.json').write_text(json.dumps(rows), encoding='utf-8')
    print('reproduced', sum(len(v) for v in rows.values()), 'games; mismatched', bad)
    for era, G in rows.items():
        n = len(G)
        if not n:
            continue
        print(f'\n=== {era}: {n} games; margin {sum(g["her"]["cash"] - g["opp"]["cash"] for g in G) / n:+,.0f}')
        cats = sorted({k for g in G for w in ('her', 'opp') for k in g[w]['spend']})
        print('spending by category            her       opp      diff     (units her / opp)')
        tot = [0, 0]
        for k in cats:
            h = sum(g['her']['spend'].get(k, 0) for g in G) / n
            o = sum(g['opp']['spend'].get(k, 0) for g in G) / n
            hu = sum(g['her']['bought'].get(k, 0) for g in G) / n
            ou = sum(g['opp']['bought'].get(k, 0) for g in G) / n
            tot[0] += h
            tot[1] += o
            print(f'  {k:<26} {h:>9,.0f} {o:>9,.0f} {h - o:>+9,.0f}     ({hu:.0f} / {ou:.0f})')
        print(f'  {"TOTAL":<26} {tot[0]:>9,.0f} {tot[1]:>9,.0f} {tot[0] - tot[1]:>+9,.0f}')
        for who in ('her', 'opp'):
            wb = sum(g[who]['bought'].get('BUY_PRODUCT:WHEAT', 0) for g in G) / n
            ws = sum(g[who]['sold'].get('WHEAT', 0) for g in G) / n
            cb = sum(g[who]['spend'].get('BUY_PRODUCT:WHEAT', 0) for g in G) / n
            cs = sum(g[who]['revenue'].get('WHEAT', 0) for g in G) / n
            fb = sum(g[who]['bought'].get('BUY_PRODUCT:FERTILIZER', 0) for g in G) / n
            fs = sum(g[who]['sold'].get('FERTILIZER', 0) for g in G) / n
            print(f'  wheat {who}: bought {wb:.0f} for {cb:,.0f} ({cb / max(1, wb):.1f} each), sold {ws:.0f} for {cs:,.0f} ({cs / max(1, ws):.1f} each); '
                  f'net cash {cs - cb:+,.0f}, net units {ws - wb:+.0f} | fertilizer bought {fb:.0f}, sold {fs:.0f}')
        print('  physical wheat per game          cut from fields   bought   fed to animals   sold   (cut + bought - fed - sold = lost or left over)')
        for who in ('her', 'opp'):
            cut = sum(g[who]['cut'] for g in G) / n
            fed = sum(g[who]['fed'] for g in G) / n
            wb = sum(g[who]['bought'].get('BUY_PRODUCT:WHEAT', 0) for g in G) / n
            ws = sum(g[who]['sold'].get('WHEAT', 0) for g in G) / n
            print(f'    {who:<4}                          {cut:>8.0f}        {wb:>6.0f}   {fed:>10.0f}      {ws:>6.0f}   ({cut + wb - fed - ws:+.0f})')
        rev = [sum(sum(g[w]['revenue'].values()) for g in G) / n for w in ('her', 'opp')]
        print(f'  revenue her {rev[0]:,.0f} vs opp {rev[1]:,.0f} ({rev[0] - rev[1]:+,.0f}); revenue excluding wheat: '
              f'{rev[0] - sum(g["her"]["revenue"].get("WHEAT", 0) for g in G) / n:,.0f} vs {rev[1] - sum(g["opp"]["revenue"].get("WHEAT", 0) for g in G) / n:,.0f}')


if __name__ == '__main__':
    main()
