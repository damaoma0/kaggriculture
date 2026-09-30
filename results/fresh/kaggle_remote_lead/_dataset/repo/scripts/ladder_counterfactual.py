"""Counterfactual on OUR ladder games: same seed, same shops, the opponent's RECORDED actions, our agent live.

The recorded opponent cannot react, but the comparison is between builds of ours in the same world against the same
moves, so that handicap is common to every arm. Weeds are natural (they differ from the recorded game).
usage: ladder_counterfactual.py <agent>[,<agent>...] <episode>[,<episode>...]   (replays in data/ladder_t10/)
Output: results/fresh/ladder_t10/cf_<agent>_<episode>.json
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/ladder_t10'


def run(job):
    name, ep = job
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay = json.loads((ROOT / f'data/ladder_t10/episode-{ep}-replay.json').read_text(encoding='utf-8'))
    steps = replay['steps']
    names = replay['info']['TeamNames']
    seat = next(i for i, n in enumerate(names) if 'ghost rule' in (n or '').lower())
    shops = [steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    ap = ROOT / 'agents' / f'{name}.py'
    entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
    rec = [steps[t + 1][1 - seat].get('action') if t + 1 < len(steps) else None for t in range(720)]
    players = [None, None]
    players[seat] = lambda obs, t: entry(obs)
    players[1 - seat] = lambda obs, t: (rec[t] if isinstance(rec[t], dict) else {'farmer': ['PASS'], 'hands': [], 'market': []})
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': replay['info']['seed']})
    res = TV._play(E, env, players, seat, shops, None, None, seat)
    d = res['daily'][seat][-1]
    G = entry.__globals__
    out = dict(agent=name, episode=ep, final=res['final'][seat], rival=res['final'][1 - seat], margin=res['final'][seat] - res['final'][1 - seat],
               recorded=[replay['rewards'][seat], replay['rewards'][1 - seat]], no_effect=d['physical'].get('no_effect', 0),
               missing=d['physical'].get('missing_worker_commands', 0), revenue=d['revenue'], spend=d['spend'],
               overlay={k: v for k, v in (G.get('_SHP_REPORT') or {}).items() if isinstance(v, (int, float))},
               switches=[h for i, h in enumerate(G.get('_MGT_HISTORY') or []) if i == 0 or h[1] != G['_MGT_HISTORY'][i - 1][1]])
    (OUT / f'cf_{name}_{ep}.json').write_text(json.dumps(out), encoding='utf-8')
    return out


def main():
    agents = sys.argv[1].split(',')
    eps = [int(x) for x in sys.argv[2].split(',')]
    jobs = [(a, e) for e in eps for a in agents if not (OUT / f'cf_{a}_{e}.json').exists()]
    with ProcessPoolExecutor(max_workers=4, max_tasks_per_child=1) as pool:
        futures = {pool.submit(run, j): j for j in jobs}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as exc:
                print('FAILED', futures[f], type(exc).__name__, exc, flush=True)
    print(f'{"episode":>10} {"recorded (ours / theirs)":>26} | ' + ' | '.join(f'{a:>22}' for a in agents))
    for e in eps:
        cells, recd = [], None
        for a in agents:
            f = OUT / f'cf_{a}_{e}.json'
            if f.exists():
                r = json.loads(f.read_text(encoding='utf-8'))
                recd = r['recorded']
                o = r['overlay']
                cells.append(f'{r["margin"]:>+8,.0f} dead {r["no_effect"]:>3} exp {int(o.get("commitments", 0))}/{int(o.get("sheep_bought", 0))}')
            else:
                cells.append(f'{"-":>22}')
        print(f'{e:>10} {recd[0]:>12,.0f} / {recd[1]:>9,.0f} ({recd[0] - recd[1]:>+7,.0f}) | ' + ' | '.join(cells))


if __name__ == '__main__':
    main()
