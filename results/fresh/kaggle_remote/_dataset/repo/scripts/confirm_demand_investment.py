"""Additional coverage of a frozen rule's trigger, not a natural-frequency panel."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from statistics import mean
import json,random
from research_demand_investment import OUT,ROOT,SELECTED,run

def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    from importlib.metadata import version
    frozen=json.loads((OUT/'frozen_rule.json').read_text())
    for path,digest in frozen['sources'].items():assert sha256((ROOT/path).read_bytes()).hexdigest()==digest
    seeds=[];seed=132000
    while len(seeds)<8:
        shops=random.Random(seed^0xE31A).choices(sorted(E.SHOPS),k=8)
        if sum('MILK' in E.SHOPS[s] for s in shops[:3])>=2:seeds.append(seed)
        seed+=1
    manifest={'engine':version('kaggle-environments'),'seeds':seeds,'rule':frozen['rule'],
      'selection':'First eight seeds >=132000 with at least two milk shops among the first three draws; selection uses no outcomes. Remaining draws stay independent and hidden.',
      'purpose':'Resolve sparse trigger coverage. Original natural-panel promotion gate remains unchanged. This enriched panel cannot estimate average natural-game gains.',
      'source_sha256':sha256((ROOT/'scripts/confirm_demand_investment.py').read_bytes()).hexdigest()}
    path=OUT/'conditional_manifest.json'
    if path.exists():assert json.loads(path.read_text())==manifest
    else:path.write_text(json.dumps(manifest,indent=2))
    jobs=[('conditional',s,i,o,c) for s in seeds for i in (0,1) for o in ('selected','sixday') for c in ('SHEEP','COW')]
    def file(j):return OUT/'games'/('-'.join(map(str,j))+'.json')
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if not file(j).exists()]):print(f.result(),flush=True)
    rows=[json.loads(file(j).read_text()) for j in jobs]
    results={}
    for opponent in ('selected','sixday','all'):
        pairs=[]
        for seed in seeds:
            for seat in (0,1):
                for other in ('selected','sixday'):
                    if opponent!='all' and other!=opponent:continue
                    g={r['choice']:r for r in rows if r['seed']==seed and r['seat']==seat and r['opponent']==other}
                    a,b=g['COW'],g['SHEEP'];assert a['decision']['features']==b['decision']['features'] and a['shops']==b['shops']
                    assert a['decision']['features']['MILK_demand']>=2
                    pairs.append({'seed':seed,'seat':seat,'opponent':other,'cash_gain':a['cash']-b['cash'],'margin_gain':a['margin']-b['margin']})
        results[opponent]={'cases':len(pairs),'cash_gain':mean(p['cash_gain'] for p in pairs),'margin_gain':mean(p['margin_gain'] for p in pairs),'worst_margin_gain':min(p['margin_gain'] for p in pairs),'positive_cases':sum(p['margin_gain']>0 for p in pairs),'negative_cases':sum(p['margin_gain']<0 for p in pairs),'seed_gains':{s:mean(p['margin_gain'] for p in pairs if p['seed']==s) for s in seeds},'pairs':pairs}
    (OUT/'conditional_summary.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2),flush=True)

if __name__=='__main__':main()
