"""Static public-dawn comparisons, not gameplay or a native-state replay."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from semantic_strategy_blocks_reveal_20260928 import SemanticRevealBlockPolicy

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths=[ROOT/'scripts/semantic_strategy_blocks_reveal_20260928.py',
           ROOT/'scripts/semantic_strategy_blocks_20260928.py',ROOT/'scripts/semantic_strategy_policy_20260928.py',
           BASE/'block_model_reveal_modern100.json',BASE/'block_model_modern100.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    rows=[];inputs={};equal=0;day6_equal=0;retirement_equal=0
    for path in sorted((BASE/'runs/strategy_v5_blocks100_finance/development/live').glob('live-??.json')):
        inputs[str(path.relative_to(ROOT))]=sha(path);x=json.loads(path.read_text());seat=x['case']['seat']
        cfg=dict(land_limit=4,forecast=True)
        baseline=SemanticBlockPolicy(paths[-1],cfg)
        off=SemanticRevealBlockPolicy(paths[-2],cfg)
        on=SemanticRevealBlockPolicy(paths[-2],dict(cfg,reveal_features=True))
        oldmem={};newmem={}
        for day in range(6,30):
            saved=x['diagnostics'][seat][day]['current_observation'];other=x['diagnostics'][1-seat][day]['current_observation']
            farms=[None,None];farms[seat]=deepcopy(saved['own_farm']);farms[1-seat]=deepcopy(other['own_farm'])
            obs=dict(day=day,hour=0,step=24*day,player=seat,farms=farms,private=deepcopy(saved['private']),
                market=deepcopy(saved['market']),town=deepcopy(saved['town']))
            # Only prior accepted intent belongs in the current morning input.
            prior=Counter(r['animal'] for r in x['final_diagnostics'][str(seat)][day].get('retirements',[]) if r['first_unfed_day']<day)
            oldmem['committed_retirement_counts']=dict(prior);newmem['committed_retirement_counts']=dict(prior)
            a=baseline.propose(obs,oldmem);b=off.propose(obs,oldmem);c=on.propose(obs,newmem)
            assert a==b,(path,day,'OFF mismatch');equal+=1
            if day==6:
                assert a['today']==c['today'] and a['memory']==c['memory'];day6_equal+=1
            oldmem=a['memory'];newmem=c['memory']
            same_retire=a['today']['animal_retire_counts']==c['today']['animal_retire_counts'];retirement_equal+=same_retire
            changed={field:{s:c['today'][field].get(s,0)-a['today'][field].get(s,0) for s in set(a['today'][field])|set(c['today'][field])
                if c['today'][field].get(s,0)!=a['today'][field].get(s,0)} for field in ('plant_counts','animal_add_counts','animal_retire_counts')}
            rows.append(dict(case=x['case']['id'],day=day,counts_delta=changed,
                baseline_block_totals=a['diagnostics']['totals'],reveal_block_totals=c['diagnostics']['totals'],
                baseline_today=a['today'],reveal_today=c['today'],retirement_equal=same_retire))
    changed=[r for r in rows if any(r['counts_delta'].values())]
    out=dict(scope=__doc__,source_hashes=hashes,input_hashes=inputs,
        caveats=['Own and rival dawn states come from completed old-executor V5 development games.',
            'Memory is replayed through daily policy calls with prior accepted retirement counts; hourly public_history is not reconstructed.',
            'These comparisons establish OFF equivalence under identical supplied inputs, not native action parity or profitability.',
            'Quantities include repeated unfinished requests; summing them is not a count of actual purchases.'],
        summary=dict(dawns=len(rows),off_full_proposal_equal=equal,d6_today_and_memory_equal=day6_equal,
            changed_dawns=len(changed),retirement_today_equal=retirement_equal),rows=rows)
    dest=BASE/'reveal_feature_static_audit.json';dest.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),sha256=sha(dest),summary=out['summary'])))


if __name__=='__main__':main()
