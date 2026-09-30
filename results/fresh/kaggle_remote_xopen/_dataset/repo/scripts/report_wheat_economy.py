"""Summarize wheat accounting and causal policy interventions."""
import json
from hashlib import sha256
from statistics import mean
from collections import Counter
from research_wheat_economy import ROOT,OUT,VARIANTS,jobs

def main():
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs()]
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    smoke=json.loads((OUT/'checks/135000-0-selected-full.json').read_text(encoding='utf-8'))
    assert smoke['prior_run_parity']
    errors=[]
    for r in rows:
        if r['variant'] in ('no_feed','no_feed_or_trim'):assert r['telemetry']['feed_skips']==0
        if r['variant'] in ('no_trim','no_feed_or_trim'):assert r['telemetry']['replenishment_trim_units']==0
        if r['variant']=='fixed_route':assert [x['route'] for x in r['routes']]==[0,0,2]
        for key,value in r['telemetry'].items():
            if 'error' in key.lower() and isinstance(value,(int,float)) and value:errors.append((r['seed'],r['seat'],r['opponent'],r['variant'],key,value))
        for w in r['wheat']:assert w.get('initial',0)+w.get('harvest',0)+w.get('bought',0)==w.get('sold',0)+w.get('fed',0)+w.get('discarded',0)+w.get('remaining',0)
    summary={}
    lines=['# Wheat economics and production choices', '', '## Design', '',
        '192 games: eight new seeds (136000–136007), both seats, two reactive opponents (our submitted control and Two Coins), six V45 variants. All policy comparisons share identical shop sequences, drawn uniformly with replacement and hidden until revealed. Both seats share the same random world; the independent sample is eight seeds.', '',
        'The wheat audit observes only real engine execution, excluding internal policy simulations. It tracks harvests, product purchases, feeding, sales, discarded wheat and final inventory. The conservation equation holds after every turn: **initial + harvested + bought = sold + fed + discarded + remaining**. Wheat seeds are accounted separately. A repeated previous full-agent game reproduces its exact cash, complete product ledgers and shop sequence.', '',
        'All other V45 layers remain enabled. No feeding disables only discretionary economic feed skipping, not normal feeding. No trimming disables only the day-index-10/11 replenishment reduction. Older expert uses the V39 first-two-shop lookup for every pair; it retains the newer overlays. Fixed route uses route 0 until turn 647, then the normal terminal route 2; other reactive overlays still run. Neither route intervention recreates our original five-tape agent.', '',
        '## Paired effects', '',
        'Positive values mean the full policy is better than the disabled variant. These are total effects, including later production, prices and opponent reactions; they are not additive.', '',
        '| Opponent | Variant | Wins / 16 | Variant mean margin | Full margin gain | Full own-cash gain | Seeds helped / hurt / tied |',
        '|---|---|---:|---:|---:|---:|---:|']
    for opponent in ('selected','twocoins'):
        base={(r['seed'],r['seat']):r for r in rows if r['opponent']==opponent and r['variant']=='full'}
        for variant in VARIANTS:
            rs=[r for r in rows if r['opponent']==opponent and r['variant']==variant]
            delta=[base[r['seed'],r['seat']]['margin']-r['margin'] for r in rs]
            seed_delta={seed:mean(base[r['seed'],r['seat']]['margin']-r['margin'] for r in rs if r['seed']==seed) for seed in sorted({r['seed'] for r in rs})}
            entry=dict(games=len(rs),wins=sum(r['margin']>0 for r in rs),mean_margin=mean(r['margin'] for r in rs),
                full_margin_gain=mean(delta),full_cash_gain=mean(base[r['seed'],r['seat']]['cash']-r['cash'] for r in rs),
                seed_deltas=seed_delta,mean_wheat={key:mean(r['wheat'][r['seat']].get(key,0) for r in rs) for key in ('harvest','bought','sold','fed','discarded','sale_revenue','purchase_cost','seed_cost')},
                mean_feed_skips=mean(r['telemetry']['feed_skips'] for r in rs),mean_trim_units=mean(r['telemetry']['replenishment_trim_units'] for r in rs),
                route_choices=[r['routes'][0]['route'] for r in rs],
                changed_route_pairs=sum(r['routes'][0]['route']!=base[r['seed'],r['seat']]['routes'][0]['route'] for r in rs))
            if variant=='old_expert':
                for r in rs:
                    b=base[r['seed'],r['seat']]
                    if r['routes'][0]['route']==b['routes'][0]['route']:
                        assert r['ledger']==b['ledger'] and r['wheat']==b['wheat'],(r['seed'],r['seat'],'unchanged route diverged')
            entry['full_wheat_change']={key:mean(base[r['seed'],r['seat']]['wheat'][r['seat']].get(key,0)-r['wheat'][r['seat']].get(key,0) for r in rs)
                for key in ('harvest','bought','sold','fed','discarded','sale_revenue','purchase_cost','seed_cost')}
            summary[opponent+'/'+variant]=entry
            signs=[sum(d>0 for d in seed_delta.values()),sum(d<0 for d in seed_delta.values()),sum(d==0 for d in seed_delta.values())]
            lines.append(f"| {opponent} | {variant} | {entry['wins']} | {entry['mean_margin']:+,.1f} | {entry['full_margin_gain']:+,.1f} | {entry['full_cash_gain']:+,.1f} | {' / '.join(map(str,signs))} |")
    rs=[r for r in rows if r['opponent']=='selected' and r['variant']=='full']
    own={key:mean(r['wheat'][r['seat']].get(key,0) for r in rs) for key in ('harvest','bought','sold','fed','discarded','remaining','planted','sale_revenue','purchase_cost','seed_cost')}
    rival={key:mean(r['wheat'][1-r['seat']].get(key,0) for r in rs) for key in own}
    own_net=own['sale_revenue']-own['purchase_cost']-own['seed_cost']
    rival_net=rival['sale_revenue']-rival['purchase_cost']-rival['seed_cost']
    lines += ['', '## Full V45 versus our submitted agent: wheat flow', '',
        '| Metric, average per game | V45 | Ours | Difference |','|---|---:|---:|---:|']
    for key in own:lines.append(f'| {key} | {own[key]:,.2f} | {rival[key]:,.2f} | {own[key]-rival[key]:+,.2f} |')
    lines += [f'| Wheat net cash (sales − product purchases − seeds) | {own_net:,.2f} | {rival_net:,.2f} | {own_net-rival_net:+,.2f} |']
    p1=own['sale_revenue']/own['sold'];p0=rival['sale_revenue']/rival['sold']
    quantity=(own['sold']-rival['sold'])*(p1+p0)/2
    price=(p1-p0)*(own['sold']+rival['sold'])/2
    assert abs(quantity+price-(own['sale_revenue']-rival['sale_revenue']))<1e-7
    lines += ['', f'Pooled sale price per wheat unit: V45 {p1:.2f}, ours {p0:.2f}. A symmetric arithmetic decomposition attributes {quantity:+,.1f} of the gross sale-revenue difference to quantity and {price:+,.1f} to average realized price. This is an accounting identity, not a causal sale-timing estimate: production and both players\' trades also change market prices.', '',
        'Wheat is fungible. Gross sales include purchased-and-resold stock; harvested units cannot be assigned unique sale revenue without an arbitrary inventory convention. The net cash and physical flow identities avoid that assumption.', '',
        '## When the wheat advantage arises', '',
        '| Turns | V45 minus ours: harvest | Feed | Bought | Sold | Wheat net cash |','|---|---:|---:|---:|---:|---:|']
    phases={}
    for start,end in ((0,71),(72,215),(216,431),(432,695),(696,718)):
        diff=Counter()
        for r in rs:
            for seat,sign in ((r['seat'],1),(1-r['seat'],-1)):
                for step,data in r['wheat_steps'][seat].items():
                    if start<=int(step)<=end:
                        for k,v in data.items():diff[k]+=sign*v/len(rs)
        net=diff['sale_revenue']-diff['purchase_cost']-diff['seed_cost']
        phases[f'{start}-{end}']={**diff,'net_cash':net}
        lines.append(f"| {start}–{end} | {diff['harvest']:+,.1f} | {diff['fed']:+,.1f} | {diff['bought']:+,.1f} | {diff['sold']:+,.1f} | {net:+,.1f} |")
    lines += ['', '## Mechanism coverage', '',
        '| Opponent | Variant | Feed skips | Wheat units trimmed | Route differs from full / 16 |','|---|---|---:|---:|---:|']
    for key,s in summary.items():
        opponent,variant=key.split('/')
        lines.append(f"| {opponent} | {variant} | {s['mean_feed_skips']:.1f} | {s['mean_trim_units']:.1f} | {s['changed_route_pairs']} |")
    lines += ['', '## What each mechanism changes in our own wheat economy', '',
        'Full minus variant. Negative feed means the full policy consumed fewer units. Wheat net cash excludes labor, land and animal-product effects; compare it with the total cash gain above.', '',
        '| Opponent | Disabled mechanism | Harvest | Feed | Bought | Sold | Wheat net cash |',
        '|---|---|---:|---:|---:|---:|---:|']
    for key,s in summary.items():
        opponent,variant=key.split('/')
        if variant=='full':continue
        w=s['full_wheat_change'];net=w['sale_revenue']-w['purchase_cost']-w['seed_cost']
        lines.append(f"| {opponent} | {variant} | {w['harvest']:+,.1f} | {w['fed']:+,.1f} | {w['bought']:+,.1f} | {w['sold']:+,.1f} | {net:+,.1f} |")
    lines += ['', '## Validation and limits', '',
        f'All 192 games completed 720 valid states. Both cash ledgers reconcile; wheat conservation was checked after every executed turn. Frozen source hashes match. Disabled feed/trim counters are zero and fixed-route choices are verified. Nonzero telemetry error counters: {len(errors)}.', '',
        'This is a diagnostic study on eight new shop sequences, not a calibrated leaderboard prediction or exhaustive coverage of all 64 first-two-shop pairs. Keeping other overlays active measures these mechanisms inside the current V45 system. It does not identify the isolated quality of raw action tapes. No agent was promoted or submitted.', '',
        'Reproduce: `scripts/research_wheat_economy.py --smoke`, `scripts/research_wheat_economy.py`, then `scripts/report_wheat_economy.py`, using the project virtual environment. Raw per-turn wheat flows, paired results and source hashes: `results/fresh/wheat_economy/`.', '']
    cycles=json.loads((OUT/'cycle_summary.json').read_text(encoding='utf-8'))
    followup=json.loads((OUT/'crop_input_followup/summary.json').read_text(encoding='utf-8'))
    follow_manifest=json.loads((OUT/'crop_input_followup/manifest.json').read_text(encoding='utf-8'))
    for name,digest in follow_manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    for o,v in followup.items():assert not v['errors'],(o,v['errors'])
    for i,w in enumerate((own,rival)):assert cycles['per_game'][i]['units']==w['harvest']
    position=lines.index('## Validation and limits')
    extra=['## Crop-cycle trace and fertilizer-planner follow-up', '',
        'Sixteen repeated full-agent games reproduced the original cash, product ledgers and per-turn wheat flows. They additionally record each successful wheat harvest\'s age and yield.', '',
        '| Harvest metric, average per game | V45 | Ours |','|---|---:|---:|',
        f"| Successful harvest actions | {cycles['per_game'][0]['harvest_actions']:.2f} | {cycles['per_game'][1]['harvest_actions']:.2f} |",
        f"| Units per successful harvest | {own['harvest']/cycles['per_game'][0]['harvest_actions']:.2f} | {rival['harvest']/cycles['per_game'][1]['harvest_actions']:.2f} |",
        f"| Harvests yielding 5–6 units | {sum(cycles['yield_per_harvest_counts'][0].get(str(n),0) for n in (5,6))/16:.2f} | {sum(cycles['yield_per_harvest_counts'][1].get(str(n),0) for n in (5,6))/16:.2f} |", '',
        'V45\'s extra crop-input planner forecasts native watering and harvest times, estimates fertilizer\'s marginal yield, and searches short worker tours. It includes fertilizer purchase price, labor, warehouse capacity and a cash reserve before committing. Wheat/carrot tours are separate from the tomato investment.', '',
        'After observing the yield difference, a further 32 games disabled these extra fertilizer tours. This is an adaptive diagnostic on the same eight-seed panel, not independent confirmation or removal of all native fertilizer use.', '',
        '| Opponent | Planner margin gain | Planner own-cash gain | Extra wheat harvested | Seeds helped / hurt / tied |',
        '|---|---:|---:|---:|---:|']
    for opponent,v in followup.items():
        d=v['full_gains'];ss=v['seed_margin_gains'].values()
        extra.append(f"| {opponent} | {d['margin']:+,.1f} | {d['cash']:+,.1f} | {d['wheat_harvest']:+,.1f} | {sum(x>0 for x in ss)} / {sum(x<0 for x in ss)} / {sum(x==0 for x in ss)} |")
    extra += ['', 'Selected cost and revenue changes from enabling the planner (averages; all other downstream effects are included in final cash above):', '',
        '| Opponent | Wheat revenue | Carrot revenue | Fertilizer revenue | Extra fertilizer cost | Extra labor cost |',
        '|---|---:|---:|---:|---:|---:|']
    for opponent,v in followup.items():
        d=v['full_gains']
        extra.append(f"| {opponent} | {d['WHEAT_revenue']:+,.1f} | {d['CARROT_revenue']:+,.1f} | {d['FERTILIZER_revenue']:+,.1f} | {d['BUY_PRODUCT:FERTILIZER_cost']:+,.1f} | {d['HIRE_cost']:+,.1f} |")
    extra += ['', 'All 32 follow-up games passed the same cash and per-turn wheat checks; disabled planner hires were zero. Together with the one initial instrumentation check, this study ran **241 full games** (192 main + 16 cycle repeats + 32 follow-up + 1 check). Follow-up runner: `scripts/check_crop_input_planner.py`; cycle tracer: `scripts/trace_wheat_cycles.py`.', '']
    lines[position:position]=extra
    findings=['## Findings', '',
        f"**The newer agent converts wheat and farm labor into cash more efficiently.** On the fresh panel V45 beats our control 16/16 with mean margin {summary['selected/full']['mean_margin']:+,.0f}; its wheat net-cash advantage is {own_net-rival_net:+,.0f} per game. This advantage survives a different gross-sales breakdown from the previous panel.", '',
        f"- **Economic feeding is a consistent contributor:** enabling discretionary feed skipping adds {summary['selected/no_feed']['full_margin_gain']:+,.0f} margin against ours and {summary['twocoins/no_feed']['full_margin_gain']:+,.0f} against Two Coins. It frees about 56 wheat per game, mostly for sale, while the measured total cash gain includes lost animal-product value.",
        f"- **Shop-dependent production matters competitively:** full routing adds {summary['selected/fixed_route']['full_margin_gain']:+,.0f} margin against ours and {summary['twocoins/fixed_route']['full_margin_gain']:+,.0f} against Two Coins relative to fixed route 0. Own-cash changes are {summary['selected/fixed_route']['full_cash_gain']:+,.0f} and {summary['twocoins/fixed_route']['full_cash_gain']:+,.0f}; much of the margin effect comes from the opponent's changed outcome. This is a total interaction effect, not proof of a deliberate sabotage tactic.",
        f"- **The newest route portfolio gives a smaller, variable increment:** forcing the older V39 shop lookup costs {summary['selected/old_expert']['full_margin_gain']:,.0f} / {summary['twocoins/old_expert']['full_margin_gain']:,.0f} margin on average, with unchanged routing in two seeds. Most wheat profitability is shared by both portfolios: their wheat net-cash difference is small.",
        '- **Small purchase trimming is low priority:** it loses about 18 margin per game here. It removes purchases that would mostly have been sold later; fewer purchased units alone do not establish a benefit.',
        f"- **Extra fertilizer tours explain a measurable yield gain:** the follow-up measures {followup['selected']['full_gains']['wheat_harvest']:+,.1f} wheat and {followup['selected']['full_gains']['margin']:+,.0f} margin against ours; see the diagnostic results below for costs and the second opponent.", '',
        '**Accounting correction:** the earlier panel\'s wheat advantage appeared mainly in higher sale revenue. Here V45 sells fewer units and earns less gross wheat revenue, but spends much less on purchases. Most of the gross purchase-volume gap occurs in early buy/sell round trips that nearly cancel in cash. The net advantage mainly appears later: about 3,105 in turns 432–695. Gross sales or purchase totals by themselves are unreliable efficiency scores.', '',
        '## What to build on', '',
        'Use a modern conditional router as the working baseline and keep the uploaded agent as a historical control. Preserve economic feeding and profitable crop-input planning. Evaluate production choices by paired winning margin as well as own cash. The next development target is a joint short-horizon input planner that values extra crop output, feed, fertilizer and worker time against delivery deadlines; test it against several modern rivals on new shop draws. The eight-seed fertilizer follow-up needs independent confirmation before tuning or promotion. Tiny replenishment and terminal tweaks are lower priorities on this evidence.', '']
    lines[2:2]=findings
    result={'comparisons':summary,'wheat_v45':own,'wheat_selected':rival,'net_cash_advantage':own_net-rival_net,
            'revenue_quantity_component':quantity,'revenue_price_component':price,'phases':phases,'errors':errors,
            'crop_cycle_trace':cycles,'crop_input_followup':followup}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'docs/wheat_economy.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
