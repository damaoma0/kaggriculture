"""Second, deposit-aware sales experiment on another frozen set of fresh seeds."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
from importlib.metadata import version
import json
from market_corpus import ROOT, OUT, PATHS
from evaluate_market_sales import run


def main():
    (OUT/'deposit_sales_games').mkdir(exist_ok=True)
    manifest={'engine':version('kaggle-environments'),'seeds':list(range(99000,99004)),
      'modes':['baseline','current','visible'],'opponents':['sixday','pasture'],
      'selection':json.loads((OUT/'forecast_selection.json').read_text()),
      'change':'The initial experiment rarely acts because goods usually sell on deposit. This variant permits same-turn deposits, projected with the official engine. Forecast and other rules unchanged. New seeds reserved before running.',
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/'agents/market_sales_dp_deposits.py',ROOT/'agents/market_forecast.py',*PATHS.values()]}}
    mp=OUT/'deposit_sales_manifest.json'
    if mp.exists(): assert json.loads(mp.read_text())==manifest
    else: mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in manifest['seeds'] for i in (0,1) for o in manifest['opponents'] for m in manifest['modes']]
    pending=[j for j in jobs if not (OUT/'deposit_sales_games'/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j,True) for j in pending]):
            r=f.result();print(r['seed'],r['seat'],r['opponent'],r['mode'],r['cash'],r['stats'],flush=True)
    rows=[json.loads(p.read_text()) for p in sorted((OUT/'deposit_sales_games').glob('*.json'))]
    (OUT/'deposit_sales_results.json').write_text(json.dumps(rows,indent=2))
    print('COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()
