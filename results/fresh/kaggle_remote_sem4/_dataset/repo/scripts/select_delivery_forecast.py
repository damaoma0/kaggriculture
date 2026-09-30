"""Select a delivery estimator on training games; use engine trades only as labels."""
from collections import Counter
from statistics import mean
import json
from research_opponent_sales import OUT

def score(rows):
    errors=[];inference=[];floor_explained=0;known_mismatches=0
    for r in rows:
        actual=Counter((e[0],e[2]) for e in r['events'] if e[1]!=r['seat'])
        floor_sales=Counter((e[0],e[2]) for e in r['events'] if e[3]==1)
        for rec in r['inferred']:
            for p in ('MILK','WOOL'):
                inference.append({'known':rec['known'][p],'error':abs(rec['other'][p]-actual[rec['step'],p])})
                if rec['known'][p] and rec['other'][p]!=actual[rec['step'],p]:
                    known_mismatches+=1
                    floor_explained+=int(rec['other'][p]==max(0,actual[rec['step'],p]-floor_sales[rec['step'],p]))
        for checkpoint in r['forecasts']:
            for method,products in checkpoint['predictions'].items():
                for p,values in products.items():
                    for h in (6,12,24):
                        truth=sum(actual[checkpoint['step']+k,p] for k in range(h))
                        errors.append({'seed':r['seed'],'seat':r['seat'],'opponent':r['opponent'],'step':checkpoint['step'],
                          'method':method,'item':p,'horizon':h,'error':abs(sum(values[:h])-truth),'truth':truth,
                          'above_floor':checkpoint['prices'][p]>1})
    summary=[]
    for m in ('recent','clock','visible'):
        for h in (6,12,24):
            xs=[e for e in errors if e['method']==m and e['horizon']==h]
            summary.append({'method':m,'horizon':h,'mae':mean(x['error'] for x in xs),
              'above_floor_mae':mean(x['error'] for x in xs if x['above_floor']),
              'by_opponent':{o:mean(x['error'] for x in xs if x['opponent']==o) for o in sorted({x['opponent'] for x in xs})}})
    known=[x for x in inference if x['known']]
    return summary,{'identifiable_turns':len(known),'total_product_turns':len(inference),'known_mae':mean(x['error'] for x in known),
      'known_mismatches':known_mismatches,'explained_by_floor_sales':floor_explained},errors

def main():
    rows=json.loads((OUT/'train_results.json').read_text());metrics,inference,errors=score(rows)
    selected=min([r for r in metrics if r['horizon']==12],key=lambda r:r['above_floor_mae'])['method']
    result={'method':selected,'criterion':'Lowest 12-turn opponent-delivery MAE when current price exceeds floor, on training seeds only','metrics':metrics,'inference':inference}
    (OUT/'forecast_selection.json').write_text(json.dumps(result,indent=2));(OUT/'train_forecast_errors.json').write_text(json.dumps(errors));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
