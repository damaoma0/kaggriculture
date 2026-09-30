"""How early, and how reliably, can we tell which deterministic opponent we are facing?

We cannot see the opponent's orders, only its public farm: its worker and hand positions, its tiles,
its hires and its cash. A deterministic opponent replays the same opening every game, so its farm
trajectory over the first hours is a signature. This script extracts, for every seat of every replay on
disk, the public farm trajectory over the first two days, then asks for each target signature:

  * at step k, how many of the target's own games still match its canonical trajectory (true positives);
  * how many seats of OTHER agents still match it (false positives);
  * the earliest step at which the target is separated from every other agent in the sample.

The canonical trajectory is the per-step majority over the target's games. Cash is included only as a
separate signal, because it depends on the rival's simultaneous market orders.
"""
import glob, hashlib, json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from market_corpus import ROOT

OUT = ROOT / 'results/fresh/opponent_fingerprint'
SOURCES = ['data/leaders_20260917', 'data/replays', 'results/fresh/leader_strategy/replays',
           'results/fresh/leader_opening/replays', 'results/fresh/bigangel', 'results/fresh/qq_farming',
           'results/fresh/napster_y', 'data/router_refresh_20260916/live_replays']
STEPS = 48


def key(farm):
    """Public, rival-independent part of a farm: positions, hires and tiles (not money)."""
    return hashlib.sha1(json.dumps([farm['farmer'], farm['hands'], farm['hires_today'], farm['tiles'],
                                    farm['unlocked_quadrants']], sort_keys=True).encode()).hexdigest()[:12]


def extract(path):
    replay = json.loads(open(path, encoding='utf-8').read())
    info = replay.get('info') or {}
    teams = info.get('TeamNames') or ['?', '?']
    rows = []
    for seat in (0, 1):
        traj, cash = [], []
        for t in range(STEPS):
            obs = replay['steps'][t][0]['observation']
            if not obs.get('farms'):
                obs = replay['steps'][t][seat]['observation']
            farm = obs['farms'][seat]
            traj.append(key(farm))
            cash.append(farm['money'])
        rows.append(dict(episode=info.get('EpisodeId'), path=str(path), seat=seat, team=teams[seat], traj=traj, cash=cash))
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted({p for src in SOURCES for p in glob.glob(str(ROOT / src / '**' / '*replay*.json'), recursive=True)})
    rows, seen = [], set()
    with ProcessPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(extract, p) for p in paths]):
            for r in f.result():
                ident = (r['episode'], r['seat'])
                if ident in seen:
                    continue
                seen.add(ident)
                rows.append(r)
    (OUT / 'trajectories.json').write_text(json.dumps(rows), encoding='utf-8')
    teams = Counter(r['team'] for r in rows)
    print(f'{len(rows)} seat-trajectories from {len({r["episode"] for r in rows})} episodes, {len(teams)} teams')
    report = {}
    for target in ('Unknown Mother-Goose', 'Majkel1337'):
        mine = [r for r in rows if r['team'] == target]
        others = [r for r in rows if r['team'] != target]
        if not mine:
            continue
        canon = [Counter(r['traj'][t] for r in mine).most_common(1)[0][0] for t in range(STEPS)]
        print(f'\n== {target}: {len(mine)} own games vs {len(others)} other seats ({len({r["team"] for r in others})} teams)')
        separated = None
        rows_out = []
        for t in range(STEPS):
            tp = sum(1 for r in mine if all(r['traj'][u] == canon[u] for u in range(t + 1)))
            fp_rows = [r for r in others if all(r['traj'][u] == canon[u] for u in range(t + 1))]
            rows_out.append((t, tp, len(fp_rows), sorted({r['team'] for r in fp_rows})))
            if separated is None and not fp_rows:
                separated = t
        for t, tp, fp, who in rows_out:
            if t in (0, 1, 2, 3, 5, 8, 12, 16, 20, 23, 30, 47) or t == separated:
                print(f'   through step {t:2d}: own games matching {tp:2d}/{len(mine)} | other seats matching {fp:3d}'
                      + (f'  {who[:6]}' if 0 < fp <= 12 else ''))
        print(f'   earliest step with zero false positives: {separated}')
        report[target] = dict(own=len(mine), others=len(others), separated_at=separated,
                              curve=[dict(step=t, tp=tp, fp=fp) for t, tp, fp, _ in rows_out])
    (OUT / 'summary.json').write_text(json.dumps(report, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
