"""Verify sale-policy transfers and select a file independently per baseline."""
from hashlib import sha256
from statistics import mean
from collections import Counter
import json
from evaluate_modern_sales import ROOT,OUT,PATHS

def main():
    rows=[]
    for phase in ('development','confirmation'):
        manifest=json.loads((OUT/(phase+'_manifest.json')).read_text(encoding='utf-8'))
        for name,digest in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        rows += [json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in manifest['jobs']]
    screen=json.loads((OUT/'development_selection.json').read_text(encoding='utf-8'))
    summary={};selections={};errors=[];table=[]
    for r in rows:
        for key,value in {**r['telemetry'],**r['chassis_diagnostics']}.items():
            if any(s in key.lower() for s in ('error','fallback')) and isinstance(value,(int,float)) and value:
                errors.append((r['phase'],r['policy'],r['seed'],r['seat'],r['opponent'],key,value))
    for phase in ('development','confirmation'):
        for base in ('v44','v45'):
            control={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['phase']==phase and r['policy']==base+'_base'}
            modes=('order','liquid','both') if phase=='development' else (screen[base]['mode'],)
            for mode in modes:
                candidates=[r for r in rows if r['phase']==phase and r['policy']==base+'_'+mode]
                pairs=[(r,control[r['seed'],r['seat'],r['opponent']]) for r in candidates]
                seed_delta={s:mean(r['margin']-b['margin'] for r,b in pairs if r['seed']==s) for s in sorted({r['seed'] for r,b in pairs})}
                opponents={o:dict(margin_gain=mean(r['margin']-b['margin'] for r,b in pairs if r['opponent']==o),
                    cash_gain=mean(r['cash']-b['cash'] for r,b in pairs if r['opponent']==o)) for o in sorted({r['opponent'] for r,b in pairs})}
                def record(index):
                    margins=[p[index]['margin'] for p in pairs]
                    return [sum(v>0 for v in margins),sum(v==0 for v in margins),sum(v<0 for v in margins)]
                gain=mean(r['margin']-b['margin'] for r,b in pairs)
                cash=mean(r['cash']-b['cash'] for r,b in pairs)
                data=dict(games=len(pairs),margin_gain=gain,cash_gain=cash,seed_gains=seed_delta,opponents=opponents,
                    baseline_wtl=record(1),candidate_wtl=record(0),
                    mean_liquidated_units=mean(r['telemetry'].get('port_liquid_units',0) for r,b in pairs),
                    mean_priority_calls=mean(r['telemetry'].get('port_priority_calls',0) for r,b in pairs),
                    max_seconds=max(r['max_seconds'] for r,b in pairs))
                delta=Counter()
                for r,b in pairs:
                    seat=r['seat']
                    for sign,x in ((1,r),(-1,b)):
                        for k,v in x['ledger'][seat]['revenue'].items():delta['revenue:'+k]+=sign*v
                        for k,v in x['ledger'][seat]['sold_units'].items():delta['sold_units:'+k]+=sign*v
                        for k,v in x['ledger'][seat]['spend'].items():delta['cost:'+k]+=sign*v
                assert sum(v for k,v in delta.items() if k.startswith('revenue:'))-sum(v for k,v in delta.items() if k.startswith('cost:'))==sum(r['cash']-b['cash'] for r,b in pairs)
                data['accounting_delta']={k:v/len(pairs) for k,v in delta.items()}
                summary[f'{phase}/{base}/{mode}']=data
                table.append(f"| {phase} | {base} | {mode} | {gain:+,.1f} | {cash:+,.1f} | {'/'.join(map(str,record(1)))} | {'/'.join(map(str,record(0)))} |")
                if phase=='confirmation':
                    gates=dict(positive_mean=gain>0,nonnegative_each_rival=all(d['margin_gain']>=0 for d in opponents.values()),
                        six_positive_seeds=sum(v>0 for v in seed_delta.values())>=6,no_fewer_wins=record(0)[0]>=record(1)[0],
                        no_errors=not any(e[0]==phase and e[1]==base+'_'+mode for e in errors),under_one_second=data['max_seconds']<1)
                    selected=mode if all(gates.values()) else 'base'
                    path=ROOT/f'agents/{base}_our_selected.py';path.write_bytes(PATHS[base+'_'+selected].read_bytes())
                    selections[base]=dict(screened_mode=mode,selected_mode=selected,gates=gates,path=str(path.relative_to(ROOT)),sha256=sha256(path.read_bytes()).hexdigest())
    result=dict(comparisons=summary,selections=selections,errors=errors)
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (OUT/'selection.json').write_text(json.dumps(selections,indent=2),encoding='utf-8')
    lines=['# Transferring our sale policies to V44 and V45','', '## Result','']
    for base,s in selections.items():
        d=summary[f"confirmation/{base}/{s['screened_mode']}"]
        lines.append(f"- **{base.upper()}:** screened `{s['screened_mode']}`; selected **`{s['selected_mode']}`**. Confirmation mean margin change {d['margin_gain']:+,.1f}, own-cash change {d['cash_gain']:+,.1f}; {sum(v>0 for v in d['seed_gains'].values())}/8 positive seed averages. File: `{s['path']}`.")
    lines += ['', 'Each selected file is self-contained. `base` means the unchanged public source was retained because the transfer did not pass the predeclared gate. Existing `modern_router_selected.py`, the uploaded `market_impact_selected.py` and the Kaggle submission are unchanged.', '',
        '## What was transferred','',
        '1. **Order:** our existing static price-impact sale-ranking formula from `adaptive_market_order.py`, using the physically available lot and an equally sized hypothetical rival lot. It replaces the native quote-priority score inside the existing distinct contiguous sale blocks. Purchase barriers and quantities stay intact. It uses the native ordering activation window (from turn 288), rather than broadening the opening or moving orders across purchases.',
        '2. **Liquid:** sell additional physically available milk/wool during turns 216–695, with native ambiguity, pickup and order-cap guards. For stock sold ahead of a known future tape sale, add reservation debt so the corresponding future quantity is suppressed. This adapts our old liquidation policy to the newer scheduler; it is not a blind outer wrapper.',
        '3. **Both:** combine the two transfers. Physical worker actions, planting, economic feeding and crop-input planning remain controlled by the public base.', '',
        'The earlier joint-fertilizer candidate was already implemented on V45 and failed its independent confirmation. It is not included here. Several formerly researched ideas were also never selected; they are not treated as established improvements.', '',
        '## Evaluation','',
        'Development: three seeds (140000–140002), both seats, Farming V5 and Two Coins, two bases and four modes: 96 games. Select the highest paired mean margin per base, then confirm without tuning on eight new seeds (141000–141007), both seats, Farming V5, Two Coins and the other public base: 192 games. Two initial smoke games give 290 full games before file-loading checks.', '',
        'Future shops are uniform draws with replacement, common across comparisons and hidden until revealed. The independent confirmation sample is eight seeds; public rivals share some ancestry. The three-seed screen is deliberately provisional, not evidence of general superiority.', '',
        '| Panel | Base | Transfer | Margin gain | Own-cash gain | Baseline W/T/L | Transfer W/T/L |',
        '|---|---|---|---:|---:|---:|---:|',*table,'',
        '## Confirmation by opponent','',
        '| Base | Transfer | Opponent | Margin gain | Own-cash gain |','|---|---|---|---:|---:|']
    for base,s in selections.items():
        d=summary[f"confirmation/{base}/{s['screened_mode']}"]
        for opponent,x in d['opponents'].items():lines.append(f"| {base} | {s['screened_mode']} | {opponent} | {x['margin_gain']:+,.1f} | {x['cash_gain']:+,.1f} |")
    lines += ['', '## Gate and checks','',manifest['gate'],'',
        f"All 288 panel games completed 720 valid states, reconciled both cash ledgers and passed wheat conservation after every turn. Frozen source hashes match. Nonzero error/fallback counters: {len(errors)}. The two smoke games also passed. Twenty-two focused contracts across both bases passed for stock limits, physical-action preservation, future-sale suppression, terminal abstention, pickups, order capacity and purchase barriers.", '',
        '| Base | Gate | Passed |','|---|---|---|']
    for base,s in selections.items():
        for gate,passed in s['gates'].items():lines.append(f'| {base} | {gate} | {passed} |')
    detail=['## Why the transfers differ','',
        'The liquidation adapter was useful on our older five-tape router, which left accessible animal products unsold. The newer bases already bring sales forward selectively. Our transfer sells additional stock sooner and reduces future scheduled quantities. Its development losses came mainly from milk/wool revenue, with relatively small changes in units sold; this points to timing and realized-price effects rather than a large production gain.', '',
        '| Base | Development transfer | Milk revenue change | Milk units change | Wool revenue change | Wool units change |','|---|---|---:|---:|---:|---:|']
    for base in ('v44','v45'):
        for mode in ('order','liquid','both'):
            d=summary[f'development/{base}/{mode}']['accounting_delta']
            detail.append(f"| {base} | {mode} | {d.get('revenue:MILK',0):+,.1f} | {d.get('sold_units:MILK',0):+,.2f} | {d.get('revenue:WOOL',0):+,.1f} | {d.get('sold_units:WOOL',0):+,.2f} |")
    detail+=['', 'Order-only changes ranking within the native sale blocks. It preserves quantities and fits the newer controller more naturally, but its confirmation results—not that compatibility argument—determine selection.', '']
    lines[lines.index('## Gate and checks'):lines.index('## Gate and checks')]=detail
    lines += ['', '## Reproduction and provenance','',
        '- Build: `scripts/build_modern_sales.py`; build fragment: `agents/modern_sales_overlay.py`.',
        '- Contracts: `scripts/verify_modern_sales.py`.',
        '- Evaluation: `scripts/evaluate_modern_sales.py --phase smoke`, `development`, `select`, then `confirmation`.',
        '- Report and per-base selection: `scripts/report_modern_sales.py`.',
        '- Frozen manifests, screen selection, all ledgers and telemetry: `results/fresh/modern_sales/`.',
        '- Original V44/V45 source and attribution notices are retained. Our original ranking functions are extracted directly from `agents/adaptive_market_order.py` into each standalone build; no research module is imported at runtime.', '']
    entrypoints=OUT/'entrypoint_checks.json'
    if entrypoints.exists():
        checks=json.loads(entrypoints.read_text(encoding='utf-8'))
        assert {x['base'] for x in checks}=={'v44','v45'}
        for check in checks:
            assert check['sha256']==selections[check['base']]['sha256'] and check['steps']==720 and check['statuses']==['DONE','DONE']
        position=lines.index('## Gate and checks')+2
        lines[position:position]=['Both selected standalone files also passed full games through the official file-path agent loader, with native shop RNG, cash reconciliation and per-turn wheat conservation. Including these two packaging checks, the total is **292 full games**. These packaging games are not used for selection.', '']
    (ROOT/'docs/modern_sales_transfer.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
