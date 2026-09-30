"""Day-by-day trace of the O1r failure (DSM opening + day-6 handoff) against mgt_m1 in the same recorded ladder world.

Per day, for each build: cash, animals, our board's distance from (a) DSM's recorded board on days 0-6 and (b) the
recorded board of the tape we follow (days 6+), failed ('no effect') commands by type, and hands present.
usage: trace_opening_o1r.py <episode> [<episode> ...]   (worlds from data/ladder_panel/56368334)
"""
import gzip, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from opening_replay_probe import label


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    ref = json.loads((ROOT / 'data/openings/dsm_329f3ad2.json').read_text(encoding='utf-8'))
    dsm = [[ref['boards'][d][i:i + 2] for i in range(0, 200, 2)] for d in range(7)]
    out = {}
    for ep in sys.argv[1:]:
        g = json.load(gzip.open(ROOT / f'data/ladder_panel/56368334/{ep}.json.gz', 'rt', encoding='utf-8'))
        seat, rec = g['seat'], g['opp_actions']
        out[ep] = {}
        for name in ('mgt_o1r', 'mgt_lib584'):
            ap = ROOT / 'agents' / f'{name}.py'
            entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
            G = entry.__globals__
            days = {}

            def ours(obs, t, G=G, days=days):
                if t % 24 == 0:
                    farm = obs['farms'][seat]
                    b = [label(x) for row in farm['tiles'] for x in row]
                    d = t // 24
                    tapes = G.get('_MGT_TAPES') or []
                    route = (G['_MGT_IMPL'].chassis.players.get(seat) or {}).get('route') if '_MGT_IMPL' in G else None
                    tb = None
                    if route is not None and route < len(tapes) and d < 30:
                        tb = [(' .' if x == ' w' else x) for x in tapes[route]['lab'][d]]
                    days[d] = dict(cash=farm['money'],
                                   animals=Counter(c.get('animal') for row in farm['tiles'] for c in row if isinstance(c, dict) and c.get('animal')),
                                   vs_dsm=sum(1 for x, y in zip(b, dsm[d]) if x != y) if d <= 6 else None,
                                   vs_tape=sum(1 for x, y in zip(b, tb) if x != y) if tb else None,
                                   seeds=dict(obs['private'].get('seeds') or {}))
                return entry(obs)
            players = [None, None]
            players[seat] = ours
            players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else {'farmer': ['PASS'], 'hands': [], 'market': []})
            env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': g['seed']})
            res = TV._play(E, env, players, seat, g['shops'], None, None, seat)
            daily = res['daily'][seat]
            rows = []
            for d in range(29):
                a = {k: v for k, v in daily[d + 1]['physical'].items() if k.startswith('no_effect:')}
                b = {k: v for k, v in daily[d]['physical'].items() if k.startswith('no_effect:')}
                dead = {k[10:]: a[k] - b.get(k, 0) for k in a if a[k] - b.get(k, 0) > 0}
                x = days.get(d, {})
                rows.append(dict(day=d, cash=x.get('cash'), animals=dict(x.get('animals') or {}), vs_dsm=x.get('vs_dsm'),
                                 vs_tape=x.get('vs_tape'), dead=sum(dead.values()), dead_by_op=dead,
                                 revenue=round(sum(daily[d + 1]['revenue'].values()) - sum(daily[d]['revenue'].values()))))
            out[ep][name] = dict(final=res['final'][seat], rival=res['final'][1 - seat], rows=rows,
                                 history=[h[:4] for h in (G.get('_MGT_HISTORY') or [])])
            print(f"{ep} {name}: final {res['final'][seat]:,.0f} rival {res['final'][1 - seat]:,.0f}", flush=True)
        o, m = out[ep]['mgt_o1r'], out[ep]['mgt_lib584']
        print(f"  day | o1r cash  m1 cash | o1r vs DSM board | o1r vs its tape | m1 vs its tape | failed cmds o1r / m1 | day revenue o1r / m1 | o1r animals")
        for d in list(range(0, 13)) + [15, 18, 21, 24, 27]:
            a, b = o['rows'][d], m['rows'][d]
            print(f"  {d:3d} | {a['cash'] or 0:8,.0f} {b['cash'] or 0:8,.0f} | {str(a['vs_dsm']):>6} | {str(a['vs_tape']):>6} | {str(b['vs_tape']):>6} | "
                  f"{a['dead']:4d} / {b['dead']:<4d} | {a['revenue']:6,d} / {b['revenue']:<6,d} | {a['animals']}")
        print('  o1r routes:', o['history'][:4])
    (ROOT / 'results/fresh/newphase_20260923/opening/o1r_traces.json').write_text(json.dumps(out, default=str), encoding='utf-8')


if __name__ == '__main__':
    main()
