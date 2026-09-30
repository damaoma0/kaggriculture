"""Local whole-farm production transfer at missing UMG shop prefixes.

All donor selection uses current revealed shops/current native farm only.
Recorded next-three-day output is a historical donor label: no new shop opens
inside [D,D+3). Later donor output is deliberately never transferred.
This is an offline diagnostic and aggregate-plan input, not an executable agent.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
DAYS=(12,15,18,21,24)
PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,indent=2),encoding='utf-8')
def vector(x):return np.array([x.get(p,0) for p in PRODUCTS],dtype=float)
def mapping(x):return {p:float(n) for p,n in zip(PRODUCTS,x)}
def farm(cp):o=cp['observation'];return o['farms'][o['player']]
def shops(cp):return cp['observation']['town']['unlocked_shops']
def assets(cp):return Counter(t.get('crop') or t.get('animal') for row in farm(cp)['tiles'] for t in row if isinstance(t,dict) and (t.get('crop') or t.get('animal')))
def label(t):return (t.get('crop') or t.get('animal') or t.get('kind')) if isinstance(t,dict) else t

@lru_cache(maxsize=100000)
def tile_profile(raw,day):
    from cumulative_engine_profiles import engine_profile
    outputs,_,_,_=engine_profile(json.loads(raw),day,min(30,day+6),fertilize=False,care=True)
    return tuple(sum(outputs.get(p,{}).get(d,0) for d in range(day,day+3)) for p in PRODUCTS)

def committed(cp):
    result=np.zeros(len(PRODUCTS))
    for row in farm(cp)['tiles']:
        for t in row:
            if isinstance(t,dict) and (t.get('crop') or t.get('animal')):
                result+=tile_profile(json.dumps(t,sort_keys=True),int(cp['day']))
    return result

def output(g,day):
    return vector(next(s['output'] for s in g['segments'] if s['days'][0]==day))

def rank_key(a,b,ma,mb):
    ca,cb=Counter(shops(a)),Counter(shops(b));aa,ab=assets(a),assets(b)
    market=sum(abs(ca[s]-cb[s]) for s in ca.keys()|cb.keys())/2
    asset=sum(abs(aa[s]-ab[s]) for s in aa.keys()|ab.keys())
    profile=float(np.abs(ma-mb).sum())
    board=sum(label(x)!=label(y) for ar,br in zip(farm(a)['tiles'],farm(b)['tiles']) for x,y in zip(ar,br))
    order=sum(x!=y for x,y in zip(shops(a),shops(b)))
    return (market,asset,profile,board,order)

def freeze():
    p=OUT/'local_transfer_protocol.json'
    if p.exists():return
    save(p,dict(created='2026-09-22',primary_submission=56395605,secondary_submission=56368334,
        days=DAYS,donor_policy=56266758,donors='105 exact-state UMG episodes in previous train+test corpora; no new fitting',
        rank=['shop-count replacements','crop/animal count L1','committed next3 output L1','tile-label mismatch','reveal order mismatch'],
        transfer='max(0, mechanical_own + historical_donor_next3 - mechanical_donor)',
        mechanical='Existing assets only; maintained and cared; no added fertilizer/replants; simulate six days then sum first3 to avoid a false three-day end-of-season effect.',
        cohort='All verified m1 checkpoint states at listed days; separately label missing ordered prefixes in all584 compact tapes.',
        pilot='Two cases per day with missing full ordered prefix, sorted by matching key then episode; at most one day per own episode.',
        future='Never use later donor production. Later next6/end targets are the previously frozen forecaster on actual own checkpoint, coherently raised if below new next3 target.',
        evaluation='Own observed output agreement is diagnostic, not an improvement or optimality measure. UMG leave-first4-composition-out transfer uses old75 train donors and30 already-seen test queries; not a new blind test.',
        no_gameplay_claim=True,no_submission=True))

def library():
    seen={};prefixes=defaultdict(set)
    for p in [ROOT/'results/fresh/cumulative_planning/dataset_train.json',ROOT/'results/fresh/cumulative_planning/dataset_test.json']:
        for g in read(p)['games']:
            if int(g['submission'])==56266758:seen[(g['episode'],g['seat'])]=g
    for sub in ('56266758','56266899'):
        for path in (ROOT/f'data/mg_tapes/{sub}').glob('*.json.gz'):
            with gzip.open(path,'rt',encoding='utf-8') as f:g=json.load(f)
            for day in DAYS:prefixes[day].add(tuple(g['shops'][day]))
    return list(seen.values()),prefixes

def summarize(rows):
    result=[]
    for day in DAYS:
        group=[r for r in rows if r['day']==day]
        for scope in ('all','missing_prefix','smallest_quartile_gap'):
            items=group if scope=='all' else [r for r in group if not r['ordered_prefix_available_584']]
            if scope=='smallest_quartile_gap':items=sorted(items,key=lambda r:(r['rank_key'],r['episode']))[:max(1,len(items)//4)]
            if not items:continue
            result.append(dict(day=day,scope=scope,n=len(items),
                identical_asset_counts=sum(r['rank_key'][1]==0 for r in items),
                same_shop_multiset=sum(r['rank_key'][0]==0 for r in items),
                median_asset_l1=float(np.median([r['rank_key'][1] for r in items])),
                median_committed_output_l1=float(np.median([r['rank_key'][2] for r in items])),
                mean_actual_minus_donor=mapping(np.mean([vector(r['actual'])-vector(r['donor_output']) for r in items],axis=0)),
                mean_actual_minus_transfer=mapping(np.mean([vector(r['actual'])-vector(r['transferred_target']) for r in items],axis=0)),
                mean_absolute_error={k:float(np.mean([np.abs(vector(r[k])-vector(r['actual'])) for r in items])) for k in ('donor_output','mechanical_own','transferred_target','frozen_forecast')},
                median_asset_difference={p:float(np.median([r['asset_delta'].get(p,0) for r in items])) for p in ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','GOOSE','COW','SHEEP')}))
    return result

def run():
    from cumulative_trajectory_model import load,predict_trajectory
    freeze();data=read(OUT/'dataset_primary.json');own=data['games'];donors,prefixes=library();model=load()
    cached={(g['episode'],g['seat'],d):committed(g['checkpoints'][str(d)]) for g in donors for d in DAYS}
    rows=[];cp_lookup={};forecasts={}
    for g in own:
        for day in DAYS:
            cp=g['checkpoints'][str(day)];mine=committed(cp);ranked=[]
            for donor in donors:
                if donor['episode']==g['episode']:continue
                dcp=donor['checkpoints'][str(day)];m=cached[(donor['episode'],donor['seat'],day)]
                ranked.append((rank_key(cp,dcp,mine,m),donor,dcp,m))
            key,donor,dcp,dm=min(ranked,key=lambda r:(r[0],r[1]['episode'],r[1]['seat']))
            recorded=output(donor,day);transferred=np.maximum(0,mine+recorded-dm)
            trajectory=predict_trajectory(model,cp);pred=vector(trajectory['horizons'][0]['remaining'])
            aa,ab=assets(cp),assets(dcp)
            row=dict(episode=g['episode'],seat=g['seat'],day=day,own_submission=g['submission'],
                ordered_prefix_available_584=tuple(shops(cp)) in prefixes[day],shops=shops(cp),
                donor_episode=donor['episode'],donor_seat=donor['seat'],donor_submission=donor['submission'],donor_shops=shops(dcp),
                rank_key=list(key),actual=mapping(output(g,day)),donor_output=mapping(recorded),
                mechanical_own=mapping(mine),mechanical_donor=mapping(dm),transferred_target=mapping(transferred),frozen_forecast=mapping(pred),
                own_assets=dict(aa),donor_assets=dict(ab),asset_delta={p:aa[p]-ab[p] for p in aa.keys()|ab.keys()},
                own_planted=next(s.get('planted',{}) for s in g['segments'] if s['days'][0]==day),
                donor_planted=next(s.get('planted',{}) for s in donor['segments'] if s['days'][0]==day))
            rows.append(row);cp_lookup[(g['episode'],day)]=cp;forecasts[(g['episode'],day)]=trajectory
    cases=[];used=set()
    for day in DAYS:
        candidates=sorted([r for r in rows if r['day']==day and not r['ordered_prefix_available_584']],key=lambda r:(r['rank_key'],r['episode']))
        count=0
        for r in candidates:
            if r['episode'] in used:continue
            used.add(r['episode']);count+=1;key=r['episode'],day
            baseline=[];targets=[];running=np.zeros(len(PRODUCTS))
            # Collapse duplicate horizon=end_day at D24.
            by_day={x['end_day']:vector(x['remaining']) for x in forecasts[key]['horizons']}
            for end,x in sorted(by_day.items()):
                baseline.extend(dict(day=end,product=p,units=int(round(n))) for p,n in zip(PRODUCTS,x))
                chosen=vector(r['transferred_target']) if end==day+3 else x
                running=np.maximum(running,chosen)
                targets.extend(dict(day=end,product=p,units=int(round(n))) for p,n in zip(PRODUCTS,running))
            cases.append(dict(episode=r['episode'],seat=r['seat'],day=day,checkpoint=cp_lookup[key],source=r,
                              baseline_targets=baseline,targets=targets))
            if count==2:break
    # Previously exposed held-out corpus: a falsification check, no fitted knobs.
    train=[g for g in donors if g.get('split')=='train'];test=[g for g in donors if g.get('split')=='test'];umg_rows=[]
    for g in test:
        for day in DAYS:
            cp=g['checkpoints'][str(day)];m=cached[(g['episode'],g['seat'],day)];options=[]
            for d in train:
                if Counter(shops(g['checkpoints']['12']))==Counter(shops(d['checkpoints']['12'])):continue
                dc=d['checkpoints'][str(day)];dm=cached[(d['episode'],d['seat'],day)]
                options.append((rank_key(cp,dc,m,dm),d,dm))
            _,d,dm=min(options,key=lambda r:(r[0],r[1]['episode']));y=output(g,day);dy=output(d,day)
            umg_rows.append(dict(episode=g['episode'],day=day,donor_episode=d['episode'],
                raw_mae=float(np.abs(y-dy).mean()),residual_mae=float(np.abs(y-np.maximum(0,m+dy-dm)).mean()),mechanical_mae=float(np.abs(y-m).mean())))
    save(OUT/'local_transfer.json',dict(protocol=read(OUT/'local_transfer_protocol.json'),cases=cases))
    summary=dict(own_games=len(own),own_checkpoints=len(rows),exact_state_donors=len(donors),compact_donors=584,
        primary_submission=56395605,summary=summarize(rows),pilot_cases=[{k:c[k] for k in ('episode','day','seat')} for c in cases],
        umg_diagnostic=[dict(day=d,n=len([r for r in umg_rows if r['day']==d]),**{k:float(np.mean([r[k] for r in umg_rows if r['day']==d])) for k in ('raw_mae','residual_mae','mechanical_mae')}) for d in DAYS],
        interpretation='Predictions/desired targets, not executed new plans. Own forecast agreement does not establish superior production or profit.',
        source_sha256={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in [OUT/'dataset_primary.json',OUT/'local_transfer_protocol.json',Path(__file__)]})
    save(OUT/'local_transfer_analysis.json',dict(summary=summary,rows=rows,umg_diagnostic_rows=umg_rows))
    print(json.dumps(summary,indent=2))
    plots(summary)

def plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(14,4.7),constrained_layout=True)
    vals=[r for r in summary['summary'] if r['scope']=='missing_prefix']
    limit=max(1,max(abs(r[field][p]) for r in vals for field in ('mean_actual_minus_donor','mean_actual_minus_transfer') for p in PRODUCTS))
    for field,title,ax in [('mean_actual_minus_donor','Our observed production minus nearest UMG',axes[0]),('mean_actual_minus_transfer','Our observed production minus adjusted target',axes[1])]:
        a=np.array([[r[field][p] for p in PRODUCTS] for r in vals])
        im=ax.imshow(a,cmap='RdBu_r',vmin=-limit,vmax=limit,aspect='auto')
        ax.set_xticks(range(9),['Wheat','Carrot','Tomato','Strawb.','Melon','Egg','Milk','Wool','Fert.'],rotation=55,ha='right')
        ax.set_yticks(range(len(vals)),[f"D{r['day']}–{r['day']+2} (n={r['n']})" for r in vals]);ax.set_title(title,fontsize=11)
        for y in range(len(vals)):
            for x in range(9):ax.text(x,y,f'{0 if abs(a[y,x])<.05 else a[y,x]:+.1f}',ha='center',va='center',fontsize=8,color='white' if abs(a[y,x])>limit*.65 else 'black')
        fig.colorbar(im,ax=ax,label='Mean harvested/collected units')
    fig.suptitle('Missing ordered shop-prefix cases • m1 vs native-state UMG neighbours\nHistorical diagnostic; smaller imitation error is not evidence of higher profit',fontsize=12)
    fig.savefig(OUT/'production_differences.png',dpi=160);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');a=p.parse_args()
    freeze() if a.freeze else run()
