"""Train a compact decision library and evaluate held-out-episode prediction."""
from collections import Counter,defaultdict
from pathlib import Path
import gzip,json,hashlib,statistics
from semantic_farm.common import E,SPECIES
from semantic_farm.model import distance,DEFAULT

ROOT=Path(__file__).resolve().parents[1]


def main():
    study=json.loads((ROOT/'results/fresh/semantic_architecture_20260924/study.json').read_text(encoding='utf8'))
    rows=[]; opening=None; sources={}
    for donor in study['donors']:
        path=ROOT/donor['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=donor['sha256']:raise ValueError('donor_changed')
        with gzip.open(path,'rt',encoding='utf8') as f:trace=json.load(f)
        daily={int(r['day']):r for r in trace['daily']}
        by_day=defaultdict(list)
        for job in trace['jobs']:by_day[job['day']].append(job)
        source=[]
        for day in range(30):
            now,end=daily[day],daily[day+1]
            def counts(farm):return dict(Counter(t.get('crop') or t.get('animal') for line in farm['tiles']
                for t in line if isinstance(t,dict) and (t.get('crop') or t.get('animal'))))
            ages=Counter()
            for line in now['farm']['tiles']:
                for tile in line:
                    if not isinstance(tile,dict):continue
                    s=tile.get('crop') or tile.get('animal')
                    if s:
                        age=day-tile.get('planted_day',tile.get('placed_day',day))
                        ages[f'{s}:{min(9,age//3)}']+=1
            early=sum(j['command'][0]=='HARVEST' and isinstance(j['before'],dict)
                and j['before'].get('crop')=='WHEAT' and day-j['before']['planted_day']<4
                for j in by_day[day])
            additions=Counter(j['command'][1] for j in by_day[day] if j['command'][0]=='PLANT'
                or (j['command'][0]=='PLACE' and len(j['command'])>1 and j['command'][1] in E.ANIMALS))
            row=dict(episode=trace['episode'],day=day,submission=donor['submission'],
                features=dict(day=day,shops=dict(Counter(now['shops'])),assets=counts(now['farm']),
                    ages=dict(ages),money=now['cash'],land=len(now['farm']['unlocked_quadrants'])),
                additions=dict(additions),end_assets=counts(end['farm']),early_wheat=early,
                land=len(end['farm']['unlocked_quadrants']))
            rows.append(row);source.append(row)
        if trace['episode']==112802103:opening={str(r['day']):r for r in source[:6]}
        sources[donor['path']]=donor['sha256']
    if opening is None:raise ValueError('opening_source_missing')
    # Whole episodes remain excluded from neighbors; no scores/rewards selected.
    errors=[];median_errors=[]
    for row in rows:
        if row['day']<6:continue
        train=[r for r in rows if r['day']==row['day'] and r['episode']!=row['episode']]
        nearest=min(train,key=lambda r:(distance(row['features'],r['features']),r['episode']))
        errors.extend(abs(row['additions'].get(s,0)-nearest['additions'].get(s,0)) for s in SPECIES)
        median_errors.extend(abs(row['additions'].get(s,0)-statistics.median(r['additions'].get(s,0) for r in train)) for s in SPECIES)
    result=dict(schema=1,opening_episode=112802103,opening=opening,rows=rows,source_hashes=sources,
        validation=dict(episodes=len({r['episode'] for r in rows}),seats=len(study['donors']),rows=len(rows),split='leave_whole_episode_out',
            nearest_quantity_mae=statistics.mean(errors),calendar_median_mae=statistics.mean(median_errors),
            claim='imitation diagnostic, not policy performance'),
        rating_snapshot=study['rating_snapshot_utc'],benchmark_excluded=True)
    DEFAULT.parent.mkdir(parents=True,exist_ok=True)
    DEFAULT.write_text(json.dumps(result,separators=(',',':')),encoding='utf8')
    print(json.dumps(result['validation']))


if __name__=='__main__':main()
