"""Paired economics, exact streams, decision gates and clustered uncertainty."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse
import random
import statistics
import run_tape_margin_study as S
from audit_tape_repair_panel import comparison as previous_comparison,distribution,percentile

def comparison(rows,reference):
    result=previous_comparison(rows,reference)
    clusters=defaultdict(list)
    for row in rows:clusters[row['world']].append(row['delta_'+reference])
    blocks=[(sum(v),len(v)) for v in clusters.values()]
    rng=random.Random(72416093);means=[]
    for _ in range(10000):
        sample=rng.choices(blocks,k=len(blocks))
        means.append(sum(v for v,n in sample)/sum(n for v,n in sample))
    result['world_cluster_bootstrap_95']=[percentile(means,.025),percentile(means,.975)]
    return result

def audit(panel,partial=False):
    folder=S.OUT/panel;design=S.read(folder/'design.json')
    manifest=S.read(S.OUT/'source_manifest.json')
    for rel,h in manifest['sha256'].items():assert S.sha256((S.OUT/'payload'/rel).read_bytes()).hexdigest()==h,rel
    assert S.sha256((folder/'run_panel.py').read_bytes()).hexdigest()==design['harness_sha256']
    if panel=='development':
        for rel,value in S.read(S.OUT/'reference_manifest.json').items():
            assert S.sha256((S.OUT/rel).read_bytes()).hexdigest()==value['sha256'],rel
    rows=[];checks=Counter();times=defaultdict(list);banks=defaultdict(list);rss=defaultdict(list)
    durations=defaultdict(list);decisions=Counter();overrides=[];errors=[]
    arms=['baseline','r3','candidate']+(['v9'] if panel=='development' else [])
    for spec in design['specs']:
        case=spec['id']
        if not all((folder/'arms'/f'{case}-{arm}.json').exists() for arm in arms):continue
        results={arm:S.read(folder/'arms'/f'{case}-{arm}.json') for arm in arms}
        if not all(r.get('completed') for r in results.values()):
            errors.append(dict(case=case,failed=[a for a,r in results.items() if not r.get('completed')]));continue
        streams={}
        for arm,r in results.items():
            assert r['spec']==spec and r['ledger_verified']
            assert r['margin']==r['cash']-r['rival_cash']
            for seat,e in enumerate(r['economics']):
                assert 3000+sum(e['revenue'].values())-sum(e['spend'].values())==r['cash_by_seat'][seat]
            stream=S.read(folder/'actions'/f'{case}-{arm}.json');streams[arm]=stream
            assert [len(s) for s in stream]==[719,719]
            assert S.digest(stream)==r['actions_sha256']
            assert S.digest([[stream[s][t] for s in range(2)] for t in range(288)])==r['prefix_sha256']
            assert len(r['timings'])==719
            assert abs(r['remaining_overage_seconds']-(60-sum(max(0,t['seconds']-1) for t in r['timings'])))<1e-8
            if arm=='candidate':assert 'native_telemetry' in r
            if 'native_telemetry' in r:checks['telemetry_checked']+=1
            else:checks['historical_telemetry_unavailable']+=1
            assert not any(('error' in k.lower() or 'exception' in k.lower()) and v for k,v in r.get('native_telemetry',{}).items())
            banks[arm].append(r['remaining_overage_seconds']);rss[arm].append(r['peak_rss_gib']);durations[arm].append(r['seconds'])
            times[arm].extend(t['seconds'] for t in r['timings'] if t['searched'])
            checks['ledgers']+=2;checks['action_streams']+=2;checks['games']+=1
            if r['measured_bank_exhausted']:checks['exhausted_bank']+=1
        assert len({r['prefix_sha256'] for r in results.values()})==1
        seat=spec['seat'];candidate=results['candidate']
        row=dict(case=case,world=('old-' if case.startswith('random') else 'panel-')+str(spec.get('world',case)),
                 opponent=spec['opponent'],candidate=candidate['margin'],
                 override_days=[],r3_action_exact=streams['candidate']==streams['r3'])
        for arm in arms:
            if arm=='candidate':continue
            ref=results[arm];row[arm]=ref['margin'];row['delta_'+arm]=candidate['margin']-ref['margin']
            row['own_cash_delta_'+arm]=candidate['cash']-ref['cash']
            row['rival_cash_delta_'+arm]=candidate['rival_cash']-ref['rival_cash']
        row['economics_delta_r3']=[{field:{k:candidate['economics'][s][field].get(k,0)-results['r3']['economics'][s][field].get(k,0)
            for k in set(candidate['economics'][s][field])|set(results['r3']['economics'][s][field])
            if candidate['economics'][s][field].get(k,0)!=results['r3']['economics'][s][field].get(k,0)}
            for field in ('revenue','spend','units')} for s in range(2)]
        for day in (12,15,18):
            d=S.read(folder/'decisions'/f'{case}-candidate-d{day}.json')
            decisions['total']+=1;decisions['timeouts']+=bool(d['timed_out'])
            for gate in d['margin_admission']:
                decisions['ordinary_candidates']+=1
                decisions['fully_evaluated_ordinary']+=gate['complete']
                decisions['extra_spending_failure_rejects']+=bool(gate['extra_failed_spending'])
                if gate['complete'] and gate['mean_own_cash'] is not None and gate['mean_own_cash']<=0:
                    decisions['fully_evaluated_nonpositive_own_cash']+=1
                    decisions['nonpositive_own_cash_passing_other_gates']+=gate['admitted']
            if d['margin_override']:
                selected=next(c for c in d['candidates'] if c['route']==d['selected'])
                gate=next(c for c in d['margin_admission'] if c['route']==d['selected'])
                assert isinstance(d['selected'],int) and selected['fully_evaluated'] and len(selected['predictions'])==8
                assert gate['admitted'] and not gate['extra_failed_spending'] and not selected['protection_failures']
                assert selected['risk_score']>350 and selected['minimum_margin']>=-selected['loss_budget']
                row['override_days'].append(day);decisions['overrides']+=1
                overrides.append(dict(case=case,day=day,selected=d['selected'],r3_selected=d['r3_selected'],
                    mean_margin=selected['mean_margin'],risk_score=selected['risk_score'],minimum_margin=selected['minimum_margin'],
                    mean_own_cash=gate['mean_own_cash']))
            else:assert d['selected']==d['r3_selected']
        if not row['override_days']:assert row['r3_action_exact'],'No override but R3 actions changed'
        rows.append(row)
    if not partial:assert len(rows)==len(design['specs']) and not errors,(len(rows),errors)
    comparisons={ref:comparison(rows,ref) for ref in arms if ref!='candidate'} if rows else {}
    by_opponent={rival:{ref:comparison([r for r in rows if r['opponent']==rival],ref) for ref in arms if ref!='candidate'}
                 for rival in sorted({r['opponent'] for r in rows})}
    result=dict(panel=panel,completed=len(rows),expected=len(design['specs']),rows=rows,checks=dict(checks),errors=errors,
        comparisons=comparisons,by_opponent=by_opponent,decisions=dict(decisions),overrides=overrides,
        action_exact_r3=sum(r['r3_action_exact'] for r in rows),
        timings={a:distribution(v) for a,v in times.items()},banks={a:distribution(v) for a,v in banks.items()},
        peak_rss={a:distribution(v) for a,v in rss.items()},full_game_seconds={a:distribution(v) for a,v in durations.items()})
    S.write(folder/'audit.json',result)
    print(S.json.dumps(dict(panel=panel,completed=len(rows),expected=len(design['specs']),comparisons=comparisons,
                           decisions=decisions,changed=[r for r in rows if r['delta_r3']]),indent=2))
    return result

def report():
    panels={p:S.read(S.OUT/p/'audit.json') for p in ('development','qualification') if (S.OUT/p/'audit.json').exists()}
    lines=['# Margin admission challenger R4 — 24 September 2026','',
        'R4 runs frozen R3, then considers fully evaluated ordinary alternatives using competitive margin. It retains cohort protection, the risk threshold, downside limits, and requires no additional failed purchases/hires in any paired scenario. Validated R3 repairs remain available. No extra rollouts are added. Native m1, V9 and R3 source files are unchanged.','',
        'Development uses 50 exposed matchups: the earlier 24 worlds crossed with V56 and original m1, plus two repair controls. Qualification uses 24 newly generated IID shop worlds crossed with both live opponents and three arms: native m1, R3, R4. The policy and both panels were frozen before new outcomes.','']
    for name,d in panels.items():
        lines += [f'## {name.title()}: {d["completed"]}/{d["expected"]} matchups','',
            '| Comparator | Better / same / worse | Mean margin gain | 95% world bootstrap interval | Wins before → after | Wins gained / lost |',
            '|---|---:|---:|---|---:|---:|']
        for ref,c in d['comparisons'].items():
            lo,hi=c['world_cluster_bootstrap_95']
            lines.append(f"| {ref} | {c['better']} / {c['equal']} / {c['worse']} | {c['margin_gain']['mean']:+,.1f} | [{lo:+,.1f}, {hi:+,.1f}] | {c['reference_wins']} → {c['candidate_wins']} | {c['wins_gained']} / {c['wins_lost']} |")
        lines += ['',f"{d['decisions'].get('overrides',0)} admission overrides across {d['decisions'].get('total',0)} decisions; {d['action_exact_r3']} complete two-seat action streams identical to R3. {d['decisions'].get('timeouts',0)} search timeouts.",'',
            '| Changed case vs R3 | R3 margin | R4 margin | Margin change | Own cash change | Rival cash change | Override days |',
            '|---|---:|---:|---:|---:|---:|---|']
        for r in d['rows']:
            if r['delta_r3']:
                lines.append(f"| {r['case']} | {r['r3']:,.0f} | {r['candidate']:,.0f} | {r['delta_r3']:+,.0f} | {r['own_cash_delta_r3']:+,.0f} | {r['rival_cash_delta_r3']:+,.0f} | {r['override_days']} |")
        if name=='qualification':
            lines += ['','### Full R3/R4 package versus native m1','',
                'These changes are shared by R3 and R4; they are not incremental gains from the new admission rule.','',
                '| Case | Native margin | R3/R4 margin | Change |','|---|---:|---:|---:|']
            for r in d['rows']:
                if r['delta_baseline']:
                    lines.append(f"| {r['case']} | {r['baseline']:,.0f} | {r['candidate']:,.0f} | {r['delta_baseline']:+,.0f} |")
        lines += ['','| Opponent, vs R3 | Better / same / worse | Mean margin gain | Wins before → after |','|---|---:|---:|---:|']
        for rival,cs in d['by_opponent'].items():
            c=cs['r3'];lines.append(f"| {rival} | {c['better']} / {c['equal']} / {c['worse']} | {c['margin_gain']['mean']:+,.1f} | {c['reference_wins']} → {c['candidate_wins']} |")
        lines+=['','| Timing | R3 | R4 |','|---|---:|---:|']
        for label,field in [('Mean reveal seconds','mean'),('P95 reveal seconds','p95'),('Maximum reveal seconds','maximum')]:
            lines.append(f"| {label} | {d['timings']['r3'][field]:.3f} | {d['timings']['candidate'][field]:.3f} |")
        lines += ['',f"Minimum measured remaining time bank: R4 {d['banks']['candidate']['minimum']:.2f}s. Maximum R4 process RSS: {d['peak_rss']['candidate']['maximum']:.2f} GiB.",'']
    micro=S.OUT/'admission_microbenchmark.json'
    if micro.exists():
        m=S.read(micro)
        lines += ['## Incremental admission cost','',
            f"Across {m['calls']} calls on the saved recovery checkpoint, the new admission pass takes median {m['median_microseconds']:.1f} microseconds and P95 {m['p95_microseconds']:.1f} microseconds. It adds zero rollouts. Full-game timings include the existing search and local contention.",'']
    attribution=S.OUT/'forecast_regression_attribution.json'
    if attribution.exists():
        d=S.read(attribution)
        lines += ['## Separate diagnosis of the retained route-47 regression','',
            f"Actual margin change: {d['actual']['margin_delta']:+,.0f}, comprising own cash {d['actual']['own_delta']:+,.0f} and rival cash {d['actual']['rival_delta']:+,.0f}. The unchanged public eight-world forecast was +4,842. All substitutions below use offline future information and are unavailable to the playing selector.",'',
            '| Diagnostic | Predicted own change | Predicted rival change | Predicted margin change | Margin prediction error |','|---|---:|---:|---:|---:|']
        for r in d['rows']:
            lines.append(f"| {r['label']} | {r['own_delta']:+,.0f} | {r['rival_delta']:+,.0f} | {r['margin_delta']:+,.0f} | {r['margin_prediction_error']:+,.0f} |")
        lines += ['',f"Actual same-hour product buy/sell round trips: {len(d['same_hour_round_trips']['baseline'])} baseline and {len(d['same_hour_round_trips']['candidate'])} candidate. Ordered-trade diagnostics preserve gross order instead of netting these trades.",'',
            'The branch-specific rival net supply predicts −2,155. Adding the actual rival cost change predicts −2,532, within 2 of the realized −2,530. Preserving gross transaction order and adding actual weeds make no further cash-difference change here. All prescribed ordered trades execute with zero shortfall/excess. One late opponent weed location collides with the projected opponent board, so the weed substitution is not a fully exact physical reconstruction.',
            'This case points to rival sales volume/timing and cost response as the useful modeling target. It does not establish that weeds or trade order are immaterial in other games.','',
            'These substitutions are nested diagnostics, not independent causal effect estimates. Net supply, trade order, own weeds and rival costs can interact. Raw outputs record weed collisions and ordered-trade shortfall/excess to expose invalid oracle assumptions.','']
    q=panels.get('qualification')
    if q and q['completed']==q['expected']:
        c=q['comparisons']['r3']
        lines+=['## Conclusion','']
        if c['better']==0 and c['worse']==0:
            lines+=['R4 fixes a concrete competitive-objective mismatch and preserves the +8,054 development recovery. It produces no incremental result on the 48 fresh matchups. This is a narrow, inexpensive research change; broad recovery or an ELO gain has not been established. Keep it as a challenger and prioritize forecast fidelity and plans that can adapt at future reveals.','']
        else:
            lines += [f"Fresh R4 versus R3: {c['better']} better, {c['equal']} equal, {c['worse']} worse, mean margin change {c['margin_gain']['mean']:+,.1f}. Treat these 24 independent worlds as limited qualification; inspect regressions and win conversions before promotion.",'']
    lines += ['## Limits','',
        '- Matchups sharing the same shop world are correlated; intervals resample whole worlds. Only 24 new independent worlds are included.',
        '- If every paired difference is zero, a bootstrap interval of [0, 0] describes this observed sample; it cannot rule out rare gains or regressions.',
        '- Development controls were reused by verified content hashes. Their timing was measured in an earlier run, so development timing differences are not a controlled speed comparison.',
        '- Qualification arms run locally with at most two workers and a memory gate; these are synchronous official-engine games, not the actual competition runner. The time bank is measured, not enforced.',
        '- Passing the simulated spending check does not establish accurate rival forecasts. The known route-47 regression is intentionally retained and reported.',
        '- No submission or native-agent replacement is performed.','']
    path=S.ROOT/'docs/tape_margin_r4_20260924.md';path.write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('panel',choices=['development','qualification']);ap.add_argument('--partial',action='store_true')
    a=ap.parse_args();audit(a.panel,a.partial);report()
