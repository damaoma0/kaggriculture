"""Follow-up to thread_shopday_behavior.py: per-product-family targeted contrasts (read-only, reads the
per_game/*.json this script's sibling already wrote under results/fresh/threads_20260928/shopdays/).

For each product whose shop can reveal (WOOL/SHEEP, MILK/COW, EGG/GOOSE, STRAWBERRY, TOMATO, WHEAT, CARROT),
compares, across all 40 games:
  - shed deliveries (during-day DROP/PLACE, and the midnight dump) of that product, on THAT product's own
    reveal day vs all NORMAL days (any game)
  - HARVEST/FEED/CARE/WATER/FERTILIZE/COLLECT_FERTILIZER op counts for that product's source (animal or crop),
    on the reveal day itself, and separately on the reveal day + the following 2 days, vs the per-game NORMAL-day
    baseline rate for the same op family.
"""
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
PER_GAME = ROOT / 'results/fresh/threads_20260928/shopdays/per_game'
DAY0, DAY1 = 11, 28
SRC_OF = {'STRAWBERRY': 'STRAWBERRY', 'TOMATO': 'TOMATO', 'CARROT': 'CARROT', 'WHEAT': 'WHEAT',
          'WOOL': 'SHEEP', 'MILK': 'COW', 'EGG': 'GOOSE'}


def s(xs):
    xs = list(xs)
    return {'n': len(xs), 'mean': (mean(xs) if xs else None), 'sd': (pstdev(xs) if len(xs) > 1 else 0.0)}


def main():
    games = []
    for p in sorted(PER_GAME.glob('*.json')):
        games.append(json.loads(p.read_text(encoding='utf-8')))

    days = list(range(DAY0, DAY1 + 1))
    out = {}
    for product, src in SRC_OF.items():
        reveal_instances = []  # (game, day)
        for g in games:
            for d_str, info in g['reveal'].items():
                d = int(d_str)
                if product in info['products']:
                    reveal_instances.append((g, d))

        def deliv_rate(key):
            rev_vals, nor_vals = [], []
            for g, d in reveal_instances:
                rev_vals.append(g[key].get(str(d), {}).get(product, 0))
            for g in games:
                normal_days_g = [d for d in days if str(d) not in g['reveal']]
                for d in normal_days_g:
                    nor_vals.append(g[key].get(str(d), {}).get(product, 0))
            return s(rev_vals), s(nor_vals)

        deliv_day_rev, deliv_day_nor = deliv_rate('deliv_day')
        deliv_mid_rev, deliv_mid_nor = deliv_rate('deliv_mid')

        def ops_rate(window):
            rev_vals, nor_vals = [], []
            for g, d in reveal_instances:
                win = [dd for dd in range(d, d + window) if dd <= DAY1]
                tot = 0
                for dd in win:
                    c = g['ops'].get(str(dd), {})
                    tot += sum(v for k, v in c.items() if k.split('|')[1] == src)
                rev_vals.append(tot / len(win) if win else 0.0)
            for g in games:
                normal_days_g = [d for d in days if str(d) not in g['reveal']]
                base_tot = 0
                for dd in normal_days_g:
                    c = g['ops'].get(str(dd), {})
                    base_tot += sum(v for k, v in c.items() if k.split('|')[1] == src)
                if normal_days_g:
                    nor_vals.append(base_tot / len(normal_days_g))
            return s(rev_vals), s(nor_vals)

        ops_day0_rev, ops_day0_nor = ops_rate(1)
        ops_win3_rev, ops_win3_nor = ops_rate(3)

        out[product] = {
            'n_reveal_instances': len(reveal_instances),
            'deliv_during_day': {'reveal': deliv_day_rev, 'normal_baseline': deliv_day_nor},
            'deliv_midnight_dump': {'reveal': deliv_mid_rev, 'normal_baseline': deliv_mid_nor},
            'ops_on_reveal_day_only': {'reveal': ops_day0_rev, 'normal_baseline': ops_day0_nor},
            'ops_reveal_day_plus2': {'reveal': ops_win3_rev, 'normal_baseline': ops_win3_nor},
        }

    out_path = ROOT / 'results/fresh/threads_20260928/shopdays/targeted_by_product.json'
    out_path.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))
    print('wrote', out_path)


if __name__ == '__main__':
    main()
