"""Isolated sale-policy transfers, followed by fresh confirmation per baseline."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from statistics import mean
import argparse,json
import evaluate_modern_router as runner
from market_corpus import ROOT
from compare_router_refresh import PATHS as PUBLIC

OUT=ROOT/'results/fresh/modern_sales'
PATHS=dict(PUBLIC)
for base in ('v44','v45'):
    PATHS[base+'_base']=PUBLIC[base]
    for mode in ('order','liquid','both'):PATHS[base+'_'+mode]=ROOT/f'agents/{base}_our_{mode}.py'
runner.OUT=OUT;runner.PATHS=PATHS

def jobs(phase):
    if phase=='smoke':return [('smoke',140999,0,b+'_both','twocoins') for b in ('v44','v45')]
    if phase=='development':return [(phase,s,i,b+'_'+m,o) for s in range(140000,140003) for i in (0,1)
        for b in ('v44','v45') for m in ('base','order','liquid','both') for o in ('farmingv5','twocoins')]
    chosen=json.loads((OUT/'development_selection.json').read_text(encoding='utf-8'))
    return [(phase,s,i,b+'_'+m,o) for s in range(141000,141008) for i in (0,1) for b in ('v44','v45')
            for m in ('base',chosen[b]['mode']) for o in ('farmingv5','twocoins','v45' if b=='v44' else 'v44')]

def select():
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs('development')]
    result={}
    for base in ('v44','v45'):
        control={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['policy']==base+'_base'}
        modes={}
        for mode in ('order','liquid','both'):
            rs=[r for r in rows if r['policy']==base+'_'+mode]
            modes[mode]=dict(margin_gain=mean(r['margin']-control[r['seed'],r['seat'],r['opponent']]['margin'] for r in rs),
                cash_gain=mean(r['cash']-control[r['seed'],r['seat'],r['opponent']]['cash'] for r in rs))
        best=max(modes,key=lambda m:(modes[m]['margin_gain'],modes[m]['cash_gain'],m=='order',m=='liquid'))
        result[base]={'mode':best,'development':modes}
    (OUT/'development_selection.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('smoke','development','select','confirmation'),required=True);args=parser.parse_args()
    if args.phase=='select':select();return
    OUT.mkdir(parents=True,exist_ok=True)
    if args.phase!='smoke':
        paths=set(PATHS.values())|set(PUBLIC['twocoins'].parent.glob('*.py'))|{PUBLIC['twocoins'].parent/'actions.json',PUBLIC['twocoins'].parent/'settings.json',
            ROOT/'agents/adaptive_market_order.py',ROOT/'agents/modern_sales_overlay.py',ROOT/'scripts/evaluate_modern_sales.py',ROOT/'scripts/evaluate_modern_router.py',ROOT/'scripts/research_wheat_economy.py'}
        manifest={'jobs':jobs(args.phase),'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
            'design':'Both seats; identical hidden uniform shop sequences across variants. Three development seeds screen three transfers per base; eight separate confirmation seeds test one frozen winner per base. No tuning after screening.',
            'screen':'Highest development paired mean margin per base; ties broken by cash then order-only then liquidation-only. Confirm even if screening gains are negative.',
            'gate':'Per base, promote only with positive confirmation mean paired margin, nonnegative mean against each rival, >=6 of 8 positive seed averages, no fewer wins, no nonzero errors/fallbacks and max call <1s. Otherwise keep that unchanged base. Do not overwrite existing local selection or submit to Kaggle.'}
        path=OUT/(args.phase+'_manifest.json')
        if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
        else:path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(args.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(runner.run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()
