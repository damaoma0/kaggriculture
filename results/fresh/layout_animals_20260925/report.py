"""Summarise events.jsonl.gz (from fert_chains.py) into chains.txt and summary.json. Stored data only.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/report.py
"""
import glob
import gzip
import json
import os
import statistics as stt
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
ANIMALS = {'COW', 'SHEEP', 'GOOSE'}
CROPS = {'WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON'}


def dshed(p):
    return min(abs(p[0] - sx) + abs(p[1] - sy) for sx, sy in SHED)


def man(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def via_shed(p, q):
    return min(abs(p[0] - sx) + abs(p[1] - sy) + abs(q[0] - sx) + abs(q[1] - sy) for sx, sy in SHED)


def quad(p):
    return ('N' if p[1] < 5 else 'S') + ('W' if p[0] < 5 else 'E')


QNAME = {'NW': 'first(NW)', 'NE': 'second(NE)', 'SW': 'third(SW)', 'SE': 'fourth(SE)'}


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def pct(a, b):
    return 100.0 * a / b if b else float('nan')


def main():
    recs = []
    with gzip.open(os.path.join(HERE, 'events.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            recs.append(json.loads(line))
    G = len(recs)
    eps = sorted({r['episode'] for r in recs})
    L = []
    P = L.append
    S = {}
    ver_ok = sum(r['verify']['ok'] for r in recs)
    ver_bad = sum(r['verify']['bad'] for r in recs)
    pos_bad = sum(r['verify']['pos_bad'] for r in recs)
    P('Fertilizer chains of DSM (3000+ leader) hands, stored Kaggle replays only (no engine runs)')
    P('=' * 100)
    P(f'Source: data/dsm_replays/episode-*-replay.json, {len(eps)} episodes, {G} DSM seat-games '
      f'(episode 111777242 is DSM vs DSM, both seats counted).')
    P('Method: results/fresh/layout_animals_20260925/fert_chains.py re-applies the engine rules for PICKUP/DROP/PLACE/')
    P('FERTILIZE/COLLECT_FERTILIZER (data/kaggriculture.py::_apply_unit_action) to each recorded pre-step observation +')
    P('recorded action, per unit, and tracks each fertilizer unit (token) from its source to its fate. Replays DO contain')
    P("each seat's private inventories, so the simulation is checked against the recorded post-step inventory:")
    P(f'  unit-steps verified (non-day-boundary): {ver_ok + ver_bad}; fertilizer-count mismatches: {ver_bad}; '
      f'position mismatches: {pos_bad}.')
    P('  At the 30 day-boundary steps (hour 23) inventories are auto-dumped, so those steps are simulated, not checked.')
    P('Attribution: fertilizer is fungible; each FERTILIZE consumes the most recently acquired token (LIFO). FIFO and')
    P('"holdings homogeneous" shares are reported to show how much that choice matters.')
    P('Distances: Manhattan; dshed = distance to the nearest shed-access tile (4,4),(5,4),(4,5),(5,5); "shed visit" =')
    P('the unit stands on a shed-access tile (spawn counts).')
    P('')

    # ---------------------------------------------------------------- flows
    tot = Counter()
    for r in recs:
        tot['collect'] += len(r['collect'])
        tot['pick_units'] += sum(p['n'] for p in r['pick'])
        tot['pick_ops'] += len(r['pick'])
        tot['applied'] += len(r['fert'])
        tot['dep_units'] += sum(d['n'] for d in r['dep'])
        tot['dep_field'] += sum(d['field'] for d in r['dep'])
        for fa in r['fates']:
            tot['fate_' + fa['src'] + '_' + fa['fate'] + ('' if fa['same_trip'] is None else
                                                        ('_sametrip' if fa['same_trip'] else '_aftershed'))] += 1
        tot['sell_req'] += r['market']['sell_req']
        tot['buy_req'] += r['market']['buy_req']
        tot['net_resid'] += r['market']['net_resid']
        tot['moves'] += sum(u['moves'] for u in r['unit_days'])
        tot['unit_steps'] += sum(u['steps'] for u in r['unit_days'])
    autodump = sum(v for k, v in tot.items() if k.endswith('_autodump'))
    P('1) FERTILIZER FLOW PER GAME (mean over %d seat-games)' % G)
    P('-' * 100)
    P(f'  collected in field (effective COLLECT_FERTILIZER): {tot["collect"] / G:7.1f}')
    P(f'  picked up at the shed (units):                     {tot["pick_units"] / G:7.1f}   '
      f'({tot["pick_ops"] / G:.1f} PICKUP ops)')
    P(f'  applied (effective FERTILIZE):                     {tot["applied"] / G:7.1f}')
    P(f'  deposited at shed by DROP/PLACE (units):           {tot["dep_units"] / G:7.1f}   '
      f'(of which field-collected {tot["dep_field"] / G:.1f})')
    P(f'  auto-dumped into the shed at day end (carried):    {autodump / G:7.1f}')
    P(f'  market orders requested: SELL FERTILIZER {tot["sell_req"] / G:.1f}, BUY_PRODUCT FERTILIZER '
      f'{tot["buy_req"] / G:.1f}; shed net market residual {tot["net_resid"] / G:+.1f}/game')
    P(f'  (context: effective moves {tot["moves"] / G:.0f}/game, unit-steps {tot["unit_steps"] / G:.0f}/game)')
    P('')
    S['flow_per_game'] = {k: tot[k] / G for k in tot}
    S['flow_per_game']['autodump'] = autodump / G

    # ---------------------------------------------------------------- 1. source of each FERTILIZE
    F = [dict(f, ep=r['episode'], seat=r['seat']) for r in recs for f in r['fert']]
    nF = len(F)
    src = Counter(f['src'] for f in F)
    fifo = Counter(f['fifo_src'] for f in F)
    homog = sum(1 for f in F if f['held_field'] == 0 or f['held_shed'] == 0)
    field = [f for f in F if f['src'] == 'field']
    chain = [f for f in field if not f['shed_between']]
    after = [f for f in field if f['shed_between']]
    P('2) WHERE DOES EACH FERTILIZE GET ITS FERTILIZER?  (n = %d FERTILIZE ops, %d seat-games)' % (nF, G))
    P('-' * 100)
    P(f'  from an in-field COLLECT by the same unit, same day:  {src["field"]:6d}  {pct(src["field"], nF):5.1f}%  '
      f'(FIFO attribution: {pct(fifo["field"], nF):.1f}%)')
    P(f'     ... carried directly, no shed visit in between:   {len(chain):6d}  {pct(len(chain), nF):5.1f}%')
    P(f'     ... unit passed a shed tile after collecting:      {len(after):6d}  {pct(len(after), nF):5.1f}%')
    P(f'  from a shed PICKUP:                                    {src["shed"]:6d}  {pct(src["shed"], nF):5.1f}%  '
      f'(FIFO: {pct(fifo["shed"], nF):.1f}%)')
    if src.get('unknown'):
        P(f'  unknown (resync):                                      {src["unknown"]:6d}')
    P(f'  holdings homogeneous at the FERTILIZE (attribution unambiguous): {pct(homog, nF):.1f}%')
    pg_field = sorted(pct(sum(1 for f in r['fert'] if f['src'] == 'field'), len(r['fert'])) for r in recs)
    pg_chain = sorted(pct(sum(1 for f in r['fert'] if f['src'] == 'field' and not f['shed_between']), len(r['fert']))
                      for r in recs)
    P(f'  per seat-game field share: min {pg_field[0]:.0f}%, median {stt.median(pg_field):.0f}%, max {pg_field[-1]:.0f}%;'
      f' direct-chain share: min {pg_chain[0]:.0f}%, median {stt.median(pg_chain):.0f}%, max {pg_chain[-1]:.0f}%')
    lag = [f['t'] - f['tA'] for f in field]
    lagc = [f['t'] - f['tA'] for f in chain]
    P(f'  steps from COLLECT to FERTILIZE (field-sourced): mean {mean(lag):.1f}, median {stt.median(lag):.0f}; '
      f'direct chains: mean {mean(lagc):.1f}, median {stt.median(lagc):.0f}')
    lagdist = Counter(min(x, 12) for x in lagc)
    P('  direct-chain lag distribution (steps; 12 = 12+): ' +
      ', '.join(f'{k}:{pct(v, len(lagc)):.0f}%' for k, v in sorted(lagdist.items())))
    crops = Counter(f['crop'] for f in F)
    P('  FERTILIZE by crop: ' + ', '.join(f'{k} {v / G:.1f}/game ({pct(v, nF):.0f}%)' for k, v in crops.most_common()))
    byhalf = Counter(('d0-11' if f['day'] < 12 else 'd12-19' if f['day'] < 20 else 'd20-29', f['src']) for f in F)
    P('  source by season part: ' + '; '.join(
        f'{p}: field {pct(byhalf[(p, "field")], byhalf[(p, "field")] + byhalf[(p, "shed")]):.0f}% of '
        f'{byhalf[(p, "field")] + byhalf[(p, "shed")]}' for p in ('d0-11', 'd12-19', 'd20-29')))
    P('')
    S['fertilize'] = {'n': nF, 'field': src['field'], 'shed': src['shed'], 'chain_direct': len(chain),
                      'field_after_shed': len(after), 'fifo_field': fifo['field'], 'homogeneous': homog,
                      'lag_field_mean': mean(lag), 'lag_chain_median': stt.median(lagc)}

    # ---------------------------------------------------------------- 2. geometry of direct chains
    nC = len(chain)
    dA = [dshed(f['A']) for f in chain]
    dC = [dshed(f['C']) for f in chain]
    closer = sum(1 for a, c in zip(dA, dC) if a < c)
    equal = sum(1 for a, c in zip(dA, dC) if a == c)
    onpath = sum(1 for f in chain if dshed(f['A']) + man(f['A'], f['C']) == dshed(f['C']))
    geo_detour = [dshed(f['A']) + man(f['A'], f['C']) - dshed(f['C']) for f in chain]
    wAC = [f['walk_AC'] for f in chain]
    mAC = [man(f['A'], f['C']) for f in chain]
    wSC = [f['walk_shedC'] for f in chain if f['walk_shedC'] is not None]
    dSC = [dshed(f['C']) for f in chain if f['walk_shedC'] is not None]
    P('3) DIRECT CHAINS (collected in field, carried to the crop with no shed visit between; n = %d)' % nC)
    P('-' * 100)
    P('   Every direct chain is by construction "after the last shed visit and before the crop" (outbound in that sense).')
    P(f'  mean dshed: animal {mean(dA):.2f}, crop {mean(dC):.2f}')
    P(f'  animal nearer the shed than the crop: {pct(closer, nC):.1f}%; same distance {pct(equal, nC):.1f}%; '
      f'animal farther {pct(nC - closer - equal, nC):.1f}%')
    P(f'  animal on a shortest shed->crop path (dshed(A)+|A-C| == dshed(C)): {pct(onpath, nC):.1f}%')
    P(f'  geometric detour of routing shed->animal->crop vs shed->crop: mean {mean(geo_detour):.2f} steps '
      f'(median {stt.median(geo_detour):.0f}; 0 = on the way)')
    P(f'  walked animal->crop: mean {mean(wAC):.2f} moves vs Manhattan |A-C| mean {mean(mAC):.2f} '
      f'(extra = other work done in between)')
    P(f'  walked from last shed visit to the crop (via the animal and any other work): mean {mean(wSC):.2f} vs '
      f'direct dshed(crop) {mean(dSC):.2f}')
    ddist = Counter((dshed(f['A']), dshed(f['C'])) for f in chain)
    P('  animal dshed distribution: ' + ', '.join(f'{k}:{pct(v, nC):.0f}%' for k, v in sorted(Counter(dA).items())))
    P('  crop dshed distribution:   ' + ', '.join(f'{k}:{pct(v, nC):.0f}%' for k, v in sorted(Counter(dC).items())))
    samequad = sum(1 for f in chain if quad(f['A']) == quad(f['C']))
    P(f'  animal and crop in the same quadrant: {pct(samequad, nC):.1f}%')
    anim_of = Counter()
    for r in recs:
        cmap = {(c['t'], c['u']): c['animal'] for c in r['collect']}
        for f in r['fert']:
            if f['src'] == 'field' and not f['shed_between']:
                anim_of[cmap.get((f['tA'], f['u']), '?')] += 1
    P('  direct chains by source animal: ' + ', '.join(f'{k} {pct(v, nC):.0f}%' for k, v in anim_of.most_common()))
    P('')
    S['chains'] = {'n': nC, 'dshed_animal': mean(dA), 'dshed_crop': mean(dC), 'animal_closer': closer,
                   'equal': equal, 'on_shortest_path': onpath, 'geo_detour_mean': mean(geo_detour),
                   'walk_AC_mean': mean(wAC), 'man_AC_mean': mean(mAC), 'walk_shedC_mean': mean(wSC),
                   'dshed_C_mean_for_walk': mean(dSC)}

    # ---------------------------------------------------------------- 3. per unit-day and walking saved
    uds = [u for r in recs for u in r['unit_days']]
    nud = len(uds)
    with_f = [u for u in uds if u['fert'] > 0]
    with_c = [u for u in uds if u['chain_out'] > 0]
    P('4) PER UNIT-DAY  (n = %d unit-days with at least one step)' % nud)
    P('-' * 100)
    P(f'  unit-days with >=1 FERTILIZE: {len(with_f)} ({pct(len(with_f), nud):.1f}%); with >=1 direct chain: '
      f'{len(with_c)} ({pct(len(with_c), nud):.1f}%)')
    P(f'  direct-chained FERTILIZE per unit-day: all unit-days {mean([u["chain_out"] for u in uds]):.2f}; '
      f'unit-days that fertilize {mean([u["chain_out"] for u in with_f]):.2f}; '
      f'unit-days with a chain {mean([u["chain_out"] for u in with_c]):.2f}')
    dist = Counter(min(u['chain_out'], 8) for u in with_f)
    P('  distribution over fertilizing unit-days (8 = 8+): ' +
      ', '.join(f'{k}:{pct(v, len(with_f)):.0f}%' for k, v in sorted(dist.items())))

    # walking-saved counterfactuals
    per_game_up = defaultdict(float)
    per_game_trip = defaultdict(float)
    have_prev = [f for f in chain if f['prev'] is not None]
    sav = []
    act_walk = []
    for f in have_prev:
        cf = via_shed(f['prev'], f['C'])
        direct = man(f['prev'], f['C'])
        sav.append(cf - direct)
        act_walk.append(f['walk_prevC'])
        per_game_up[(f['ep'], f['seat'])] += cf - direct
    prev_is_A = sum(1 for f in have_prev if tuple(f['prev']) == tuple(f['A']) and f['prev_t'] == f['tA'])
    trips = defaultdict(list)
    for f in chain:
        trips[(f['ep'], f['seat'], f['day'], f['u'], f['trip'])].append(f)
    trip_sav = []
    stock_ok = 0
    stock_n = 0
    need_ok = 0
    for key, fs in trips.items():
        fs.sort(key=lambda x: x['t'])
        f0 = fs[0]
        if f0['prev'] is not None:
            s0 = via_shed(f0['prev'], f0['C']) - man(f0['prev'], f0['C'])
            trip_sav.append(s0)
            per_game_trip[(key[0], key[1])] += s0
        st0 = f0.get('shed_stock_trip_start')
        if st0 is not None:
            stock_n += 1
            stock_ok += st0 >= 1
            need_ok += st0 >= len(fs)
    P('')
    P('5) WALKING SAVED BY DIRECT CHAINS vs FETCHING THE FERTILIZER AT THE SHED')
    P('-' * 100)
    P('  (a) task formula, per chained FERTILIZE: counterfactual = dist(prev position, shed) + dist(shed, crop), where')
    P('      prev = where the unit did its previous effective (non-move) op; actual = |prev - crop|.')
    P(f'      n = {len(have_prev)} (prev op was the COLLECT itself in {pct(prev_is_A, len(have_prev)):.0f}%)')
    P(f'      saving per chained FERTILIZE: mean {mean(sav):.2f} steps (median {stt.median(sav):.0f}); '
      f'actual walked prev->crop {mean(act_walk):.2f}')
    P(f'      per game: {sum(per_game_up.values()) / G:.0f} steps = '
      f'{pct(sum(per_game_up.values()), tot["moves"]):.1f}% of all effective moves '
      f'({tot["moves"] / G:.0f}/game)')
    P('      This is an UPPER bound: it charges a separate shed round trip for every single fertilizer.')
    P(f'  (b) one shed detour per trip (a PICKUP of n covers the whole trip; detour inserted before the trip\'s first')
    P(f'      chained FERTILIZE): trips with chains {len(trips)} ({len(trips) / G:.1f}/game, '
      f'{nC / max(1, len(trips)):.2f} chained FERTILIZE per trip)')
    P(f'      saving per trip mean {mean(trip_sav):.2f}; per game {sum(per_game_trip.values()) / G:.0f} steps = '
      f'{pct(sum(per_game_trip.values()), tot["moves"]):.1f}% of effective moves')
    P('  (c) pick the fertilizer up at the shed visit that STARTED the trip (every direct chain starts from one):')
    P('      walking saved = 0 by construction; the chain instead saves 1 PICKUP action per trip '
      f'(~{len(trips) / G:.0f} unit-steps/game) and spends 1 COLLECT per fertilizer.')
    P(f'      shed fertilizer stock at that trip-start step: >=1 in {pct(stock_ok, stock_n):.0f}% of trips, '
      f'>= the trip\'s chained count in {pct(need_ok, stock_n):.0f}% (n = {stock_n}).')
    P('')
    S['walking'] = {'upper_per_game': sum(per_game_up.values()) / G, 'trip_per_game': sum(per_game_trip.values()) / G,
                    'moves_per_game': tot['moves'] / G, 'trips_per_game': len(trips) / G,
                    'upper_per_fert_mean': mean(sav), 'trip_mean': mean(trip_sav),
                    'stock_ge1_share': pct(stock_ok, stock_n), 'stock_ge_need_share': pct(need_ok, stock_n)}

    # ---------------------------------------------------------------- 4. fates of collected fertilizer
    fates = Counter()
    for r in recs:
        for fa in r['fates']:
            key = fa['fate'] + ('' if fa['same_trip'] is None else ('_direct' if fa['same_trip'] else '_aftershed'))
            fates[(fa['src'], key)] += 1
    nfield = sum(v for (s, k), v in fates.items() if s == 'field')
    nshed = sum(v for (s, k), v in fates.items() if s == 'shed')
    P('6) FATE OF FERTILIZER UNITS (per game)')
    P('-' * 100)
    for s_, n_ in (('field', nfield), ('shed', nshed)):
        P(f'  {s_}-sourced: {n_ / G:.1f}/game -> ' + ', '.join(
            f'{k} {v / G:.1f} ({pct(v, n_):.0f}%)' for (s2, k), v in sorted(fates.items(), key=lambda x: -x[1])
            if s2 == s_))
    cs = [c for r in recs for c in r['collect']]
    csd = Counter(dshed(c['A']) for c in cs)
    P(f'  COLLECT locations: mean dshed {mean([dshed(c["A"]) for c in cs]):.2f}; by animal ' +
      ', '.join(f'{k} {v / G:.1f}/game' for k, v in Counter(c['animal'] for c in cs).most_common()))
    straight = sum(1 for c in cs if c['since_shed'] == dshed(c['A']))
    P(f'  COLLECT reached by walking straight from the shed (moves since last shed visit == dshed(animal)): '
      f'{pct(straight, len(cs)):.0f}%')
    P('')
    S['fates'] = {f'{s}|{k}': v / G for (s, k), v in fates.items()}

    # ---------------------------------------------------------------- layout
    tiledays = defaultdict(Counter)   # group -> dshed -> count
    quadc = defaultdict(Counter)
    for r in recs:
        for day in r['layout']:
            for k, x, y in day:
                grp = 'animal' if k in ANIMALS else 'crop' if k in CROPS else 'other'
                tiledays[grp][dshed((x, y))] += 1
                quadc[grp][quad((x, y))] += 1
    allt = Counter(dshed((x, y)) for x in range(10) for y in range(10))
    P('7) DSM LAYOUT: tile-days by distance to shed (day-start boards, all 30 days)')
    P('-' * 100)
    P('  dshed:          ' + ' '.join(f'{d:>6d}' for d in range(9)) + '   mean')
    P('  board tiles %:  ' + ' '.join(f'{pct(allt[d], 100):6.0f}' for d in range(9)) +
      f'   {sum(d * v for d, v in allt.items()) / 100:.2f}')
    for grp in ('animal', 'crop'):
        c = tiledays[grp]
        n_ = sum(c.values())
        P(f'  {grp:7s} %:      ' + ' '.join(f'{pct(c[d], n_):6.1f}' for d in range(9)) +
          f'   {sum(d * v for d, v in c.items()) / n_:.2f}   (n = {n_} tile-days)')
    for grp in ('animal', 'crop'):
        c = quadc[grp]
        n_ = sum(c.values())
        P(f'  {grp} tile-days by quadrant: ' + ', '.join(f'{QNAME[q]} {pct(c[q], n_):.0f}%' for q in
                                                    ('NW', 'NE', 'SW', 'SE')))
    S['layout'] = {g: dict(tiledays[g]) for g in tiledays}
    P('')

    # ---------------------------------------------------------------- comparison with lead_ledger
    P('8) COMPARISON WITH THE OTHER THREAD\'S LEDGER (stored results/fresh/lead_ledger/{leader,ours}_*.json, 12 games:')
    P('   4 each of UMG 16730612, DSM 16732748, Vadim 16770421; engine-hook counts from that thread, not re-run here)')
    P('-' * 100)
    TEAM = {'16732748': 'DSM', '16770421': 'Vadim', '16730612': 'UMG'}
    for side in ('leader', 'ours'):
        tot2 = defaultdict(Counter)
        ng = Counter()
        for fp in sorted(glob.glob(os.path.join(ROOT, 'results', 'fresh', 'lead_ledger', f'{side}_*.json'))):
            d = json.load(open(fp, encoding='utf-8'))
            tm = TEAM.get(d['game'].split(':')[0], '?')
            for grp in ('all', tm):
                ng[grp] += 1
                for dd in d['days']:
                    tot2[grp]['collect'] += dd['eff'].get('COLLECT_FERTILIZER', 0)
                    tot2[grp]['applied'] += dd['eff'].get('FERTILIZE', 0)
                    tot2[grp]['picked'] += dd['picked'].get('FERTILIZER', 0)
                    tot2[grp]['deposited'] += dd['deposited'].get('FERTILIZER', 0)
                    tot2[grp]['autodump'] += (dd.get('carried_mid') or {}).get('FERTILIZER', 0)
                    tot2[grp]['sold'] += dd['sold'].get('FERTILIZER', 0)
                    tot2[grp]['moves'] += dd['move'] - dd['move_noeff']
        for grp in ('all', 'DSM'):
            n_ = ng[grp]
            c = tot2[grp]
            P(f'  {side:6s} {grp:3s} (n={n_:2d}): picked at shed {c["picked"] / n_:5.1f}  collected {c["collect"] / n_:5.1f}  '
              f'applied {c["applied"] / n_:5.1f}  deposited {c["deposited"] / n_:5.1f}  day-end dump '
              f'{c["autodump"] / n_:5.1f}  sold {c["sold"] / n_:5.1f}  moves {c["moves"] / n_:5.0f}')
    fl = S['flow_per_game']
    P(f'  DSM replays here (n={G}): picked at shed {fl["pick_units"]:5.1f}  collected {fl["collect"]:5.1f}  '
      f'applied {fl["applied"]:5.1f}  deposited {fl["dep_units"]:5.1f}  day-end dump {fl["autodump"]:5.1f}  '
      f'sell orders {fl["sell_req"]:5.1f}  moves {fl["moves"]:5.0f}')
    P('  Our executor\'s positions/chains are not stored in that ledger (only counts), so the chain share and walking')
    P('  of OUR hands cannot be measured from stored data; only the flow counts above compare.')
    P('')
    with open(os.path.join(HERE, 'chains.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    with open(os.path.join(HERE, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(S, f, indent=1, default=str)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
