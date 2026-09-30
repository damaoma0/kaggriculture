"""KD thread helper: aggregate scripts/season_shed.py's per-night shed/carried/lost data into the same summary shape the
coordinator used (season_shed.py k5b panel13): mean pre-dump shed contents (leader vs an arm), mean carried-in, nights
over 100, mean deleted units/night. Reuses season_shed.run() directly (no changes to season_shed.py).

usage: dump_shed_summary.py <arm lowercase> [--games panel13|team:ep,...]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import season_shed as SS  # noqa: E402
import upkeep_engine as UE  # noqa: E402
from run_arms import PANEL13  # noqa: E402


def summarize(days):
    n = 0
    shed = Counter()
    carried = Counter()
    over100 = 0
    lost_tot = 0
    for d, rec in days.items():
        if 'shed23' not in rec:
            continue
        n += 1
        shed.update(rec['shed23'])
        carried.update(rec['carried'])
        tot = sum(rec['carried'].values()) + sum(rec['shed23'].values())
        if tot > 100:
            over100 += 1
        lost_tot += sum(rec.get('lost', {}).values())
    return {'nights': n, 'shed_mean': round(sum(shed.values()) / n, 2) if n else 0,
            'shed_by_product': {k: round(v / n, 2) for k, v in shed.most_common(6)} if n else {},
            'carried_mean': round(sum(carried.values()) / n, 2) if n else 0,
            'carried_by_product': {k: round(v / n, 2) for k, v in carried.most_common(6)} if n else {},
            'nights_over_100': over100, 'deleted_per_night': round(lost_tot / n, 2) if n else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arm')
    ap.add_argument('--games', default='panel13')
    a = ap.parse_args()
    games = PANEL13 if a.games == 'panel13' else a.games.split(',')
    leader_days, arm_days = {}, {}
    for g in games:
        team, ep = g.split(':')
        tape = UE.load_tape(int(team), int(ep))
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{a.arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
        ld = SS.run(tape, None)
        ad = SS.run(tape, s['actions'])
        for d, rec in ld.items():
            leader_days[f'{ep}:{d}'] = rec
        for d, rec in ad.items():
            arm_days[f'{ep}:{d}'] = rec
    print('leader', json.dumps(summarize(leader_days)))
    print(a.arm, json.dumps(summarize(arm_days)))


if __name__ == '__main__':
    main()
