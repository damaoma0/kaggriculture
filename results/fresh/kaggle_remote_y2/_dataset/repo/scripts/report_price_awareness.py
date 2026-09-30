"""Markdown tables for the price-awareness study: reads results/fresh/newphase_20260923/price_awareness/results.json
(scripts/analyze_price_awareness.py) and writes tables.md next to it."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results/fresh/newphase_20260923/price_awareness'
ITEMS = ['SHEEP', 'COW', 'GOOSE', 'STRAWBERRY', 'TOMATO', 'WHEAT', 'CARROT', 'MELON']
DAYS = ['9', '12', '15', '18', '21', '24']


def cell(x):
    if not x:
        return '–'
    return f"{x['delta']:+.3f} [{x['ci'][0]:+.2f},{x['ci'][1]:+.2f}]"


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    r = json.loads((D / 'results.json').read_text(encoding='utf-8'))
    L = []
    L.append(f"n = {r['n_games']} DSM farm-games in {r['n_episodes']} episodes; engine re-resolution mismatches: "
             f"{r['extraction_check']}\n")

    L.append('## Price variation across DSM games (day-start price, coins): mean / SD, and the opponent-caused part (SD)\n')
    L.append('| day | ' + ' | '.join(['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL']) + ' |')
    L.append('|---' * 9 + '|')
    for d in DAYS:
        pv = r['price_variation'][d]
        L.append(f'| {d} | ' + ' | '.join(f"{pv[p]['mean']:.0f} / {pv[p]['sd']:.0f} (opp {pv[p]['opp_part_sd']:.0f}, own {pv[p]['dsm_part_sd']:.0f})"
                                          for p in ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL']) + ' |')

    L.append('\n## Block summary over the 8 items x 6 days (incremental out-of-sample R^2)\n')
    L.append('| model | block | cells | median delta | mean delta | max delta | CI low > 0 | CI high < 0 | median residual share explained |')
    L.append('|---' * 9 + '|')
    for model in ('level', 'flow'):
        for blk in ('PRICE_OWN', 'PRICE_OPP_OWN', 'PRICE_ALL', 'PRICE_OPP', 'CASH', 'OPP', 'ALL'):
            xs = [r[model][d][it][blk] for d in DAYS for it in ITEMS if r[model].get(d, {}).get(it, {}).get(blk)]
            ds = sorted(x['delta'] for x in xs)
            rs = sorted(x['resid_share_explained'] for x in xs if x['resid_share_explained'] is not None)
            L.append(f"| {model} | {blk} | {len(xs)} | {ds[len(ds) // 2]:+.3f} | {sum(ds) / len(ds):+.3f} | {ds[-1]:+.3f} | "
                     f"{sum(x['ci'][0] > 0 for x in xs)} | {sum(x['ci'][1] < 0 for x in xs)} | {rs[len(rs) // 2]:+.3f} |")

    for model, title in (('level', 'Level: day-d count, base = shops DSM could see'),
                         ('flow', 'Flow: day-d count, base = shops + DSM own day-(d-3) board')):
        for blk in ('ALL', 'PRICE_OPP', 'PRICE_ALL', 'CASH', 'OPP', 'PRICE_OWN'):
            L.append(f'\n## {title}; incremental out-of-sample R^2 of block {blk} (measured at day d-3) [95% bootstrap CI]\n')
            L.append('| item | ' + ' | '.join(f'd{d} base / +{blk}' for d in DAYS) + ' |')
            L.append('|---' * 7 + '|')
            for it in ITEMS:
                row = []
                for d in DAYS:
                    x = r[model].get(d, {}).get(it, {}).get(blk)
                    row.append(f"{x['r2_base']:.2f} / {cell(x)}" if x else '–')
                L.append(f'| {it} | ' + ' | '.join(row) + ' |')

    L.append('\n## Pre-specified channels (base = shops + own day-(d-3) board; window = days d-3..d-1)\n')
    L.append('| day | channel | mean y | SD y | incr R^2 [CI] | perm p | partial r [CI] | slope (units per coin) [CI] | SD resid x (coins) | units per 1 SD of x [CI] |')
    L.append('|---' * 10 + '|')
    for d in DAYS:
        for name, x in r['channels'][d].items():
            if not x:
                continue
            if 'note' in x:
                L.append(f"| {d} | {name} | {x['mean_y']} | | {x['note']} | | | | | |"); continue
            pc = x['partial']
            if pc.get('r') is None:
                L.append(f"| {d} | {name} | {x['mean_y']} | {x['sd_y']} | {cell(x)} | {x.get('perm_p')} | – | | | |"); continue
            sx = pc['sd_x_resid']
            L.append(f"| {d} | {name} | {x['mean_y']} | {x['sd_y']} | {cell(x)} | {x.get('perm_p')} | "
                     f"{pc['r']:+.2f} [{pc['r_ci'][0]:+.2f},{pc['r_ci'][1]:+.2f}] | {pc['slope']:+.4f} | {sx} | "
                     f"{pc['slope'] * sx:+.2f} [{pc['slope_ci'][0] * sx:+.2f},{pc['slope_ci'][1] * sx:+.2f}] |")

    L.append('\n## Timing (event step in hours; base = shops visible at the median event day)\n')
    L.append('| event | n | median day | SD h | IQR h | shop R^2 | resid SD h | +CASH [CI] | +PRICE_ALL [CI] | +PRICE_OPP [CI] | resid SD h after cash+price |')
    L.append('|---' * 11 + '|')
    for name, x in r['timing'].items():
        if name.startswith('_') or 'shop_r2' not in x:
            continue
        L.append(f"| {name} | {x['n']} | {x['median_day']} | {x['sd_hours']} | {x['iqr_hours']} | {x['shop_r2']} | {x['resid_sd_hours']} | "
                 f"{cell(x['CASH'])} | {cell(x['PRICE_ALL'])} | {cell(x['PRICE_OPP'])} | {x['CASH+PRICE']['resid_sd_hours_after']} |")
    L.append('\nCash gating: ' + json.dumps(r['timing']['_cash_gating']))

    L.append('\n## Board value index V_d = sum v_i * count_i (coins/day)\n')
    L.append('value per item-day: ' + json.dumps(r['value_per_item_day']) + f"; mean final cash {r['mean_final_cash']}\n")
    L.append('Upper bound = sqrt(max(0, CI high of the +ALL increment)) x SD(V_d): the largest SD of production value (coins/day) '
             'that price / cash / opponent could explain and still be consistent with the data; x remaining days = season coins.\n')
    L.append('| day | mean V | SD V | shop R^2 | SD shop pred | resid RMSE | +ALL [CI] | upper-bound SD (coins/day) | x remaining days | flow +ALL [CI] | flow upper-bound SD | x remaining days | +PRICE_OPP [CI] | +CASH [CI] |')
    L.append('|---' * 14 + '|')
    for d in DAYS:
        v = r['board_value'][d]; a = v['blocks']['ALL']
        ub = max(0.0, a['ci'][1]) ** 0.5 * v['sd_value_per_day']; ubf = max(0.0, a['flow_ci'][1]) ** 0.5 * v['sd_value_per_day']
        L.append(f"| {d} | {v['mean_value_per_day']} | {v['sd_value_per_day']} | {v['shop_r2']} | {v['sd_shop_pred']} | {v['resid_rmse']} | "
                 f"{cell(a)} | {ub:.0f} | {ub * v['remaining_days']:.0f} | "
                 f"{a['flow_delta']:+.3f} [{a['flow_ci'][0]:+.2f},{a['flow_ci'][1]:+.2f}] | {ubf:.0f} | {ubf * v['remaining_days']:.0f} | "
                 f"{cell(v['blocks']['PRICE_OPP'])} | {cell(v['blocks']['CASH'])} |")

    L.append('\n## Feasibility / budget-exactness in DSM\'s own games\n')
    fe = r['feasibility']
    L.append('| day | median cash at day start | p10 | p90 | share < 50 | share < 10 |')
    L.append('|---' * 6 + '|')
    for d, c in fe['day_start_cash'].items():
        L.append(f"| {d} | {c['median']:.0f} | {c['p10']:.0f} | {c['p90']:.0f} | {c['share_below_50']} | {c['share_below_10']} |")
    L.append('\n| period / order | requested per game | filled per game | fill rate |')
    L.append('|---|---|---|---|')
    for k, v in fe['request_vs_fill'].items():
        L.append(f"| {k} | {v['requested_per_game']} | {v['filled_per_game']} | {v['fill_rate']} |")
    for k in fe:
        if k not in ('day_start_cash', 'request_vs_fill'):
            L.append(f'- {k}: {json.dumps(fe[k])}')
    (D / 'tables.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('wrote', D / 'tables.md')


if __name__ == '__main__':
    main()
