"""Paired development cash and product quantities; no policy tuning."""
import json
from collections import Counter
from evaluate_leader_hybrids import OUT,jobs

def main():
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs('screen')]
    bases={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['policy']=='baseline'}
    result={}
    for mode in ('berries','herd','both'):
        rs=[r for r in rows if r['policy']==mode];totals=Counter()
        for r in rs:
            for sign,x in ((1,r),(-1,bases[r['seed'],r['seat'],r['opponent']])):
                for field in ('revenue','spend','sold_units'):
                    for key,value in x['ledger'][x['seat']][field].items():totals[field+':'+key]+=sign*value
        result[mode]={k:v/len(rs) for k,v in totals.items()}
    (OUT/'screen_accounting.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({m:{k:round(v,2) for k,v in values.items() if abs(v)>5} for m,values in result.items()},indent=2))

if __name__=='__main__':main()
