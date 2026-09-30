"""Static activation audit; no games and no qualification observations."""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import semantic_strategy_policy_20260928 as P
from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
from check_semantic_block_shadow_20260928 import GROUPS,BASE,ROOT


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen_path=BASE/'candidates/strategy_v6_blocks100_recovery/project/scripts/semantic_strategy_blocks_20260928.py'
    spec=importlib.util.spec_from_file_location('frozen_block_audit',frozen_path)
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
    files=[ROOT/'scripts/semantic_strategy_blocks_20260928.py',ROOT/'scripts/semantic_strategy_market_admission_20260928.py',
           ROOT/'scripts/semantic_strategy_policy_20260928.py',BASE/'block_model_modern100.json']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
    model=BASE/'block_model_modern100.json';cfg={'forecast':False,'land_limit':4}
    off=SemanticBlockPolicy(model,cfg);old=frozen.SemanticBlockPolicy(model,cfg)
    gate=SemanticBlockPolicy(model,dict(cfg,animal_market_gate=True))
    report=dict(config=dict(start_day=12,max_units_per_day=1,loss_buffer=300),source_hashes=hashes,
                frozen_off_sha256=digest(frozen_path),groups={})
    for group,folder in GROUPS.items():
        events=[];candidates=[];checks=0;timings=[];input_hashes={}
        for path in sorted(folder.glob('live-*.json')):
            if path.name.endswith('.actions.json'):continue
            raw=json.loads(path.read_text());seat=int(raw['case']['seat'])
            input_hashes[str(path.relative_to(ROOT))]=digest(path)
            snapshots={v['day']:v for v in raw['diagnostics'][seat]}
            rival={v['day']:v for v in raw['diagnostics'][1-seat]};memory={};intents={}
            for day in range(6,30):
                saved=snapshots[day]['current_observation'];farms=[None,None]
                farms[seat]=deepcopy(saved['own_farm']);farms[1-seat]=deepcopy(rival[day]['current_observation']['own_farm'])
                obs=dict(day=day,hour=0,step=24*day,player=seat,farms=farms,private=deepcopy(saved['private']),
                         market=deepcopy(saved['market']),town=deepcopy(saved['town']))
                cells={y*10+x:t for y,row in enumerate(farms[seat]['tiles']) for x,t in enumerate(row) if isinstance(t,dict)}
                intents={tile:v for tile,v in intents.items() if tile in cells and
                         (cells[tile].get('animal'),cells[tile].get('placed_day'))==(v['species'],v['birth'])}
                memory['committed_retirement_counts']=dict(Counter(v['species'] for v in intents.values()))
                baseline=off.propose(obs,memory);assert baseline==old.propose(obs,memory)
                start=time.perf_counter();choice=gate.propose(obs,memory);timings.append(time.perf_counter()-start)
                assert choice['memory']==baseline['memory'];checks+=1
                detail=choice['diagnostics']['market_admission']
                for species,value in detail['candidates'].items():
                    candidates.append(dict(case=raw['case']['id'],day=day,species=species,**value))
                if detail['withheld']:
                    assert sum(detail['withheld'].values())<=1
                    events.append(dict(case=raw['case']['id'],day=day,cash=farms[seat]['money'],shops=P._shops(obs),
                        withheld=detail['withheld'],before=baseline['today']['animal_add_counts'],
                        after=choice['today']['animal_add_counts'],estimates=detail['candidates'],
                        completed_unchanged=baseline['diagnostics']['completed']==choice['diagnostics']['completed']))
                memory=baseline['memory']
                for intent in snapshots[day]['diagnostics'][-1].get('retirements',[]):
                    tile=int(intent['tile']);cell=cells.get(tile)
                    if cell and cell.get('animal')==intent['animal']:
                        intents[tile]=dict(species=cell['animal'],birth=int(cell['placed_day']))
        report['groups'][group]=dict(decisions=checks,default_equals_frozen_all=checks,events=events,
            eligible_species_decisions=len(candidates),candidate_values=candidates,input_hashes=input_hashes,
            max_shadow_seconds=max(timings),mean_shadow_seconds=sum(timings)/len(timings))
    assert hashes=={str(p.relative_to(ROOT)):digest(p) for p in files}
    report['limitations']=['Off-policy current-state diagnostic, not a game or profit prediction.',
        'Held animals are excluded regardless of estimated value.',
        'Nine scenarios are declared stress assumptions, not bounds over every possible future.',
        'Current public daily states have no hourly observed-rival-flow history.']
    path=BASE/'market_admission_static_audit.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),summary={k:{x:v[x] for x in ('decisions','eligible_species_decisions','max_shadow_seconds')}
        | {'activations':len(v['events'])} for k,v in report['groups'].items()}),indent=2))


if __name__=='__main__':main()
