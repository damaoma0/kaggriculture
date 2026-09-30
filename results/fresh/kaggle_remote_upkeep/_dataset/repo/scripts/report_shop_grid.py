"""Summarize systematic shop-stratified opening search and verify selected agent."""
from collections import defaultdict
from copy import deepcopy
import json
import random
from statistics import mean
from evaluate_boards import ROOT, module_at, observation
from search_shop_grid import SHOPS, OUT


def paired_interval(rows, a, b):
    lookup={(r['name'],r['seed'],r['seat']):r['margin'] for r in rows}
    by_seed=defaultdict(list)
    for r in rows:
        if r['name']==a:
            by_seed[r['first_shop'],r['seed']].append(r['margin']-lookup[b,r['seed'],r['seat']])
    by_shop=defaultdict(list)
    for (shop,seed),v in by_seed.items(): by_shop[shop].append(mean(v))
    rng=random.Random(572101)
    boot=sorted(mean(mean(rng.choices(v,k=len(v))) for v in by_shop.values()) for _ in range(4000))
    return mean(mean(v) for v in by_shop.values()),boot[100],boot[3899]


def main():
    panels={s:json.loads((OUT/f'{s}.json').read_text()) for s in ('train','validate','test')}
    assert [len(panels[s]) for s in panels]==[288,128,128]
    learned=json.loads((OUT/'learned.json').read_text())
    selection=json.loads((OUT/'selection.json').read_text())
    names=('public-router','growth-control','shop-fixed','shop-adaptive')
    verified=0
    for seat in (0,1):
        folder=OUT/f"test-{selection['name']}-89000-seat{seat}"
        replay=json.loads((folder/'opening.json').read_text())
        selected=module_at('selected_grid',ROOT/'agents/opening_v3.py')
        for t in range(216):
            obs=observation(replay['steps'][t],seat); original=deepcopy(obs)
            assert selected.agent(obs)==replay['steps'][t+1][seat]['action']
            assert obs==original
            verified+=1
        # Every searched/adaptive opening must share the actual router prefix.
        prefix=json.loads((OUT/f'test-public-router-89000-seat{seat}/opening.json').read_text())
        for name in ('shop-fixed','shop-adaptive'):
            other=json.loads((OUT/f'test-{name}-89000-seat{seat}/opening.json').read_text())
            assert other['steps'][:73]==prefix['steps'][:73]
    lines=['# Systematic opening search across shop scenarios','',
           f"Validation-selected experimental policy: **{selection['name']}**, fixed before the test panel. Local experimental entry point: `agents/opening_v3.py`. It did not beat the router on the held-out test mean; **keep the unchanged public-router opening as the baseline**. This grid found no reliable improvement over it.",'',
           '## Experimental design','',
           'The first shop unlocks on day 3. All searched policies use the exact public-router prefix through action 71, then choose a numerical configuration using the first visible shop. This spends starting capital before seeing any shop; the search optimizes reinvestment after the first reveal, not different day-0 allocations. The old growth opening is retained as a separate control.','',
           'Full factorial grid: cow target {4, 8} × sheep target {4, 8} × crop for vacant expansion plots {WHEAT, STRAWBERRY} × daily hand target {8, 10}: **16 configurations**. Existing crops/animals are preserved. New animal targets take nearby free plots; NE becomes eligible when cash covers its cost plus 50. Buying and worker movement remain observation-driven. All agents hand off at day 9 to the same replanting rule, and face the router opening followed by that same rule.','',
           '| Panel | Independent scenario seeds | Games | Purpose |','|---|---:|---:|---|',
           '| Training | 16 (two per first shop) | 288 | Full grid plus router and old-growth controls; one seat per scenario, balanced across repetitions |',
           '| Validation | 16 new (two per first shop) | 128 | Four policies, both seats; choose final policy |',
           '| Test | 16 new (two per first shop) | 128 | Four frozen policies, both seats; no tuning |','',
           'The fixture balances all eight first shops and generates seven later shop draws independently for each scenario. A shop replaces the engine draw only when its normal unlock time arrives; policies never receive future shops or seeds. Weather is not modeled by this game. Weeds and all other mechanics still use the official engine. This is a controlled shop experiment, not a claim that these exact trajectories follow unmodified seed RNG. Different farms can change weed draws; prices and opponent responses are endogenous.','',
           'The fixed policy is the best training-wide mean margin. The adaptive policy chooses a configuration per first-shop type, using a 50/50 blend of that shop’s mean margin and the global mean to reduce overfitting. The selector can keep the original router. It chooses only at day 3 and never consults future shops. This is a deterministic shop-dependent mixture of configurations, not randomized play.','',
           '## Untouched test results','',
           '| Policy | Our mean cash | Opponent mean cash | Mean margin | Wins / draws / losses | Mean day-1 cash |','|---|---:|---:|---:|---:|---:|']
    for n in names:
        g=[r for r in panels['test'] if r['name']==n]
        lines.append(f"| {n} | {mean(r['our_final'] for r in g):,.0f} | {mean(r['router_final'] for r in g):,.0f} | {mean(r['margin'] for r in g):+,.0f} | {sum(r['margin']>0 for r in g)} / {sum(r['margin']==0 for r in g)} / {sum(r['margin']<0 for r in g)} | {mean(r['day1_cash'] for r in g):,.0f} |")
    for a,b in (('shop-adaptive','shop-fixed'),(selection['name'],'growth-control')):
        m,lo,hi=paired_interval(panels['test'],a,b)
        lines += ['',f'{a} versus {b}: paired margin change {m:+,.0f}; descriptive 95% stratified seed-bootstrap interval [{lo:+,.0f}, {hi:+,.0f}]. Both seats are averaged within each seed before resampling. Only two seeds per shop are available; these intervals do not establish broad generalization.']
    lines += ['','## Performance by first shop (test mean margin)','','| First shop | Old growth | Fixed | Adaptive |','|---|---:|---:|---:|']
    for shop in SHOPS:
        values=[mean(r['margin'] for r in panels['test'] if r['name']==n and r['first_shop']==shop) for n in names[1:]]
        lines.append(f'| {shop} | '+' | '.join(f'{v:+,.0f}' for v in values)+' |')
    lines += ['','## Learned policy','','```json',json.dumps(learned,indent=2),'```','','## Validation ranking','','| Policy | Mean margin |','|---|---:|']
    for n in sorted(names,key=lambda n:-mean(r['margin'] for r in panels['validate'] if r['name']==n)):
        lines.append(f"| {n} | {mean(r['margin'] for r in panels['validate'] if r['name']==n):+,.0f} |")
    lines += ['','## Training grid','','| Configuration | Mean margin | Worst first-shop mean margin |','|---|---:|---:|']
    training=panels['train']
    for n in sorted({r['name'] for r in training},key=lambda n:-mean(r['margin'] for r in training if r['name']==n)):
        g=[r for r in training if r['name']==n]
        worst=min(mean(r['margin'] for r in g if r['first_shop']==s) for s in SHOPS)
        lines.append(f"| {n} | {mean(r['margin'] for r in g):+,.0f} | {worst:+,.0f} |")
    lines += ['','## Checks and limits','',
              f'All 544 games completed with valid intermediate statuses and exact continuation cash accounting. Verified {verified} selected file-entry actions with no observation mutation. Saved fixed/adaptive trajectories share the exact first 72 actions and resulting states with the router. Source hashes and scenarios are recorded in the manifests; the rebooted training run resumed from its 36 saved results.','',
              'This evaluates one opponent opening and one simple continuation. The continuation replaces cleared crop plots with wheat through day 25, buys no land/animals, and caps staff at 10 using the same workload rule on both farms. It can service different layouts with different efficiency. Only the first shop selects the opening configuration; adaptation to the second shop, fertilizer use, alternative day-0 allocations, and a wider parameter range are not searched here.','',
              'The earlier two-seed semantic screen was interrupted by an unsupported tomato-root case and superseded by this design. Its partial results were not used to fit or select these policies.','',
              f"[Selected opening moves](../results/fresh/shop_grid/test-{selection['name']}-89000-seat0/moves.md) · [Full replay](../results/fresh/shop_grid/test-{selection['name']}-89000-seat0/full_replay.json)",'',
              'Reproduce with `scripts/search_shop_grid.py --stage train`, then `--stage fit`, `--stage validate`, and `--stage test`. Each simulation stage resumes saved results and verifies scenario/source consistency. `--workers` controls local simulator processes. The local opening entry point requires sibling source files.','']
    (ROOT/'docs/shop_grid_search.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f'PASS: {verified} selected decisions and common-prefix checks.')
    for n in names:
        g=[r for r in panels['test'] if r['name']==n]
        print(n,'cash',mean(r['our_final'] for r in g),'margin',mean(r['margin'] for r in g),'wins',sum(r['margin']>0 for r in g))


if __name__=='__main__': main()
