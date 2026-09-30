"""Read-only action/movement accounting, independently checked against native logs."""
from collections import Counter
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics

import semantic_strategy_policy_20260928 as P

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'results/fresh/semantic_strategy_20260928'
MOVES={'NORTH':(0,-1),'SOUTH':(0,1),'EAST':(1,0),'WEST':(-1,0)}
ACCESS=((4,4),(5,4),(4,5),(5,5))


def positions(actions,counts,start):
    """Only movement and spawn arithmetic; no crop/market simulation or games."""
    out=[];pos=deepcopy(start)
    for hour,action in enumerate(actions):
        assert len(pos)==counts[hour]+1
        out.append(deepcopy(pos))
        cmds=[action.get('farmer',['PASS'])]+action.get('hands',[])
        for u,p in enumerate(pos):
            c=cmds[u] if u<len(cmds) else ['PASS']
            if c and c[0] in MOVES:
                dx,dy=MOVES[c[0]];x,y=p[0]+dx,p[1]+dy
                if 0<=x<10 and 0<=y<10:pos[u]=[x,y]
        if hour+1<len(counts):
            for _ in range(counts[hour+1]-counts[hour]):
                occupied=Counter(map(tuple,pos))
                tile=min(ACCESS,key=lambda p:(occupied[p],ACCESS.index(p)))
                pos.append(list(tile))
    return out


def totals(actions,counts,lo,hi):
    result=Counter()
    for h in range(lo,hi):
        cmds=[actions[h].get('farmer',['PASS'])]+actions[h].get('hands',[])
        for u in range(counts[h]+1):
            cmd=cmds[u] if u<len(cmds) else ['PASS'];result[cmd[0] if cmd else 'PASS']+=1
    return dict(result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='strategy_v4_modern4_finance')
    parser.add_argument('--label',default='v4');args=parser.parse_args()
    controls=BASE/'oracle_diagnostics/d6_exact_vs_retile_v3/controls';checks=0;native=[];sources={}
    for path in sorted(controls.glob('oracle6-*.json')):
        if path.name.endswith('.actions.json'):continue
        raw=json.loads(path.read_text());seat=int(raw['case']['seat'])
        acts=json.loads(path.with_suffix('.actions.json').read_text())[seat][240:264]
        observed=[v for v in raw['early_window_audit'] if v['day']==10]
        counts=[v['hands_count'] for v in observed]
        reconstructed=positions(acts,counts,[observed[0]['farmer']]+observed[0]['hands'])
        for before,seen in zip(reconstructed,observed):
            assert before==[seen['farmer']]+seen['hands'];checks+=1
        unlock=next((v['hour'] for v in observed if len(v['unlocked_quadrants'])==4),None)
        native.append(dict(case=raw['case']['id'],hands=max(counts),unlock_hour=unlock,
            hires=[dict(hour=h-1,count=counts[h]-counts[h-1]) for h in range(1,24) if counts[h]!=counts[h-1]],
            post_unlock=totals(acts,counts,unlock,24) if unlock is not None else {}))
        sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[];folder=BASE/'runs'/args.candidate/'development/live'
    allocation=json.loads((BASE/f'early_allocation_{args.label}_diagnostic.json').read_text())
    for path in sorted(folder.glob('live-*.json')):
        if path.name.endswith('.actions.json'):continue
        raw=json.loads(path.read_text());seat=int(raw['case']['seat']);acts=json.loads(path.with_suffix('.actions.json').read_text())[seat][240:264]
        counts=[len(a['hands']) for a in acts];d=next(v for v in raw['final_diagnostics'][str(seat)] if v['day']==10)
        start=next(v['current_observation']['own_farm'] for v in raw['diagnostics'][seat] if v['day']==10)
        pos=positions(acts,counts,[start['farmer']]+start['hands']);cut=d['observed_land_unlock']['hour']
        actual_hourly=[v for v in raw.get('early_window_audit',[]) if v['day']==10]
        if actual_hourly:
            assert len(actual_hourly)==24
            assert all(p==[v['farmer']]+v['hands'] for p,v in zip(pos,actual_hourly))
        hire_spend=raw['daily'][seat][11]['spend']['HIRE']-raw['daily'][seat][10]['spend']['HIRE']
        assert hire_spend==P._hire_cost(max(counts))
        # Every D10 unit command in these recordings has no reported no-effect.
        before=raw['daily'][seat][10]['physical'];after=raw['daily'][seat][11]['physical']
        errors={k:after[k]-before.get(k,0) for k in after if k.startswith('no_effect') and after[k]!=before.get(k,0)}
        workbefore=totals(acts,counts,0,cut);plan=d['realized_plan']
        animal_before=sum(1 for h in range(cut) for cmd in [acts[h]['farmer']]+acts[h]['hands']
                          if cmd and cmd[0]=='PLACE' and len(cmd)>1 and cmd[1] in P.ANIMALS)
        remaining=dict(plant=sum(plan['plant_counts'].values())-workbefore.get('PLANT',0),
            build=sum(plan['build_counts'].values())-workbefore.get('BUILD_COOP',0)-workbefore.get('BUILD_PASTURE',0),
            animal_place=sum(plan['animal_add_counts'].values())-animal_before)
        row=next(r for r in allocation['rows'] if r['case']==raw['case']['id'] and r['day']==10)
        distances=[max(0,5-x)+max(0,5-y) for x,y in pos[cut]]
        post=totals(acts,counts,cut,24);late=totals(acts,counts,23,24)
        perunitpass=[sum(([a['farmer']]+a['hands'])[u][0]=='PASS' for a in acts[cut:]) for u in range(counts[cut]+1)]
        rows.append(dict(case=raw['case']['id'],unlock_hour=cut,planned_hands=d['proposal']['hands'],actual_hands=max(counts),
            direct_hourly_positions_verified=len(actual_hourly),no_effect_commands=errors,
            remaining_jobs_exact=not any(errors.get('no_effect:'+op,0) for op in ('PLANT','BUILD_COOP','BUILD_PASTURE','PLACE')),
            dawn_animals=row.get('dawn_animals'),
            hire_spend=hire_spend,hires=[dict(hour=h-1,count=counts[h]-counts[h-1]) for h in range(1,24) if counts[h]!=counts[h-1]],
            positions_at_unlock=pos[cut],distance_to_SE=dict(median=statistics.median(distances),mean=statistics.mean(distances),max=max(distances)),
            post_unlock_commands=post,post_unlock_unit_hours=sum(post.values()),last_hour_commands=late,
            pass_before_last_hour=post.get('PASS',0)-late.get('PASS',0),passes_per_unit=perunitpass,
            remaining_jobs_at_unlock=remaining,paid_crop_backlog_at_end=row['paid_unfilled_plants'],
            one_more_hand_cost=P._hire_cost(max(counts)+1)-hire_spend,
            two_more_hands_cost=P._hire_cost(max(counts)+2)-hire_spend,
            cash_at_next_dawn=row['cash_end']))
        sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    agg=dict(sum((Counter(r['post_unlock_commands']) for r in rows),Counter()))
    report=dict(candidate=args.candidate,native_position_snapshots_verified=checks,native=native,**{args.label:rows},aggregate_post_unlock_commands=agg,input_hashes=sources,
                limitations=['No games run. V4 positions reconstructed only from bounded movement and observed hand-count changes.',
                'The same movement/spawn arithmetic matches192 recorded native hourly positions exactly.',
                'PASS measures idle commands, not spare routable capacity; remaining actions may already be committed to care and delivery.',
                'No new hand counterfactual or price/cash feasibility of extra hires is simulated.'])
    dst=BASE/f'd10_labor_{args.label}_diagnostic.json';dst.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(dst),native=native,v4_summary=[{k:r[k] for k in ('case','actual_hands','hires','unlock_hour','post_unlock_unit_hours','pass_before_last_hour','remaining_jobs_at_unlock','distance_to_SE','one_more_hand_cost','two_more_hands_cost')} for r in rows],aggregate=agg),indent=2))


if __name__=='__main__':main()
