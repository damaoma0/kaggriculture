"""Map native tape worker visits without changing agents."""
from market_corpus import ROOT,load
import json

def visits(module,tape,limit=216):
    positions=[[4,4]];out=[]
    for step,a in enumerate(tape[:limit]):
        commands=[a.get('farmer') or ['PASS'],*(a.get('hands') or [])]
        for actor,(pos,c) in enumerate(zip(positions,commands)):
            out.append(dict(step=step,actor=actor,pos=list(pos),command=c))
            if c and c[0] in module.MOVES:
                dx,dy=module.MOVES[c[0]];pos[0]=max(0,min(9,pos[0]+dx));pos[1]=max(0,min(9,pos[1]+dy))
        for o in a.get('market',[]):
            if o and o[0]=='HIRE':
                access=((4,4),(5,4),(4,5),(5,5))
                p=min(access,key=lambda xy:(sum(tuple(v)==xy for v in positions),access.index(xy)))
                positions.append(list(p))
        if (step+1)%24==0:positions=[[4,4]]
    return out

if __name__=='__main__':
    m=load('inspect_native',ROOT/'agents/v45_event_candidate.py')
    records=visits(m,m._IMPL.chassis.routes[0])
    print(json.dumps([v for v in records if v['command'] and v['command'][0] in ('PLANT','PLACE','PICKUP','BUILD_PASTURE')],indent=2))
