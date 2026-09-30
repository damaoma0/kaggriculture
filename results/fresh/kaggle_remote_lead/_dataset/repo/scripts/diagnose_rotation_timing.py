"""Serial timing reproduction with GC callbacks; never alters the policies or GC policy."""
import gc
from hashlib import sha256
import json
from pathlib import Path
import time
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/rotation_experiments'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seat',type=int,required=True);args=parser.parse_args()
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    seed=1285358863;seat=args.seat
    old=json.loads((OUT/f'direct/games/mgt_exp_hold-mgt_m1-{seed}-{seat}.json').read_text())
    manifest=json.loads((OUT/'direct/manifest.json').read_text())
    agents={role:get_last_callable((ROOT/manifest['source_paths'][name]).read_text(encoding='utf-8'))
            for role,name in [('own','mgt_exp_hold'),('opponent','mgt_m1')]}
    current=[None];starts={};collections=[];calls={'own':[],'opponent':[]};slow=[]
    def callback(phase,info):
        gen=info['generation']
        if phase=='start':starts[gen]=(time.perf_counter(),current[0])
        elif gen in starts:
            t,where=starts.pop(gen);elapsed=time.perf_counter()-t
            if elapsed>0.05:collections.append(dict(generation=gen,seconds=elapsed,where=where,collected=info.get('collected')))
    def timed(role):
        def act(obs,step):
            current[0]=[role,step];start=time.perf_counter()
            try:return agents[role](obs)
            finally:
                duration=time.perf_counter()-start
                calls[role].append(duration)
                if duration>0.1:slow.append(dict(role=role,step=step,seconds=duration))
                current[0]=None
        return act
    players=[None,None];players[seat]=timed('own');players[1-seat]=timed('opponent')
    gc.callbacks.append(callback)
    try:
        env=make('kaggriculture',configuration={'episodeSteps':720},info={'seed':seed})
        result=TV._play(E,env,players,seat,None,None,None,seat)
    finally:gc.callbacks.remove(callback)
    action_hash=sha256(json.dumps(result['actions'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    report={'seed':seed,'seat':seat,'frozen_hashes':manifest['source_hashes'],'serial':True,
            'same_actions':action_hash==old['action_sha256'],'same_rewards':result['final'][seat]==old['cash'] and result['final'][1-seat]==old['opponent_cash'],
            'max_seconds':{k:max(v) for k,v in calls.items()},'slow_calls':slow,'gc_collections':collections}
    assert report['same_actions'] and report['same_rewards']
    (OUT/f'timing_diagnostic_seat{seat}.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
