"""Audit and summarize the frozen mechanism experiment."""
import json
from collections import Counter
from hashlib import sha256
from statistics import mean
from research_router_mechanisms import ROOT, OUT, VARIANTS, jobs
from compare_router_refresh import PATHS
from market_corpus import load

def main():
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs()]
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['sources'].items(): assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    errors=[]
    for r in rows:
        for key,value in r['telemetry'].items():
            if 'error' in key.lower() and isinstance(value,(int,float)) and value: errors.append((r['seed'],r['variant'],key,value))
        if r['variant'] in ('no_tomatoes','combined_off'): assert r['tomato_stats']['commitments']==0
        if r['variant'] in ('no_reservations','combined_off'): assert r['reservation_stats']['sale_reservations']==0
        if r['variant'] in ('no_terminal','combined_off'): assert r['terminal_stats']['accepted']==0
    module=load('report_mechanism_v45',PATHS['v45'])
    source_map={'v45_tapes':len(module._ROUTES),'first_two_shop_lookup_entries':len(module._R108_SHOP_ROUTES),
                'old_expert_lookup_entries':len(module._R110_OLD_SHOPS)}
    lines=['# What makes the newer router stronger?','',
      '## Method','',
      '192 full games: eight new seeds (135000–135007), both seats, two reactive opponents, and six V45 variants. Each paired comparison uses the same hidden shop sequence, sampled uniformly with replacement. Both cash ledgers reconcile in every game. Eight seeds are the independent sample; seats are paired coverage, not sixteen independent worlds.', '',
      'The full agent is the downloaded V45. Interventions disable its conditional tomato investment, advance-sale reservations, seven-turn terminal planner, or V45 opening round trip separately; combined-off disables all four. Other production tapes, sale ordering, inventory safeguards, and repair layers remain active. Combined-off is not the old router.', '',
      'Positive gain below means enabling the mechanism helped the full agent. It includes downstream changes and opponent reactions; the rows are not additive.', '',
      '| Opponent | Disabled mechanism | Variant wins / 16 | Full margin gain | Full own-cash gain | Positive / negative pairs | Seed-average gain range |',
      '|---|---|---:|---:|---:|---:|---:|']
    detail={}
    for opponent in ('selected','twocoins'):
        full={(r['seed'],r['seat']):r for r in rows if r['opponent']==opponent and r['variant']=='full'}
        for variant in VARIANTS:
            rs=[r for r in rows if r['opponent']==opponent and r['variant']==variant]
            ds=[full[r['seed'],r['seat']]['margin']-r['margin'] for r in rs]
            cs=[full[r['seed'],r['seat']]['cash']-r['cash'] for r in rs]
            byseed={s:mean(full[r['seed'],r['seat']]['margin']-r['margin'] for r in rs if r['seed']==s) for s in sorted({r['seed'] for r in rs})}
            detail[opponent+'/'+variant]={'mean_margin':mean(r['margin'] for r in rs),'gain':mean(ds),'cash_gain':mean(cs),'seed_gains':byseed,
              'tomato_games':sum(r['tomato_stats']['commitments']>0 for r in rs),
              'terminal_accepted_games':sum(r['terminal_stats']['accepted']>0 for r in rs)}
            lines.append(f"| {opponent} | {variant} | {sum(r['margin']>0 for r in rs)} | {mean(ds):+,.1f} | {mean(cs):+,.1f} | {sum(d>0 for d in ds)} / {sum(d<0 for d in ds)} | {min(byseed.values()):+,.0f} to {max(byseed.values()):+,.0f} |")
    lines += ['', '## Full-agent coverage', '']
    for opponent in ('selected','twocoins'):
        rs=[r for r in rows if r['opponent']==opponent and r['variant']=='full']
        lines.append(f"- Against {opponent}: mean margin {mean(r['margin'] for r in rs):+,.1f}; tomato commitments in {sum(r['tomato_stats']['commitments']>0 for r in rs)}/16 games; terminal plans accepted in {sum(r['terminal_stats']['accepted']>0 for r in rs)}/16 games.")
    lines += ['', '## Where our submitted control loses cash', '',
        'Mean exact ledger difference, full V45 minus our submitted agent in their direct games. Product contribution is revenue less purchases of that product, its seeds, and its animals; labor and land are separate. These are accounting differences, not independent causal effects.', '',
        '| Contribution | V45 advantage | Mean units sold: V45 / ours |','|---|---:|---:|']
    totals=Counter()
    own_units=Counter();rival_units=Counter()
    rs=[r for r in rows if r['opponent']=='selected' and r['variant']=='full']
    for r in rs:
        for seat,sign in ((r['seat'],1),(1-r['seat'],-1)):
            ledger=r['ledger'][seat]
            (own_units if sign==1 else rival_units).update(ledger['sold_units'])
            for item,value in ledger['revenue'].items():totals[item]+=sign*value
            for key,value in ledger['spend'].items():
                item=key.split(':')[-1]
                if key.startswith('BUY_ANIMAL:'): item={'COW':'MILK','SHEEP':'WOOL','GOOSE':'EGG'}.get(item,item)
                totals[item]-=sign*value
    assert abs(sum(totals.values())/len(rs)-mean(r['margin'] for r in rs))<1e-7
    for item,value in sorted(totals.items(),key=lambda kv:-kv[1]):
        units=f'{own_units[item]/len(rs):,.1f} / {rival_units[item]/len(rs):,.1f}' if item in own_units or item in rival_units else '—'
        lines.append(f'| {item} | {value/len(rs):+,.1f} | {units} |')
    lines += ['', 'Sold units are gross market sales, including purchased-and-resold goods such as wheat; they are not necessarily farm production.']
    wheat_revenue=mean(r['ledger'][r['seat']]['revenue']['WHEAT']-r['ledger'][1-r['seat']]['revenue']['WHEAT'] for r in rs)
    wheat_buy=mean(r['ledger'][1-r['seat']]['spend'].get('BUY_PRODUCT:WHEAT',0)-r['ledger'][r['seat']]['spend'].get('BUY_PRODUCT:WHEAT',0) for r in rs)
    wheat_seed=mean(r['ledger'][1-r['seat']]['spend'].get('BUY_SEED:WHEAT',0)-r['ledger'][r['seat']]['spend'].get('BUY_SEED:WHEAT',0) for r in rs)
    lines += ['', f'The wheat contribution comprises {wheat_revenue:+,.1f} sale revenue, {wheat_buy:+,.1f} savings on purchased wheat, and {wheat_seed:+,.1f} savings on wheat seeds. It cannot all be attributed to feeding or sale timing without further interventions.']
    lines += ['', '## What the code teaches us', '',
        f"- **Production selection:** V45 contains {source_map['v45_tapes']} action tapes, with {source_map['first_two_shop_lookup_entries']} ordered first-two-shop lookup entries. At turn 144 it chooses an expert based on whether either first shop is Yarn Store, then chooses that expert's route for the shop pair. At turn 648 it switches to its terminal route. These are full-game continuations, not six-day-only plans. The old parent has five tapes; Two Coins has thirteen. Tape count is a source fact, not an isolated measure of quality.",
        '- **Investment:** the tomato expansion checks land, cash (at least 12,000), current tomato price (at least 70), and at least three revealed Pizza Shop/Farmers Market appearances. It reserves new worker indices and plants ten tomatoes on day index 18, leaving time for harvests before termination. Fertilizer has a separate marginal-benefit check. It commits to a production-and-delivery plan, not just cheap seeds.',
        '- **Inventory and execution:** the chassis repairs weed-interrupted work. Additional layers project physical deposits before market actions, protect upcoming pickups, trim redundant replenishment, and reclaim warehouse overflow. Advance-sale reservations move eligible future sales forward and suppress the corresponding later orders so inventory is not sold twice.',
        '- **Input economics:** feeding can be skipped when the estimated extra output is worth less than wheat, subject to tomorrow\'s planned service and escape constraints. Fertilizer reserves account for upcoming native and dedicated-worker pickups. These policies value the whole production cycle, including inputs and labor.',
        '- **Opponent interaction:** sale horizons can extend when observed worker positions and production resemble the same public tape. The V45 opening replaces its predecessor\'s split wheat orders with a 70-unit round trip. Whether either helps depends on the opposing order stream.', '',
        'Source: `data/router_refresh_20260916/v45/main.py`, especially `_router`, `_v219_qualifies`, `_v219_request`, `_r36_reserve`, `_r85_feed`, `_r85_reserve`, and the final `_OPEN_PARENT` wrapper. Published notebook: [V45](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v45-first-turn-wheat-round-trip).', '',
        '## Why our earlier research missed this', '',
        'Our changes mostly improved selling around an older production schedule. In the previous refresh, they added only about 101–353 average margin over the raw parent against the four stronger public agents, while both versions lost all sixteen games to each. The earlier narrow benchmark rewarded beating relatives of the same older policy. It did not validate strength against the newer production-and-execution family. See [the refresh study](router_refresh.md).', '',
        '## Research priority', '',
        'Use the frozen newer routers as baselines, keeping our uploaded agent as a historical control. Next isolate the remaining production selection and wheat economy: separate harvested wheat from purchased-and-resold stock, record feed consumption and discarded inventory, and compare wheat sale quantities and execution prices. Then disable feed/replenishment rules and route selection separately under common shop draws. Test early-sale decisions against several modern opponents because their effects reverse across opponents here. Terminal planning is a low priority on this evidence. These are next-step recommendations, not a promoted policy or a new submission.', '',
        '## Validation and limits','',
        f"All {len(rows)} games completed 720 valid states. Frozen source hashes match; disabled mechanisms have zero recorded activations. Nonzero error counters: {len(errors)}. Maximum measured action time under concurrent load: {max(r['max_seconds'] for r in rows):.3f}s (not a competition-host timing certificate).", '',
        'Results depend on these two opponents and eight shop sequences. This experiment does not isolate the entire production-route portfolio or all execution layers, estimate a settled ladder rating, or establish why QQ Farming had a particular displayed rating. The uploaded agent remains unchanged.', '',
        'Reproduce: `.venv/Scripts/python.exe scripts/research_router_mechanisms.py`, then `.venv/Scripts/python.exe scripts/report_router_mechanisms.py`. Raw data and the frozen source manifest are in `results/fresh/router_mechanisms/`.', '']
    (OUT/'diagnostics.json').write_text(json.dumps({'comparisons':detail,'errors':errors,'source_map':source_map,'net_contributions':{k:v/len(rs) for k,v in totals.items()}},indent=2),encoding='utf-8')
    findings=['## Findings', '',
        '**Most of the advantage over our submitted agent survives removing all four tested mechanisms.** Full V45 wins 16/16 with mean margin +11,282; combined-off also wins 16/16 with mean margin +11,569. The remaining production selection, input management, and execution layers need the next causal breakdown. This does not isolate the route portfolio itself.', '',
        '- Tomato expansion adds +1,872 mean margin against ours and +1,709 against Two Coins. It activates on only two of eight shop sequences (four seat-paired games), so this is a conditional gain with limited trigger coverage.',
        '- Advance-sale reservations add +3,405 margin against Two Coins but lose 753 against ours. Their usefulness depends on the rival and market trajectory.',
        '- The V45 opening round trip loses 1,374 margin against ours and 1,326 against Two Coins relative to its predecessor opening. This does not rule out value against other opening order streams.',
        '- The seven-turn terminal planner adds only about 4 cash and margin against either opponent on this panel. It activates in twelve games per opponent; the small gain is not simply lack of activation.',
        '- Wheat accounts for +5,338 of V45\'s average cash advantage over ours, mostly higher sale revenue. This is the largest accounting lead and the clearest next target for mechanism tracing.', '',
        'QQ Farming may have been a strong submission with an unrepresentative displayed rating. That is compatible with an unlucky pairing, but does not remove the reproducible gap against the newer public agents. No historical QQ rating was independently verified in this study.', '']
    lines[2:2]=findings
    (ROOT/'docs/router_mechanisms.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'comparisons':detail,'errors':errors},indent=2))

if __name__=='__main__':main()
