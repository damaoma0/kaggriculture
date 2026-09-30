"""Reconcile frozen branch outcomes; hindsight labels never enter the selector."""
from collections import Counter
from pathlib import Path
import json
import statistics
import tape_opportunity_audit as A

def difference(a,b): return {k:a.get(k,0)-b.get(k,0) for k in sorted(set(a)|set(b)) if a.get(k,0)!=b.get(k,0)}
def assets(arm,day,seat): return set(map(tuple,next(d for d in arm['daily'] if d['day']==day)['assets'][seat]))

def summarize():
    design=A.read(A.OUT/'design.json');cases=[];allrows=[]
    for spec in design['specs']:
        case=spec['id'];seat=spec['seat'];day=spec['checkpoint']//24
        candidates=A.read(A.OUT/'candidates'/f'{case}.json')
        bp=A.OUT/'arms'/f'{case}-c00-native.json'
        if not bp.exists(): continue
        baseline=A.read(bp);assert baseline['completed']
        old=A.read(Path(spec['reference'])/'arms'/f'{case}-baseline.json')
        assert baseline['actions_sha256']==old['actions_sha256'],('native full-game mismatch',case)
        assert baseline['cash_by_seat']==old['cash_by_seat']
        protected=assets(baseline,day,seat)&assets(baseline,day+3,seat)
        rows=[]
        for c in candidates['rows']:
            p=A.OUT/'arms'/f"{case}-{c['id']}-native.json"
            if not p.exists(): continue
            arm=A.read(p);assert arm['completed'] and arm['prefix_verified'] and arm['ledger_verified']
            missing=sorted(protected-assets(arm,day+3,seat))
            econ=arm['economics'];be=baseline['economics']
            for s in range(2):
                assert 3000+sum(econ[s]['revenue'].values())-sum(econ[s]['spend'].values())==arm['cash_by_seat'][s]
            metadata=c['metadata'];delta=arm['margin']-baseline['margin']
            row=dict(case=case,id=c['id'],route=c['route'],group=c['group'],selected=c['selected'],
                margin=arm['margin'],delta=delta,own_delta=arm['cash']-baseline['cash'],
                rival_delta=arm['rival_cash']-baseline['rival_cash'],missing=missing,
                cohort_preserving=not missing,predicted_margin=metadata.get('mean_margin'),
                predicted_risk=metadata.get('risk_score'),forecast_scenarios=len(metadata.get('predictions',[])),
                predicted_own_delta=statistics.mean(metadata['cash_deltas']) if metadata.get('cash_deltas') else None,
                forecast_cohort_rejected=bool(metadata.get('protection_failures')),
                admitted=metadata.get('admitted',False),
                revenue_delta=[difference(econ[s]['revenue'],be[s]['revenue']) for s in range(2)],
                cost_delta=[difference(econ[s]['spend'],be[s]['spend']) for s in range(2)],
                sold_delta=[difference(econ[s]['units'],be[s]['units']) for s in range(2)],
                physical_delta=[difference(arm['physical'][s],baseline['physical'][s]) for s in range(2)],
                seconds=arm['seconds'],peak_rss_gib=arm['peak_rss_gib'])
            assert row['delta']==row['own_delta']-row['rival_delta']
            rows.append(row)
        if not rows: continue
        eligible=[r for r in rows if r['cohort_preserving']]
        best=max(eligible,key=lambda r:r['margin'])
        selected=next((r for r in rows if r['selected']),None)
        original=max((r for r in eligible if r['group']=='original'),key=lambda r:r['margin'])
        oldset=max((r for r in eligible if r['group'] in ('original','repair')),key=lambda r:r['margin'])
        confirms=[]
        confirmbase=A.OUT/'arms'/f'{case}-c00-r3.json'
        if confirmbase.exists():
            cb=A.read(confirmbase);assert cb['completed']
            for r in rows:
                cp=A.OUT/'arms'/f"{case}-{r['id']}-r3.json"
                if not cp.exists():continue
                cr=A.read(cp);assert cr['completed'] and cr['prefix_verified'] and cr['ledger_verified']
                confirms.append(dict(id=r['id'],route=r['route'],margin=cr['margin'],
                    delta_vs_no_switch_with_replanning=cr['margin']-cb['margin'],
                    delta_vs_native=cr['margin']-baseline['margin'],later_choices=cr['selected'][1:],
                    own_delta_vs_native=cr['cash']-baseline['cash'],
                    rival_delta_vs_native=cr['rival_cash']-baseline['rival_cash']))
        cases.append(dict(case=case,day=day,baseline_margin=baseline['margin'],n=len(rows),expected=len(candidates['rows']),
            best_unrestricted=max(rows,key=lambda r:r['margin']),
            profitable_cohort_losses=[r['id'] for r in rows if r['delta']>0 and not r['cohort_preserving']],
            best=best,best_original=original,best_original_plus_repairs=oldset,
            selected=selected,selection_regret=None if selected is None else best['margin']-selected['margin'],
            false_negative_positive=[r['id'] for r in eligible if r['delta']>0 and not r['selected']],
            false_negative_500=[r['id'] for r in eligible if r['delta']>=500 and not r['selected']],
            predicted_negative_winners=[r['id'] for r in eligible if r['delta']>0 and r['predicted_risk'] is not None and r['predicted_risk']<=0],
            cohort_failures=sum(not r['cohort_preserving'] for r in rows),confirmation=confirms))
        allrows.extend(rows)
    result=dict(cases=cases,rows=allrows,completed=len(allrows),
        caution='Deliberately selected exposed development worlds. Best branch uses realized future outcomes and cannot be deployed. Cohort-preserving checks survival at next reveal, not guaranteed long-run profitability or all execution constraints.',
        mean_seconds=statistics.mean(r['seconds'] for r in allrows) if allrows else None)
    A.write(A.OUT/'audit.json',result)
    print(json.dumps(dict(completed=len(allrows),cases=[dict(case=c['case'],n=c['n'],expected=c['expected'],baseline=c['baseline_margin'],best=c['best']['delta'],route=c['best']['route'],group=c['best']['group'],original=c['best_original']['delta'],oldset=c['best_original_plus_repairs']['delta'],selected=None if c['selected'] is None else c['selected']['delta'],prednegative=c['predicted_negative_winners'],fails=c['cohort_failures'],confirms=c['confirmation']) for c in cases]),indent=2))
    return result

def report(result):
    cases=result['cases'];rows=result['rows']
    complete=len(cases)==8 and all(c['n']==c['expected'] for c in cases)
    lines=['# Tape opportunity audit — 24 September 2026','',
        '## Findings','',
        'The four large untouched losses all contain strong alternatives in the existing shortlist: +1,372, +9,839, +5,185 and +8,054 margin. Their gains persist with later R3 replanning. Additional donor retrieval did not improve the best cohort-preserving result in any of these eight cases. Prioritize admission and forecast quality on this evidence; it does not establish exhaustive tape coverage.','',
        'A concrete admission mismatch rejects a robust forecast margin gain because our own cash falls slightly. A post-hoc checkpoint ablation removes only that requirement for ordinary, fully evaluated alternatives while retaining cohort, downside and risk gates. It changes one of eight decisions, recovering +8,054; the other seven decisions remain identical, including the known bad +4,842-forecast/−2,530-realized switch. This is a small development ablation, not general qualification.','',
        'The largest missed recovery is conditional on later shops. Its original single scout predicted −6,949; completing all eight public futures still predicts −2,031. Supplying true future shops predicts +9,896 versus +9,839 realized. This establishes substantial hindsight headroom, not that switching was correct in expectation at D15. Fully evaluating the missed best branches did not admit any new one. More rollout samples alone did not fix these examples.','',
        'There is also residual model error: with true future shops, the known bad route 47 still predicts about +404 versus −2,530 realized, and is ranked above the profitable alternative (about +49 predicted versus +1,366 realized). Own simulation approximations and the nonresponsive rival model both remain possible causes.','',
        '## Recommended implementation order','',
        '1. Build a separate margin-based admission challenger with explicit cash-feasibility checks. Full simulation already charges spending; requiring higher final own cash can block a useful relative gain. Preserve the existing downside and execution gates initially.',
        '2. Value contingent plans that can adjust at the next actual shop reveal. Preserve profitable options where their cost is justified. Use honest future-shop distributions; these results do not justify adding unrevealed shops to the playing selector or assuming every hindsight winner was an expected-value mistake.',
        '3. Improve responsive opponent and own-continuation forecasts where fully evaluated candidates are still ranked incorrectly. The existing bad switch remains a required regression test.',
        '4. Keep the unrecovered old random-06 world as a candidate-generation/earlier-reveal target: no tested alternative improved its native result. Add persistent production edits and explicit retirement operators as a separate action family.',
        '5. Freeze the challenger and run genuinely new worlds against both live opponents. These eight selected development worlds cannot establish population gains or safety.','',
        '## What was tested','',
        f"{'Completed' if complete else 'Partial'}: {len(rows)} full-game branches across {len(cases)} deliberately selected, previously exposed worlds. Seven worlds use live V56; one uses live original m1. These are development counterfactuals, not a random performance estimate or a qualified new policy.",'',
        'Each branch reproduces the native prefix exactly, forces one candidate for three days at the specified reveal, then resumes native routing. The existing shortlist and repairs are supplemented by six additional donors, selected with known-shop distance under board mismatch caps 8/14/24, with bounded repairs where applicable. All candidate choices were frozen before new branch outcomes. No new planting or retirement operator is implemented in this stage.','',
        '“Cohort-preserving” means retaining all starting tomato, strawberry and melon crops and animals that native retains at the next reveal. It does not guarantee perfect execution, preservation forever, or profitable continuation. Wheat and carrot cohorts are not in this guard. All physical failures and economics are retained.','',
        f"There are {sum(len(c['confirmation']) for c in cases)} later-replanning confirmation games in addition to the {len(rows)} initial full games.",'',
        '## Realized opportunity with common native continuation','',
        'All gains below are changes in final own cash minus rival cash. Best alternatives are selected with hindsight from this bounded audit; they are not deployable decisions.','',
        '| World | Reveal | Native margin | Current selection gain | Best original shortlist gain | Best tested cohort-preserving gain | Best route |',
        '|---|---:|---:|---:|---:|---:|---|']
    for c in cases:
        sel='pending' if c['selected'] is None else f"{c['selected']['delta']:+,.0f}"
        route=c['best']['route'];route=route[0] if isinstance(route,list) else route
        lines.append(f"| {c['case']} | D{c['day']} | {c['baseline_margin']:,.0f} | {sel} | {c['best_original']['delta']:+,.0f} | {c['best']['delta']:+,.0f} | {route} ({c['best']['group']}) |")
    negative=[r for r in rows if r['route'] is not None and r['cohort_preserving'] and r['delta']>0 and r['predicted_risk'] is not None and r['predicted_risk']<=0]
    large=[r for r in negative if r['delta']>=500]
    lines+=['',f"There are {len(negative)} cohort-preserving branches with positive realized gains despite nonpositive forecast scores, including {len(large)} gains of at least 500. These are correlated branches within eight selected worlds. A realized winner does not establish that its expected gain was positive using information available at the reveal.",'',
        f"{sum(not r['cohort_preserving'] for r in rows)} branches lost at least one cohort that native retained at the next reveal. {sum(r['delta']>0 and not r['cohort_preserving'] for r in rows)} of those still improved realized margin; this motivates explicit priced-retirement experiments, rather than treating accidental loss as a valid replacement plan.",'',
        '## Check later replanning','',
        'The predeclared confirmation set is native, the current R3 choice, and the two highest-margin cohort-preserving branches in each world (deduplicated). R3 runs at remaining D12/D15/D18 checkpoints. Selection of these confirmation branches uses hindsight and supplies no independent qualification.','',
        '| World | Route | Final margin | Gain vs no forced switch with R3 later | Gain vs original native | Later choices |','|---|---|---:|---:|---:|---|']
    for c in cases:
        for r in c['confirmation']:
            lines.append(f"| {c['case']} | `{json.dumps(r['route'])}` | {r['margin']:,.0f} | {r['delta_vs_no_switch_with_replanning']:+,.0f} | {r['delta_vs_native']:+,.0f} | `{json.dumps(r['later_choices'])}` |")
    lines+=['','## Economics of the strongest alternatives','']
    specs={s['id']:s for s in A.read(A.OUT/'design.json')['specs']}
    for c in sorted(cases,key=lambda c:c['best']['delta'],reverse=True)[:4]:
        r=c['best'];seat=specs[c['case']]['seat'];opp=1-seat
        lines += [f"### {c['case']}: {r['delta']:+,.0f}",'',
            f"Route `{json.dumps(r['route'])}`. Own cash changes {r['own_delta']:+,.0f}; rival cash changes {r['rival_delta']:+,.0f}. Forecast margin change was {r['predicted_margin']} over {r['forecast_scenarios']} scenario(s); risk score {r['predicted_risk']}.",'',
            '| Product | Our sale receipts change | Rival sale receipts change | Our sold units change |','|---|---:|---:|---:|']
        for p in sorted(set(r['revenue_delta'][seat])|set(r['revenue_delta'][opp])):
            lines.append(f"| {p} | {r['revenue_delta'][seat].get(p,0):+,} | {r['revenue_delta'][opp].get(p,0):+,} | {r['sold_delta'][seat].get(p,0):+,} |")
        lines+=['',f"Our cost changes: `{json.dumps(r['cost_delta'][seat],sort_keys=True)}`.",
                f"Rival cost changes: `{json.dumps(r['cost_delta'][opp],sort_keys=True)}`.",'']
    lines+=['## Future-shop attribution','',
        'A separate oracle diagnostic gives the forecasting model the actual future shops, keeps the modeled rival, and evaluates three donor trajectories. This cannot be used online. Residual errors can reflect rival behavior, own rollout approximations, and exogenous events; this test does not isolate the rival model alone.','',
        '| World | Candidate | Actual gain | Original forecast | Full 8 public scenarios | Forecast with true future shops |','|---|---|---:|---:|---:|---:|']
    for c in cases:
        p=A.OUT/'attribution'/f"{c['case']}.json"
        if not p.exists():continue
        attribution=A.read(p)
        for cid,means in attribution['means'].items():
            r=next(r for r in rows if r['case']==c['case'] and r['id']==cid)
            predicted='unavailable' if r['predicted_margin'] is None else f"{r['predicted_margin']:+,.0f}"
            full=attribution['balanced_public_forecast'][cid]['mean_margin']
            lines.append(f"| {c['case']} | {cid} | {r['delta']:+,.0f} | {predicted} | {full:+,.0f} | {means['margin_delta']:+,.0f} |")
    lines+=['','## Verification and limits','',
        '- Every completed branch checks both cash ledgers and the exact two-seat action prefix. Native-control action hashes and final cash match the earlier full games.',
        '- The official engine runs both policies live; no frozen-opponent continuation is counted here.',
        '- Input and candidate hashes were saved before branch execution. Frozen policy payload files are rechecked in every worker.',
        '- Local execution is diagnostic. The audit does not enforce the competition time bank; unlimited-budget later R3 confirmation is not a speed qualification.',
        f"- Native-continuation branch time averages {result['mean_seconds']:.2f} seconds including local setup; this is full-game labeling time, not playing-selector latency.",
        '- Raw audit, candidates, traces, action streams, confirmations and attribution are under `results/fresh/tape_opportunity_20260924_01a0/`.',
        '- Native m1, V9, and the frozen R3 policy were not changed. No submission was made.','']
    target=A.ROOT/'docs/tape_opportunity_audit_20260924.md'
    target.write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__': report(summarize())
