"""Follow-up diagnostic: disable extra wheat/carrot fertilizer tours."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from statistics import mean
import json
import research_wheat_economy as study

OUT=study.OUT/'crop_input_followup'

def run(job):
    original=study.configure
    def configure(module,variant):
        original(module,variant)
        module._r51_input_control=lambda obs,action,state:action
    study.configure=configure
    return study.run(job,OUT/'games')

def main():
    jobs=[(s,i,o,'no_crop_input_planner') for s in range(136000,136008) for i in (0,1) for o in ('selected','twocoins')]
    OUT.mkdir(parents=True,exist_ok=True)
    manifest={'jobs':jobs,'design':'Adaptive diagnostic on the same completed panel; not new independent validation. Disable additional wheat/carrot fertilizer tours only, preserving native fertilizer and other crop investments.',
        'sources':json.loads((study.OUT/'manifest.json').read_text(encoding='utf-8'))['sources']}
    p=study.ROOT/'scripts/check_crop_input_planner.py';manifest['sources'][str(p.relative_to(study.ROOT))]=sha256(p.read_bytes()).hexdigest()
    dest=OUT/'manifest.json'
    if dest.exists():assert json.loads(dest.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:dest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs]):print(f.result(),flush=True)
    summary={}
    for opponent in ('selected','twocoins'):
        changes=[];errors=[]
        for j in jobs:
            if j[2]!=opponent:continue
            row=json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8'))
            full=json.loads((study.OUT/'games'/('-'.join(map(str,(*j[:3],'full')))+'.json')).read_text(encoding='utf-8'))
            assert row['telemetry']['input_confirmed_hires']==0
            for k,v in row['telemetry'].items():
                if 'error' in k.lower() and isinstance(v,(int,float)) and v:errors.append((j,k,v))
            seat=j[1]
            d={key:full[key]-row[key] for key in ('cash','margin','opponent_cash')}
            d.update(seed=j[0],seat=seat,wheat_harvest=full['wheat'][seat].get('harvest',0)-row['wheat'][seat].get('harvest',0))
            for item in ('WHEAT','CARROT','FERTILIZER'):
                d[item+'_revenue']=full['ledger'][seat]['revenue'].get(item,0)-row['ledger'][seat]['revenue'].get(item,0)
            for item in ('BUY_PRODUCT:FERTILIZER','HIRE'):
                d[item+'_cost']=full['ledger'][seat]['spend'].get(item,0)-row['ledger'][seat]['spend'].get(item,0)
            changes.append(d)
        seed_gains={s:mean(d['margin'] for d in changes if d['seed']==s) for s in sorted({d['seed'] for d in changes})}
        summary[opponent]={'full_gains':{k:mean(d[k] for d in changes) for k in changes[0] if k not in ('seed','seat')},'seed_margin_gains':seed_gains,'errors':errors}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
