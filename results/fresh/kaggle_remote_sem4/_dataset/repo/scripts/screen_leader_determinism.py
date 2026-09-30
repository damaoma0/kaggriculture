"""Direction 2 screen: is a leader's recorded action stream a *shop-conditioned deterministic plan*
(harvestable as a tape, the way Unknown Mother-Goose's old submission was) or a closed-loop policy?

Test: among that agent's own episodes, take every pair whose revealed shop sequences agree for the
first k reveals, and measure how long the two recorded action streams agree. A shop-conditioned
deterministic agent agrees until the shops part (UMG old: 8-12 days). A closed-loop or wall-clock
agent diverges within hours.

usage: screen_leader_determinism.py <cache_dir_with_episode-*-replay.json> <team-name-substring> [label]
       screen_leader_determinism.py umg   (positive control, uses the compact data/mg_tapes library)
"""
import gzip, json, sys
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'


def canon(a):
    return json.dumps(a or {}, sort_keys=True, separators=(',', ':'))


def shop_seq(unlocked_by_day):
    seq, seen = [], 0
    for cur in unlocked_by_day:
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
        if len(seq) >= 8:
            break
    return seq[:8]


def extract(args):
    path, team = args
    try:
        r = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        return None
    steps = r.get('steps') or []
    if len(steps) < 720:
        return None
    names = r['info'].get('TeamNames') or []
    seat = next((i for i, n in enumerate(names) if team.lower() in (n or '').lower()), None)
    if seat is None:
        return None
    shops = [steps[min(719, d * 24)][0]['observation']['town']['unlocked_shops'] for d in range(31)]
    acts = [canon(steps[t + 1][seat].get('action')) for t in range(719)]
    return dict(ep=r.get('id') or Path(path).stem, seat=seat, shops=shop_seq(shops), acts=acts,
                rewards=r.get('rewards'), opponent=names[1 - seat] if len(names) > 1 else None)


def agree_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def report(games, label):
    print(f'\n=== {label}: {len(games)} episodes ===')
    if len(games) < 2:
        return {}
    buckets = defaultdict(list)
    for g in games:
        for k in range(1, 9):
            buckets[(k, tuple(g['shops'][:k]))].append(g)
    rows = {}
    for k in range(0, 9):
        pairs = []
        seen = set()
        src = buckets if k else {(0, ()): games}
        for (kk, key), gs in src.items():
            if kk != k:
                continue
            for i in range(len(gs)):
                for j in range(i + 1, len(gs)):
                    pid = (gs[i]['ep'], gs[j]['ep'])
                    if pid in seen:
                        continue
                    seen.add(pid)
                    pairs.append(agree_len(gs[i]['acts'], gs[j]['acts']))
        if pairs:
            pairs.sort()
            rows[k] = dict(n_pairs=len(pairs), median_steps=pairs[len(pairs) // 2], max_steps=pairs[-1],
                           median_days=round(pairs[len(pairs) // 2] / 24, 1), frac_diverge_day0=sum(p < 24 for p in pairs) / len(pairs))
            r = rows[k]
            print(f'  shops matching for first {k}: {r["n_pairs"]:5d} pairs, median action agreement '
                  f'{r["median_steps"]:4d} steps ({r["median_days"]:4.1f} days), max {r["max_steps"]:4d}, '
                  f'{100*r["frac_diverge_day0"]:5.1f}% diverge inside day 0')
    return rows


def main():
    if sys.argv[1] == 'compact':
        # compact leader tapes from scripts/harvest_leader_tapes.py
        d = Path(sys.argv[2])
        label = sys.argv[3] if len(sys.argv) > 3 else d.name
        games = []
        for q in sorted(d.glob('*.json.gz')):
            g = json.load(gzip.open(q, 'rt', encoding='utf-8'))
            games.append(dict(ep=g['episode'], shops=g['shops'], acts=[canon(a) for a in g['actions']]))
        rows = report(games, label)
    elif sys.argv[1] == 'umg':
        games = []
        for p in sorted((ROOT / 'data/mg_tapes').rglob('*.json.gz')):
            g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
            games.append(dict(ep=g.get('episode'), shops=g['shops'] if isinstance(g['shops'][0], str) else shop_seq(g['shops']),
                              acts=[canon(a) for a in g['actions']]))
        rows = report(games, 'UMG old 56266758+56266899 (positive control)')
        label = 'umg_old'
    else:
        cache, team = sys.argv[1], sys.argv[2]
        label = sys.argv[3] if len(sys.argv) > 3 else team
        paths = sorted(Path(cache).glob('episode-*-replay.json'))
        with ProcessPoolExecutor(max_workers=6) as pool:
            games = [g for g in pool.map(extract, [(str(p), team) for p in paths]) if g]
        rows = report(games, label)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f'determinism_{label}.json'
    f.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    print('wrote', f)


if __name__ == '__main__':
    main()
