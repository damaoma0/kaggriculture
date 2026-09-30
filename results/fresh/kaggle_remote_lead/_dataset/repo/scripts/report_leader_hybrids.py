"""Compare opening mechanisms and apply the independent promotion gate."""
from collections import Counter
from hashlib import sha256
from statistics import mean
import json
from evaluate_leader_hybrids import ROOT,OUT,PATHS,jobs

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    choice=json.loads((OUT/'discovery_selection.json').read_text(encoding='utf-8'))['candidate']
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for phase in ('screen','confirmation') for j in jobs(phase)]
    summary={};pairs_by={};errors=[];shop_table={}
    for phase in ('screen','confirmation'):
        base={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['phase']==phase and r['policy']=='baseline'}
        for policy in (('berries','herd','both') if phase=='screen' else (choice,)):
            pairs=[(r,base[r['seed'],r['seat'],r['opponent']]) for r in rows if r['phase']==phase and r['policy']==policy]
            pairs_by[phase+'/'+policy]=pairs
            for rival in ('all',*sorted({r['opponent'] for r,b in pairs})):
                ps=[(r,b) for r,b in pairs if rival=='all' or r['opponent']==rival]
                seeds={s:mean(r['margin']-b['margin'] for r,b in ps if r['seed']==s) for s in sorted({r['seed'] for r,b in ps})}
                summary[phase+'/'+policy+'/'+rival]=dict(games=len(ps),margin_gain=mean(r['margin']-b['margin'] for r,b in ps),cash_gain=mean(r['cash']-b['cash'] for r,b in ps),
                    candidate_wins=sum(r['margin']>0 for r,b in ps),baseline_wins=sum(b['margin']>0 for r,b in ps),candidate_ties=sum(r['margin']==0 for r,b in ps),baseline_ties=sum(b['margin']==0 for r,b in ps),seed_gains=seeds)
            if phase=='screen':
                for r,b in pairs:shop_table.setdefault(r['shops'][0],{}).setdefault(policy,[]).append(r['margin']-b['margin'])
    for r in rows:
        for field in ('telemetry','chassis_diagnostics'):
            for k,v in r[field].items():
                if any(w in k.lower() for w in ('error','fallback')) and isinstance(v,(int,float)) and v:errors.append((r['phase'],r['policy'],r['seed'],k,v))
    pairs=pairs_by['confirmation/'+choice];v=summary['confirmation/'+choice+'/all']
    gates=dict(positive_margin=v['margin_gain']>0,
        nonnegative_each_rival=all(summary['confirmation/'+choice+'/'+o]['margin_gain']>=0 for o in ('v45','twocoins','farmingv5')),
        six_positive_seeds=sum(x>0 for x in v['seed_gains'].values())>=6,no_fewer_wins=v['candidate_wins']>=v['baseline_wins'],cash_floor=v['cash_gain']>=-500,
        no_errors=not [e for e in errors if e[0]=='confirmation' and e[1]==choice],max_call_below_one_second=max(r['max_seconds'] for r,b in pairs)<1)
    selected=choice if all(gates.values()) else 'baseline'
    packaged=ROOT/('agents/v45_event_entrypoint_fixed.py' if selected=='baseline' else f'agents/v45_leader_{selected}_submission.py')
    path=ROOT/'agents/v45_leader_selected.py';path.write_bytes(packaged.read_bytes())
    accounting=Counter()
    for r,b in pairs:
        for sign,x in ((1,r),(-1,b)):
            for k,val in x['ledger'][x['seat']]['revenue'].items():accounting['revenue:'+k]+=sign*val
            for k,val in x['ledger'][x['seat']]['spend'].items():accounting['cost:'+k]+=sign*val
    assert abs(sum(val for k,val in accounting.items() if k.startswith('revenue:'))-sum(val for k,val in accounting.items() if k.startswith('cost:'))-v['cash_gain']*len(pairs))<1e-6
    boards={}
    for phase,policies in (('screen',('baseline','berries','herd','both')),('confirmation',('baseline',choice))):
        for policy in policies:
            rs=[r for r in rows if r['phase']==phase and r['policy']==policy]
            six=[next(s for s in r['snapshots'] if s['step']==144) for r in rs]
            boards[phase+'/'+policy]=dict(cash=mean(s['cash'] for s in six),cows=mean(s['animals'].get('COW',0) for s in six),sheep=mean(s['animals'].get('SHEEP',0) for s in six),
                early_berries=mean(sum(b['birth']<5 for b in s['berries']) for s in six),
                confirmed=mean(r['telemetry'].get('hybrid_confirmed_plants',0) for r in rs),lost=mean(r['telemetry'].get('hybrid_lost_before_handoff',0) for r in rs))
    own_units=Counter();opponent_revenue=Counter()
    for r,b in pairs:
        for sign,x in ((1,r),(-1,b)):
            for item,n in x['ledger'][x['seat']]['sold_units'].items():own_units[item]+=sign*n
            for item,value in x['ledger'][1-x['seat']]['revenue'].items():opponent_revenue[item]+=sign*value
    result=dict(discovery_choice=choice,selected=selected,sha256=sha256(path.read_bytes()).hexdigest(),source_sha256=sha256(PATHS[selected].read_bytes()).hexdigest(),gates=gates,comparisons=summary,boards=boards,
        own_sold_unit_changes={k:n/len(pairs) for k,n in own_units.items()},opponent_revenue_changes={k:n/len(pairs) for k,n in opponent_revenue.items()},
        accounting={k:val/len(pairs) for k,val in accounting.items()},errors=errors,max_seconds=max(r['max_seconds'] for r,b in pairs))
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Leader-inspired opening hybrids on V45','',
        f"Best discovery variant: **{choice}**. Selected after fresh confirmation: **{selected}**. Confirmation margin change: **{v['margin_gain']:+.1f}**; own cash: **{v['cash_gain']:+.1f}**. Positive seed averages: {sum(x>0 for x in v['seed_gains'].values())}/8.",'',
        '## What was combined','',
        'All candidates are standalone derivatives of the submitted V45 event-forecast agent (submission 56280048). We transfer leader-inspired investment choices onto V45\'s existing coordinates and worker routes. This is not a replay splice or a reconstruction of the rank-1 agent.', '',
        '- **berries:** buy strawberry seeds with available cash from turn 70, then replace eligible day-4 wheat replants at four sites that V45 will otherwise convert to strawberries on day 6. Existing seedlings are protected from incompatible early DIG/PLANT/HARVEST commands. Native later seed purchases are reduced to avoid buying the same four seeds twice.',
        '- **herd:** change the third cow purchase to a sheep and omit the fourth cow. Purchase, pickup and placement are changed consistently; all movement and service routes remain native. Extra wool is offered at existing native wool-sale slots.',
        '- **both:** combine those changes, purchasing the planned sheep before spending on early strawberry seeds.', '',
        'Important scope: the first-day V45 board and its 12 early melons remain. We do not reproduce the leader\'s first-day extra sheep, staged six-melon opening, or 7-8 strawberries at six days. Those require a different startup schedule and compatible continuation. A failure here does not disprove that full opening.', '',
        '## Frozen evaluation','',manifest['design'],'',
        'Discovery: 128 games, one seed per first-shop type, both seats, two rivals and four policies. Confirmation: 96 games, eight fresh seeds with natural-frequency hidden shop draws, both seats, three rivals, baseline plus the discovery winner. The shop-stratified screen is a coverage check, not enough evidence for a learned first-shop selection rule. No tuning after the discovery sources were frozen.', '',
        'Eight earlier full-game smoke checks were used for implementation: the first four exposed that seed spending could prevent the intended sheep purchase. Purchase sequencing was corrected before freezing; the final four tested the revised code. They are not counted as independent performance evidence.', '',
        '| Phase / candidate / rival | Margin gain | Own cash gain | Candidate wins | Baseline wins |',
        '|---|---:|---:|---:|---:|']
    for key,value in summary.items():
        if key.startswith('screen/') and not key.endswith('/all'):continue
        lines.append(f"| {key} | {value['margin_gain']:+.1f} | {value['cash_gain']:+.1f} | {value['candidate_wins']}/{value['games']} | {value['baseline_wins']}/{value['games']} |")
    lines+=['','## First-shop screen','', '| First shop | Berries | Herd | Both |','|---|---:|---:|---:|',
        *['| '+shop+' | '+' | '.join(f'{mean(values[p]):+.1f}' for p in ('berries','herd','both'))+' |' for shop,values in sorted(shop_table.items())],'',
        '## Six-day board checks','', '| Phase / policy | Cash | Cows | Sheep | Strawberries planted before native day | Early plants lost before handoff |','|---|---:|---:|---:|---:|---:|',
        *[f"| {key} | {b['cash']:.1f} | {b['cows']:.2f} | {b['sheep']:.2f} | {b['early_berries']:.2f} | {b['lost']:.2f} |" for key,b in boards.items()],'',
        'The strawberry-only variant can crowd out a scheduled cow purchase even though each immediate seed purchase is affordable. These are competing uses of early capital; the six-day herd counts show the actual resulting policy, not just the intended planting change. A skipped animal leaves some native service visits unproductive. Crop ages also differ after handoff, so unchanged routes are legal but not necessarily optimal.','',
        '## Confirmation cash accounting','', '| Flow | Mean candidate minus baseline |','|---|---:|',
        *[f"| {k} | {val:+.2f} |" for k,val in sorted(result['accounting'].items()) if abs(val)>.01],'',
        '## Promotion gate','',manifest['gate'],'',*[f'- {k}: {passed}' for k,passed in gates.items()],'',
        f"Maximum confirmation candidate call: {result['max_seconds']:.3f}s. Nonzero execution error/fallback entries across discovery and confirmation: {len(errors)}. All games checked 720 valid states, exact cash ledgers and per-turn wheat conservation. Focused contracts verify the paired purchase/pickup/place changes, seed affordability, observation immutability and early-crop protection.",'',
        '## Files','',
        '- `agents/leader_opening_overlay.py`; `scripts/build_leader_hybrids.py`.',
        '- `scripts/evaluate_leader_hybrids.py --phase smoke/screen/select/confirmation` (one phase per invocation).',
        '- `scripts/verify_leader_hybrids.py`; `scripts/report_leader_hybrids.py`.',
        '- `results/fresh/leader_hybrids/`: source manifest, individual game ledgers, board snapshots, discovery selection and summary.',
        '- `agents/v45_leader_selected.py`: exact file selected by the promotion gate. Existing agents and Kaggle submissions are unchanged.','']
    check=OUT/'entrypoint.json'
    if check.exists():
        verification=json.loads(check.read_text(encoding='utf-8'))
        assert verification['source_sha256']==sha256(PATHS[choice].read_bytes()).hexdigest() and verification['steps']==720 and verification['action_parity_count']==719
        lines += ['## Packaging correction','',
            'The first file-loader check exposed a last-callable export bug: the loader selected the cash-budget helper and silently produced a no-op game. Named-agent performance tests were unaffected. The submission-ready copy explicitly re-exports the intended agent as the final callable; all 719 actions then matched the research entry point exactly in a native-shop-RNG game. The original frozen experiment sources remain unchanged. A completed valid-state game alone is not an adequate packaging check.', '',
            f"Corrected candidate package: `{verification['packaged_file']}`. Total full games: 234 (224 performance-panel games, eight smoke/debug games, two packaging checks, one of which exposed the bug).",'']
    export=OUT/'event_export_fix.json'
    if export.exists():
        fix=json.loads(export.read_text(encoding='utf-8'))
        assert fix['parity_actions']==719 and fix['original_sha256']==sha256(PATHS['baseline'].read_bytes()).hexdigest()
        if selected=='baseline':assert fix['sha256']==result['sha256']
        lines += ['## Existing event-agent export issue','',
            'The audit also found that the previously submitted event agent exported its parent wrapper to Kaggle\'s last-callable loader. This bypassed forecast-history initialization: the original loader run left the event model uninitialized and its forecast planning calls reverted to the native input plan. Earlier packaging checks verified completion and accounting but did not verify entry-point/action parity, so they missed this.', '',
            f"Prepared `{fix['corrected_file']}` and verified all 719 actions against the research entry point in a further native-RNG game. The selected baseline copy in this study uses that corrected export. The prior submitted file is preserved, and no new submission was made. Including this audit, 235 full games were run.",'']
    index=lines.index('## Files')
    lines[index:index]=['## Interpretation','',
        f"In confirmation, our cash changed by {v['cash_gain']:+.1f}, while opponent cash changed by {v['cash_gain']-v['margin_gain']:+.1f}. Thus most of the match-margin loss comes from a richer opponent, not a comparably large drop in our cash. Our milk sales changed by {result['own_sold_unit_changes'].get('MILK',0):+.1f} units; opponent milk revenue changed by {result['opponent_revenue_changes'].get('MILK',0):+.1f}. This is consistent with reduced milk supply benefiting rivals through the shared market; it is not a controlled causal decomposition of every changed action.",'',
        'Retain the V45 policy. These selective transfers failed; the full leader opening remains untested as a hybrid. A fuller attempt would need coordinated first-day livestock, delayed melon planting and rewritten harvest/service schedules, not only earlier seeds or a different herd mix.','']
    (ROOT/'docs/leader_hybrids.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
