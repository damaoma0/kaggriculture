"""Saved-data-only V8 live03/06 production, inventory and retirement diagnosis.

No engine, policy, agent, or qualification calls. All game and training inputs
are read from the original workspace; output is confined to this worktree.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY = SOURCE / 'results/fresh/semantic_strategy_20260928'
OUT = ROOT / 'results/fresh/semantic_kb115lt2_recovery/diagnostics/v8_live03_live06'
PRODUCTS = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'MILK', 'WOOL', 'EGG', 'FERTILIZER')
ANIMALS = {'COW': ('MILK', 8, 2), 'SHEEP': ('WOOL', 6, 3), 'GOOSE': ('EGG', 4, 1)}
LABELS = {'co': 'COW', 'sh': 'SHEEP', 'go': 'GOOSE'}
HASHES = {}


def read(path):
    raw = path.read_bytes()
    HASHES[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def flat(obs):
    return [t if isinstance(t, dict) else {} for row in obs['own_farm']['tiles'] for t in row]


def identity(t):
    if t.get('animal'):
        return t['animal'], t['placed_day']
    if t.get('crop'):
        return t['crop'], t['planted_day']
    return None


def stocks(obs):
    private = obs.get('private')
    if private is None:
        return None
    result = Counter(private.get('shed', {}))
    for inventory in private.get('inventories', []):
        result.update(inventory)
    return result


def field(tiles):
    counts = Counter()
    for tile in tiles:
        if tile.get('animal'):
            counts[ANIMALS[tile['animal']][0]] += tile.get('yield_units', 0)
            counts['FERTILIZER'] += int(tile.get('fertilizer_available', False))
        elif tile.get('crop'):
            counts[tile['crop']] += tile.get('yield_units', 0)
    return counts


def delta(a, b, key):
    return {k: b.get(key, {}).get(k, 0)-a.get(key, {}).get(k, 0)
            for k in sorted(set(a.get(key, {})) | set(b.get(key, {})))}


def animal_action_trace(game, actions, seat):
    """Reconstruct positions only, not a gameplay rollout.

    Directions ignore land/occupancy in the official rules. The next action's
    full hands list identifies successful spawns; fixed NWSE min-occupancy spawn
    reproduces all 120 saved early positions. Every daily milk/wool/egg harvest
    is independently checked against the observed physical ledger.
    """
    shed = ((4,4),(5,4),(4,5),(5,5))
    dirs = {'NORTH':(0,-1),'SOUTH':(0,1),'WEST':(-1,0),'EAST':(1,0)}
    snapshots={r['day']:r['current_observation'] for r in game['diagnostics'][seat]}
    early={r['step']:r for r in game['early_window_audit']} if seat==game['case']['seat'] else {}
    rows=[];checked=0
    for day in range(30):
        farm=snapshots[day]['own_farm'];tiles=flat(snapshots[day])
        pos=[tuple(farm['farmer'])]+[tuple(x) for x in farm['hands']]
        ready={i:dict(tile=i,species=t['animal'],birth=t['placed_day'],dawn_yield=t.get('yield_units',0),
                next_production=min([d for d in range(day+1,31) if d-t['placed_day']>=ANIMALS[t['animal']][1] and (d-t['placed_day']-ANIMALS[t['animal']][1])%ANIMALS[t['animal']][2]==0] or [None]),
                pending_bonus=t.get('pending_care_bonus',0),visits=[],harvest_hour=None)
            for i,t in enumerate(tiles) if t.get('animal')}
        harvested=Counter();units=[];market=[]
        for step in range(day*24,min((day+1)*24,len(actions[seat]))):
            action=actions[seat][step];cmds=[action.get('farmer',['PASS'])]+action.get('hands',[])
            assert len(pos)==len(cmds),(day,step,len(pos),len(cmds))
            if step in early:
                e=early[step]
                assert pos==[tuple(e['farmer'])]+[tuple(x) for x in e['hands']],(day,step,'positions')
                checked+=1
            for unit,(xy,cmd) in enumerate(zip(pos,cmds)):
                tile=xy[1]*10+xy[0];op=cmd[0] if cmd else 'PASS'
                units.append(dict(hour=step%24,unit=unit,tile=tile,command=cmd))
                if tile in ready and op not in dirs:
                    ready[tile]['visits'].append(dict(hour=step%24,unit=unit,command=cmd))
                    if op=='HARVEST' and ready[tile]['harvest_hour'] is None:
                        ready[tile]['harvest_hour']=step%24
                        harvested[ANIMALS[ready[tile]['species']][0]]+=ready[tile]['dawn_yield']
                if op in dirs:
                    dx,dy=dirs[op];n=(xy[0]+dx,xy[1]+dy)
                    if 0<=n[0]<10 and 0<=n[1]<10:pos[unit]=n
            for order in (action.get('market') or [])[:10]:
                market.append(dict(hour=step%24,order=order))
            if step%24<23 and step+1<len(actions[seat]):
                new_count=1+len(actions[seat][step+1].get('hands',[]))-len(pos)
                assert new_count>=0
                for _ in range(new_count):
                    occupancy=Counter(pos)
                    pos.append(min(shed,key=lambda p:(occupancy[p],shed.index(p))))
        a,b=game['daily'][seat][day:day+2]
        observed=delta(a,b,'physical')
        assert all(harvested[p]==observed.get('produced:'+p,0) for p in ('MILK','WOOL','EGG')),(game['case']['id'],seat,day,harvested,observed)
        rows.append(dict(day=day,animal_tiles=list(ready.values()),commands=units,market_requests=market,
            issued_op_counts=dict(Counter(x['command'][0] for x in units if x['command']))))
    return dict(days=rows,early_position_snapshots_verified=checked,
        daily_species_harvest_balances_verified=90,
        limitation='Commands show issued jobs and positions, not the internal scheduler rationale. Market requests are not assumed fully filled.')


def native_retirements(model):
    # Compact board label 'co' aliases a cow and an empty coop. Use the
    # independently validated exact-cohort training rows, never board labels.
    by_source = {}
    for r in model['rows']:
        by_source.setdefault(r['meta']['source'], {})[r['day']] = r
    rows = []
    for source, days in sorted(by_source.items()):
        for day in range(6,29):
            current, after = days[day], days[day+1]
            old = {(r['species'],r['birth']):r['count'] for r in current['features']['own_animal_cohorts']}
            new = {(r['species'],r['birth']):r['count'] for r in after['features']['own_animal_cohorts']}
            for (species,birth), n in old.items():
                for _ in range(max(0,n-new.get((species,birth),0))):
                    rows.append(dict(episode=current['meta']['episode'],source=source,
                        species=species,birth=birth,first_unfed_day=day-1,
                        disappearance_day=day+1,
                        before_first_possible_output=day+1 <= birth+ANIMALS[species][1]))
    return dict(episodes=len(by_source), observed_cohort_exits=rows,
        before_first=[r for r in rows if r['before_first_possible_output']],
        by_day_species={str(d): dict(Counter(r['species'] for r in rows if r['first_unfed_day']==d)) for d in range(29)},
        caveat='Validated morning cohorts D6..29. An animal disappearing at dawn d+1 necessarily reached its second unfed night at end of d, so inferred first-unfed is d-1. Private native intention is unavailable. Compact co board labels alias empty coops and cows and are deliberately unused.')


def case_data(case, service):
    path = STUDY / 'runs/strategy_v8_kb115lt2_readiness/development/live' / f'{case}.json'
    g = read(path)
    actions = read(path.with_name(path.stem+'.actions.json'))
    assert g['completed'] and g['eligible'] and g['ledger_verified'] is True
    seat = g['case']['seat']
    plans = {r['day']: r for r in g['final_diagnostics'][str(seat)]}
    sw = next(row for row in service['games'] if row['case']['id']==case)
    result = dict(case=case, own_seat=seat, margin=g['margin'], shops=g['shops'],
        engine_audit=g['engine_audit'], sides={}, retirement_events=[],animal_action_traces={})
    for side, s in (('ours', seat), ('rival', 1-seat)):
        snapshots = {r['day']: r['current_observation'] for r in g['diagnostics'][s]}
        daily = []
        for day in range(30):
            obs = snapshots[day]
            before = flat(obs)
            after = flat(snapshots[day+1]) if day < 29 else None
            a, b = g['daily'][s][day:day+2]
            phys, sold, revenue, spending = (delta(a,b,k) for k in ('physical','sold_units','revenue','spend'))
            assert abs(b['money']-a['money']-sum(revenue.values())+sum(spending.values())) < 1e-8
            start_field, end_field = field(before), field(after) if after is not None else None
            start_stock = stocks(obs)
            end_stock = stocks(snapshots[day+1]) if day < 29 else None
            added, removed, gross, animal_exits = Counter(), Counter(), Counter(), Counter()
            production_events=[]
            if after is not None:
                for tile_index,(old, new) in enumerate(zip(before, after)):
                    old_id, new_id = identity(old), identity(new)
                    if old_id != new_id:
                        if old_id:
                            removed[old_id[0]] += 1
                            if old_id[0] in ANIMALS:
                                animal_exits[ANIMALS[old_id[0]][0]] += 1
                        if new_id:
                            added[new_id[0]] += 1
                    if new.get('animal'):
                        product, first, interval = ANIMALS[new['animal']]
                        if day+1-new['placed_day'] >= first and (day+1-new['placed_day']-first)%interval == 0:
                            # Bonus bank is consumed before this day's new care
                            # is banked; next-dawn hunger identifies fed_today.
                            old_bonus = old.get('pending_care_bonus',0) if old_id==new_id else 0
                            gross[product] += 1 + (old_bonus if new['consecutive_unfed']==0 else 0)
                            production_events.append(dict(available_dawn=day+1,tile=tile_index,
                                species=new['animal'],birth=new['placed_day'],
                                base=1,bonus=old_bonus if new['consecutive_unfed']==0 else 0,
                                fed=new['consecutive_unfed']==0,
                                gross_units=1+(old_bonus if new['consecutive_unfed']==0 else 0)))
            products = {}
            for p in PRODUCTS:
                harvested = phys.get('produced:'+p,0)
                net = end_field[p]-start_field[p]+harvested if end_field is not None else None
                consumed = phys.get('op:FEED',0)-phys.get('no_effect:FEED',0) if p=='WHEAT' else (
                    phys.get('op:FERTILIZE',0)-phys.get('no_effect:FERTILIZE',0) if p=='FERTILIZER' else 0)
                biological = gross[p] if p in ('MILK','WOOL','EGG') and after is not None else None
                residual = biological-net if biological is not None else None
                if residual is not None:
                    assert residual >= 0, (case,side,day,p,residual)
                lost_stock = None
                if start_stock is not None and end_stock is not None and spending.get('BUY_PRODUCT:'+p,0)==0:
                    lost_stock = start_stock[p]+harvested-sold.get(p,0)-consumed-end_stock[p]
                    assert lost_stock>=0,(case,side,day,p,lost_stock)
                final = g['daily'][s][30]
                closed_stock = (p not in ('WHEAT','FERTILIZER')
                    and final['spend'].get('BUY_PRODUCT:'+p,0)==0
                    and final['physical'].get('produced:'+p,0)==final['sold_units'].get(p,0))
                inferred_stock = a['physical'].get('produced:'+p,0)-a['sold_units'].get(p,0) if closed_stock else None
                if inferred_stock is not None and start_stock is not None:
                    assert inferred_stock==start_stock[p]
                products[p] = dict(harvested=harvested,sold=sold.get(p,0),revenue=revenue.get(p,0),
                    realized_average_price=revenue.get(p,0)/sold[p] if sold.get(p) else None,
                    dawn_market_quote=obs['market']['prices'].get(p),
                    dawn_field=start_field[p],next_dawn_field=end_field[p] if end_field is not None else None,
                    dawn_own_stock=start_stock[p] if start_stock is not None else None,
                    retrospective_stored_exact_from_closed_balance=inferred_stock,
                    next_dawn_own_stock=end_stock[p] if end_stock is not None else None,
                    field_net_generated_minus_losses=net,
                    animal_gross_generated_before_capacity_cap=biological,
                    animal_capacity_or_escape_output_loss=residual,
                    animal_capacity_loss_exact=residual if not animal_exits[p] else None,
                    own_stock_discard_residual_without_purchase=lost_stock,consumed=consumed,
                    product_purchase_spend=spending.get('BUY_PRODUCT:'+p,0))
            daily.append(dict(day=day,dawn_cash=a['money'],end_cash=b['money'],
                crops_and_animals=dict(Counter(t.get('crop',t.get('animal')) for t in before if t.get('crop') or t.get('animal'))),
                successful_births=dict(added),cohort_disappearances=dict(removed),spending=spending,
                products=products,physical=phys,
                animal_production_events_at_refresh=production_events,
                proposal=plans[day].get('proposal') if side=='ours' else None,
                admitted_plan=plans[day].get('realized_plan') if side=='ours' else None))
        result['sides'][side]=dict(daily=daily,final_ledger=g['daily'][s][30])
        result['animal_action_traces'][side]=animal_action_trace(g,actions,s)
    snapshots = {r['day']: r['current_observation'] for r in g['diagnostics'][seat]}
    for retirement in sw['execution']['retirements']:
        r = dict(retirement)
        d, tile, species = r['first_unfed_day'],int(r['tile']),r['animal']
        o=snapshots[d];t=flat(o)[tile];product,first,interval=ANIMALS[species]
        r.update(dawn_tile=t,dawn_product_quote=o['market']['prices'][product],
            dawn_feed_quote=o['market']['prices']['WHEAT'],
            first_possible_output_day=r['birth']+first,
            before_first_possible_output=r['observed_exit_day']+1 <= r['birth']+first,
            remaining_calendar_output_days=[n for n in range(d+1,30) if n-r['birth']>=first and (n-r['birth']-first)%interval==0],
            later_crop_use=None)
        for later in range(d+1,30):
            tt=flat(snapshots[later])[tile]
            if tt.get('crop'):
                r['later_crop_use']=dict(first_observed_dawn=later,crop=tt['crop'],birth=tt['planted_day'])
                break
        result['retirement_events'].append(r)
    result['unintended_exits']=[r for r in sw['execution']['animal_exits'] if r['classification']=='no_matching_recorded_retirement']
    assert not result['unintended_exits']
    return result


def render_report(result):
    c3,c6=result['cases']
    lines=['# V8 live03/live06: what was produced, delivered and sold', '',
        'Read-only development diagnosis. No new games or policy calls were made. All raw inputs are frozen V8 games from the original workspace; this report and its script are new worktree artifacts. The two chosen games are losses without unintended animal exits. They do not constitute an independent performance test.', '',
        'The narrow semantic recommendation is a **same-retirement-count, current-public-care-bank tie-break**. Live03 retires a cow before its first production despite a larger saved care bank than every same-count alternative. Live06’s high-price wool gap, in contrast, is mostly a harvest/delivery timing problem during the valuable window; simply adding sheep is not supported.', '',
        '## Accounting and verification', '',
        '- Daily flow is ledger[d+1] − ledger[d], including the executed final day29.',
        '- Biological animal generation is reconstructed from actual surviving cohorts, feeding and saved care banks. Crop net generation is labelled separately because decay/digging cannot be separated from growth from morning-only snapshots.',
        '- All 120 daily cash balances reconcile. The independent movement/spawn reconstruction matches 240 hourly own-position snapshots and all 360 daily milk/wool/egg harvest totals across the two games and both farms.',
        '- No day30 board/private snapshot is saved. Day29 harvest/sale/cost totals are exact; final-day field/generation changes are censored.',
        '- Opponent private stocks are not logged. For wool, no purchases and full-season collected=sold proves zero final stock and zero discard; retrospective intermediate stored wool therefore equals cumulative collected minus sold. This proof is offline only.', '',
        'Full daily data and commands are in [daily_product_flow.json](daily_product_flow.json). Source hashes are embedded there.', '',
        '## Profit and spending', '',
        '| Case | Margin | Revenue difference | Spending difference | Extra land | Extra hires | Extra seeds | Extra animals |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in result['cases']:
        a,b=(c['sides'][s]['final_ledger'] for s in ('ours','rival'))
        dif=lambda prefix:sum(v for k,v in a['spend'].items() if k.startswith(prefix))-sum(v for k,v in b['spend'].items() if k.startswith(prefix))
        lines.append(f"| {c['case']} | {c['margin']:+,.0f} | {sum(a['revenue'].values())-sum(b['revenue'].values()):+,.0f} | {dif(''):+,.0f} | {dif('BUY_LAND'):+,.0f} | {dif('HIRE'):+,.0f} | {dif('BUY_SEED:'):+,.0f} | {dif('BUY_ANIMAL:'):+,.0f} |")
    lines += ['', 'Both farms earned more revenue than MGT, but paid more for land, labor and inputs. This is not proof that a fourth quadrant or all extra animals were mistakes: the extra production also earned money, and modern native DSM commonly uses four quadrants. Costs and foregone opportunities need a controlled intervention.', '',
        '## Live06: valuable wool sat on the farm before the price decline', '',
        '| Dawn | Gross produced ours / rival | Collected ours / rival | Sold ours / rival | Still on animals ours / rival | Stored ours / rival |',
        '|---|---:|---:|---:|---:|---:|']
    for d in (12,15,18,21,24,27,29):
        stats=[]
        for side in ('ours','rival'):
            rows=c6['sides'][side]['daily'];p=rows[d]['products']['WOOL']
            stats.append([sum(r['products']['WOOL']['animal_gross_generated_before_capacity_cap'] or 0 for r in rows[:d]),
                sum(r['products']['WOOL']['harvested'] for r in rows[:d]),sum(r['products']['WOOL']['sold'] for r in rows[:d]),
                p['dawn_field'],p['dawn_own_stock'] if side=='ours' else p['retrospective_stored_exact_from_closed_balance']])
        lines.append('| '+str(d)+' | '+' | '.join(f'{a} / {b}' for a,b in zip(*stats))+' |')
    lines += ['', 'By dawn21, our farm had generated **three more wool** but sold **32 fewer**. The later whole-season production deficit must not be substituted for this earlier, valuable-window timing gap.', '',
        '| Sale window | Own units / revenue | Rival units / revenue |', '|---|---:|---:|']
    for start,end in ((6,14),(15,20),(21,26),(27,29)):
        ss=[]
        for side in ('ours','rival'):
            rows=c6['sides'][side]['daily'][start:end+1]
            ss.append((sum(r['products']['WOOL']['sold'] for r in rows),sum(r['products']['WOOL']['revenue'] for r in rows)))
        lines.append(f'| D{start}–{end} | {ss[0][0]} / ${ss[0][1]:,} | {ss[1][0]} / ${ss[1][1]:,} |')
    lines += ['',
        'On D15, our four-unit sheep at tile43 was visited at H4 COLLECT_FERTILIZER, H5 FEED and H6 CARE, but not harvested. Tile27 was fed/cared at H22/23 without collecting its four units. The day used every available command slot (no PASS). On D18, five ready sheep holding20 units were visited for feed/care/collection but not harvested; only one PASS existed anywhere. On D22, all20 dawn wool remained unharvested while workers visited all five animals; there were six PASS actions, not evidence of six usable hours on those routes.', '',
        'The frozen recipe enables sd_tier_anim_harv=1, sd_tier_anim_harv_frac=0.3, sd_tier_anim_harv_end=29 and sd_tier_dawn=3. In `_tier_pre`, a non-overflow animal harvest is downgraded to an optional task, valued at 30% of held units × current quote. `_tier_anim_harv_needed` considers next refresh capacity, not a falling market-price deadline. The observed choices are consistent with that rule; the internal route state was not saved, so a particular skipped task’s exact search explanation remains unverified.', '',
        'Collection and shed delivery are separate. On D15 the farm collected16 wool but issued only one wool PLACE of4, and sold4;12 remained in stock next dawn. On D18 it collected12, sold14 from opening stock14, and retained12. MGT harvested all its ready wool each of those days and used early/late deliveries. A policy that only increases herd size can worsen these service and delivery demands.', '',
        'The whole-season wool quantity gap decomposes exactly: **240 − 204 = 23 less gross generation + 10 units lost with intended retirements + 3 discarded from private stock**. Our gross217 became207 collected and204 sold. No cap loss is confirmed on any no-exit sheep day. The ten exit-loss units are five each at tile49 endD27 and tile48 endD28. These are physical losses, not automatically economic errors.', '',
        'At D27 dawn, wool was$1 while fertilizer was$35; skipping the first five units can be sensible. The second retirement was committed at that low quote, but on D28 the visible wool quote was$43 (own realized average$58), versus fertilizer$34. Unit11 visits tile48 atH9 to collect fertilizer and has three final PASS slots after its last harvest atH20. An extra collection fits those raw hours, but this is not a free gain: the D29 shed is already full100 and three wool were discarded on D28. From the worker’s ending tile29, shed distance is six, so a same-day return does not fit three spare hours. Collection must be paired with a feasible delivery/storage budget. All eight shops were revealed byD24; no unknown future shop can justify this retrospective finding.', '',
        'The average realized wool prices were $141.67 and $146.18. The exact algebraic revenue split is approximately −$5,262 from36 fewer sold units at MGT’s average price and −$919 from the average-price difference. Neither component is a recoverable-profit estimate: selling earlier changes shared inventory and both agents’ prices.', '',
        '### Where the later gross-output gap came from', '',
        '| Side | Sheep births by day | Production events | Paid-out care bonus | Gross wool |', '|---|---|---:|---:|---:|']
    for side in ('ours','rival'):
        ev=[e for r in c6['sides'][side]['daily'] for e in r['animal_production_events_at_refresh'] if e['species']=='SHEEP']
        born={}
        for e in ev:born.setdefault(e['birth'],set()).add(e['tile'])
        lines.append(f"| {side} | {', '.join('D'+str(d)+': '+str(len(ts)) for d,ts in sorted(born.items()))} | {len(ev)} | {sum(e['bonus'] for e in ev)} | {sum(e['gross_units'] for e in ev)} |")
    lines += ['',
        'The23-unit gross difference is seven fewer realized production events plus16 fewer paid-out bonus units. These are accounting components, not independent causal effects. Two sheep boughtD8 were only placedD11; first output moved from a possibleD14 to actualD17. Our retirement and lower-care choices remove further late production; by dawn24 gross output was still202 versus198, while by dawn29 it was217 versus240. This locates the final gross deficit largely in the low-price tail, not the earlier $200+ wool window.', '',
        '## Live03: retiring one cow need not mean retiring its saved first yield', '',
        'On D15 the semantic block asks to retire exactly one cow. The selected animal is **tile50, bornD9**, with zero held milk, care bank4, and first possible outputD17. It receives two unfed days and is absent at dawn17. The tile is replanted TOMATO onD18; first possible tomato output isD26, so the decision does not immediately release a harvest or finance a new sale.', '',
        '| D15 candidate | Birth | Held milk | Care bank | Next output | Remaining output dates throughD29 |', '|---|---:|---:|---:|---:|---:|']
    t3=c3['animal_action_traces']['ours']['days'][15]['animal_tiles']
    for r in t3:
        if r['species']!='COW':continue
        remaining=sum(d-r['birth']>=8 and (d-r['birth']-8)%2==0 for d in range(16,30))
        lines.append(f"| {r['tile']} | {r['birth']} | {r['dawn_yield']} | {r['pending_bonus']} | {r['next_production']} | {remaining} |")
    lines += ['',
        'The compiler’s remaining-production-count score ties all eight cows at seven dates. Distance then selects remote tile50; its input cells omit the current saved-care bank. The seven mature alternatives all have bank2. A current-dawn bank-sensitive tie-break can keep the retirement count and planned workload reduction while changing which production credit is sacrificed. The young cow still requires feeding, collection and travel; its first milk arrives one day later than the mature alternatives, so this is a controlled candidate, not guaranteed profit.', '',
        'At D15 the observed milk quote is$160, but it subsequently falls sharply; the realized season milk prices differ little ($96.72 vs$97.72). A blanket “never retire before first production” or “preserve all cows” rule is not justified. In validated native modern100 morning cohorts, four of1,046 observed animal disappearances during the measured window precede their first possible output (three cows, one goose). Native intention is unavailable; this is context, not a safe-policy rule.', '',
        '## Proposed isolated intervention and limits', '',
        '**Test only the current-dawn public care-bank tie-break among otherwise tied retirement candidates.** Preserve the requested retirement count, committed identities, release feasibility and all future-state default scoring. A useful diagnostic should show the current bank, next production, distance and selected alternative. It must not reuse today’s bank in modeled future days.', '',
        'For live06, keep a separate executor hypothesis: prioritize selected already-produced high-value wool for collection and delivery when the public price path is deteriorating, without adding animals or forcing below-floor harvesting. The saved trace supports the mechanism but does not prove an insertion fits mandatory routes or that earlier shared-market sales improve margin. A small controlled gate is required before a larger panel; there is no40-world authorization from a failed eight-world gate.', '',
        'No main policy, executor, frozen candidate, training label or qualification artifact was changed by this investigation.']
    lines += ['', '## All-product ledger summary', '',
        'Animal gross generation is separately reconstructed above. Here “collected” is successful physical harvest or fertilizer collection, and sold quantities can include purchased tradable wheat. Do not subtract these columns to infer wheat waste. Every product also has daily field stock, own private stock, quote, sale revenue and cost entries in the JSON.', '']
    for c in result['cases']:
        lines += [f"### {c['case']}", '', '| Product | Collected ours / rival | Sold ours / rival | Realized average price ours / rival | Revenue difference |', '|---|---:|---:|---:|---:|']
        a,b=(c['sides'][s]['final_ledger'] for s in ('ours','rival'))
        for p in PRODUCTS:
            ha,hb=(x['physical'].get('produced:'+p,0) for x in (a,b))
            sa,sb=(x['sold_units'].get(p,0) for x in (a,b))
            ra,rb=(x['revenue'].get(p,0) for x in (a,b))
            lines.append(f'| {p} | {ha} / {hb} | {sa} / {sb} | ${ra/sa if sa else 0:.2f} / ${rb/sb if sb else 0:.2f} | ${ra-rb:+,} |')
    report='\n'.join(lines)+'\n'
    report=re.sub(r'(?<=[a-z])(?=\d|\$|[DH]\d)', ' ', report)
    return report.replace('four of1,046','four of 1,046')


def main():
    service = read(STUDY / 'service_audit_v7_v8.json')
    group = next(value for key,value in service['groups'].items() if 'strategy_v8_' in key)
    model = read(STUDY / 'causal_daily_rows_modern100.json')
    frozen=STUDY/'candidates/strategy_v8_kb115lt2_readiness/project'
    for reference in (
        SOURCE/'.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py',
        frozen/'results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py',
        frozen/'results/fresh/semantic_strategy_20260928/executor_recipe_online.json',
        frozen/'scripts/semantic_strategy_tiles_20260928.py'):
        HASHES[str(reference)]=hashlib.sha256(reference.read_bytes()).hexdigest()
    result=dict(scope=__doc__,cases=[case_data(c,group) for c in ('live-03','live-06')],
        native100_retirement_patterns=native_retirements(model),new_games=0,
        accounting_notes=[
            'Day d flow is cumulative ledger[d+1]-ledger[d]. D29 is complete, but no D30 tile/private snapshot is retained.',
            'Harvested means physically collected; it is not biological generation.',
            'Animal gross generation is exact before max-held capacity cap, using surviving cohorts, next-dawn feeding and prior bonus bank.',
            'Field net generated minus losses is next-dawn field yield minus dawn field yield plus harvested. For crops this includes initial seedling yield, water increments, production, caps, decay, digging and death.',
            'Animal gross minus net is cap loss plus output lost with escaping animals. On species-days with no disappearance this is exact cap loss.',
            'Fertilizer field count is uncollected availability, not a crop yield; its net flow includes replenishment and disappearing availability.',
            'Rival private stocks are unavailable. Their stored quantities are null, never invented.',
            'A separate retrospective_stored_exact field is proved only for non-consumed products with no purchases and full-season harvest=sales: nonnegative final stock/discard must both be zero, so intermediate stock equals cumulative harvested minus sold. This proof uses the final ledger and is for offline attribution only.',
            'Own stock discard residual is exact only on days with no purchased quantity of that product; bought-product counts are not inferred from dollars.',
            'Current prices and matched same-game realized prices are descriptive, not counterfactual marginal profit.',
            'Native source market arrays have a known one-day offset and are not used here.',
            'No selected-case outcome or future shop suffix is supplied to a runtime planner; this is retrospective development diagnosis.'])
    result['input_hashes']=HASHES
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'daily_product_flow.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    report=OUT/'report.md';report.write_text(render_report(result),encoding='utf-8')
    manifest=dict(new_games=0,source_workspace=str(SOURCE),output_workspace=str(ROOT),
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),path,report)},
        input_hashes=HASHES,verified=dict(cash_days=120,animal_product_day_balances=360,own_hourly_position_snapshots=240))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        native_before_first=result['native100_retirement_patterns']['before_first'],
        animal_losses={c['case']:{side:{p:sum(r['products'][p]['animal_capacity_loss_exact'] or 0 for r in v['daily']) for p in ('MILK','WOOL','EGG')} for side,v in c['sides'].items()} for c in result['cases']})))


if __name__=='__main__':main()
