"""Fresh policy confirmation after forecast-only validation; no retuning."""
import json
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
import evaluate_modern_router as runner
from market_corpus import ROOT

OUT=ROOT/'results/fresh/event_inputs'
PATHS={**runner.PUBLIC,'baseline':ROOT/'agents/v45_our_selected.py','candidate':ROOT/'agents/v45_event_candidate.py'}
def jobs():return [('confirmation',s,i,p,o) for s in range(147000,147008) for i in (0,1) for p in ('baseline','candidate') for o in ('v45','twocoins','farmingv5')]
def run(job):
    runner.OUT=OUT;runner.PATHS=PATHS
    return runner.run(job)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources={PATHS[k] for k in ('baseline','candidate','v45','twocoins','farmingv5')}|set(PATHS['twocoins'].parent.glob('*.py'))|{PATHS['twocoins'].parent/'actions.json',PATHS['twocoins'].parent/'settings.json',ROOT/'scripts/evaluate_event_inputs.py',ROOT/'scripts/evaluate_modern_router.py',ROOT/'agents/event_input_overlay.py',ROOT/'agents/event_price_forecast.py',ROOT/'scripts/build_event_inputs.py',ROOT/'results/fresh/event_prices/models.json'}
    manifest=dict(jobs=jobs(),sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(sources)},
        design='One candidate. Eight fresh policy-test seeds after forecast gate; both seats; 3 rivals; hidden common shops. Native tour generation, costs, safety factors and sale ordering unchanged. Only output valuation uses frozen event forecasts, interpolated for 12-72h deliveries within turns216-636; otherwise current-price valuation retained.',
        gate='Positive average margin; nonnegative margin change per rival; positive seed averages >=6/8; no fewer wins; own cash delta >=-500; zero errors/fallbacks; max call <1sec. Otherwise retain prior hybrid. No automatic submission.')
    path=OUT/'manifest.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs() if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()
