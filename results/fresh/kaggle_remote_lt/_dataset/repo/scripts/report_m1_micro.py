"""Report complete paired small-change experiments without dropping failures."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/m1_minimal_20260922'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def mean(a):
    return statistics.mean(a) if a else None


def interval(seed_deltas):
    if not seed_deltas:
        return None
    rng=random.Random(22319)
    n=len(seed_deltas)
    values=sorted(sum(rng.choices(seed_deltas,k=n))/n for _ in range(10000))
    return [values[250],values[9749]]


def live(stage):
    folder=OUT/stage
    manifest=read(folder/'manifest.json')
    rows=[read(p) for p in (folder/'games').glob('*.json')]
    by=defaultdict(dict)
    for r in rows:
        assert r['own_sha256']==manifest['source_hashes'][r['agent']]
        assert r['opponent_sha256']==manifest['source_hashes'][r['opponent']]
        by[r['agent']][(r['seed'],r['seat'])]=r
    base=by['mgt_m1']
    result=dict(stage=stage,expected=manifest['expected_games'],present=len(rows),
        completed=sum(r['completed'] for r in rows),arms={})
    for arm in manifest['agents']:
        rr=list(by[arm].values())
        completed=[r for r in rr if r['completed']]
        pairs=[(r,base[k]) for k,r in by[arm].items() if r['completed'] and k in base and base[k]['completed']]
        deltas=[r['margin']-b['margin'] for r,b in pairs]
        cash=[r['cash']-b['cash'] for r,b in pairs]
        grouped=defaultdict(list)
        for r,b in pairs:
            grouped[r['seed']].append(r['margin']-b['margin'])
        paired_seeds=[mean(ds) for ds in grouped.values() if len(ds)==2]
        report=lambda r:r['agent_reports']['own'].get('_SHP_REPORT',{})
        last=lambda r:r['daily'][r['seat']][-1]
        item=dict(present=len(rr),completed=len(completed),paired_games=len(pairs),paired_seeds=len(paired_seeds),
            wins=sum(r['margin']>0 for r in completed),ties=sum(r['margin']==0 for r in completed),
            losses=sum(r['margin']<0 for r in completed),mean_margin=mean([r['margin'] for r in completed]),
            mean_margin_delta=mean(deltas),margin_delta_ci95=interval(paired_seeds),mean_cash_delta=mean(cash),
            mean_opponent_cash_delta=mean([r['opponent_cash']-b['opponent_cash'] for r,b in pairs]),
            better=sum(d>0 for d in deltas),worse=sum(d<0 for d in deltas),same=sum(d==0 for d in deltas),
            worst_delta=min(deltas,default=None),best_delta=max(deltas,default=None),
            worst_margin=min((r['margin'] for r in completed),default=None),
            mean_wages_delta=mean([last(r)['spend'].get('HIRE',0)-last(b)['spend'].get('HIRE',0) for r,b in pairs]),
            mean_wool_output_delta=mean([last(r)['physical'].get('produced:WOOL',0)-last(b)['physical'].get('produced:WOOL',0) for r,b in pairs]),
            games_adding_sheep=sum(report(r).get('sheep_bought',0)>0 for r in completed),
            sheep_bought=sum(report(r).get('sheep_bought',0) for r in completed),
            same_shop_paths=sum(r['shops']==b['shops'] for r,b in pairs),
            identical_action_streams=sum(r['action_sha256']==b['action_sha256'] for r,b in pairs),
            max_action_seconds=max((r['timing']['own']['max_seconds'] for r in completed),default=None),
            actions_over_1s=sum(r['timing']['own']['over_1s'] for r in completed),
            policy_errors=sum(report(r).get('errors',0)+r['agent_reports']['own'].get('_MGT_REPORT',{}).get('router_errors',0) for r in completed),
            runtime_errors=sum(not r['completed'] or bool(r.get('errors')) for r in rr),
            all_ledgers_verified=all(r.get('ledger_verified') for r in completed),
            per_game=[dict(seed=r['seed'],seat=r['seat'],margin=r['margin'],delta=r['margin']-b['margin'],
                cash_delta=r['cash']-b['cash'],wool_delta=last(r)['physical'].get('produced:WOOL',0)-last(b)['physical'].get('produced:WOOL',0),
                wage_delta=last(r)['spend'].get('HIRE',0)-last(b)['spend'].get('HIRE',0),
                extra_hand_days=report(r).get('hand_days',0)-report(b).get('hand_days',0)) for r,b in pairs])
        result['arms'][arm]=item
    (OUT/f'{stage}_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def historical():
    design=read(OUT/'design.json')
    rows=[read(p) for p in (OUT/'historical').glob('*.json')]
    base={r['episode']:r for r in rows if r['arm']=='mgt_m1' and r['completed']}
    result=dict(expected=len(design['arms'])*len(design['historical_diagnostic']),present=len(rows),
        completed=sum(r['completed'] for r in rows),arms={})
    for arm in design['arms']:
        rr=[r for r in rows if r['arm']==arm and r['completed']]
        ds=[r['margin']-base[r['episode']]['margin'] for r in rr]
        result['arms'][arm]=dict(games=len(rr),mean_margin_delta=mean(ds),better=sum(d>0 for d in ds),
            worse=sum(d<0 for d in ds),same=sum(d==0 for d in ds),
            action_changed_games=sum(r['action_changes']>0 for r in rr),
            games_adding_sheep=sum(r['overlay'].get('sheep_bought',0)>0 for r in rr),
            per_game=[dict(episode=r['episode'],delta=r['margin']-base[r['episode']]['margin'],
                cash_delta=r['cash']-base[r['episode']]['cash'],action_changes=r['action_changes']) for r in rr])
    (OUT/'historical_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def ladder():
    design=read(OUT/'ladder_full/design.json')
    meta={e['episode']:e for e in design['episodes']}
    rows=[read(p) for p in (OUT/'ladder_full/historical').glob('*.json')]
    assert all(r['source_sha256']==design['source_hash'] for r in rows)
    cases=[]
    for r in rows:
        if not r['completed']:
            continue
        e=meta[r['episode']]
        cases.append(dict(episode=r['episode'],seed=e.get('seed',r.get('seed')),rating=e['rating'],
            original_margin=e['margin'],margin=r['margin'],delta=r['margin']-e['margin'],
            cash_delta=r['cash']-e['ours'],action_changes=r['action_changes'],
            first_change=r['first_change'],reused=bool(r.get('reused_from'))))
    result=dict(expected=len(meta),present=len(rows),completed=len(cases),
                reused_diagnostic_rows=sum(r.get('reused_from') is not None for r in rows),groups={})
    groups={'All available matches':cases,'Original losses':[r for r in cases if r['original_margin']<0],
        'Original wins':[r for r in cases if r['original_margin']>0],
        'Original losses below 2500':[r for r in cases if r['original_margin']<0 and r['rating'] is not None and r['rating']<2500]}
    for label,rr in groups.items():
        result['groups'][label]=dict(games=len(rr),mean_margin_delta=mean([r['delta'] for r in rr]),
            mean_cash_delta=mean([r['cash_delta'] for r in rr]),better=sum(r['delta']>0 for r in rr),
            worse=sum(r['delta']<0 for r in rr),same=sum(r['delta']==0 for r in rr),
            action_changed_games=sum(r['action_changes']>0 for r in rr),
            wins_before=sum(r['original_margin']>0 for r in rr),wins_after=sum(r['margin']>0 for r in rr),
            wins_gained=sum(r['original_margin']<0 and r['margin']>0 for r in rr),
            wins_lost=sum(r['original_margin']>0 and r['margin']<0 for r in rr),
            worst_delta=min((r['delta'] for r in rr),default=None),best_delta=max((r['delta'] for r in rr),default=None))
    result['cases']=sorted(cases,key=lambda r:r['delta'])
    result['actions_over_1s']=sum(r.get('actions_over_1s',0) for r in rows)
    result['runtime_errors']=sum(not r['completed'] for r in rows)
    result['policy_errors']=sum(r.get('overlay',{}).get('errors',0)+r.get('router',{}).get('router_errors',0) for r in rows)
    (OUT/'ladder_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def final_report():
    development=live('development')
    confirmation=live('confirmation')
    history=ladder()
    diagnostics=historical()
    for r in (development,confirmation,history,diagnostics):
        assert r['present']==r['completed']==r['expected'], 'Incomplete experiment'
    choice=read(OUT/'selection.json')['candidate']
    c=confirmation['arms'][choice]
    b=confirmation['arms']['mgt_m1']
    h=history['groups']['All available matches']
    low=history['groups']['Original losses below 2500']
    fmt=lambda n:f'{n:+,.0f}'
    ci=c['margin_delta_ci95']
    text=f'''# Minimal mgt_m1 changes, 2026-09-22

Three isolated changes were built directly from unchanged mgt_m1. No new planner, tape router, crop system or execution controller was introduced. The selected experimental candidate is {choice}; the baseline file remains unchanged.

## Changes and development evidence

Six historical diagnostics (four identified failure cases and two wins) ran every arm and the baseline. All six baseline controls exactly reproduced recorded actions and both final cash values. Then all four arms played 12 fresh random seeds, both seats, against responsive V56: 96 full games.

| Independent change | Policy edit | Mean paired margin change | Better / worse / unchanged |
|---|---|---:|---:|
'''
    descriptions={
        'mgt_micro_single':'Minimum sheep deficit 2 → 1; existing profitability/cash checks retained',
        'mgt_micro_yarn18':'D18 Yarn Store adds two to the target; D19 purchase cutoff retained',
        'mgt_micro_wool_upturn':'Allow the existing three-day wool forecast above today’s price when a Yarn Store is open; retain value discount and wage checks',
    }
    for arm,desc in descriptions.items():
        r=development['arms'][arm]
        text+=f"| {arm} | {desc} | {fmt(r['mean_margin_delta'])} | {r['better']} / {r['worse']} / {r['same']} |\n"
    text+='''
The first two changes did not change any actions in the six diagnostics or the 24 development games per arm. Their inactivity is evidence that target eligibility alone did not unlock an investment, not evidence that an executed purchase was unprofitable. For example, allowing one sheep in episode 111743130 reached the evaluator but produced modeled profits of −2,893 and −2,298 on D18/D19. Raising the D18 target in episode 111678108 produced modeled profits of +51 and +705, still below the unchanged 3,000 requirement.

The wool forecast change replaces one return statement with six lines. m1 previously used the smaller of today’s quote and its existing three-day forecast, so a predicted price recovery could never justify earlier feed/care. The candidate removes that upper bound only for wool with an already revealed Yarn Store. It retains the existing sheep purchase and staffing rules and the existing forecast model. This also affects existing-sheep payout/adoption valuation, not just CARE commands. The original 20% value discount and 1.5-times marginal-wage check stay active.

The diagnostic change gained 611 margin in episode 111678108: wool revenue +870, feed purchases +203 and wages +144, alongside smaller wheat effects. It lost 494 in 111261836: two additional feeds, no net additional care or hand-days, and weaker realized revenue. Both cases were retained. Development selection used the largest positive mean paired margin with positive own cash and no errors/time overruns; it selected the wool forecast change without combining edits.

An exact physical-work trace explains the latter regression. Extra feeding on tile (3,4) kept a sheep alive across the donor's D26 DIG/PLANT-WHEAT conversion, so that crop work could not execute. The added stop also delayed an existing worker's route: the sheep at (6,2) missed its D26 harvest and three wool units were lost when it escaped. Wool generated rose 67 → 69, but harvested/sold fell 67 → 66. This is a concrete retirement/replacement and route-capacity interaction, not a reason to abandon the small-change approach. Trace artifacts are in case_traces/; scripts/trace_m1_micro_case.py reproduces both arms through the official engine.

## Untouched live confirmation

'''
    text+=f'''The same frozen candidate and unchanged m1 each played all 24 reserved confirmation seeds, both seats, against live V56: 96 additional full-game executions. These seeds were frozen before development outcomes. They are separate from the project's untouched 3000-Elo qualification panel.

| Metric | Confirmation result |
|---|---:|
| Mean paired margin change | {fmt(c['mean_margin_delta'])} |
| Seed-bootstrap 95% interval | {fmt(ci[0])} to {fmt(ci[1])} |
| Mean own-cash change | {fmt(c['mean_cash_delta'])} |
| Better / worse / unchanged games | {c['better']} / {c['worse']} / {c['same']} |
| Wins vs V56, baseline → candidate | {b['wins']}/48 → {c['wins']}/48 |
| Worst paired change | {fmt(c['worst_delta'])} |
| Best paired change | {fmt(c['best_delta'])} |
| Mean wool-output change | {c['mean_wool_output_delta']:+.2f} units |
| Mean wage change | {fmt(c['mean_wages_delta'])} |
| Matching shop paths | {c['same_shop_paths']}/48 |
| Runtime / internal policy errors | {c['runtime_errors']} / {c['policy_errors']} |
| Own actions above 1 second | {c['actions_over_1s']} |

The interval resamples whole seeds, averaging both seats within each seed. Both seats are not independent worlds. Natural engine RNG is preserved; shop draws can in general diverge through policy-dependent weed draws. All completed live games have 719 actions, 720 states, DONE statuses and both cash ledgers reconciled. Runtime timings are measured offline; they are not an online submission certificate.

## Historical regression check

The frozen selected candidate was also evaluated on every locally available game of submission 56395605: {h['games']} games, including all 89 audited losses and 109 wins. This is 198 of the 305 known completed public matches: all losses but only 109 of 216 wins. Its mean reflects that availability mix and is not an unbiased estimate of ladder gain. Six already executed diagnostic candidate rows were reused with explicit source provenance. Opponent actions and shop schedules are recorded; the comparison is to original m1 rewards, not a responsive opponent or an independent qualification.

| Cohort | Mean margin change | Better / worse / unchanged | Wins gained / lost |
|---|---:|---:|---:|
'''
    for label,r in history['groups'].items():
        text+=f"| {label} ({r['games']}) | {fmt(r['mean_margin_delta'])} | {r['better']} / {r['worse']} / {r['same']} | {r['wins_gained']} / {r['wins_lost']} |\n"
    text+=f'''
The worst historical change is {fmt(h['worst_delta'])}; the best is {fmt(h['best_delta'])}. Against opponents below 2500, the 58 original losses have mean change {fmt(low['mean_margin_delta'])}. Complete per-match results, including regressions, are retained in ladder_summary.json. This losing-cohort mean should not be presented as an expected ladder gain.

## Interpretation

'''
    if ci[0]>0 and c['mean_cash_delta']>0 and not c['runtime_errors'] and not c['policy_errors']:
        text+='The small forecast change has positive held-out evidence for a modest cash-margin improvement against V56. Its scope and measured benefit remain small; it does not resolve the larger strawberry/herd-capacity gap or establish a rating gain. '
    else:
        text+='The small forecast change remains an experimental candidate: the confirmation does not establish a reliable positive margin improvement. The individual gains and regressions identify a valuation tradeoff; they do not invalidate incremental improvements to m1. '
    text+='The baseline agent was not edited or submitted. The two inactive purchase changes were not bundled into the selected candidate. A specific next experiment is a small guard against preserving an animal when the tape explicitly repurposes its tile, evaluated separately before combination.\n\n'
    text+=f'''Panel full-game executions: 24 initial historical diagnostics + 96 development + 96 confirmation + {h['games']-history['reused_diagnostic_rows']} additional historical checks = {24+96+96+h['games']-history['reused_diagnostic_rows']}. Reused diagnostic rows are not additional executions. Two additional full-game trace reruns diagnose episode 111261836; these are not independent evidence or additional worlds.

Artifacts: [candidate](../agents/{choice}.py), [exact small diff](../results/fresh/m1_minimal_20260922/{choice}.diff), [frozen design](../results/fresh/m1_minimal_20260922/design.json), [confirmation summary](../results/fresh/m1_minimal_20260922/confirmation_summary.json), [historical summary](../results/fresh/m1_minimal_20260922/ladder_summary.json). Baseline SHA-256 remains 1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470. Candidate SHA-256 is {read(OUT/'design.json')['source_hashes'][choice]}.

Reproduction: scripts/experiment_m1_micro.py (freeze, historical, development, confirmation); scripts/evaluate_m1_micro_ladder.py; scripts/report_m1_micro.py final. The bundled Python 3.12 runtime used the existing project kaggle-environments 1.32.7 packages. No dependency changes were made.
'''
    path=ROOT/'docs/mgt_m1_minimal_experiments.md'
    path.write_text(text,encoding='utf8')
    return dict(report=str(path),candidate=choice,confirmation=c,historical=h)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['historical','development','confirmation','select','ladder','final'])
    args=parser.parse_args()
    if args.stage=='final':
        result=final_report()
        result['confirmation'].pop('per_game',None)
        print(json.dumps(result,indent=2));return
    if args.stage=='ladder':
        result=ladder()
        result.pop('cases',None)
        print(json.dumps(result,indent=2));return
    report=historical() if args.stage=='historical' else live('development' if args.stage=='select' else args.stage)
    if args.stage=='select':
        assert report['present']==report['completed']==report['expected']
        eligible=[(v['mean_margin_delta'],a) for a,v in report['arms'].items()
            if a!='mgt_m1' and v['paired_games']==24 and v['mean_margin_delta']>0 and v['mean_cash_delta']>0
            and not v['runtime_errors'] and not v['policy_errors'] and not v['actions_over_1s']]
        choice=max(eligible,default=(0,None))
        selection=dict(candidate=choice[1],development_mean_margin_delta=choice[0],
                       selected_utc=datetime.now(timezone.utc).isoformat(),rule=read(OUT/'design.json')['selection'])
        dest=OUT/'selection.json'
        if dest.exists():
            assert read(dest)['candidate']==selection['candidate']
        else:
            dest.write_text(json.dumps(selection,indent=2),encoding='utf8')
        print(json.dumps(selection,indent=2))
    for v in report['arms'].values():
        v.pop('per_game',None)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
