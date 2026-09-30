"""Direct, frozen comparison with the original public router, in both seats."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from importlib.metadata import version
from statistics import mean,median
import json,random,time
from market_corpus import ROOT,PATHS,load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/original_router_test'
SELECTED=ROOT/'agents/market_impact_selected.py'
OPPONENT=PATHS['old']


def run(job):
    panel,seed,seat=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own=load('original_test_selected',SELECTED);other=load('original_test_public',OPPONENT)
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    initial=[f.money for f in env.state[0].observation.farms]
    original_end=E._end_of_day
    if panel=='shops':
        schedule=random.Random(seed^0xBC28).choices(sorted(E.SHOPS),k=8)
        schedule[0]=sorted(E.SHOPS)[seed-128000]
        def end(state,environment,day):
            original_end(state,environment,day)
            revealed=state[0].observation.town.unlocked_shops
            revealed[:]=schedule[:len(revealed)]
        E._end_of_day=end
    elapsed=[]
    def act(obs):
        start=time.perf_counter();action=own.agent(obs);elapsed.append(time.perf_counter()-start);return action
    def rival(obs):return other.agent(obs)
    agents=[None,None];agents[seat]=act;agents[1-seat]=rival
    try:
        with Ledger(E) as ledger:env.run(agents)
    finally:E._end_of_day=original_end
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for states in env.steps for s in states)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row={'panel':panel,'seed':seed,'seat':seat,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
      'margin':env.state[seat].reward-env.state[1-seat].reward,'ledger':ledger.data,
      'shops':env.state[0].observation.town.unlocked_shops,'max_action_seconds':max(elapsed),
      'states':len(env.steps),'status':[s.status for s in env.state]}
    (OUT/'games'/f'{panel}-{seed}-{seat}.json').write_text(json.dumps(row,indent=2))
    return {k:row[k] for k in ('panel','seed','seat','cash','opponent_cash','margin')}


def summarize(rows):
    return {'games':len(rows),'wins':sum(r['margin']>0 for r in rows),'ties':sum(r['margin']==0 for r in rows),
      'losses':sum(r['margin']<0 for r in rows),'mean_cash':mean(r['cash'] for r in rows),
      'mean_opponent_cash':mean(r['opponent_cash'] for r in rows),'mean_margin':mean(r['margin'] for r in rows),
      'median_margin':median(r['margin'] for r in rows),'minimum_margin':min(r['margin'] for r in rows),'maximum_margin':max(r['margin'] for r in rows),
      'seed_mean_margins':{s:mean(r['margin'] for r in rows if r['seed']==s) for s in sorted({r['seed'] for r in rows})}}


def main():
    (OUT/'games').mkdir(parents=True,exist_ok=True)
    panels={'natural':list(range(127000,127016)),'shops':list(range(128000,128008))}
    manifest={'engine':version('kaggle-environments'),'panels':panels,'seats':[0,1],
      'selected':str(SELECTED.relative_to(ROOT)),'opponent':str(OPPONENT.relative_to(ROOT)),
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in (SELECTED,OPPONENT,ROOT/'scripts/test_original_router.py')},
      'purpose':'Direct comparison with the original public router; no policy tuning or selection.',
      'shop_control':'Natural panel uses the unmodified engine. Shops panel covers every first shop once, both seats; later draws fixed and hidden until revealed.'}
    path=OUT/'manifest.json'
    if path.exists():assert json.loads(path.read_text())==manifest,'Frozen test changed'
    else:path.write_text(json.dumps(manifest,indent=2))
    jobs=[(panel,s,i) for panel,seeds in panels.items() for s in seeds for i in (0,1)]
    pending=[j for j in jobs if not (OUT/'games'/('{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)
    rows=[json.loads((OUT/'games'/('{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    summary={panel:summarize([r for r in rows if r['panel']==panel]) for panel in panels}
    summary['all']=summarize(rows)
    (OUT/'results.json').write_text(json.dumps(rows,indent=2));(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    report=['# Direct test against the original public router\n',
      'Selected agent: `agents/market_impact_selected.py`. Opponent: **`agents/public/tschinkel_router_v31.py`**, the original public router, distinct from the six-day router. No agent code was changed or tuned for this test.\n',
      '## Results\n','| Panel | Games | Wins / ties / losses | Our average cash | Router average cash | Average margin | Worst margin |\n|---|---:|---|---:|---:|---:|---:|']
    for panel,s in summary.items():report.append(f"| {panel} | {s['games']} | {s['wins']} / {s['ties']} / {s['losses']} | {s['mean_cash']:,.1f} | {s['mean_opponent_cash']:,.1f} | {s['mean_margin']:+,.1f} | {s['minimum_margin']:+,.0f} |")
    report+=['\n## Coverage\n',
      'The natural panel uses 16 fresh seeds (127000–127015), each played in both seats. The additional controlled panel uses eight fresh seeds (128000–128007), one for each possible first shop, also in both seats. Future controlled shop draws remain hidden from both agents until revealed. The two panels are reported separately; the controlled panel is a coverage check, not a sample of natural shop frequencies.\n',
      '| First shop in controlled panel | Mean margin across both seats |\n|---|---:|']
    for seed in panels['shops']:
        subset=[r for r in rows if r['seed']==seed]
        assert subset[0]['shops']==subset[1]['shops']
        report.append(f"| {subset[0]['shops'][0]} | {mean(r['margin'] for r in subset):+,.1f} |")
    report+=['\n## Checks and limits\n',
      '- All 48 games completed the 30-day season (720 states) with valid statuses. Both players\' final cash reconciled exactly against the transaction ledger. Each game ran in a fresh worker process.\n',
      '- Source hashes and seeds were frozen before play. Seats are paired checks, not independent seeds. No Kaggle submission was made; these results concern the exact local router file above.\n',
      '- The previously recorded six-day-router result remains 16–0 on confirmation plus 8–0 in discovery. Those were different seeds and a different opponent file.\n',
      'Reproduce with `.venv/Scripts/python.exe scripts/test_original_router.py`. Full results, ledgers, shop sequences and source hashes: `results/fresh/original_router_test/`.\n']
    (ROOT/'docs/original_router_test.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
