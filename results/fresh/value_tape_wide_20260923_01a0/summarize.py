"""Audit and summarize the frozen panel; partial summaries are marked explicitly."""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import json
import random
import statistics

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]

def write(path,x):
    path.write_text(json.dumps(x,indent=2,ensure_ascii=True),encoding='utf-8')

def percentile(xs,p):
    ordered=sorted(xs);pos=(len(ordered)-1)*p;lo=int(pos);hi=min(lo+1,len(ordered)-1)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(pos-lo)

def bootstrap(rows,cluster):
    groups=defaultdict(list)
    for r in rows:groups[cluster(r)].append(r['margin_delta'])
    values=list(groups.values())
    if len(values)<2:return None
    rng=random.Random(93238756)
    samples=[]
    for _ in range(10000):
        chosen=[values[rng.randrange(len(values))] for _ in values]
        samples.append(sum(sum(x) for x in chosen)/sum(len(x) for x in chosen))
    return [percentile(samples,.025),percentile(samples,.975)]

def stats(rows,cluster=None):
    if not rows:return {'n':0}
    vals=[r['margin_delta'] for r in rows]
    losses=[r for r in rows if r['baseline_margin']<0]
    deficit=-sum(r['baseline_margin'] for r in losses)
    remaining=sum(max(0,-r['candidate_margin']) for r in losses)
    return dict(n=len(rows),worlds=len(set(r['spec']['world'] for r in rows)),
        improved=sum(v>0 for v in vals),regressed=sum(v<0 for v in vals),unchanged=sum(v==0 for v in vals),
        mean_margin=statistics.mean(vals),median_margin=statistics.median(vals),
        total_margin=sum(vals),minimum=min(vals),maximum=max(vals),
        mean_own_cash=statistics.mean(r['cash_delta'] for r in rows),
        mean_rival_cash=statistics.mean(r['rival_delta'] for r in rows),
        baseline_wins=sum(r['baseline_margin']>0 for r in rows),candidate_wins=sum(r['candidate_margin']>0 for r in rows),
        baseline_ties=sum(r['baseline_margin']==0 for r in rows),candidate_ties=sum(r['candidate_margin']==0 for r in rows),
        losses_to_wins=sum(r['baseline_margin']<0 and r['candidate_margin']>0 for r in rows),
        wins_to_losses=sum(r['baseline_margin']>0 and r['candidate_margin']<0 for r in rows),
        baseline_losses=len(losses),baseline_losses_improved=sum(r['margin_delta']>0 for r in losses),
        baseline_losses_worse=sum(r['margin_delta']<0 for r in losses),
        baseline_loss_deficit=deficit,remaining_deficit_on_baseline_losses=remaining,
        net_deficit_recovered=deficit-remaining,recovered_fraction=(deficit-remaining)/deficit if deficit else None,
        interventions=sum(r['intervened'] for r in rows),actions_changed=sum(r['actions_changed'] for r in rows),
        intervention_types=dict(Counter(r.get('intervention_type','none') for r in rows)),
        multiple_interventions=sum(sum(x is not None for x in r['selected'])>1 for r in rows),
        measured_candidate_time_bank_failures=sum(r['candidate_bank']<0 for r in rows),
        minimum_candidate_time_bank=min(r['candidate_bank'] for r in rows),
        margin_95pct_cluster_bootstrap=bootstrap(rows,cluster) if cluster else None)

def main():
    manifest=json.loads((OUT/'panel_manifest.json').read_text())
    for name,expected in manifest['sha256'].items():
        assert sha256((OUT/name).read_bytes()).hexdigest()==expected,name
    rows=[json.loads(p.read_text()) for p in sorted((OUT/'pairs').glob('*.json')) if not p.name.startswith('anchor-')]
    valid=[r for r in rows if r['completed']]
    live=[r for r in valid if r['spec']['kind']=='live']
    replay=[r for r in valid if r['spec']['kind']=='replay']
    clean_replay=[r for r in replay if not any(r[k]['material_command_break'] for k in ('baseline_divergence','candidate_divergence'))]
    recorded=[json.loads(p.read_text()) for p in (OUT/'arms').glob('*-recording.json') if not p.name.startswith('anchor-')]
    decision_files={p:p.read_text() for p in (OUT/'decisions').glob('*.json') if not p.name.startswith('anchor-')}
    decisions=[(p,json.loads(value)) for p,value in decision_files.items()]
    veto=Counter();counts=Counter();selected=Counter();predicted=[]
    types_by_case=defaultdict(set)
    for path,d in decisions:
        counts['decisions']+=1
        counts['native_fallback']+=d['selected'] is None
        counts['time_out']+=bool(d['timed_out'])
        counts['rollout_calls']+=d['rollouts']
        counts['pruned_rollouts']+=d['pruned_rollouts']
        for c in d['candidates']:
            if c['route'] is None:continue
            counts['candidate_routes']+=1
            counts['scouted']+=bool(c['scouted'])
            counts['expanded']+=bool(c['expanded'])
            counts['all_eight_worlds']+=bool(c['fully_evaluated'])
            counts['admitted']+=bool(c['admitted'])
            if c.get('protection_failures'):veto['protected_cohort_or_hire_failure']+=1
            elif not c['expanded']:veto['scout_did_not_expand']+=1
            elif not c['fully_evaluated']:veto['four_world_screen_did_not_advance']+=1
            elif not c['admitted']:veto['eight_world_cash_or_risk_gate']+=1
        if d['selected'] is not None:
            selected[d['day']]+=1
            c=next(c for c in d['candidates'] if c['route']==d['selected'])
            case=path.stem.rsplit('-d',1)[0]
            kind='hold_incumbent' if d['selected']==d['candidates'][1]['route'] else 'change_tape'
            types_by_case[case].add(kind)
            predicted.append(dict(case=case,intervention_type=kind,day=d['day'],episode=d['selected_episode'],route=d['selected'],
                predicted_mean_margin=c['mean_margin'],risk_score=c['risk_score'],minimum=c['minimum_margin']))
    for r in valid:
        kinds=types_by_case[r['spec']['id']]
        r['intervention_type']='+'.join(sorted(kinds)) if kinds else 'none'
    groups={name:stats([r for r in live if r['spec']['opponent']==name],lambda r:r['spec']['world'])
            for name in ('v56','original_m1')}
    team_groups={name:stats([r for r in replay if r['spec']['opponent']==name])
                 for name in sorted(set(r['spec']['opponent'] for r in replay))}
    timing=[];native=[];rss=[]
    for p in (OUT/'arms').glob('*-candidate.json'):
        if p.name.startswith('anchor-'):continue
        a=json.loads(p.read_text())
        if not a['completed']:continue
        timing.extend(t['seconds'] for t in a['timings'] if t['searched'])
        native.extend(t['seconds'] for t in a['timings'] if not t['searched'])
        rss.append(a['peak_rss_gib'])
    summary=dict(completed_pairs=len(valid),planned_pairs=96,complete=len(valid)==96,
        failed_pairs=[r for r in rows if not r['completed']],
        recorded_reproductions=len(recorded),exact_recorded_reproductions=sum(r.get('reproduced_exactly',False) for r in recorded),
        live=stats(live,lambda r:r['spec']['world']),live_by_opponent=groups,
        replay_all=stats(replay,lambda r:r['spec']['opponent']),replay_by_opponent=team_groups,
        replay_without_material_command_break=stats(clean_replay,lambda r:r['spec']['opponent']),
        replay_material_command_breaks=len(replay)-len(clean_replay),
        replay_any_board_divergence=sum(any(r[k]['first_board_difference'] is not None for k in ('baseline_divergence','candidate_divergence')) for r in replay),
        replay_baseline_extra_failures=[r['baseline_divergence']['extra_failed_commands'] for r in replay],
        replay_candidate_extra_failures=[r['candidate_divergence']['extra_failed_commands'] for r in replay],
        selected_by_day=dict(selected),search_counts=dict(counts),search_exclusions=dict(veto),
        time=dict(reveal_calls=len(timing),mean_reveal=statistics.mean(timing) if timing else None,
            p95_reveal=percentile(timing,.95) if timing else None,max_reveal=max(timing,default=None),
            max_native_action=max(native,default=None),max_rss_gib=max(rss,default=None)),
        worst_regressions=sorted([r for r in valid if r['margin_delta']<0],key=lambda r:r['margin_delta'])[:12],
        best_gains=sorted([r for r in valid if r['margin_delta']>0],key=lambda r:-r['margin_delta'])[:12],
        unchanged_losses=sorted([r for r in valid if r['baseline_margin']<0 and r['margin_delta']==0],key=lambda r:r['baseline_margin']),
        forecasts_of_accepted_routes=predicted)
    write(OUT/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k in ('completed_pairs','complete','live','live_by_opponent',
        'replay_all','replay_material_command_breaks','time','search_counts','selected_by_day')},indent=2))

if __name__=='__main__':main()
