"""Build fragment: appended to the frozen V45 source by build_modern_router.py.

Original joint input-tour selection for this project. Retains public router's
physical execution, feeding economics and crop-gain model. Not a standalone agent.
"""
_MODERN_PARENT_JOINT = _r68_joint_plans
_MODERN_INPUT_STATS = dict(calls=0, changed=0, errors=0)


def _modern_tours(obs, targets, action, index):
    ready, start = _r62_input_start(obs, action, index)
    day = int(obs['step']) // 24
    prices = {p: max(1, int(obs['market']['prices'][p])-2) for p in ('WHEAT','CARROT')}
    fertilizer = max(1, _r37_market_price('FERTILIZER', obs['market']['inventory']['FERTILIZER']-16)+2)
    beam = [(0, ready, start, (), frozenset(), 0, 0)]
    options = []
    for depth in range(8):
        expanded = []
        for score, now, pos, path, used, wheat, carrot in beam:
            for xy, target in targets.items():
                if xy in used: continue
                arrival = now + abs(pos[0]-xy[0]) + abs(pos[1]-xy[1])
                if arrival >= day*24+23: continue
                gain = _r51_input_gain(target, arrival, day)
                if not gain: continue
                nw = wheat + (gain if target['crop']=='WHEAT' else 0)
                nc = carrot + (gain if target['crop']=='CARROT' else 0)
                route = path + ((xy[0],xy[1],target['crop'],target['birth']),)
                value = nw*prices['WHEAT']+nc*prices['CARROT']-1.5*fertilizer*len(route)
                expanded.append((value,arrival+1,xy,route,used|{xy},nw,nc))
        if not expanded: break
        expanded.sort(key=lambda x:(-x[0],x[1],x[3]))
        beam = expanded[:8]
        options.extend(beam[:2])
    options.sort(key=lambda x:(-x[0],x[1],x[3]))
    result=[]; seen=set()
    for _, _, _, path, used, wheat, carrot in options:
        if used in seen: continue
        seen.add(used)
        result.append((list(path),{'WHEAT':wheat,'CARROT':carrot}))
        if len(result)==6: break
    return result


def _modern_cost_value(obs, action, paths, topup):
    """Conservative current-market valuation; not a future-price oracle."""
    farm=obs['farms'][obs['player']]; inventory=obs['market']['inventory']
    qty=sum(len(path) for path,units in paths)
    parent_fert=sum(max(0,int(o[2])) for o in action.get('market',[]) if len(o)>2 and o[:2]==['BUY_PRODUCT','FERTILIZER'])
    cost=sum(max(1,_r37_market_price('FERTILIZER',inventory['FERTILIZER']-parent_fert-n)+2) for n in range(1,qty+topup+1))
    cost+=sum(_v219_fib(int(farm['hires_today'])+i) for i in range(len(paths)))
    units={p:sum(u[p] for path,u in paths) for p in ('WHEAT','CARROT')}
    value=sum(max(1,_r37_market_price(item,inventory[item]+n)-2) for item,q in units.items() for n in range(1,q+1))
    return cost,value,qty,units


def _r68_joint_plans(obs,action,targets,stock,purchases,topup):
    original=_MODERN_PARENT_JOINT(obs,action,targets,stock,purchases,topup)
    _MODERN_INPUT_STATS['calls']+=1
    try:
        farm=obs['farms'][obs['player']]
        best=original; best_score=0
        if original[0]:
            paths=[]
            for i,plan in enumerate(original[0]):
                now,pos=_r62_input_start(obs,action,i);u={'WHEAT':0,'CARROT':0}
                for x,y,crop,birth in plan['path']:
                    now+=abs(pos[0]-x)+abs(pos[1]-y)
                    u[crop]+=_r51_input_gain(targets[x,y],now,int(obs['step'])//24)
                    now+=1;pos=(x,y)
                paths.append((plan['path'],u))
            cost,value,_,_=_modern_cost_value(obs,action,paths,topup)
            best_score=value-cost
        def consider(paths):
            nonlocal best,best_score
            n=len(paths)
            cost,value,qty,units=_modern_cost_value(obs,action,paths,topup)
            if len(action.get('market',[]))+1+n>10: return
            if sum(stock.values())+purchases+qty+topup>95: return
            if farm['money']<cost+3000 or value<1.5*cost+50*n: return
            score=value-cost
            if score<=best_score+1: return
            best_score=score
            best=([{'path':path,'quantity':len(path),'loaded':False} for path,u in paths],qty,cost,units)
        for first in _modern_tours(obs,targets,action,0):
            consider([first])
            used={(x,y) for x,y,_,_ in first[0]}
            remaining={xy:t for xy,t in targets.items() if xy not in used}
            for second in _modern_tours(obs,remaining,action,1): consider([first,second])
        if best is not original:_MODERN_INPUT_STATS['changed']+=1
        return best
    except Exception:
        _MODERN_INPUT_STATS['errors']+=1
        return original


_MODERN_AGENT_PARENT=agent
def agent(observation,configuration=None):
    if int(observation['step'])==0:_MODERN_INPUT_STATS.update(calls=0,changed=0,errors=0)
    result=_MODERN_AGENT_PARENT(observation,configuration)
    agent.telemetry=dict(getattr(_MODERN_AGENT_PARENT,'telemetry',{}),
        modern_input_calls=_MODERN_INPUT_STATS['calls'],modern_input_changed=_MODERN_INPUT_STATS['changed'],
        modern_input_errors=_MODERN_INPUT_STATS['errors'])
    return result
agent.telemetry={}
