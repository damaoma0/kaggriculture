"""Compatibility audit of optional reveal policy against exact frozen V8 base."""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_reveal_20260928 import SemanticRevealBlockPolicy as EditableReveal

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'
FROZEN=BASE/'candidates/strategy_v8_kb115lt2_readiness/project/scripts'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def main():
    assert sha(Path(P.__file__))==sha(FROZEN/'semantic_strategy_policy_20260928.py')
    frozen=module('frozen_v8_block_for_reveal_audit',FROZEN/'semantic_strategy_blocks_20260928.py')
    saved=sys.modules['semantic_strategy_blocks_20260928']
    try:
        sys.modules['semantic_strategy_blocks_20260928']=frozen
        revealed=module('frozen_v8_reveal_audit',ROOT/'scripts/semantic_strategy_blocks_reveal_20260928.py')
    finally:sys.modules['semantic_strategy_blocks_20260928']=saved
    files=[FROZEN/'semantic_strategy_blocks_20260928.py',FROZEN/'semantic_strategy_policy_20260928.py',
           ROOT/'scripts/semantic_strategy_blocks_reveal_20260928.py',BASE/'block_model_reveal_modern100.json']
    cases=[];inputs={};off_count=on_count=d6_count=0
    for path in sorted((BASE/'runs/strategy_v5_blocks100_finance/development/live').glob('live-??.json')):
        inputs[str(path.relative_to(ROOT))]=sha(path);x=json.loads(path.read_text());seat=x['case']['seat'];cfg=dict(land_limit=4,forecast=True)
        base=frozen.SemanticBlockPolicy(BASE/'block_model_modern100.json',cfg)
        off=revealed.SemanticRevealBlockPolicy(files[-1],cfg)
        on=revealed.SemanticRevealBlockPolicy(files[-1],dict(cfg,reveal_features=True))
        editable=EditableReveal(files[-1],dict(cfg,reveal_features=True))
        oldmem={};newmem={}
        for day in range(6,30):
            a=x['diagnostics'][seat][day]['current_observation'];b=x['diagnostics'][1-seat][day]['current_observation']
            farms=[None,None];farms[seat]=deepcopy(a['own_farm']);farms[1-seat]=deepcopy(b['own_farm'])
            obs=dict(day=day,hour=0,step=24*day,player=seat,farms=farms,private=deepcopy(a['private']),market=deepcopy(a['market']),town=deepcopy(a['town']))
            prior=dict(Counter(r['animal'] for r in x['final_diagnostics'][str(seat)][day].get('retirements',[]) if r['first_unfed_day']<day))
            oldmem['committed_retirement_counts']=prior;newmem['committed_retirement_counts']=prior
            orig=base.propose(obs,oldmem);disabled=off.propose(obs,oldmem)
            active=on.propose(obs,newmem);current=editable.propose(obs,newmem)
            assert orig==disabled,(path,day,'OFF');off_count+=1
            assert active==current,(path,day,'editable/frozen enabled');on_count+=1
            if day==6:
                assert orig['today']==active['today'] and orig['memory']==active['memory'];d6_count+=1
            oldmem=orig['memory'];newmem=active['memory']
        cases.append(path.stem)
    out=dict(scope=__doc__,source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files},input_hashes=inputs,
        cases=cases,off_full_proposals_equal=off_count,enabled_editable_vs_frozen_full_proposals_equal=on_count,
        d6_today_memory_equal=d6_count,new_games=0,
        note='FrozenV8 block d568c806 is compatible. Its byte-identical base policy is verified. New reveal module requires no symbols from optional market/labor edits.')
    dest=BASE/'reveal_feature_frozen_v8_compatibility_audit.json';dest.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),sha256=sha(dest),off=off_count,on=on_count,d6=d6_count)))


if __name__=='__main__':main()
