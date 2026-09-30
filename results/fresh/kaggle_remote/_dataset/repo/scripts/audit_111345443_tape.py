"""Reproducible descriptive audit of the unchanged mgt_m1 episode 111345443.

Uses recorded actions and the exact game engine. Donor rankings see only shops
revealed at the checkpoint. They are retrieval diagnostics, not profit estimates.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_production_plan_fit import LABELS, load_library
from research_labour_profit import Simulator, engine

EPISODE = 111345443
OUT = ROOT / f'results/fresh/all_umg_m1/diagnosis/{EPISODE}_deep.json'


def grouping(trace, start, stop):
    product = defaultdict(lambda: [0, 0, 0, 0])
    spend = defaultdict(lambda: [0, 0])
    for day in range(start, stop):
        for key, (units, revenue) in trace['sales'].get(str(day), {}).items():
            side, item = key.split(':', 1)
            i = 0 if side == 'own' else 2
            product[item][i] += units
            product[item][i + 1] += revenue
        for key, price in trace['spend'].get(str(day), {}).items():
            side, item = key.split(':', 1)
            spend[item][0 if side == 'own' else 1] += price
    return dict(days=[start, stop - 1], products=dict(product), spending=dict(spend),
                revenue=[sum(v[1] for v in product.values()), sum(v[3] for v in product.values())],
                total_spending=[sum(v[0] for v in spend.values()), sum(v[1] for v in spend.values())])


def main():
    ns, library = load_library()
    tapes = library['tapes']
    by_ep = {int(t['ep']): t for t in tapes}
    trace = json.loads((ROOT / f'results/fresh/larger_shift_20260923/sheep/worst_loss_trace_{EPISODE}.json').read_text())['mgt_m1']
    plan = json.loads((ROOT / f'results/fresh/all_umg_m1/plans/{EPISODE}.json').read_text())
    loss = json.loads((ROOT / f'results/fresh/all_umg_m1/losses/{EPISODE}.json').read_text())
    diagnosis = json.loads((ROOT / f'results/fresh/all_umg_m1/diagnosis/{EPISODE}.json').read_text())
    with gzip.open(ROOT / f'data/ladder_panel/56395605/{EPISODE}.json.gz', 'rt', encoding='utf8') as f:
        game = json.load(f)
    seat = game['seat']
    actions = [None, None]
    actions[seat], actions[1-seat] = game['our_actions'], game['opp_actions']
    E = engine()
    snapshots = {}
    no_effect = [defaultdict(Counter), defaultdict(Counter)]
    no_effect_details = []
    commands = [defaultdict(Counter), defaultdict(Counter)]
    crop_service = [defaultdict(lambda: defaultdict(Counter)), defaultdict(lambda: defaultdict(Counter))]
    with Simulator(game) as sim:
        original_interpreter = E.interpreter
        original_unit = E._apply_unit_action

        def interpreter(state, env):
            day = sim.t // 24
            if sim.t % 24 == 0:
                obs = state[seat].observation
                snapshots[day] = dict(
                    shops=list(obs.town.unlocked_shops),
                    own_labels=ns['_mgt_labels'](ns['_mgt_board'](obs.farms[seat])),
                    opponent_labels=ns['_mgt_labels'](ns['_mgt_board'](obs.farms[1-seat])),
                    cash=[f['money'] for f in obs.farms])
            return original_interpreter(state, env)

        def unit(farm, private, idx, action, *args, **kwargs):
            side = sim.seats[id(farm)]
            op = action[0] if action else 'PASS'
            commands[side][sim.t//24][op] += 1
            if idx >= len(private['inventories']):
                return original_unit(farm, private, idx, action, *args, **kwargs)
            pos = E._farmer_position(farm, idx)
            if pos is None:
                return original_unit(farm, private, idx, action, *args, **kwargs)
            before = (deepcopy(private['inventories'][idx]), dict(private['seeds']), deepcopy(farm['tiles'][pos[1]][pos[0]]))
            result = original_unit(farm, private, idx, action, *args, **kwargs)
            after = (private['inventories'][idx], private['seeds'], farm['tiles'][pos[1]][pos[0]])
            if before != after and op in ('WATER', 'FERTILIZE', 'HARVEST', 'DIG') and isinstance(before[2], dict):
                crop = before[2].get('crop')
                if crop:
                    crop_service[side][sim.t//24][op][crop] += 1
            if op in ('PLANT', 'HARVEST', 'WATER', 'CARE', 'FEED', 'FERTILIZE', 'COLLECT_FERTILIZER', 'DIG') and before == after:
                no_effect[side][sim.t//24][op] += 1
                if side == seat:
                    no_effect_details.append(dict(day=sim.t//24, hour=sim.t%24, op=op,
                                                  crop=before[2].get('crop') if isinstance(before[2],dict) else None,
                                                  fertilizer=before[0].get('FERTILIZER',0), pos=list(pos)))
            return result

        E.interpreter = interpreter
        E._apply_unit_action = unit
        try:
            result = sim.run(sim.initial, 0, 719, actions, capture=True)
        finally:
            E.interpreter = original_interpreter
            E._apply_unit_action = original_unit
    assert result['money'] == game['rewards']
    assert sum(no_effect[seat].values(), Counter()) == Counter(loss['no_effect'][0])

    cfg = ns['_MGT_CFG']
    ranks = {}
    for day in (9, 12, 15, 18, 21, 24, 27):
        snap = snapshots[day]
        shops = snap['shops']
        board = snap['own_labels']
        k = len(shops)
        current_ep = int([h for h in plan['history'] if h[0] <= day][-1][1])
        current_index = next(i for i, t in enumerate(tapes) if int(t['ep']) == current_ep)
        vectors = [ns['_mgt_vec'](shops, j) for j in range(9)]
        mine = [j for j, x in enumerate(board) if x in ('go', 'co', 'sh')]
        rows = []
        all_exact = []
        for i, t in enumerate(tapes):
            h = sum(x != y for x, y in zip(board, t['lab'][day]))
            if t['shops'][:k] == shops:
                all_exact.append(dict(ep=int(t['ep']), hamming=h,
                                      assets={p: t['counts'][day][p] for p in LABELS}))
            if h > cfg.get('max_hamming', 8) and i != current_index:
                continue
            strand = sum(t['lab'][day][j] not in ('go', 'co', 'sh') and
                         t['lab'][min(29, day+2)][j] not in ('go', 'co', 'sh') for j in mine)
            distance = ns['_mgt_distance'](vectors, shops, t, k)
            if i == current_index and h > cfg.get('max_hamming', 8):
                distance += cfg.get('incompatible_penalty', 4)
            score = distance + cfg.get('strand_penalty', 0) * strand + cfg.get('hamming_weight', 0) * h
            exact = t['shops'][:k] == shops
            counts = t['counts'][day]
            rows.append(dict(ep=int(t['ep']), score=round(score, 2), demand=round(distance, 2),
                             hamming=h, strand=strand, exact_known_shops=exact,
                             donor_shops=t['shops'][:k],
                             assets={p: counts[p] for p in LABELS}))
        rows.sort(key=lambda r: (r['score'], 0 if r['ep'] == current_ep else 1, r['hamming'],
                                 next(i for i,t in enumerate(tapes) if int(t['ep']) == r['ep'])))
        exact = [r for r in rows if r['exact_known_shops']]
        ranks[str(day)] = dict(current_ep=current_ep, current=next(r for r in rows if r['ep'] == current_ep),
                               eligible=len(rows), exact_known_shop_candidates=len(exact),
                               best_exact=exact[:3], all_exact=sorted(all_exact, key=lambda x:x['hamming'])[:3], top=rows[:10])

    intervals = [grouping(trace, a, b) for a,b in ((0,9),(9,15),(15,18),(18,24),(24,30))]
    cash_path = {str(d): {'own': snapshots[d]['cash'][seat], 'opponent': snapshots[d]['cash'][1-seat],
                          'margin': snapshots[d]['cash'][seat]-snapshots[d]['cash'][1-seat]}
                 for d in (0, 9, 12, 15, 18, 21, 24, 27, 29)}
    escaped = [dict(species=x['species'], placed_day=x['placed_day'], escaped_day=x['escaped_day'],
                    last_production_day=x['production'][-1]['day'] if x['production'] else None)
               for x in diagnosis['cohorts'] if x['seat'] == seat and x['escaped_day'] is not None]
    prices = {str(d): {p: next(x['opening_price'] for x in loss['daily'] if x['day']==d and x['product']==p)
                       for p in ('STRAWBERRY','WOOL','MILK','WHEAT','CARROT','TOMATO')}
              for d in (0,3,6,9,12,15,18,21,24,27,29)}
    strawberry_work = []
    strawberry_cohorts = []
    for side in (seat, 1-seat):
        plants = [x for x in result['work'] if x['seat']==side and x['cmd'][0]=='PLANT' and x['cmd'][1]=='STRAWBERRY']
        harvests = [x for x in result['work'] if x['seat']==side and x['cmd'][0]=='HARVEST' and x['delta'].get('STRAWBERRY',0)>0]
        cohorts = []
        for plant in plants:
            pos = tuple(plant['pos'])
            when = plant['t']//24
            h = [x for x in harvests if tuple(x['pos']) == pos and x['t'] > plant['t']]
            later_plant = min((x['t'] for x in plants if tuple(x['pos'])==pos and x['t']>plant['t']), default=720)
            digs = [x for x in result['work'] if x['seat']==side and x['cmd'][0]=='DIG'
                    and tuple(x['pos'])==pos and plant['t']<x['t']<later_plant]
            dig = digs[0] if digs else None
            cutoff = min(dig['t'] if dig else 720, later_plant)
            h = [x for x in h if x['t'] < cutoff]
            cohorts.append(dict(pos=list(pos), planted_day=when,
                                harvested_units=sum(x['delta']['STRAWBERRY'] for x in h),
                                harvest_days=[x['t']//24 for x in h],
                                dug_day=dig['t']//24 if dig else None))
        strawberry_cohorts.append(cohorts)
        strawberry_work.append(dict(plants_by_day=dict(Counter(x['t']//24 for x in plants)),
                                    harvests_by_day=dict(Counter(x['t']//24 for x in harvests)),
                                    units_by_day=dict(Counter({d:sum(x['delta']['STRAWBERRY'] for x in harvests if x['t']//24==d)
                                                               for d in range(30)})),
                                    total_harvests=len(harvests), total_units=sum(x['delta']['STRAWBERRY'] for x in harvests)))
    for i, side in enumerate((seat, 1-seat)):
        strawberry = next(x for x in loss['products'] if x['product']=='STRAWBERRY')
        label = 'ours' if i == 0 else 'opponent'
        assert strawberry_work[i]['total_units'] == strawberry[label]['produced']
        assert sum(strawberry_work[i]['plants_by_day'].values()) == loss['planted'][i]['STRAWBERRY']
        assert sum(crops.get('FERTILIZE', {}).get(crop, 0)
                   for crops in crop_service[side].values()
                   for crop in ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON')) == loss['products'][-1][label]['consumed']
    doc = dict(episode=EPISODE, validated=True, final=result['money'],
               actual_shops=game['shops'][29], donor_shops=by_ep[110141763]['shops'],
               cash_path=cash_path, intervals=intervals, ranks=ranks,
               board_counts={str(d): dict(ours=dict(Counter(snapshots[d]['own_labels'])),
                                          opponent=dict(Counter(snapshots[d]['opponent_labels'])))
                             for d in (9,12,15,18,21,24,27,29)},
               price_path=prices, escaped=escaped,
               strawberry_work=strawberry_work,
               strawberry_cohorts=strawberry_cohorts,
               crop_service=[{str(d):{op:dict(crops) for op,crops in by_op.items()}
                              for d,by_op in one.items()} for one in crop_service],
               no_effect_by_day={str(d): dict(no_effect[seat][d]) for d in range(30)},
               no_effect_details=no_effect_details,
               commands_by_day={str(d): dict(commands[seat][d]) for d in range(30)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding='utf8')
    print(json.dumps(dict(path=str(OUT), final=doc['final'], cash_path=cash_path,
                          ranks={d:dict(current=v['current'], eligible=v['eligible'],
                                        exact_candidates=v['exact_known_shop_candidates'],
                                        best_exact=v['best_exact'][:1]) for d,v in ranks.items()},
                          escaped=escaped), indent=2))


if __name__ == '__main__':
    main()
