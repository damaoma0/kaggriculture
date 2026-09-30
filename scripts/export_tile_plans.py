"""Export the tile plan interface (agents/mgt_lead_sector_search.py TilePlanView) of recorded games as JSON: the exact
input a trained tile planner has to produce for KB115LT (sd_tp_iface 1 + sd_tp_file). DSM's plans exported here must
reproduce the recorded-plan run when fed back through sd_tp_file (the interface completeness check).

usage: export_tile_plans.py <panel file | team:ep,...> <out.json>
out: {episode: {n, plant, events, struct_by_day, animals_by_day, board, harv_tiles, removals, land_day, hands, cum_sold}}
"""
import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEM = ROOT / 'data/leader_semantics'


def main():
    src, out = sys.argv[1], sys.argv[2]
    games = (ROOT / src).read_text().strip().split(',') if (ROOT / src).exists() else src.split(',')
    spec = importlib.util.spec_from_file_location('agent', ROOT / 'agents/mgt_lead_sector_search.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = {}
    for g in games:
        team, ep = g.strip().split(':')
        sem = json.load(gzip.open(SEM / team / f'{ep}.json.gz', 'rt', encoding='utf-8'))
        v = mod.TilePlanView(mod.Target(sem))
        d = v.to_dict()
        back = mod.TilePlanView.from_dict(json.loads(json.dumps(d)))     # the JSON round trip must be lossless
        for f in mod.TilePlanView._FIELDS:
            a, b = getattr(v, f), getattr(back, f)
            if f == 'cum_sold':
                a, b = [list.__getitem__(a, i) for i in range(11)], [list.__getitem__(b, i) for i in range(11)]
            assert a == b, (ep, f)
        res[ep] = d
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out, 'w', encoding='utf-8'))
    print(f'{len(res)} plans -> {out} ({Path(out).stat().st_size // 1024} KB); JSON round trip lossless on every field')


if __name__ == '__main__':
    main()
