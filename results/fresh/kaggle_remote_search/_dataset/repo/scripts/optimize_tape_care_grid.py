"""Exact-engine finite search over the already registered single-tape care edit.

This is a discovery-world sensitivity check, not an online policy evaluation.
Each arm recompiles the existing small variant with a subset of its eligible
days. The full mgt agent reacts to the changed state; the recorded opponent's
commands and actual shop sequence remain fixed.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import ast
import gzip
import io
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/store_mismatch_shift_20260923/care_grid'
CASE = 111678108
ELIGIBLE = (17, 19, 21)


def run_arm(days, game, source, spec, line):
    from kaggle_environments.agent import get_last_callable
    from research_labour_profit import Simulator, engine, economic

    arm = '-'.join(map(str, days)) or 'none'
    path = OUT / f'agent-{arm}.py'
    edited = dict(spec)
    edited['days'] = {d: v for d, v in spec['days'].items() if int(d) in days}
    path.write_text(source.replace(line, '_TV_SPEC = ' + repr(edited), 1), encoding='utf8')
    entry = get_last_callable(path.read_text(encoding='utf8'), path=str(path))
    assert entry.__name__ == 'mgt_kaggle_entry'
    seat = game['seat']
    actions = [None, None]
    actions[seat], actions[1-seat] = game['our_actions'], game['opp_actions']
    changed = []
    with Simulator(game) as sim:
        native = engine().interpreter

        def live(state, env):
            action = entry(deepcopy(state[seat].observation), None)
            if action != game['our_actions'][sim.t]:
                changed.append(sim.t)
            state[seat].action = action
            return native(state, env)

        engine().interpreter = live
        try:
            result = sim.run(sim.initial, 0, 719, actions, capture=True)
        finally:
            engine().interpreter = native
        ledger = [economic(result['events'], s) for s in (seat, 1-seat)]
        for s, row in zip((seat, 1-seat), ledger):
            assert 3000 + sum(row['revenue'].values()) - sum(row['spend'].values()) == result['money'][s]
        harvested = Counter()
        for work in result['work']:
            if work['seat'] == seat and work['cmd'][0] == 'HARVEST':
                harvested.update({k: v for k, v in work['delta'].items() if v > 0})
        report = entry.__globals__.get('_TV_REPORT', {})
        applied = [d['day'] for d in report.get('decisions', []) if d['reason'] == 'applied']
        return dict(days=list(days), arm=arm, source_sha256=sha256(path.read_bytes()).hexdigest(),
                    cash=result['money'][seat], opponent_cash=result['money'][1-seat],
                    margin=result['money'][seat]-result['money'][1-seat],
                    ledgers=ledger, harvested=dict(harvested), changed_steps=changed,
                    applied_days=applied, decisions=report.get('decisions', []),
                    exact_engine=True)


def main():
    source = (ROOT / 'agents/mgt_tape_care_v1.py').read_text(encoding='utf8')
    m = re.search(r'(?m)^_TV_SPEC = (.+)$', source)
    assert m
    line = m.group(0)
    spec = ast.literal_eval(m.group(1))
    assert all(str(d) in spec['days'] for d in ELIGIBLE)
    with gzip.open(ROOT / f'data/ladder_panel/56395605/{CASE}.json.gz', 'rt', encoding='utf8') as f:
        game = json.load(f)
    OUT.mkdir(parents=True, exist_ok=True)
    rows=[]
    baseline = json.loads((ROOT/f'results/fresh/tape_variants_20260922/historical/mgt_m1-{CASE}.json').read_text())
    for n in range(len(ELIGIBLE)+1):
        for days in itertools.combinations(ELIGIBLE, n):
            target = OUT / f'arm-{"-".join(map(str,days)) or "none"}.json'
            if target.exists():
                row=json.loads(target.read_text(encoding='utf8'))
            else:
                buf=io.StringIO()
                with redirect_stdout(buf), redirect_stderr(buf):
                    row=run_arm(days,game,source,spec,line)
                target.write_text(json.dumps(row,indent=2),encoding='utf8')
                (OUT/f'arm-{row["arm"]}.log').write_text(buf.getvalue(),encoding='utf8')
            if not days:
                assert row['cash']==baseline['cash'] and row['opponent_cash']==baseline['opponent_cash']
            if len(days)==len(ELIGIBLE):
                candidate=json.loads((ROOT/f'results/fresh/tape_variants_20260922/historical/mgt_tape_care_v1-{CASE}.json').read_text())
                assert row['cash']==candidate['cash'] and row['opponent_cash']==candidate['opponent_cash']
            rows.append(row)
            print(json.dumps({k:row[k] for k in ('arm','cash','opponent_cash','margin','applied_days')}),flush=True)
    base=rows[0]
    for row in rows:
        row['margin_delta']=row['margin']-base['margin']
        row['cash_delta']=row['cash']-base['cash']
        row['opponent_cash_delta']=row['opponent_cash']-base['opponent_cash']
        row['harvest_delta']={p:row['harvested'].get(p,0)-base['harvested'].get(p,0) for p in ('MILK','WOOL')}
    winner=max(rows,key=lambda x:x['margin'])
    result=dict(episode=CASE,seed=game['seed'],base_source_sha256=sha256(source.encode()).hexdigest(),
                tested_days=list(ELIGIBLE),arms=rows,
                best_tested_arm=winner['arm'],best_tested_margin_delta=winner['margin_delta'],
                meaning='Exhaustive among eight subsets of this registered three-day care edit, in one discovery world with fixed recorded opponent commands. No claim of general or globally optimal production.')
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    registry=dict(id='109740300-milk-care-to-wool-d17-diagnostic',
                  base_tape_episode=109740300,
                  parent_variant='109740300-milk-care-to-wool-v1',
                  status='diagnostic_only',
                  enabled_days=[17],
                  source=str((OUT/'agent-17.py').relative_to(ROOT)),
                  source_sha256=next(x['source_sha256'] for x in rows if x['arm']=='17'),
                  discovery_episode=CASE,discovery_seed=game['seed'],
                  full_game_margin_delta=next(x['margin_delta'] for x in rows if x['arm']=='17'),
                  full_game_harvest_delta=next(x['harvest_delta'] for x in rows if x['arm']=='17'),
                  meaning='Best of eight eligible-day subsets in one discovery world under fixed recorded opponent commands; no independent or responsive-opponent confirmation.')
    registry_path=ROOT/'data/tape_variants'/f'{registry["id"]}.json'
    registry_path.write_text(json.dumps(registry,indent=2),encoding='utf8')
    print('best',winner['arm'],winner['margin_delta'],winner['harvest_delta'])


if __name__ == '__main__':
    main()
