"""Repeat full V45 controls, recording wheat harvest ages and yields."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
import json
import research_wheat_economy as study

def trace(job):
    out=study.OUT/'cycles';out.mkdir(parents=True,exist_ok=True)
    class Cycles(study.WheatAudit):
        def __enter__(self):
            super().__enter__()
            self.events=[[],[]]
            audited=self.E._apply_unit_action
            def unit(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
                valid=self.active and id(farm) in self.seats and idx<len(private['inventories'])
                tile=None;pos=None;before=0
                if valid:
                    pos=self.E._farmer_position(farm,idx)
                    if pos is not None:
                        tile=farm['tiles'][pos[1]][pos[0]]
                        tile=dict(tile) if isinstance(tile,dict) else None
                        before=private['inventories'][idx].get('WHEAT',0)
                result=audited(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
                if valid and tile and tile.get('crop')=='WHEAT' and action and action[0]=='HARVEST':
                    gained=private['inventories'][idx].get('WHEAT',0)-before
                    if gained:
                        self.events[self.seats[id(farm)]].append(dict(step=self.step,day=day,actor=idx,xy=list(pos),
                            planted_day=tile['planted_day'],age=day-tile['planted_day'],units=gained,
                            fertilized_until=tile['fertilized_until_day']))
                return result
            self.E._apply_unit_action=unit
            return self
        def __exit__(self,*exc):
            super().__exit__(*exc)
            if not exc[0]:
                dest=out/('-'.join(map(str,job))+'-cycles.json')
                dest.write_text(json.dumps(self.events,indent=2),encoding='utf-8')
    study.WheatAudit=Cycles
    result=study.run(job,out)
    stem='-'.join(map(str,job))+'.json'
    current=json.loads((out/stem).read_text(encoding='utf-8'))
    prior=json.loads((study.OUT/'games'/stem).read_text(encoding='utf-8'))
    for key in ('cash','opponent_cash','ledger','wheat','wheat_steps','shops'):assert current[key]==prior[key],(job,key)
    return result

def main():
    jobs=[(seed,seat,'selected','full') for seed in range(136000,136008) for seat in (0,1)]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(trace,j) for j in jobs]):print(f.result(),flush=True)
    totals=[Counter(),Counter()];ages=[Counter(),Counter()];yields=[Counter(),Counter()]
    phases={}
    for j in jobs:
        events=json.loads((study.OUT/'cycles'/('-'.join(map(str,j))+'-cycles.json')).read_text(encoding='utf-8'))
        for kind,seat in enumerate((j[1],1-j[1])):
            for event in events[seat]:
                totals[kind]['harvest_actions']+=1;totals[kind]['units']+=event['units']
                ages[kind][event['age']]+=1;yields[kind][event['units']]+=1
                period=f"{(event['day']//6)*6}-{(event['day']//6)*6+5}"
                row=phases.setdefault(period,[Counter(),Counter()])[kind]
                row['harvest_actions']+=1;row['units']+=event['units']
    summary={'games':len(jobs),'labels':['V45','selected'],
        'per_game':[{k:v/len(jobs) for k,v in row.items()} for row in totals],
        'harvest_age_counts':ages,'yield_per_harvest_counts':yields,
        'phases_per_game':{key:[{k:v/len(jobs) for k,v in row.items()} for row in pair] for key,pair in phases.items()}}
    (study.OUT/'cycle_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
