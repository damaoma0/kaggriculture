"""Experimental live mgt_m1 wage-scheduling ablation; no submission changes.

Generate a causal 48h plan by rolling the current policy forward with a PASS
rival, held shops and no new weeds. Restore policy state before actual play.
Execute only an accepted first day; the second day is a continuation check.
The unchanged live parent observes every real turn to maintain its state.
"""
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr
from collections import Counter
from hashlib import sha256
from pathlib import Path
import argparse
import gzip
import io
import json
import random
import statistics as st
import time

import test_labour_selfplay as S
R = S.R
ROOT = R.ROOT
MUTABLE = ('_MGT_REPORT', '_MGT_HISTORY', '_MGT_IGNORE', '_SHP_STATES', '_SHP_REPORT', '_SHP_NUM')


class Scheduled:
    def __init__(self, entry, enabled):
        self.entry, self.enabled = entry, enabled
        self.pending, self.decisions = {}, []
        self.times = []

    def plan(self, obs):
        g = self.entry.__globals__
        chassis = g['_MGT_IMPL'].chassis
        saved = {k: deepcopy(g[k]) for k in MUTABLE}
        players, diagnostics = deepcopy(chassis.players), deepcopy(chassis.diagnostics)
        sim, state = S.project_input(obs)
        seat, start = obs.player, obs.step
        pair = [[deepcopy(R.PASS) for _ in range(720)] for _ in range(2)]
        try:
            with sim:
                for t in range(start, start + 48):
                    pair[seat][t] = self.entry(deepcopy(state[seat].observation))
                    state = sim.run(state, t, t + 1, pair)['state']
        finally:
            for k, value in saved.items():
                g[k].clear()
                if isinstance(value, list):
                    g[k].extend(value)
                else:
                    g[k].update(value)
            chassis.players.clear()
            chassis.players.update(players)
            chassis.diagnostics.clear()
            chassis.diagnostics.update(diagnostics)
        assert chassis.players == players and all(g[k] == v for k, v in saved.items())
        return pair[seat][start:start + 48]

    def __call__(self, obs):
        started = time.perf_counter()
        t = obs.step
        if self.enabled and t % 48 == 24 and 72 <= t <= 648:
            plan = self.plan(obs)
            actions, choice = S.choose(deepcopy(obs), plan, 'wage', 80)
            changed = actions[:24] != plan[:24]
            choice['executed_first_day_change'] = changed
            if changed:
                self.pending = {t + i: a for i, a in enumerate(actions[:24])}
            self.decisions.append(choice)
        original = self.entry(obs)
        result = self.pending.pop(t, original)
        self.times.append(time.perf_counter() - started)
        return result


def run(job):
    seed, treatment, folder = job
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments import make
    from evaluate_boards import Ledger
    E = R.engine()
    path = ROOT / 'agents/mgt_m1.py'
    source = path.read_text(encoding='utf-8')
    players = [Scheduled(get_last_callable(source, path=str(path)), treatment == i) for i in range(2)]
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        env.reset()
    actions = [[], []]
    # Direct framework stepping allows measuring the research scheduler without
    # terminating it at the competition's 1s action limit. Report violations.
    ledger = Ledger(E)
    for t in range(719):
        for i in range(2):
            env.state[i].observation.step = t
        pair = [p(deepcopy(env.state[i].observation)) for i, p in enumerate(players)]
        for i in range(2):
            actions[i].append(pair[i])
        with ledger:
            env.step(pair)
    assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state)
    cash = [s.reward for s in env.state]
    for i in range(2):
        assert cash[i] == 3000 + sum(ledger.data[i]['revenue'].values()) - sum(ledger.data[i]['spend'].values())
    economics = [{k: dict(v) for k, v in d.items() if isinstance(v, dict)} for d in ledger.data]
    row = dict(seed=seed, treatment=treatment, cash=cash, economics=economics,
               decisions=[p.decisions for p in players], max_seconds=[max(p.times) for p in players],
               calls_over_one_second=[sum(x > 1 for x in p.times) for p in players],
               shops=env.state[0].observation.town.unlocked_shops,
               diagnostics=[{k: deepcopy(p.entry.__globals__[k]) for k in ('_MGT_REPORT', '_SHP_REPORT')} for p in players],
               agent_sha256=sha256(path.read_bytes()).hexdigest(), actions_sha256=S.digest(actions))
    target = Path(folder) / f'{seed}-{treatment}'
    target.with_suffix('.actions.json.gz').write_bytes(gzip.compress(json.dumps(actions).encode(), mtime=0))
    target.with_suffix('.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, default=12)
    parser.add_argument('--seed-base', type=int, default=226220)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--tag', default='live_m1_wage_v1')
    args = parser.parse_args()
    folder = R.OUT / args.tag
    folder.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__), Path(S.__file__), Path(R.__file__), ROOT / 'agents/mgt_m1.py', Path(R.engine().__file__)]
    manifest = dict(arguments=vars(args), sources={str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sources},
                    protocol='Natural engine shops/weeds. Live m1 in both seats. Wage-only causal first-day rescheduling; 48h projected continuation. Same-seed mirror controls. Research timing, no enforced timeout.')
    mf = folder / 'manifest.json'
    if mf.exists():
        assert json.loads(mf.read_text()) == manifest
    else:
        mf.write_text(json.dumps(manifest, indent=2))
    jobs = [(s, t, str(folder)) for s in range(args.seed_base, args.seed_base + args.seeds) for t in (-1, 0, 1)]
    rows, todo = [], []
    for job in jobs:
        path = folder / f'{job[0]}-{job[1]}.json'
        if path.exists():
            rows.append(json.loads(path.read_text()))
        else:
            todo.append(job)
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        fs = {pool.submit(run, job): job for job in todo}
        for f in as_completed(fs):
            row = f.result()
            rows.append(row)
            print(json.dumps({k: row[k] for k in ('seed', 'treatment', 'cash', 'max_seconds')}), flush=True)
    treated = [r for r in rows if r['treatment'] >= 0]
    controls = {r['seed']: r for r in rows if r['treatment'] == -1}
    margins = [r['cash'][r['treatment']] - r['cash'][1-r['treatment']] for r in treated]
    clusters = [st.mean(r['cash'][r['treatment']] - r['cash'][1-r['treatment']] for r in treated if r['seed'] == s) for s in controls]
    rng = random.Random(20260922)
    boot = sorted(st.mean(rng.choices(clusters, k=len(clusters))) for _ in range(5000))
    choices = [c for r in treated for c in r['decisions'][r['treatment']]]
    result = dict(games=len(treated), seeds=len(controls), wins=sum(x > 0 for x in margins), ties=sum(x == 0 for x in margins), losses=sum(x < 0 for x in margins),
                  mean_margin=st.mean(margins), paired_seed_ci95=[boot[125], boot[4874]],
                  mean_enabled_cash=st.mean(r['cash'][r['treatment']] for r in treated), mean_disabled_cash=st.mean(r['cash'][1-r['treatment']] for r in treated),
                  mean_own_gain_vs_control=st.mean(r['cash'][r['treatment']] - controls[r['seed']]['cash'][r['treatment']] for r in treated),
                  decisions=len(choices), changed_days=sum(c['executed_first_day_change'] for c in choices),
                  fallbacks=dict(Counter(c.get('fallback', 'none') for c in choices)),
                  max_enabled_seconds=max(r['max_seconds'][r['treatment']] for r in treated),
                  enabled_calls_over_one_second=sum(r['calls_over_one_second'][r['treatment']] for r in treated),
                  changed_shop_histories=sum(r['shops'] != controls[r['seed']]['shops'] for r in treated))
    (folder / 'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
