"""Freeze a simple public-state decision rule, then evaluate held-out triples."""
import json,sys
from collections import defaultdict
from statistics import mean
from hashlib import sha256
from research_demand_investment import OUT,ROOT,SELECTED,jobs

def groups(panel):
    out=defaultdict(dict)
    for job in jobs(panel):
        r=json.loads((OUT/'games'/('-'.join(map(str,job))+'.json')).read_text())
        out[(r['seed'],r['seat'],r['opponent'])][r['choice']]=r
    for g in out.values():
        assert len(g)==3
        assert all(r['decision']['features']==g['SHEEP']['decision']['features'] and r['shops']==g['SHEEP']['shops'] for r in g.values())
    return list(out.values())

def choose(rule,g):
    return rule['left'] if rule['feature'] is None or g['SHEEP']['decision']['features'][rule['feature']]<=rule['threshold'] else rule['right']

def fit():
    gs=groups('train');choices=('SHEEP','COW','SKIP')
    candidates=[dict(feature=None,threshold=None,left=c,right=c) for c in choices]
    # Only one split; require at least two distinct seed groups in either leaf.
    for feature in ('MILK_demand','WOOL_demand','demand_balance','price_balance'):
        values=sorted({g['SHEEP']['decision']['features'][feature] for g in gs})
        for lo,hi in zip(values,values[1:]):
            threshold=(lo+hi)/2
            sides=[[g for g in gs if (g['SHEEP']['decision']['features'][feature]<=threshold)==side] for side in (True,False)]
            if min(len({g['SHEEP']['seed'] for g in side}) for side in sides)<2:continue
            best=[max(choices,key=lambda c:mean(g[c]['margin'] for g in side)) for side in sides]
            candidates.append(dict(feature=feature,threshold=threshold,left=best[0],right=best[1]))
    best=max(candidates,key=lambda rule:mean(g[choose(rule,g)]['margin'] for g in gs))
    payload={'rule':best,'training_cases':len(gs),'candidates':len(candidates),
      'selection':'One decision stump maximizing mean final cash margin; only public turn-265 state. First candidate wins ties.',
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in (SELECTED,ROOT/'scripts/research_demand_investment.py',ROOT/'scripts/report_demand_investment.py')},
      'heldout_seeds':list(range(130000,130008)),'stress_seeds':list(range(131000,131008)),
      'promotion_gate':'Require positive mean margin gain over sheep on each held-out opponent, and positive gain on at least 6/8 held-out seed means. Otherwise retain current selected agent. Stress results diagnostic only.'}
    path=OUT/'frozen_rule.json'
    if path.exists():assert json.loads(path.read_text())==payload
    else:path.write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))

def summary(gs,rule):
    result={}
    for policy in ('SHEEP','COW','SKIP','learned','oracle'):
        picks=[g[choose(rule,g) if policy=='learned' else max(g,key=lambda c:g[c]['margin']) if policy=='oracle' else policy] for g in gs]
        gains=[r['margin']-g['SHEEP']['margin'] for r,g in zip(picks,gs)]
        profits=[r['cash']-g['SKIP']['cash'] for r,g in zip(picks,gs)]
        result[policy]={'cases':len(gs),'mean_cash':mean(r['cash'] for r in picks),'margin_gain':mean(gains),'cash_gain':mean(r['cash']-g['SHEEP']['cash'] for r,g in zip(picks,gs)),
          'worst_margin_gain':min(gains),'positive_cases':sum(x>0 for x in gains),'negative_cases':sum(x<0 for x in gains),
          'cash_over_skip':mean(profits),'lower_quartile_cash_over_skip':mean(sorted(profits)[:max(1,len(gs)//4)]),
          'choices':{c:sum(r['choice']==c for r in picks) for c in ('SHEEP','COW','SKIP')},
          'seed_margin_gains':{s:mean(x for x,g in zip(gains,gs) if g['SHEEP']['seed']==s) for s in sorted({g['SHEEP']['seed'] for g in gs})}}
    return result

def report():
    rule=json.loads((OUT/'frozen_rule.json').read_text())['rule']
    panels={p:groups(p) for p in ('train','test','stress')}
    panels.update({f'test_{o}':[g for g in panels['test'] if g['SHEEP']['opponent']==o] for o in ('selected','sixday')})
    results={p:summary(gs,rule) for p,gs in panels.items()}
    gate=all(results['test_'+o]['learned']['margin_gain']>0 for o in ('selected','sixday')) and sum(x>0 for x in results['test']['learned']['seed_margin_gains'].values())>=6
    results['promotion_gate_passed']=gate
    (OUT/'summary.json').write_text(json.dumps(results,indent=2))
    lines=['# Demand-aware pasture investment study','',
      '## Scope','',
      'Change only the last planned pasture purchase at turn 265 (day 11): sheep, cow, or skip. Preserve the opening, routes, hiring and static market-order policy. A cow follows the same service route; skipping suppresses that animal’s pickup, placement, feed and care. No labor savings or terminal livestock salvage are assumed. Results use actual full-game cash, including feed, price effects on existing herds, capacity and subsequent router choices.','',
      '## Frozen decision rule','',f'`{json.dumps(rule)}`','',
      'A single split was fitted on eight development seeds covering all first shops, both seats against the selected agent. Only currently revealed demand and prices can enter the rule. It was frozen before the held-out runs. This is an empirical investment policy, not a calibrated price forecaster.','',
      '## Results','',
      '| Panel | Choice | Cases | Cash gain vs sheep | Margin gain vs sheep | Worst margin change | Cash gain vs skip |','|---|---|---:|---:|---:|---:|---:|']
    for panel,stats in results.items():
        if not isinstance(stats,dict):continue
        for policy,s in stats.items():lines.append(f"| {panel} | {policy} | {s['cases']} | {s['cash_gain']:+.1f} | {s['margin_gain']:+.1f} | {s['worst_margin_gain']:+.0f} | {s['cash_over_skip']:+.1f} |")
    lines+=['','The oracle chooses with hindsight and is only an upper bound for this one decision. Cases across choices, seats and opponents share seeds; they are not independent samples.','',
      '## Uncertainty and checks','',
      '- All variants within a seed use identical hidden shop schedules. Training covers all eight first shops; held-out schedules use independent uniform draws with replacement. Stress panels deliberately exclude wool demand, milk demand, both, or repeat a single shop. Stress frequencies are not natural probabilities.',
      '- At turn 265, three shops are revealed and five draws remain. If yarn has not appeared, its chance of remaining absent is (7/8)^5 = 51.3%; if no milk shop has appeared, milk-shop absence is (5/8)^5 = 9.5%. Existing shops continue consuming; town-center demand remains.',
      '- Both seats and two held-out opponents are tested. Every sheep control must match the current selected agent action-for-action. Every non-skip alternative must reach its pickup and placement with an animal in inventory. Both final cash ledgers must reconcile and all 720 states must complete.',
      '- Shop draws are controlled because engine weed generation and shop selection share random state. Farm-dependent weeds still follow the engine. Only one investment and a small seed panel are studied; this does not establish an optimal herd policy.',
      '- Future information is used only to score counterfactual outcomes, never as a decision input. The held-out oracle is not deployable.',
      '', '## Decision','',f"Frozen promotion gate: {'PASS; further packaging and confirmation required before promotion' if gate else 'FAIL; retain the current selected agent'}. No Kaggle submission was made by this study.",
      '', '## Reproduction','',
      'Run `scripts/research_demand_investment.py train`, then `scripts/report_demand_investment.py fit`; run the `test` and `stress` panels, then `scripts/report_demand_investment.py report`. Data and frozen rule: `results/fresh/demand_investment/`.']
    (ROOT/'docs/demand_investment.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':fit() if sys.argv[1]=='fit' else report()
