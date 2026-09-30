"""Does Mother-Goose condition animal CARE on demand? Offline, from the compact tape library (no games).

For every tape: simulate the crew (tape calendar), attribute FEED / CARE / HARVEST commands to tiles, read the
species on each tile from the recorded daily boards, and relate care rate (CARE ops per animal-day) to the
shops of that world. Output: results/fresh/mg_tape/care_rule.json
"""
import glob
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate = ns['_tc_simulate']

SPECIES = {'sh': 'SHEEP', 'co': 'COW', 'go': 'GOOSE'}
PRODUCT = {'SHEEP': 'WOOL', 'COW': 'MILK', 'GOOSE': 'EGG'}
# shops that consume each animal product (from the engine's shop table)
ENGINE = None


def shop_table():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    for name in dir(E):
        v = getattr(E, name)
        if isinstance(v, dict) and 'YARN_STORE' in v:
            return name, v
    return None, None


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 9
    name, table = shop_table()
    print('engine shop table:', name)
    consumers = defaultdict(set)
    if table:
        for shop, spec in table.items():
            items = spec if isinstance(spec, (list, tuple, set)) else (spec.get('products') or spec.get('items') or spec.get('buys') or []) if isinstance(spec, dict) else []
            for it in items:
                consumers[str(it)].add(shop)
        print({k: sorted(v) for k, v in consumers.items() if k in ('WOOL', 'MILK', 'EGG')})
    rows = []
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))[:limit]
    for i, p in enumerate(paths):
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        flat = [''.join(b) if isinstance(b, list) else b for b in t['boards']]
        labs = [[b[j:j + 2] for j in range(0, len(b), 2)] for b in flat]
        # boards[d] = board at the start of day d (or end); species on a tile that day or the next
        def species(day, x, y):
            for d in (day, day + 1, day - 1):
                if 0 <= d < len(labs):
                    s = SPECIES.get(labs[d][y * 10 + x])
                    if s:
                        return s
            return None
        ops = defaultdict(lambda: defaultdict(int))          # species -> op -> count
        by_day = defaultdict(lambda: defaultdict(int))       # (species, day) -> op -> count
        for step, row in sim.items():
            day = step // 24
            for x, y, c in row:
                if c and c[0] in ('FEED', 'CARE', 'HARVEST'):
                    s = species(day, x, y)
                    if s:
                        ops[s][c[0]] += 1
                        by_day[(s, day)][c[0]] += 1
        animal_days = defaultdict(int)
        per_day = defaultdict(dict)
        for d, lab in enumerate(labs):
            for code, s in SPECIES.items():
                n = sum(1 for x in lab if x == code)
                animal_days[s] += n
                per_day[s][d] = n
        shops = t['shops'][30][:8]
        rows.append(dict(episode=t['episode'], shops=shops, animal_days=dict(animal_days),
                         ops={s: dict(v) for s, v in ops.items()},
                         care_by_day={s: [by_day[(s, d)].get('CARE', 0) for d in range(30)] for s in SPECIES.values()},
                         feed_by_day={s: [by_day[(s, d)].get('FEED', 0) for d in range(30)] for s in SPECIES.values()},
                         count_by_day={s: [per_day[s].get(d, 0) for d in range(30)] for s in SPECIES.values()}))
        if (i + 1) % 100 == 0:
            print(f'{i + 1}/{len(paths)}', flush=True)
    out = ROOT / 'results/fresh/mg_tape/care_rule.json'
    out.write_text(json.dumps(rows), encoding='utf-8')

    # summary: care rate by species, split by how many consuming shops the world has
    key_shop = {'SHEEP': ('YARN_STORE',), 'COW': ('PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP'),
                'GOOSE': ('BAKERY', 'BRUNCH_SPOT')}
    for s in ('SHEEP', 'COW', 'GOOSE'):
        print(f'\n{s}: care rate = CARE ops / animal-days, feed rate likewise')
        groups = defaultdict(list)
        for r in rows:
            ad = r['animal_days'].get(s, 0)
            if ad < 10:
                continue
            care = r['ops'].get(s, {}).get('CARE', 0) / ad
            feed = r['ops'].get(s, {}).get('FEED', 0) / ad
            for shop in key_shop[s]:
                groups[(shop, sum(1 for x in r['shops'] if x == shop))].append((care, feed))
        for k in sorted(groups):
            v = groups[k]
            print(f'  {k[0]:<16} x{k[1]}  n={len(v):>3}  care {sum(c for c, _ in v) / len(v):.2f}  feed {sum(f for _, f in v) / len(v):.2f}')


if __name__ == '__main__':
    main()
