"""Are ~449 COLLECT_FERTILIZER commands a game really ~one per live animal per day? Counts distinct (day, tile) collect
positions from the dead-reckoned leader tapes (validated days only, see verify_geometry_fert.py) against live animal
tiles on the day-start board ('sh'/'go' exact; 'co' resolved via built records as cow/empty coop), and how many collect
commands land on a tile that is not a day-start animal (animals placed that day start with no fertilizer).

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_collect_distinct.py
"""
import glob
import gzip
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ns = {'__name__': 'vg_lib', '__file__': os.path.join(HERE, 'verify_geometry_fert.py')}
exec(compile(open(os.path.join(HERE, 'verify_geometry_fert.py'), encoding='utf-8').read(), 'vgf', 'exec'), ns)
reckon, TEAMS, ROOT = ns['reckon'], ns['TEAMS'], ns['ROOT']


def main():
    c = Counter()
    for tid, team in TEAMS.items():
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz'))):
            ep = os.path.basename(f).split('.')[0]
            tp = glob.glob(os.path.join(ROOT, 'data', 'leader_tapes', f'{tid}_*', f'{ep}.json.gz'))
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                sem = json.load(fh)
            with gzip.open(tp[0], 'rt', encoding='utf-8') as fh:
                t = json.load(fh)
            days, spawned = reckon(t['actions'])
            kind = {}
            for d in range(30):
                sd = sem['days'][d]
                b = sd['board']
                live = {i for i, lab in enumerate(b) if lab in ('sh', 'go') or (lab == 'co' and kind.get(i) == 'PASTURE')}
                if (sd.get('labour') or {}).get('hands_present') == spawned.get(d, 0) and d in days:
                    tiles = [p[1] * 10 + p[0] for seq in days[d].values() for p, cm in seq if cm[0] == 'COLLECT_FERTILIZER']
                    c['days'] += 1
                    c['collect_cmds'] += len(tiles)
                    c['distinct_collect_tiles'] += len(set(tiles))
                    c['distinct_on_live_animal'] += len(set(tiles) & live)
                    c['cmds_not_on_live_animal'] += sum(1 for x in tiles if x not in live)
                    c['live_animal_tile_days'] += len(live)
                for tt in sd.get('dug') or []:
                    kind.pop(tt, None)
                for k, ts in (sd.get('built') or {}).items():
                    for tt in ts:
                        kind[tt] = 'COOP' if k == 'BUILD_COOP' else 'PASTURE'
    res = dict(c)
    res['duplicate_cmd_share'] = round(1 - c['distinct_collect_tiles'] / c['collect_cmds'], 4)
    res['live_animal_days_collected_share'] = round(c['distinct_on_live_animal'] / c['live_animal_tile_days'], 4)
    txt = json.dumps(res, indent=1)
    with open(os.path.join(HERE, 'verify_geometry_collect_distinct.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(txt)


if __name__ == '__main__':
    main()
