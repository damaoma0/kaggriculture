"""Compare the ranking value with complete engine market execution."""
from types import SimpleNamespace
import json,sys
from research_adaptive_order import ROOT,OUT
sys.path.insert(0,str(ROOT/'agents'))
from adaptive_market_order import E,priority_value


def engine_value(item,inventory,ours,theirs,first):
    farms=[{'money':100000},{'money':100000}]
    market={'inventory':dict.fromkeys(E.PRODUCTS,inventory),'prices':{}}
    own=['SELL',item,ours];other=['SELL' if theirs>=0 else 'BUY_PRODUCT',item,abs(theirs)]
    queues=[[own,[]],[[],other]] if first else [[[],own],[other,[]]]
    states=[SimpleNamespace(observation=SimpleNamespace(farms=farms,market=market,private={'shed':{item:q}}),action={'market':queue})
            for q,queue in zip((ours,max(0,theirs)),queues)]
    E._process_market(states,SimpleNamespace(configuration={}))
    return farms[0]['money']-farms[1]['money']


def main():
    count=0
    for item in E.PRODUCTS:
        for inventory in (9850,9975,10000,10075,10200):
            for ours in (1,6,30):
                for theirs in ((-8,0,3,17) if item in ('WHEAT','FERTILIZER') else (0,3,17)):
                    expected=engine_value(item,inventory,ours,theirs,True)-engine_value(item,inventory,ours,theirs,False)
                    assert priority_value(item,inventory,ours,theirs)==expected,(item,inventory,ours,theirs)
                    count+=1
    # Fractional forecasts interpolate neighboring integer scenarios.
    for item in E.PRODUCTS:
        a=priority_value(item,9970,6,2);b=priority_value(item,9970,6,3)
        assert priority_value(item,9970,6,2.25)==0.75*a+0.25*b
        count+=1
    result={'status':'passed','engine_and_interpolation_checks':count}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'verification.json').write_text(json.dumps(result,indent=2));print(result)


if __name__=='__main__':main()
