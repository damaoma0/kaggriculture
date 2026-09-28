"""Saved-data animal production/collection accounting; no engine or policy calls.

Reads only frozen V12/V13 development games. Biological increments are observed
on surviving same-cohort tiles; gross and cap loss follow the official refresh
order, including escape before production and care banking after production.
"""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from diagnose_v8_daily_product_flow_20260928 import animal_action_trace, flat, stocks

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY = MAIN / 'results/fresh/semantic_strategy_20260928'
ENGINE = MAIN / '.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py'
VERSIONS = ('strategy_v12_kb115lt2_runtime_fast', 'strategy_v13_kb115lt2_harvest_exchange')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def animals_from_engine():
    tree = ast.parse(ENGINE.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ANIMALS' for t in n.targets))
    return ast.literal_eval(node.value)


def identity(tile):
    return (tile['animal'], tile['placed_day']) if tile.get('animal') else None


def ledger_delta(game, seat, day, key):
    a, b = [game['daily'][seat][d].get(key, {}) for d in (day, day+1)]
    return {k: b.get(k, 0)-a.get(k, 0) for k in set(a)|set(b)}


def side_audit(game, actions, seat, animals):
    trace = animal_action_trace(game, actions, seat)
    obs = {r['day']: r['current_observation'] for r in game['diagnostics'][seat]}
    products = [r['product'] for r in animals.values()]
    births, exits, events, daily, cohorts = [], [], [], [], {}
    commitments = []
    for diag in game.get('final_diagnostics', {}).get(str(seat), []):
        if isinstance(diag, dict):
            commitments.extend(diag.get('retirements', []))
    for day in range(30):
        before = flat(obs[day]); after = flat(obs[day+1]) if day < 29 else None
        day_trace = trace['days'][day]
        harvests = {x['tile']: x['dawn_yield'] if x['harvest_hour'] is not None else 0 for x in day_trace['animal_tiles']}
        counters = {p: Counter() for p in products}
        for tile_index, old in enumerate(before):
            ident = identity(old)
            if ident is None:
                continue
            species, birth = ident; spec = animals[species]; product = spec['product']
            key = f'{tile_index}:{species}:{birth}'
            co = cohorts.setdefault(key, dict(tile=tile_index, species=species, birth=birth, first_possible_output_day=birth+spec['first_yield_day'],
                counts=Counter(), observed_production_days=[], observed_exit_day=None))
            harvested = harvests.get(tile_index, 0); old_held = old.get('yield_units', 0); remaining = old_held-harvested
            assert remaining >= 0
            counters[product]['dawn_held'] += old_held
            counters[product]['collected'] += harvested
            co['counts']['collected'] += harvested
            if after is None:
                counters[product]['final_held_after_last_executed_action'] += remaining
                continue
            new = after[tile_index]
            survives = identity(new) == ident
            scheduled = day+1-birth-spec['first_yield_day'] >= 0 and (day+1-birth-spec['first_yield_day']) % spec['interval'] == 0
            if not survives:
                matched = [r for r in commitments if r.get('tile') == tile_index and r.get('animal') == species and r.get('first_unfed_day') == day-1]
                ex = dict(tile=tile_index, species=species, product=product, birth=birth, exit_refresh_day=day,
                    absent_dawn=day+1, remaining_held_lost=remaining, dawn_care_bank=old.get('pending_care_bonus', 0),
                    scheduled_production_skipped_by_escape=scheduled, matching_recorded_intent=matched,
                    intention_known=seat == game['case']['seat'])
                exits.append(ex); co['observed_exit_day'] = day+1
                counters[product]['exit_held_loss'] += remaining; co['counts']['exit_held_loss'] += remaining
                counters[product]['exits'] += 1
                assert old.get('consecutive_unfed') == 1, (day, tile_index, old)
                continue
            retained = new.get('yield_units', 0)-remaining
            assert retained >= 0, (day, tile_index, retained)
            fed = new.get('consecutive_unfed') == 0
            prior_bank = old.get('pending_care_bonus', 0)
            bonus = prior_bank if fed and scheduled else 0
            gross = 1+bonus if scheduled else 0
            assert new.get('yield_units', 0) == min(spec['max_held'], remaining+gross), (day, tile_index, old, new, harvested)
            cap_loss = gross-retained
            assert cap_loss >= 0
            post_production_bank = 0 if scheduled else prior_bank
            banked = new.get('pending_care_bonus', 0)-post_production_bank
            assert banked in (0, 1) and (not banked or fed), (day, tile_index, prior_bank, new)
            measures = dict(retained_biological=retained, gross_before_cap=gross, cap_loss=cap_loss,
                production_events=int(scheduled), paid_care_bonus=bonus, fed_surviving_animal_days=int(fed),
                new_care_banked=banked, first_output_events=int(scheduled and day+1==birth+spec['first_yield_day']))
            counters[product].update(measures); co['counts'].update(measures)
            if scheduled:
                co['observed_production_days'].append(day+1)
                events.append(dict(tile=tile_index, species=species, product=product, birth=birth, available_dawn=day+1,
                    remaining_before_refresh=remaining, fed=fed, prior_bank=prior_bank, bonus_paid=bonus,
                    gross_before_cap=gross, retained_biological=retained, capacity_loss=cap_loss, next_held=new.get('yield_units', 0),
                    first_output=day+1==birth+spec['first_yield_day']))
        if after is not None:
            for tile_index, new in enumerate(after):
                if identity(new) and identity(new) != identity(before[tile_index]):
                    spec = animals[new['animal']]
                    assert new['placed_day'] == day and new.get('yield_units', 0) == 0
                    births.append(dict(tile=tile_index, species=new['animal'], product=spec['product'], birth=day,
                        observed_dawn=day+1, first_possible_output_day=day+spec['first_yield_day']))
                    counters[spec['product']]['births'] += 1
        opening = stocks(obs[day]); closing = stocks(obs[day+1]) if after is not None else None
        physical, sold, rev, spent = (ledger_delta(game, seat, day, k) for k in ('physical', 'sold_units', 'revenue', 'spend'))
        for product, values in counters.items():
            assert values['collected'] == physical.get('produced:'+product, 0)
            assert not spent.get('BUY_PRODUCT:'+product, 0), (day, product, spent)
            values['sold'] = sold.get(product, 0); values['revenue'] = rev.get(product, 0)
            values['discard_exact'] = opening[product]+values['collected']-values['sold']-closing[product] if closing is not None and opening is not None else None
            assert values['discard_exact'] is None or values['discard_exact'] >= 0
            values['opening_private_stock'] = opening[product] if opening is not None else None
            values['closing_private_stock'] = closing[product] if closing is not None else None
        daily.append(dict(day=day, products={k: dict(v) for k, v in counters.items()}))
    summaries = {}
    for product in products:
        fields = ('retained_biological', 'gross_before_cap', 'cap_loss', 'production_events', 'paid_care_bonus',
            'new_care_banked', 'first_output_events', 'fed_surviving_animal_days', 'exit_held_loss', 'births', 'exits', 'collected', 'sold', 'revenue')
        s = {k: sum(row['products'][product].get(k, 0) for row in daily) for k in fields}
        s['final_held_after_last_executed_action'] = daily[-1]['products'][product].get('final_held_after_last_executed_action', 0)
        initial_held = daily[0]['products'][product].get('dawn_held', 0)
        assert initial_held+s['retained_biological'] == s['collected']+s['exit_held_loss']+s['final_held_after_last_executed_action'], (product, s)
        assert s['gross_before_cap'] == s['retained_biological']+s['cap_loss']
        known_discard = [row['products'][product]['discard_exact'] for row in daily[:-1]]
        s['discard_through_d29_dawn'] = sum(known_discard) if all(n is not None for n in known_discard) else None
        stock_gap = s['collected']-s['sold']
        assert stock_gap >= 0
        s['unresolved_final_private_stock_plus_unobserved_discard'] = stock_gap-s['discard_through_d29_dawn'] if s['discard_through_d29_dawn'] is not None else stock_gap
        s['unobserved_discard_window'] = 'D29 only' if s['discard_through_d29_dawn'] is not None else 'whole season: rival private stock absent'
        assert s['unresolved_final_private_stock_plus_unobserved_discard'] >= 0
        s['full_season_discard_exact'] = s['discard_through_d29_dawn'] if s['unresolved_final_private_stock_plus_unobserved_discard'] == 0 and s['discard_through_d29_dawn'] is not None else 0 if stock_gap == 0 else None
        s['mean_sale_price'] = s['revenue']/s['sold'] if s['sold'] else None
        summaries[product] = s
    return dict(seat=seat, summary=summaries, daily=daily, production_events=events, births=births, exits=exits,
        cohorts=list(cohorts.values()), trace_verification={k:trace[k] for k in ('early_position_snapshots_verified', 'daily_species_harvest_balances_verified')})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'results/fresh/semantic_kb115lt2_recovery/v13_animal_quantities_audit.json')
    args = parser.parse_args(); animals = animals_from_engine(); cases=[]; sources={str(ENGINE):sha(ENGINE)}
    for case in (f'live-{i:02d}' for i in range(8)):
        arms={};games=[]
        for version in VERSIONS:
            p=STUDY/'runs'/version/'development/live'/(case+'.json');a=p.with_suffix('.actions.json')
            game=json.loads(p.read_text());actions=json.loads(a.read_text());sources.update({str(x):sha(x) for x in (p,a)})
            games.append(game)
            assert game['completed'] and game['eligible'] and game['ledger_verified']
            seat=game['case']['seat']
            arms[version]=dict(margin=game['margin'], shops=game['shops'], own=side_audit(game,actions,seat,animals),
                rival=side_audit(game,actions,1-seat,animals), final_ledgers={'own':game['daily'][seat][-1], 'rival':game['daily'][1-seat][-1]})
        first_shop = next(((i+1)*3 for i,(a,b) in enumerate(zip(games[0]['shops'],games[1]['shops'])) if a != b), 30)
        same_birth_counts = Counter((r['species'],r['birth']) for r in arms[VERSIONS[0]]['own']['births']) == Counter((r['species'],r['birth']) for r in arms[VERSIONS[1]]['own']['births'])
        cases.append(dict(case=case,arms=arms,own_birth_counts_by_species_and_day_identical=same_birth_counts,
            first_differing_shop_day=first_shop, cash_delta_before_that_day_trading={
                role:games[1]['daily'][s][first_shop]['money']-games[0]['daily'][s][first_shop]['money'] for role,s in (('own',seat),('rival',1-seat))}))
    result=dict(scope=__doc__,new_games=0,cases=cases,source_hashes=sources,animal_constants=animals,
        script_sha256=sha(Path(__file__)),trace_helper_sha256=sha(ROOT/'scripts/diagnose_v8_daily_product_flow_20260928.py'),
        accounting_notes=[
            'Retained biological = next-dawn held minus unharvested old held, only for surviving identical species/birth/tile cohorts.',
            'Official refresh checks two unfed nights/escape before production. Scheduled output on an escaping animal is not counted as actual gross production.',
            'For surviving output events, gross = 1 plus prior-dawn care bank if fed. The cap applies before today\'s fed+care adds the next bank.',
            'Harvest means collection of existing held units. It is not biological production.',
            'Endogenous natural shop differences are retained. Quantity/revenue differences do not identify isolated feature profit.',
            'There are 719 executed steps through D29 H22; no final D29 night refresh. Final held output is D29 dawn held minus successful final-day harvest.',
            'Private stock is absent for rivals. Full-season harvest=sales can prove zero discard and zero final stock; otherwise their stock/discard split remains unresolved.',
            'Recorded retirement intent is checked only when available. Held units lost on an intentional exit are an accounting cost, not automatically a policy error.'
        ])
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output),cases=[dict(case=c['case'],delta={p:{k:c['arms'][VERSIONS[1]]['own']['summary'][p][k]-c['arms'][VERSIONS[0]]['own']['summary'][p][k] for k in ('gross_before_cap','cap_loss','retained_biological','collected','sold','exit_held_loss','paid_care_bonus','production_events')} for p in ('MILK','WOOL','EGG')}) for c in cases]),indent=2))


if __name__ == '__main__':
    main()
