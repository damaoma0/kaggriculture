"""KD thread helper: exact per-world midnight-dump deletions (by product) for a list of arms, reusing
scripts/season_losses.py's replay (no re-simulation of the full kaggle_environments game, no editing of season_losses.py
itself). Prints a table and writes a JSON summary.

usage: dump_collect_losses.py <arm,...> [--games panel13|team:ep,...] [--out path.json]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import season_losses as SL  # noqa: E402
from run_arms import PANEL13  # noqa: E402


def load_stream(arm, ep):
    f = ROOT / 'results/fresh/day12_viz' / (arm.lower() + '_streams') / f'{ep}.json'
    return json.loads(f.read_text(encoding='utf-8'))['actions'] if f.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arms')
    ap.add_argument('--games', default='panel13')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    games = PANEL13 if a.games == 'panel13' else a.games.split(',')
    arms = a.arms.split(',')
    out = {}
    leader_cache = {}
    for game in games:
        team, ep = game.split(':')
        tape = UE.load_tape(int(team), int(ep))
        if ep not in leader_cache:
            leader_cache[ep] = SL.run(tape, None)
        lres = leader_cache[ep]
        lost_l = sum(sum(v.values()) for v in lres['lost'].values())
        row = {'leader_lost': lost_l}
        for arm in arms:
            stream = load_stream(arm, ep)
            if stream is None:
                row[arm] = None
                continue
            r = SL.run(tape, stream)
            per_prod = defaultdict(int)
            for day, prods in r['lost'].items():
                for p, v in prods.items():
                    per_prod[p] += v
            row[arm] = {'total': sum(per_prod.values()), 'by_product': dict(per_prod),
                        'own_cash': r['final'][tape['seat']]}
        out[ep] = row
    hdr = 'ep'.ljust(11) + 'leader'.rjust(8) + ''.join(a.rjust(10) for a in arms)
    print(hdr)
    sums = defaultdict(int)
    for ep, row in out.items():
        line = ep.ljust(11) + str(row['leader_lost']).rjust(8)
        sums['leader'] += row['leader_lost']
        for arm in arms:
            v = row[arm]['total'] if row[arm] else -1
            line += str(v).rjust(10)
            sums[arm] += v if row[arm] else 0
        print(line)
    line = 'TOTAL'.ljust(11) + str(sums['leader']).rjust(8)
    for arm in arms:
        line += str(sums[arm]).rjust(10)
    print(line)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1), encoding='utf-8')
        print('wrote', a.out)


if __name__ == '__main__':
    main()
