"""Frozen, paired screen of a larger early sheep expansion on mgt_m1 tapes.

The replay uses the official engine and both players' real recorded shops. Our
candidate agent runs live; the opponent retains its recorded actions. This is
an intervention screen, not a responsive-opponent qualification.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import gzip
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from experiment_m1_micro import historical_job
import experiment_m1_micro as micro

OUT = ROOT / 'results/fresh/larger_shift_20260923/sheep'
ARMS = ('mgt_m1', 'sheep_market_credit', 'sheep_early_fields', 'sheep_early_carrot')
BASE_SHA = '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf8')


def freeze():
    path = OUT / 'design.json'
    if path.exists():
        return read(path)
    source = (ROOT / 'agents/mgt_m1.py').read_bytes()
    assert sha256(source).hexdigest() == BASE_SHA
    credit_before = b'    xa = xb = x0\r\n'
    credit_after = b'    theirs = supply - mine\r\n    xa = xb = x0\r\n'
    sale_a = b'        rev_a += mine * pa'
    sale_b = b'        rev_b += (mine + new) * pb'
    assert source.count(credit_before) == source.count(sale_a) == source.count(sale_b) == 1
    credit = source.replace(credit_before, credit_after).replace(
        sale_a, b'        rev_a += (mine - theirs) * pa').replace(
        sale_b, b'        rev_b += (mine + new - theirs) * pb')
    config_before = (b"_SHP_CFG = {'enabled': True, 'max_sheep': 16, 'max_hands': 4, "
                     b"'min_deficit': 2, 'min_profit': 3000, 'first_day': 6, "
                     b"'last_day': 19, 'latest_hour': 8, 'cash_margin': 2000, "
                     b"'labour_model': 'count', 'hire_guard': 1}")
    config_after = (b"_SHP_CFG = {'enabled': True, 'max_sheep': 20, 'max_hands': 4, "
                    b"'min_deficit': 1, 'min_profit': 0, 'first_day': 6, "
                    b"'last_day': 12, 'latest_hour': 8, 'cash_margin': 2000, "
                    b"'labour_model': 'count', 'hire_guard': 1, 'scarce_extra': 4}")
    assert credit.count(config_before) == 1
    early = credit.replace(config_before, config_after)
    guard = b"use <= {'WHEAT', 'CARROT', 'TEND'}"
    assert early.count(guard) == 2
    # A carrot-only pasture avoids the tape's wheat harvest/feed chains, even
    # when a tile is currently empty but scheduled to grow wheat later.
    carrot = early.replace(config_after, config_after[:-1] + b", 'avoid_wheat_tiles': True}").replace(
        guard, b"use <= ({'CARROT', 'TEND'} if _SHP_CFG.get('avoid_wheat_tiles') else {'WHEAT', 'CARROT', 'TEND'})")
    carrot = carrot.replace(
        b"cell.get('crop') in ('WHEAT', 'CARROT')",
        b"(cell.get('crop') == 'CARROT' or (cell.get('crop') == 'WHEAT' and not _SHP_CFG.get('avoid_wheat_tiles')))")
    candidates = dict(zip(ARMS, (source, credit, early, carrot)))
    (OUT / 'sources').mkdir(parents=True, exist_ok=True)
    hashes = {}
    for arm, body in candidates.items():
        (OUT / 'sources' / f'{arm}.py').write_bytes(body)
        hashes[arm] = sha256(body).hexdigest()

    audit = read(ROOT / 'results/fresh/all_umg_m1/summary.json')
    margins = {e['episode']: e['margin'] for e in audit['episodes']}
    available = []
    for file in (ROOT / 'data/ladder_panel/56395605').glob('*.json.gz'):
        episode = int(file.name.split('.')[0])
        if episode not in margins:
            continue
        with gzip.open(file, 'rt', encoding='utf8') as stream:
            shops = json.load(stream)['shops']
        available.append((episode, margins[episode], shops))
    high_loss = sorted(e for e, m, s in available if m < 0 and s[12].count('YARN_STORE') >= 2)
    high_win = sorted(e for e, m, s in available if m > 0 and s[12].count('YARN_STORE') >= 2)
    no_yarn = sorted(e for e, m, s in available if s[-1].count('YARN_STORE') == 0)
    assert len(high_loss) == 14 and len(high_win) == 14
    rng = random.Random(2026092304)
    rng.shuffle(high_loss); rng.shuffle(high_win); rng.shuffle(no_yarn)
    development = sorted(high_loss[:7] + high_win[:7] + no_yarn[:4])
    confirmation = sorted(high_loss[7:] + high_win[7:])
    design = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                  arms=ARMS, source_hashes=hashes,
                  development=development, confirmation=confirmation,
                  high_yarn='At least two Yarn Stores visible by D12. Seven losses and seven wins in each split.',
                  negative_controls=sorted(no_yarn[:4]),
                  baseline_sha256=BASE_SHA,
                  selection='Compare paired full-game competitive margin on development. Promote at most one early expansion to untouched confirmation only if its mean margin and own cash improve and at least half of high-Yarn games improve. The market-credit-only arm diagnoses activation.',
                  caveat='Recorded opponent actions and forced shops are fixed. The candidate chooses all its own actions live. A responsive opponent could react differently; follow any promising result with live seeds.')
    write(path, design)
    return design


def job(arm, episode, design):
    micro.OUT = OUT
    return historical_job((arm, episode, design))


def analyze(design, stage):
    episodes = design[stage]
    cases = {}
    for episode in episodes:
        cases[episode] = {a: read(OUT / 'historical' / f'{a}-{episode}.json') for a in ARMS
                          if (OUT / 'historical' / f'{a}-{episode}.json').exists()}
    valid = [e for e, rows in cases.items() if len(rows) == len(ARMS) and all(r['completed'] for r in rows.values())]
    report = dict(stage=stage, total=len(episodes), completed=len(valid), errors=[
        dict(episode=e, arm=a, error=r.get('error')) for e, rows in cases.items()
        for a, r in rows.items() if not r['completed']])
    if len(valid) == len(episodes):
        arms = {}
        for a in ARMS:
            diffs = [cases[e][a]['margin']-cases[e]['mgt_m1']['margin'] for e in valid]
            own = [cases[e][a]['cash']-cases[e]['mgt_m1']['cash'] for e in valid]
            opp = [cases[e][a]['opponent_cash']-cases[e]['mgt_m1']['opponent_cash'] for e in valid]
            opportunity = [e for e in valid if e not in design['negative_controls']]
            acts = [cases[e][a]['overlay'].get('sheep_bought', 0) for e in valid]
            arms[a] = dict(mean_margin=sum(diffs)/len(diffs), mean_own=sum(own)/len(own),
                           mean_opponent=sum(opp)/len(opp), better=sum(x>0 for x in diffs),
                           worse=sum(x<0 for x in diffs), unchanged=sum(x==0 for x in diffs),
                           high_yarn_better=sum(cases[e][a]['margin']>cases[e]['mgt_m1']['margin'] for e in opportunity),
                           high_yarn_total=len(opportunity), sheep_bought=sum(acts),
                           cases=[dict(episode=e, margin_delta=round(diffs[i], 2),
                                       own_delta=round(own[i], 2), opponent_delta=round(opp[i], 2),
                                       bought=acts[i], first_change=cases[e][a]['first_change'])
                                  for i,e in enumerate(valid)])
        report['arms'] = arms
    write(OUT / f'{stage}_summary.json', report)
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['freeze', 'development', 'confirmation', 'stress', 'analyze'])
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--candidate')
    args = parser.parse_args()
    design = freeze()
    if args.stage == 'freeze':
        print(json.dumps(design, indent=2)); return
    if args.stage == 'analyze':
        print(json.dumps({s: analyze(design,s) for s in ('development','confirmation')}, indent=2)); return
    if args.stage == 'stress':
        arms = ('mgt_m1', 'sheep_early_fields')
        jobs = [(a,e,design) for e in design['confirmation'] for a in arms]
        with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
            for future in as_completed([pool.submit(job,*j) for j in jobs]):
                print(json.dumps(future.result()), flush=True)
        cases=[]
        for e in design['confirmation']:
            base=read(OUT/'historical'/f'mgt_m1-{e}.json')
            cand=read(OUT/'historical'/f'sheep_early_fields-{e}.json')
            assert base['completed'] and cand['completed']
            cases.append(dict(episode=e,margin_delta=cand['margin']-base['margin'],
                              own_delta=cand['cash']-base['cash'],
                              opponent_delta=cand['opponent_cash']-base['opponent_cash'],
                              bought_delta=cand['overlay'].get('sheep_bought',0)-base['overlay'].get('sheep_bought',0)))
        n=len(cases)
        report=dict(label='Post-screen stress test, not a promotion confirmation',n=n,
                    mean_margin=sum(c['margin_delta'] for c in cases)/n,
                    mean_own=sum(c['own_delta'] for c in cases)/n,
                    mean_opponent=sum(c['opponent_delta'] for c in cases)/n,
                    better=sum(c['margin_delta']>0 for c in cases),
                    worse=sum(c['margin_delta']<0 for c in cases),
                    extra_sheep=sum(c['bought_delta'] for c in cases),cases=cases)
        write(OUT/'stress_summary.json',report)
        dev=read(OUT/'development_summary.json')['arms']['sheep_early_fields']['cases']
        high_dev=[x for x in dev if x['episode'] not in design['negative_controls']]
        combined=high_dev+cases
        rng=random.Random(9001)
        bootstrap=sorted(sum(rng.choice(combined)['margin_delta'] for _ in combined)/len(combined)
                         for _ in range(10000))
        total=dict(label='All frozen high-Yarn games; stress was run after development rejected the candidate',
                   n=len(combined),mean_margin=sum(x['margin_delta'] for x in combined)/len(combined),
                   mean_own=sum(x['own_delta'] for x in combined)/len(combined),
                   mean_opponent=sum(x['opponent_delta'] for x in combined)/len(combined),
                   better=sum(x['margin_delta']>0 for x in combined),
                   worse=sum(x['margin_delta']<0 for x in combined),
                   unchanged=sum(x['margin_delta']==0 for x in combined),
                   bootstrap_95=[bootstrap[250],bootstrap[9750]],cases=combined)
        write(OUT/'combined_summary.json',total)
        print(json.dumps(report,indent=2))
        return
    arms = ARMS if args.stage == 'development' else ('mgt_m1', args.candidate)
    if args.stage == 'confirmation':
        selection = read(OUT / 'selection.json')
        assert args.candidate == selection['candidate'] and args.candidate in ARMS[2:]
    jobs = [(a,e,design) for e in design[args.stage] for a in arms]
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(job,*j) for j in jobs]):
            print(json.dumps(future.result()), flush=True)
    print(json.dumps(analyze(design,args.stage),indent=2))


if __name__ == '__main__':
    main()
