"""Compile recorded routes into timed work orders and audit actual farm routines."""
from collections import Counter,defaultdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from evaluate_boards import ROOT,module_at,observation

OUT=ROOT/'results/fresh/router_routines'


def compile_orders():
    source=ROOT/'agents/public/tschinkel_router_v31.py'
    m=module_at('extract_router',source)
    names={m.MAIN:'main',m.YARN:'yarn',m.YARN_CARROT:'yarn_carrot',m.MILK_GLUT:'milk_glut'}
    templates={}
    for route_id,route in m.routes().items():
        days={};positions={};assets={}
        for step,a in enumerate(route):
            day=step//24
            if step%24==0:positions={0:[4,4]}
            for worker,op in enumerate([a.get('farmer',['PASS']),*a.get('hands',[])]):
                if worker not in positions:continue
                pos=positions[worker]
                if op[0] in m.MOVES:
                    dx,dy=m.MOVES[op[0]];new=[pos[0]+dx,pos[1]+dy]
                    if 0<=new[0]<10 and 0<=new[1]<10:
                        positions[worker]=new;continue
                if op[0]=='PASS':continue
                orders=days.setdefault(str(day),{}).setdefault(str(worker),[])
                orders.append({'step':step,'target':list(pos),'action':op,'asset':assets.get(tuple(pos)),
                               'predecessor':len(orders)-1 if orders else None})
                if op[0]=='PLANT':assets[tuple(pos)]=op[1]
                elif op[0]=='PLACE' and op[1] in m.ANIMALS:assets[tuple(pos)]=op[1]
                elif op[0]=='DIG':assets.pop(tuple(pos),None)
            if any(o[0]=='HIRE' for o in a.get('market',[])):
                for worker,pos in positions.items():
                    days.setdefault(str(day),{}).setdefault(str(worker),[]).append(
                        {'step':step+1,'target':list(pos),'action':None,'waypoint':True,'asset':None})
            for market in a.get('market',[]):
                if market[0]=='HIRE':
                    access=[(4,4),(5,4),(4,5),(5,5)]
                    spawn=min(access,key=lambda p:sum(tuple(v)==p for v in positions.values()))
                    positions[len(positions)]=list(spawn)
        for workers in days.values():
            for orders in workers.values():
                orders.sort(key=lambda t:(t['step'],not t.get('waypoint',False)))
                for i,t in enumerate(orders):t['predecessor']=i-1 if i else None
        templates[route_id]={'name':names[route_id],'days':days}
    result={'router_sha256':sha256(source.read_bytes()).hexdigest(),'templates':templates,
            'meaning':'Task targets reconstructed from the source action streams; preferred execution time equals recorded turn. Predecessors are per worker/day. No random future is encoded.'}
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data/router_work_orders.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    return m,result


def analyze(path,seat,m):
    replay=json.loads(path.read_text())
    crops={};finished=[];daily=defaultdict(lambda:{'ops':Counter(),'visits':defaultdict(set),'market':Counter()})
    placements=[];land=[];routes=[]
    agent=m.Agent()
    for t,(before,after) in enumerate(zip(replay['steps'],replay['steps'][1:])):
        obs=observation(before,seat);act=after[seat]['action'];f=obs['farms'][seat];n=after[0]['observation']['farms'][seat]
        if t<719:
            predicted=agent.act(obs)
            assert predicted==act,(path,seat,t)
            if not routes or routes[-1]['route']!=agent.cur:routes.append({'step':t,'route':agent.cur})
        positions=[f['farmer'],*f['hands']]
        for i,op in enumerate([act['farmer'],*act['hands']]):
            if i>=len(positions):continue
            x,y=positions[i];tile=f['tiles'][y][x];key=(x,y)
            daily[t//24]['ops'][op[0]]+=1
            if op[0] not in m.MOVES and op[0]!='PASS':daily[t//24]['visits'][i].add(key)
            if op[0] in ('WATER','FERTILIZE','HARVEST') and isinstance(tile,dict) and tile.get('kind')=='PLANT' and key in crops:
                crops[key]['actions'].append({'step':t,'worker':i,'op':op[0],'yield_before':tile.get('yield_units',0)})
        for op in act['market']:daily[t//24]['market'][op[0]+(':'+str(op[1]) if len(op)>1 else '')]+=1
        for y in range(10):
            for x in range(10):
                a=f['tiles'][y][x];b=n['tiles'][y][x];p=(x,y)
                if p in crops and (not isinstance(b,dict) or b.get('kind')!='PLANT' or b.get('planted_day')!=crops[p]['planted_day']):
                    c=crops.pop(p);c['end_step']=t+1;finished.append(c)
                if isinstance(b,dict) and b.get('kind')=='PLANT' and p not in crops:
                    crops[p]={'crop':b['crop'],'tile':[x,y],'planted_day':b['planted_day'],'start_step':t+1,'actions':[]}
                if isinstance(b,dict) and b.get('animal') and not (isinstance(a,dict) and a.get('animal')):placements.append({'step':t,'tile':[x,y],'animal':b['animal']})
        if len(n['unlocked_quadrants'])>len(f['unlocked_quadrants']):land.append({'step':t,'quadrants':n['unlocked_quadrants']})
    finished+=list(crops.values())
    return {'path':str(path.relative_to(ROOT)),'seat':seat,'routes':routes,'cash':replay['steps'][-1][seat]['reward'],
            'crops':finished,'animals':placements,'land':land,
            'daily':{str(d):{'ops':v['ops'],'market':v['market'],'worker_tiles':{str(i):sorted(p) for i,p in v['visits'].items()}} for d,v in daily.items()}}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    m,orders=compile_orders()
    paths=sorted((ROOT/'results/fresh/midgame').glob('audit2-router-*-router-None/replay.json'))
    rows=[]
    for p in paths:
        seat=int(p.parent.name.split('-seat')[1].split('-')[0])
        rows.append(analyze(p,seat,m))
    assert len(rows)==4
    (OUT/'routines.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    lines=['# Router production routines','',
           'Four actual router trajectories were reconstructed and every action checked against the public source. The work-order library also compiles all four recorded branch streams, including branches not visited in these four games. Planned tasks and successful farm transitions are kept separate.','',
           '## Production calendar','',
           '| Trace / route | Day | New crop cohorts | Animals placed | Land purchases |','|---|---:|---|---|---|']
    for k,r in enumerate(rows):
        for d in range(30):
            crops=Counter(c['crop'] for c in r['crops'] if c['planted_day']==d)
            animals=Counter(c['animal'] for c in r['animals'] if c['step']//24==d)
            land=[c['quadrants'] for c in r['land'] if c['step']//24==d]
            if crops or animals or land:lines.append(f"| {k+1} | {d} | {dict(crops)} | {dict(animals)} | {land} |")
    lines+=['','## Representative crop routines (trace 1)','',
            'Actions below are issued operations matched to live crop cohorts; they are not all guaranteed successful actions.','',
            '| Crop / tile | Planted | Fertilizer days | Harvest days | Harvest yield observed before action |','|---|---:|---|---|---|']
    seen=set()
    for c in rows[0]['crops']:
        key=(c['crop'],c['planted_day'])
        if key in seen:continue
        seen.add(key)
        fert=[a['step']//24 for a in c['actions'] if a['op']=='FERTILIZE']
        h=[a for a in c['actions'] if a['op']=='HARVEST']
        lines.append(f"| {c['crop']} {c['tile']} | {c['planted_day']} | {fert} | {[a['step']//24 for a in h]} | {[a['yield_before'] for a in h]} |")
    lines+=['','## Work-order model','',
            'Each worker/day has an ordered queue of operations with a target tile, preferred execution turn, operation arguments, inferred asset label and predecessor. Zero-duration position waypoints preserve shed occupancy at hiring times, which determines new-worker spawn positions. Movement is not stored as a policy action in the queue; the scheduler can compute a path from the actual position. Resource availability and crop validity still need checking at execution time. Branch selection remains the original public-state router.','',
            'The first prototype intentionally preserves the production calendar, worker ownership and market plan. Its purpose is to reproduce output while replacing movement replay with a constraint-based task executor. It is not yet a new farm-layout planner or a solver that reallocates jobs between workers.','',
            '[Machine-readable routines](../results/fresh/router_routines/routines.json) · [Compiled work orders](../data/router_work_orders.json)','']
    (ROOT/'docs/router_routines.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Verified',len(rows)*719,'source actions; compiled',sum(len(j) for t in orders['templates'].values() for d in t['days'].values() for j in d.values()),'tasks.')


if __name__=='__main__':main()
