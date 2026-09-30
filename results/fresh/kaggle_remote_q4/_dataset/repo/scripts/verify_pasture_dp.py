"""Verify the small DP against exhaustive feeding schedules and engine growth."""
from copy import deepcopy
from itertools import product
import json,sys
from audit_router_advantage import ROOT,OUT
sys.path.insert(0,str(ROOT/'agents'))
from pasture_investment_dp import E,lifecycle_dp,sell_value


def main():
    cases=0
    for species,inventory,care in product(('COW','SHEEP'),(9850,10100),(True,False)):
        start=21 if species=='COW' else 23;t=start*24
        ops=['FEED','HARVEST','COLLECT_FERTILIZER']+(['CARE'] if care else [])
        cal={'placed':t,'events':{d:[(d*24+2,o) for o in ops] for d in range(start,30)}}
        herd=E._new_animal(species,0)
        obs={'step':t,'player':0,'farms':[{'tiles':[[herd]]}]}
        paths={p:[inventory]*(720-t) for p in E.PRODUCTS}
        a=E.ANIMALS[species];item=a['product'];best=-1e100
        for choices in product((False,True),repeat=30-start):
            farm={'tiles':[[E._new_animal(species,start)]]};added=0;value=-a['cost']
            for day,fed in zip(range(start,30),choices):
                tile=farm['tiles'][0][0];alive='animal' in tile
                amount=tile['yield_units'] if alive else 0
                baseline=(1+a['interval']) if day>=a['first_yield_day'] and (day-a['first_yield_day'])%a['interval']==0 else 0
                r0,i0=sell_value(item,inventory,baseline);r1,i1=sell_value(item,inventory+added,baseline+amount)
                value+=r1-r0;added+=i1-i0
                if alive:
                    tile['yield_units']=0
                    if tile['fertilizer_available']:value+=E.market_price('FERTILIZER',inventory);tile['fertilizer_available']=False
                    tile['fed_today']=fed;tile['cared_today']=care and fed
                    if fed:value-=E.market_price('WHEAT',inventory)
                if day<29:E._daily_refresh_animals(farm,day)
            best=max(best,value)
        actual=lifecycle_dp(species,cal,obs,paths)['value']
        assert abs(best-actual)<1e-8,(species,inventory,care,best,actual)
        cases+=1
    result={'cases':cases,'method':'Exhaustive feed schedules versus official animal refresh and exact marginal sale accounting','passed':True}
    (OUT/'dp_verification.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':main()
