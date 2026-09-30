"""Check the scheduler against enumeration and the engine market implementation."""
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'agents'))
from opponent_sales import E, schedule, trade_round


def brute(item,inv,q,ours,theirs,drain,objective):
    best=(-float('inf'),0)
    for a in range(q+1):
        for b in range(q-a+1):
            sales={0:a,4:b,8:q-a-b};stock=inv;reward=0
            for t in range(len(ours)):
                x,y,stock=trade_round(item,stock,ours[t]+sales.get(t,0),theirs[t])
                reward+=x-(y if objective=='margin' else 0)
                stock-=drain[t]
            best=max(best,(reward,a))
    return best


def main():
    rng=random.Random(20260916);checks=0;example=None
    for item in ('MILK','WOOL'):
        for inventory in (9900,9970,10000,10050,10100):
            for a,b in ((0,4),(3,0),(2,7),(6,6)):
                farms=[{'money':0},{'money':0}]
                market={'inventory':dict.fromkeys(E.PRODUCTS,inventory),'prices':{}}
                states=[SimpleNamespace(observation=SimpleNamespace(farms=farms,market=market,private={'shed':{item:q}}),action={'market':[['SELL',item,q]]}) for q in (a,b)]
                E._process_market(states,SimpleNamespace(configuration={}))
                assert trade_round(item,inventory,a,b)==(farms[0]['money'],farms[1]['money'],market['inventory'][item])
                checks+=1
        for _ in range(150):
            inv=rng.randrange(9860,10080);q=rng.randint(1,4)
            ours=[rng.randrange(3) for _ in range(13)]
            theirs=[rng.randrange(5) for _ in range(13)]
            drain=[rng.randrange(5) if t%4==0 else 0 for t in range(13)]
            answers={}
            for objective in ('profit','margin'):
                result=schedule(item,inv,q,ours,theirs,drain,objective,8)
                assert result==brute(item,inv,q,ours,theirs,drain,objective),(result,item,inv)
                answers[objective]=result;checks+=1
            if example is None and answers['margin'][1]>answers['profit'][1]:
                example=dict(item=item,inventory=inv,quantity=q,ours=ours,theirs=theirs,drain=drain,answers=answers)
    assert example is not None,'No objective distinction exercised'
    result={'checks':checks,'status':'passed','objective_difference_example':example}
    (ROOT/'results/fresh/opponent_sales/verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
