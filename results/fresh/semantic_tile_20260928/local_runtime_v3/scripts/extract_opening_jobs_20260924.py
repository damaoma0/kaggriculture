"""Serial exact job/state extraction from recorded Kaggriculture replays."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import gc, gzip, hashlib, json, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FRESH=ROOT/'results/fresh/leader_opening_review_20260924_01a0/replays'
DSM=ROOT/'data/dsm_replays'
OUT=ROOT/'results/fresh/coherent_opening_20260924_01a0/extraction/full'
FRESH_TARGETS={'112802103':1,'112794038':1,'112785833':0}

def readtiles(farm):
    return {(x,y):deepcopy(t) for y,row in enumerate(farm['tiles']) for x,t in enumerate(row) if isinstance(t,dict)}

def identity(t):
    if not t:return None
    return {k:t.get(k) for k in ('kind','crop','animal','planted_day','placed_day') if k in t}

def parity_value(key,value): return value

def extract(path, engine, structify, Ledger, source, check_normalized=False):
    raw=path.read_bytes(); digest=hashlib.sha256(raw).hexdigest(); r=json.loads(raw); del raw
    steps=r['steps']; n=min(719,len(steps)-1)
    if n<1: return None
    state=structify(deepcopy(steps[0])); from types import SimpleNamespace
    env=SimpleNamespace(done=False,configuration=structify(r['configuration']),info=r['info'])
    teams=r.get('info',{}).get('TeamNames',[])
    ep={'episode_id':int(r['info'].get('EpisodeId',path.stem.split('-')[1] if path.stem.startswith('episode-') else -1)),
        'source':source,'teams':teams,'replay_sha256':digest,'transitions':n,'seats':[]}
    ep['actions']={str(s):[deepcopy(steps[t+1][s]['action']) for t in range(n)] for s in (0,1)}
    ep['market_success_by_order']={str(s):[] for s in (0,1)}
    ep['jobs_by_seat']={str(s):[] for s in (0,1)}
    with Ledger(engine) as ledger:
        parse_context={'step':0,'calls':0,'order':0,'seat':0}
        parse_orig=engine._parse_order; commit_orig=engine._commit_unit; market_orig=engine._process_market
        hire_orig=engine._do_hire; land_orig=engine._do_buy_land
        unit_orig=engine._apply_unit_action
        initial_cash=[steps[0][0]['observation']['farms'][s]['money'] for s in (0,1)]
        events=[[],[]]
        def process_market(st,en):
            max_orders=max(1,int(getattr(en.configuration,'maxMarketOrdersPerTurn',10)))
            queues=[]
            for ss in st:
                act=ss.action if isinstance(ss.action,dict) else {}
                q=act.get('market',[])
                queues.append(q[:max_orders] if isinstance(q,list) else [])
            max_len=max((len(q) for q in queues),default=0)
            parse_context['slots']=[(i,s) for i in range(max_len) for s in (0,1) if i<len(queues[s])]
            parse_context['calls']=0
            return market_orig(st,en)
        def parse(order):
            idx,seat=parse_context['slots'][parse_context['calls']]
            parse_context['calls']+=1; parse_context['seat']=seat; parse_context['order']=idx
            result=parse_orig(order)
            if seat==0 and result is not None: events[seat].append(dict(step=parse_context['step'],order_index=idx,job='market_order',command=deepcopy(order),successful=False))
            if seat==1 and result is not None: events[seat].append(dict(step=parse_context['step'],order_index=idx,job='market_order',command=deepcopy(order),successful=False))
            return result
        def commit(op,item,price,farm,private,market,shed_capacity=100):
            s=ledger.seats.get(id(farm),parse_context['seat']); ok=commit_orig(op,item,price,farm,private,market,shed_capacity)
            if ok: events[s].append(dict(step=parse_context['step'],order_index=parse_context['order'],job='market_fill',op=op,item=item,quantity=1,spend=price))
            return ok
        def hire(farm,private,board_size,mult=10):
            s=ledger.seats.get(id(farm),parse_context['seat']); before=farm['hires_today']; hand=len(farm['hands']); hire_orig(farm,private,board_size,mult)
            if farm['hires_today']>before: events[s].append(dict(step=parse_context['step'],order_index=parse_context['order'],job='hire',command=['HIRE'],quantity=farm['hires_today']-before))
        def land(farm,board_size):
            s=ledger.seats.get(id(farm),parse_context['seat']); before=len(farm['unlocked_quadrants']); cash=farm['money']; land_orig(farm,board_size)
            if len(farm['unlocked_quadrants'])>before: events[s].append(dict(step=parse_context['step'],order_index=parse_context['order'],job='buy_land',command=['BUY_LAND'],quantity=len(farm['unlocked_quadrants'])-before,spend=cash-farm['money']))
        def unit(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
            s=ledger.seats.get(id(farm),0); pos0=engine._farmer_position(farm,idx); pos=tuple(pos0) if pos0 is not None else None
            if pos is None: return unit_orig(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
            tile0=farm['tiles'][pos[1]][pos[0]] if pos else None; beforetile=deepcopy(tile0) if isinstance(tile0,dict) else tile0
            inv=private['inventories'][idx] if idx<len(private['inventories']) else {}; beforeinv=dict(inv); beforeseeds=dict(private['seeds']); beforeshed=dict(private['shed']); beforecash=farm['money']
            result=unit_orig(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
            op=action[0] if action else ''
            if op in ('WATER','FEED','CARE','HARVEST','COLLECT_FERTILIZER','DIG','BUILD_COOP','BUILD_PASTURE','PLACE','PLANT','FERTILIZE'):
                aftertile=farm['tiles'][pos[1]][pos[0]]
                aftertile=deepcopy(aftertile) if isinstance(aftertile,dict) else aftertile
                def delta(old,new): return {p:new.get(p,0)-old.get(p,0) for p in set(old)|set(new) if new.get(p,0)!=old.get(p,0)}
                inv_delta={'unit':delta(beforeinv,dict(inv)),'seeds':delta(beforeseeds,dict(private['seeds'])),'shed':delta(beforeshed,dict(private['shed']))}
                changed=(beforetile!=aftertile or any(inv_delta.values()) or beforecash!=farm['money'])
                if changed:
                    events[s].append(dict(step=parse_context['step'],day=day,job='unit_'+op.lower(),command=deepcopy(action),tile=list(pos),
                      before=beforetile,after=aftertile,inventory_delta=inv_delta))
            return result
        engine._parse_order=parse; engine._commit_unit=commit; engine._do_hire=hire; engine._do_buy_land=land; engine._apply_unit_action=unit; engine._process_market=process_market
        try:
            for t in range(n):
                parse_context.update(step=t,calls=0); events=[[],[]]
                ledger.seats={id(state[0].observation.farms[s]):s for s in (0,1)}
                cmds=[deepcopy(steps[t+1][s]['action']) for s in (0,1)]
                for s in (0,1): state[s].action=cmds[s]; state[s].observation.step=t
                state=engine.interpreter(state,env)
                for s in (0,1):
                    for key in ('farms','market','town','private'):
                        if parity_value(key,state[s].observation[key])!=parity_value(key,steps[t+1][s]['observation'][key]):
                            raise AssertionError((ep['episode_id'],t,s,key))
                    money=state[0].observation.farms[s]['money']
                    account=ledger.data[s]
                    assert initial_cash[s]+sum(account['revenue'].values())-sum(account['spend'].values())==money,(ep['episode_id'],t,s,'cash')
                for s in (0,1):
                    ep['jobs_by_seat'][str(s)].extend(e for e in events[s] if e['job'].startswith('unit_'))
                    for e in events[s]:
                        if e['job']=='market_order':
                            fills=[z for z in events[s] if z.get('order_index')==e['order_index'] and z['job']=='market_fill']
                            hires=[z for z in events[s] if z.get('order_index')==e['order_index'] and z['job']=='hire']
                            lands=[z for z in events[s] if z.get('order_index')==e['order_index'] and z['job']=='buy_land']
                            cmd=e['command']; qty=sum(z['quantity'] for z in fills)
                            if cmd[0]=='HIRE' and hires: canonical=['HIRE']
                            elif cmd[0]=='BUY_LAND' and lands: canonical=['BUY_LAND']
                            elif cmd[0] in ('BUY_PRODUCT','BUY_SEED','BUY_ANIMAL','SELL') and qty: canonical=[cmd[0],cmd[1],qty]
                            else: canonical=[]
                            e['successful']=bool(canonical)
                            e['results']=canonical
                    slot_map={e['order_index']:e for e in events[s] if e['job']=='market_order'}
                    orders=cmds[s].get('market') or []
                    ep['market_success_by_order'][str(s)].append([slot_map[i].get('results',[]) if i in slot_map else [] for i in range(min(10,len(orders)))])
                if (t+1)%24==0 or t+1==n:
                    day=30 if (t+1)==n and (t+1)%24 else (t+1)//24
                    for s in (0,1):
                        ref=steps[t+1]; f=ref[0]['observation']['farms'][s]; priv=ref[s]['observation']['private']
                        daily={'day':day,'seat':s,'cash':f['money'],'farm':deepcopy(f),'private':deepcopy(priv),
                               'shops':deepcopy(ref[0]['observation']['town'].get('unlocked_shops',[]))}
                        ep.setdefault('daily',[]).append(daily)
            for s in (0,1):
                obs=steps[0][0]['observation']; f=obs['farms'][s]; priv=steps[0][s]['observation']['private']
                ep.setdefault('daily',[]).append({'day':0,'seat':s,'cash':f['money'],'farm':deepcopy(f),'private':deepcopy(priv),'shops':deepcopy(obs['town'].get('unlocked_shops',[]))})
            ep['daily'].sort(key=lambda x:(x['seat'],x['day']))
            ep['shops_by_day']=[deepcopy(steps[min(d*24,len(steps)-1)][0]['observation']['town'].get('unlocked_shops',[])) for d in range(31)]
        finally:
            engine._parse_order=parse_orig; engine._commit_unit=commit_orig; engine._do_hire=hire_orig; engine._do_buy_land=land_orig; engine._apply_unit_action=unit_orig; engine._process_market=market_orig
    if check_normalized:
        checkstate=structify(deepcopy(steps[0])); checkenv=SimpleNamespace(done=False,configuration=structify(r['configuration']),info=r['info'])
        for t in range(n):
            for s in (0,1):
                act=deepcopy(ep['actions'][str(s)][t]); act['market']=deepcopy(ep['market_success_by_order'][str(s)][t]); checkstate[s].action=act; checkstate[s].observation.step=t
            checkstate=engine.interpreter(checkstate,checkenv)
            for s in (0,1):
                for key in ('farms','market','town','private'):
                    assert parity_value(key,checkstate[s].observation[key])==parity_value(key,steps[t+1][s]['observation'][key]),(ep['episode_id'],t,s,'normalized-'+key)
        ep['normalized_action_parity']=True
    del r,steps,state; gc.collect(); return ep

def main():
    sys.path.insert(0,str(ROOT/'results/fresh/tape_margin_20260924_01a0/payload/vendor')); sys.path.insert(0,str(ROOT/'scripts'))
    import psutil
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    from kaggle_environments.utils import structify
    from evaluate_boards import Ledger
    OUT.mkdir(parents=True,exist_ok=True); records=[]
    paths={p.stem.split('-')[1]:p for p in DSM.glob('episode-*-replay.json')}
    for eid,p in FRESH_TARGETS.items(): paths[eid]=FRESH/f'episode-{eid}-replay.json'
    files=[]; fresh=[]; normalized_verified=None
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--fresh-only',action='store_true'); ap.add_argument('--pilot',action='store_true'); ap.add_argument('--limit',type=int); args=ap.parse_args()
    if args.fresh_only: paths={eid:FRESH/f'episode-{eid}-replay.json' for eid in FRESH_TARGETS}
    if args.pilot:
        local=dict(list(sorted({p.stem.split('-')[1]:p for p in DSM.glob('episode-*-replay.json')}.items()))[:6])
        paths={**local,**{eid:FRESH/f'episode-{eid}-replay.json' for eid in FRESH_TARGETS}}
    if args.limit: paths=dict(list(sorted(paths.items()))[:args.limit])
    for seq,(eid,path) in enumerate(sorted(paths.items())):
        while psutil.virtual_memory().available<2.6e9: time.sleep(5)
        ep=extract(path,engine,structify,Ledger,'fresh' if path.parent==FRESH else 'dsm_local',check_normalized=(seq==0))
        if ep.get('normalized_action_parity'): normalized_verified=ep['episode_id']
        if ep is None: continue
        for s in (0,1):
            out=OUT/f'trace-{eid}-seat{s}.json.gz'
            trace={'episode':ep['episode_id'],'seat':s,'team':ep['teams'][s] if s<len(ep['teams']) else None,
              'source_sha256':ep['replay_sha256'],'source':ep['source'],'actions':ep['actions'][str(s)],
              'market_success_by_order':ep['market_success_by_order'][str(s)],
              'daily':[d for d in ep['daily'] if d['seat']==s],
              'jobs':ep['jobs_by_seat'][str(s)],
              'shops_by_day':ep['shops_by_day']}
            with gzip.open(out,'wt',encoding='utf-8',compresslevel=6) as f: json.dump(trace,f,separators=(',',':'))
            if trace['team']=='DSM': files.append({'episode':ep['episode_id'],'seat':s,'team':trace['team'],'path':out.name,'source_sha256':ep['replay_sha256'],'transitions':ep['transitions']})
        hires=sum(1 for seatrows in ep['market_success_by_order'].values() for orders in seatrows for order in orders if order==['HIRE'])
        if eid in FRESH_TARGETS:
            fresh.append({'episode_id':ep['episode_id'],'focus_seat':FRESH_TARGETS[eid],
              'hire_steps':{str(s):[t for t,orders in enumerate(ep['market_success_by_order'][str(s)]) if any(order==['HIRE'] for order in orders)][:10] for s in (0,1)}})
        print(f"{eid}: {ep['transitions']} transitions; hires={hires}; {out.name}",flush=True)
        del ep; gc.collect()
    meta={'schema_version':2,'scope':'full replay through min(719, recorded transitions)','order_index':'engine parser invocation index, zero-based market queue position; successful jobs carry that slot','daily':'full end-of-day farm and private observation, plus public unlocked shops','engine_sha256':hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),'normalized_action_parity_verified_episode':normalized_verified,'episodes':files}
    (OUT/'manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (OUT/'index.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text('# DSM replay traces\n\nEach `trace-<episode>-seat<seat>.json.gz` contains the original 719 target actions, successful market orders aligned to original queue positions, full daily farm/private observations, successful non-movement physical jobs, and public shops by day. `market_success_by_order[t][i]` is `[]` when no quantity of original order i committed; otherwise it is the canonical order with successfully filled quantity (or atomic HIRE/BUY_LAND). Daily includes day 0 and end states through final day 30. `index.json` lists DSM target-seat trace paths, episode/seat, and source replay hashes. Extraction replays recorded actions through the installed engine, asserts exact parity on farms/market/town/private each transition, reconciles cash, processes files serially, and waits for at least 2.6 GB available memory. `metadata.json` records a full normalized-action parity check against the first source replay.\n',encoding='utf-8')
    print('FRESH_HIRE_STEPS '+json.dumps(fresh),flush=True)

if __name__=='__main__':main()
