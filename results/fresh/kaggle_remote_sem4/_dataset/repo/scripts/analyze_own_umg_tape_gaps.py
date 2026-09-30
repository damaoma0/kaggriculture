"""Inventory own tape gaps and rank UMG compact-tape donors at visible checkpoints.

No future outcome, reward, or unrevealed shop is used in ranking.  Compact own panels
have actions and shop schedules but no boards, so this script deliberately does not
pretend they are state donors.  The existing 16-game rich v10 domain panel supplies
the only exact current-own snapshots until a recorded-action replay expands it.
"""
import argparse, gzip, json, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
DAYS=(12,15,18,21,24)
OWN={'56395605':'m1_primary','56368334':'t10_secondary'}
UMG=('56266758','56266899')
LABEL={'WHEAT':'WH','CARROT':'CA','TOMATO':'TO','STRAWBERRY':'ST','MELON':'ME','COW':'co','GOOSE':'go','SHEEP':'sh'}

def load(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)

def compact_tiles(board):
    # Canonical encoding from build_mg_tape_agent._mgt_labels: every tile is a
    # two-character label.  Stored boards are ten 20-character rows.
    raw=''.join(board) if isinstance(board,list) else board
    if len(raw)!=200: raise ValueError(f'compact board has {len(raw)} chars, expected 200')
    return [raw[i:i+2] for i in range(0,200,2)]

def own_tiles(checkpoint):
    obs=checkpoint['observation']; farm=obs['farms'][obs['player']]
    out=[]
    for row in farm['tiles']:
        for tile in row:
            if tile is None: out.append(' .')
            elif tile=='LOCKED': out.append(' L')
            elif isinstance(tile,dict):
                if tile.get('kind')=='PLANT':out.append(str(tile.get('crop'))[:2])
                elif tile.get('kind')=='WEED':out.append(' .')
                elif tile.get('animal'):out.append(str(tile['animal'])[:2].lower())
                else:out.append(str(tile.get('kind'))[:2].lower())
            else: out.append(str(tile))
    return out

def prefix(shops,day):
    # UMG compact tapes store the unlocked prefix for every day; rich snapshots
    # store one flat currently-unlocked list.
    if shops and isinstance(shops[0],list): return list(shops[day])
    return list(shops[:day//3])
def counts(shops): return Counter(shops)
def score(target, donor):
    tc,dc=counts(target['shops']),counts(donor['shops'])
    replacement=sum(abs(tc[k]-dc[k]) for k in tc.keys()|dc.keys())//2
    ta,da=Counter(target['tiles']),Counter(donor['tiles'])
    asset_l1_half=sum(abs(ta[k]-da[k]) for k in ta.keys()|da.keys() if k not in (' .',' L'))/2
    productive={'WH','CA','TO','ST','ME','co','go','sh'}
    mismatch=sum(a!=b for a,b in zip(target['tiles'],donor['tiles']) if a in productive or b in productive)
    order=sum(a!=b for a,b in zip(target['shops'],donor['shops'])) + abs(len(target['shops'])-len(donor['shops']))
    return (replacement,asset_l1_half,mismatch,order),{'shop_replacement_count':replacement,'asset_count_l1_half':asset_l1_half,'crop_animal_tile_label_mismatch':mismatch,'reveal_order_difference':order}

PRODUCTS=['WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER']

def replay_one(path):
    """Exact recorded-action season, with the observed daily shop path asserted."""
    from research_labour_profit import Simulator, load_game
    game, actions=load_game(path)
    with Simulator(game) as sim:
        run=sim.run(sim.initial,0,719,actions,capture=True,snapshots=True)
    if run['money'] != game['rewards']:
        raise AssertionError(f"reward mismatch replay={run['money']} recorded={game['rewards']}")
    for day in range(30):
        got=list(run['snapshots'][day*24][0].observation.town['unlocked_shops'])
        expected=list(game['shops'][day])
        if got != expected: raise AssertionError(f"shop path mismatch day={day} got={got} expected={expected}")
    seat=game['seat']; segments=[]
    for segment in range(10):
        physical=Counter(); start,end=segment*72,(segment+1)*72
        for work in run['work']:
            if work['seat'] != seat or not start <= work['t'] < end: continue
            cmd=work['cmd']; op=cmd[0] if cmd else ''
            if op in ('HARVEST','COLLECT_FERTILIZER'):
                for product,delta in work['delta'].items():
                    if product in PRODUCTS and delta>0: physical['produced:'+product]+=delta
            if op=='PLANT' and len(cmd)>1: physical['planted:'+cmd[1]]+=1
        for t,s,op,item,_ in run['events']:
            if s==seat and start <= t < end and op=='BUY_ANIMAL' and item in ('COW','SHEEP','GOOSE'):
                physical['animal_added:'+item]+=1
        segments.append(dict(segment=segment,days=[segment*3,segment*3+2],output={p:physical.get('produced:'+p,0) for p in PRODUCTS},
            planted={p:physical.get('planted:'+p,0) for p in PRODUCTS[:5]},animal_added={p:physical.get('animal_added:'+p,0) for p in ('COW','SHEEP','GOOSE')},physical=dict(physical)))
    checkpoints={}
    for day in DAYS:
        state=run['snapshots'][day*24]
        obs=deepcopy(state[seat].observation)
        # All fields listed below are present in the official state object and
        # deliberately retained for a continuation planner.
        for key in ('farms','private','market','town','step','day','hour'):
            assert key in obs, (game['episode'],day,key)
        obs.update(step=day*24,day=day,player=seat)
        idx=day//3
        checkpoints[str(day)]=dict(day=day,observation=obs,prior_output=segments[idx-1]['output'],
            cumulative_output={p:sum(s['output'][p] for s in segments[:idx]) for p in PRODUCTS})
    return dict(episode=game['episode'],seat=seat,seed=game['seed'],submission=56395605,leader='m1 primary',split='primary',
        shops=[list(x) for x in game['shops']],rewards=game['rewards'],checkpoints=checkpoints,segments=segments,
        compact_sha256=sha256(Path(path).read_bytes()).hexdigest(),
        validation='Official Simulator replayed both recorded action streams; exact final reward and every daily observed shop prefix matched.')

def replay_primary():
    files=sorted((ROOT/'data/ladder_panel/56395605').glob('*.json.gz'))
    failures=[]; rows=[]; started=time.time()
    # Frozen worker payload: this module is not edited while the pool is active.
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        jobs={pool.submit(replay_one,path):path for path in files}
        for future in as_completed(jobs):
            path=jobs[future]
            try: rows.append(future.result()); print('verified',path.stem,flush=True)
            except Exception as exc: failures.append({'episode':path.stem,'error':repr(exc)}); print('failed',path.stem,repr(exc),flush=True)
    rows.sort(key=lambda x:x['episode']); failures.sort(key=lambda x:x['episode'])
    previous_path=OUT/'dataset_primary.json'
    if previous_path.exists():
        previous={x['episode']:x for x in json.loads(previous_path.read_text(encoding='utf-8'))['games']}
        for row in rows:
            old=previous.get(row['episode'])
            if old is None: continue
            assert old['checkpoints']==row['checkpoints'], row['episode']
            assert [{k:s[k] for k in ('output','planted')} for s in old['segments']]==[{k:s[k] for k in ('output','planted')} for s in row['segments']], row['episode']
    payload={'schema_version':1,'products':PRODUCTS,'days':list(DAYS),'submission':56395605,'label':'m1 primary',
        'source':'data/ladder_panel/56395605 compact recorded tapes','runtime_seconds':time.time()-started,
        'requested_games':len(files),'verified_games':len(rows),'failures':failures,'games':rows,
        'validation':'Failures are excluded. Each included game has exact final reward plus all 30 observed shop-prefix checks.'}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'dataset_primary.json').write_text(json.dumps(payload,indent=1),encoding='utf-8')
    print(json.dumps({k:payload[k] for k in ('requested_games','verified_games','runtime_seconds','failures')},indent=2))

def rerank_primary():
    data=json.loads((OUT/'dataset_primary.json').read_text(encoding='utf-8'))
    umg=defaultdict(list)
    for sub in UMG:
        for path in sorted((ROOT/f'data/mg_tapes/{sub}').glob('*.json.gz')):
            g=load(path)
            for day in DAYS: umg[day].append({'episode':g['episode'],'submission':sub,'seat':g['seat'],'day':day,'shops':prefix(g['shops'],day),'tiles':compact_tiles(g['boards'][day])})
    candidates=[]
    for game in data['games']:
        for day in DAYS:
            cp=game['checkpoints'][str(day)]
            target={'episode':game['episode'],'seat':game['seat'],'submission':'56395605','day':day,'shops':prefix(cp['observation']['town']['unlocked_shops'],day),'tiles':own_tiles(cp),'source':'replayed_m1_primary'}
            ranked=[]
            for donor in umg[day]:
                if donor['episode']==target['episode']: continue
                key,components=score(target,donor); ranked.append((key,donor,components))
            for rank,(key,donor,components) in enumerate(sorted(ranked,key=lambda x:(x[0],x[1]['submission'],x[1]['episode'],x[1]['seat']))[:12],1):
                candidates.append({'target':{k:target[k] for k in ('episode','submission','seat','day','source','shops')},'rank':rank,'donor':{k:donor[k] for k in ('episode','submission','seat','day','shops')},'lexicographic_key':list(key),'difference_components':components})
    (OUT/'primary_candidates.json').write_text(json.dumps({'source_dataset':'dataset_primary.json','verified_primary_games':len(data['games']),'failures':data['failures'],'candidates':candidates},indent=2),encoding='utf-8')
    print(json.dumps({'targets':len(data['games'])*len(DAYS),'candidates':len(candidates),'failures':len(data['failures'])},indent=2))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    own_inventory={}
    for sub,label in OWN.items():
        files=sorted((ROOT/f'data/ladder_panel/{sub}').glob('*.json.gz'))
        own_inventory[sub]={'label':label,'compact_tapes':len(files),'fields':sorted(load(files[0]).keys()) if files else [],
            'full_board_checkpoints':0,'availability':'compact actions/shops only; replay required for exact checkpoints'}
    umg=[]; umg_inventory={}
    for sub in UMG:
        files=sorted((ROOT/f'data/mg_tapes/{sub}').glob('*.json.gz'))
        umg_inventory[sub]={'compact_tapes':len(files),'availability':'daily compact board strings, shops and actions'}
        for path in files:
            g=load(path)
            for day in DAYS:
                if len(g.get('boards',[]))<=day: continue
                umg.append({'episode':g['episode'],'submission':sub,'seat':g['seat'],'day':day,'shops':prefix(g['shops'],day),'tiles':compact_tiles(g['boards'][day])})
    domain=json.loads((ROOT/'results/fresh/cumulative_planning/domain/dataset.json').read_text(encoding='utf-8'))
    targets=[]
    for g in domain['games']:
        for day in DAYS:
            cp=g['checkpoints'][str(day)]
            targets.append({'episode':g['episode'],'submission':str(g['submission']),'seat':g['seat'],'day':day,
                'shops':prefix(cp['observation']['town']['unlocked_shops'],day),'tiles':own_tiles(cp),'source':'rich_v10_domain'})
    candidates=[]
    by_day=defaultdict(list)
    for x in umg: by_day[x['day']].append(x)
    for target in targets:
        rows=[]
        for donor in by_day[target['day']]:
            if donor['episode']==target['episode']: continue
            key,components=score(target,donor)
            rows.append((key,donor,components))
        for rank,(key,donor,components) in enumerate(sorted(rows,key=lambda x:(x[0],x[1]['submission'],x[1]['episode'],x[1]['seat']))[:12],1):
            candidates.append({'target':{k:target[k] for k in ('episode','submission','seat','day','source','shops')},'rank':rank,
                'donor':{k:donor[k] for k in ('episode','submission','seat','day','shops')},'lexicographic_key':list(key),'difference_components':components})
    inventory={'method':'Rank rich current-own v10 snapshots against UMG compact board donors; no rewards, outputs, or future shops used.',
       'checkpoints':list(DAYS),'own':own_inventory,'umg':umg_inventory,
       'rich_current_own':{'source':'results/fresh/cumulative_planning/domain/dataset.json','games':len(domain['games']),'checkpoint_states':len(targets),'availability':'full farm/private/market/town checkpoint state'},
       'ranking_key':['unordered visible-shop replacement count','asset count L1 / 2','crop+animal tile-label mismatch','visible reveal-order difference'],
       'limitations':['Compact own panel tapes have no board/checkpoint state and are inventory only until replayed.','UMG compact board labels omit private state and crop ages; ranks are retrieval candidates, not feasible continuations.','UMG submissions are retained as donor-version labels and never pooled into an estimated policy.']}
    (OUT/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    (OUT/'compact_candidates.json').write_text(json.dumps({'inventory_summary':inventory,'candidates':candidates},indent=2),encoding='utf-8')
    print(json.dumps({'own':{k:v['compact_tapes'] for k,v in own_inventory.items()},'umg':{k:v['compact_tapes'] for k,v in umg_inventory.items()},'targets':len(targets),'candidates':len(candidates)},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('inventory','replay-primary','rerank-primary','all'),nargs='?',default='inventory')
    args=parser.parse_args()
    if args.stage in ('inventory','all'): main()
    if args.stage in ('replay-primary','all'): replay_primary()
    if args.stage in ('rerank-primary','all'): rerank_primary()
