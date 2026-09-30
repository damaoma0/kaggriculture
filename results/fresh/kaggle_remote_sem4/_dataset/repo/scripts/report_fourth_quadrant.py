from statistics import mean
from pathlib import Path
import json
from research_fourth_quadrant import OUT,CONFIGS

def summarize(phase='discovery'):
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'games').glob(phase+'-*.json')]
    base={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['mode']=='none'}
    summary=[]
    for config in CONFIGS:
        for mode in ('native','tomato','sheep'):
            pairs=[(r,base[r['seed'],r['seat'],r['opponent']]) for r in rows if r['configuration']==config and r['mode']==mode and (r['seed'],r['seat'],r['opponent']) in base]
            if not pairs:continue
            entry=dict(configuration=config,mode=mode,pairs=len(pairs),committed=sum(r['final_quadrants']==4 for r,b in pairs),cash_delta=mean(r['cash']-b['cash'] for r,b in pairs),margin_delta=mean(r['margin']-b['margin'] for r,b in pairs),positive_margin=sum(r['margin']>b['margin'] for r,b in pairs),min_margin_delta=min(r['margin']-b['margin'] for r,b in pairs),max_margin_delta=max(r['margin']-b['margin'] for r,b in pairs),
                labor_delta=mean(r['ledger'][r['seat']]['spend'].get('HIRE',0)-b['ledger'][b['seat']]['spend'].get('HIRE',0) for r,b in pairs),
                feature_prices={item:mean(r['features'][int(mode!='sheep')]['market']['prices'][item] for r,b in pairs) for item in ('TOMATO','WOOL','WHEAT','FERTILIZER')})
            summary.append(entry)
    (OUT/f'{phase}_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--phase',default='discovery',choices=['discovery','confirmation']);args=p.parse_args()
    if args.phase=='confirmation':
        from confirm_fourth_quadrant import configs
        CONFIGS.clear();CONFIGS.update({k:v[1] for k,v in configs().items()})
    summarize(args.phase)
