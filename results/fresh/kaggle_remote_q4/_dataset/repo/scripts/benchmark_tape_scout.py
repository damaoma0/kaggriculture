"""Frozen fresh worlds: V8 scout vs native and the full V7 reference policy.

Common forecasts are shared only within identical public decision inputs.
The exact policy also plays a complete game; it may reuse a shadow decision
only when its portable input digest is identical. Runtime ratios come from
separate, uncached paired measurements, not shadow-cache wall times.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import random
import secrets
import statistics
import time
import traceback
from types import FunctionType, SimpleNamespace

import benchmark_value_tape_generalization_v2 as G
import train_tape_semantic_ranker as T
import value_tape_search_v7 as Exact
import value_tape_search_v8 as Scout

ROOT = T.OUT
OUT = ROOT / 'fresh_scout'


def digest(obs, memory):
    return sha256(json.dumps(Scout.V.canonical([obs, Scout.F.semantic_memory(memory)]),
        sort_keys=True, default=str).encode()).hexdigest()


class ForecastCache:
    def __init__(self, obs):
        self.base = Scout.runtime()
        self.rollout_impl = self.base.rollout_impl
        self.busy = False
        self.obs = obs
        self.cache = {}
        self.worlds = {}
        self.costs = {}
        self.base.prepare(obs)

    def prepare(self, obs):
        assert obs is self.obs
        self.rollouts = self.pruned_rollouts = self.simulated_turns = self.cache_hits = 0
        self.estimated_forecast_cpu = 0.0

    def shortlist(self, obs, memory, count):
        return self.base.shortlist(obs, memory, count)

    def world(self, obs, i):
        assert obs is self.obs
        if i not in self.worlds:
            self.worlds[i] = Scout.M.world(obs, i)
        return self.worlds[i]

    def rollout(self, obs, memory, route, world, until=None, protected=None):
        key = (route, world['index'], until, frozenset(protected or ()))
        self.rollouts += 1
        if key not in self.cache:
            start = time.process_time()
            self.cache[key] = self.base.rollout(obs, memory, route, world, until, protected)
            self.costs[key] = time.process_time()-start
        else:
            self.cache_hits += 1
        result = self.cache[key]
        self.estimated_forecast_cpu += self.costs[key]
        self.pruned_rollouts += bool(result.get('early_rejection'))
        self.simulated_turns += result.get('boundary_step', 719)-int(obs['step'])
        return deepcopy(result)

    def choose(self, planner, obs, memory):
        dependencies = dict(planner.choose.__globals__, runtime=lambda:self,
            M=SimpleNamespace(world=self.world, MODEL_SHA256=Scout.M.MODEL_SHA256))
        choose = FunctionType(planner.choose.__code__, dependencies, 'cached_choose', planner.choose.__defaults__)
        choose.__kwdefaults__ = planner.choose.__kwdefaults__
        selected, decision = choose(obs, memory)
        decision['forecast_cache_hits'] = self.cache_hits
        decision['estimated_uncached_forecast_cpu'] = self.estimated_forecast_cpu
        decision['timing_note'] = 'Actual call wall time includes cache hits. Estimated forecast CPU sums the measured cost of each requested cached forecast; not an uncached wall-time measurement.'
        return selected, decision


def play(spec, chooser, folder):
    dependencies = dict(G.game.__globals__, F=SimpleNamespace(choose=chooser))
    fn = FunctionType(G.game.__code__, dependencies, 'scout_live_game', G.game.__defaults__)
    return fn(spec, chooser is not None, folder)


def worker(spec):
    target = OUT / f"{spec['id']}.json"
    if target.exists():
        row = json.loads(target.read_text(encoding='utf-8'))
        assert row['completed'], row.get('error')
        return summarize(row)
    started = time.perf_counter()
    with target.with_suffix('.log').open('w', encoding='utf-8') as log:
        descriptors = [os.dup(1), os.dup(2)]
        try:
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            shadows, known = [], {}
            def choose(obs, memory):
                key = digest(obs, memory)
                cache = ForecastCache(obs)
                route, scout = cache.choose(Scout, obs, memory)
                exact_route, exact = cache.choose(Exact, obs, memory)
                assert digest(obs, memory) == key
                shadows.append(dict(day=int(obs['day']), scout=scout, exact=exact,
                    equal=route == exact_route, input_sha256=key))
                known[key] = (exact_route, exact)
                return route, scout
            def reference(obs, memory):
                key = digest(obs, memory)
                if key in known:
                    selected, decision = known[key]
                    decision = dict(decision, reused_shadow_for_identical_input=True)
                    return selected, decision
                return Exact.choose(obs, memory)
            scout_folder, exact_folder = OUT / 'scout', OUT / 'exact'
            candidate = play(spec, choose, scout_folder)
            exact = play(spec, reference, exact_folder)
            native = play(spec, None, OUT)
            assert candidate['prefix_sha256'] == exact['prefix_sha256'] == native['prefix_sha256']
            all_equal = all(r['equal'] for r in shadows)
            if all_equal:
                assert candidate['actions_sha256'] == exact['actions_sha256']
                assert (candidate['cash'], candidate['rival_cash']) == (exact['cash'], exact['rival_cash'])
            if not any(d['selected'] is not None for d in candidate['decisions']):
                assert candidate['actions_sha256'] == native['actions_sha256']
            row = dict(spec=spec, completed=True, candidate=candidate, exact=exact, baseline=native,
                shadows=shadows, shadow_selection_equal=all_equal,
                margin_delta=candidate['margin']-native['margin'],
                cash_delta=candidate['cash']-native['cash'], rival_delta=candidate['rival_cash']-native['rival_cash'],
                versus_exact=candidate['margin']-exact['margin'],
                exact_margin_delta=exact['margin']-native['margin'])
        except Exception:
            row = dict(spec=spec, completed=False, error=traceback.format_exc())
        finally:
            os.dup2(descriptors[0], 1)
            os.dup2(descriptors[1], 2)
            for fd in descriptors:
                os.close(fd)
    row['seconds'] = time.perf_counter()-started
    target.write_text(json.dumps(row, indent=2), encoding='utf-8')
    return summarize(row)


def summarize(row):
    return {k:row.get(k) for k in ('spec', 'completed', 'margin_delta', 'cash_delta',
        'rival_delta', 'versus_exact', 'exact_margin_delta', 'shadow_selection_equal', 'seconds', 'error')}


def hashes():
    paths = G.B.source_paths() + [Path(__file__)] + [Scout.V.ROOT / 'scripts' / name for name in (
        'value_tape_search_v6.py', 'value_tape_search_v7.py', 'value_tape_search_v8.py',
        'benchmark_value_tape_generalization_v2.py', 'train_tape_semantic_ranker.py', 'tape_semantic_features.py')]
    return {str(p.relative_to(Scout.V.ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def freeze():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('scout', 'exact'):
        (OUT / name).mkdir(exist_ok=True)
    path = OUT / 'design.json'
    if path.exists():
        result = json.loads(path.read_text(encoding='utf-8'))
        assert result['hashes'] == hashes(), 'Frozen experiment source changed'
        return result
    master = secrets.randbits(128)
    rng = random.Random(master)
    seen = {int(p['group'].split('-')[1]) for p in T.load_points()}
    seeds = []
    while len(seeds) < 6:
        seed = rng.randrange(1_000_000_000, 4_000_000_000)
        if seed not in seen and seed not in seeds:
            seeds.append(seed)
    shops = [[rng.choice(sorted(Scout.M.M.DEMAND)) for _ in range(8)] for _ in seeds]
    specs = [dict(id=f'{i}-{opponent}', seed=seed, seat=i%2, opponent=opponent,
        shops=shops[i], group='iid') for opponent in G.B.OPPONENTS for i, seed in enumerate(seeds)]
    result = dict(master_seed=master, hashes=hashes(), specs=specs, worlds=6, paired_matchups=18,
        policy='Frozen V8: one scout world, keep2; unchanged full8 admission; decisions D12/D15/D18. No learned ranker or model retuning.',
        protocol='Six new IID shop worlds crossed with three responsive opponents; six independent demand samples, eighteen matchups. Three complete policies per matchup: scout, full exact, native. Same shops and starting prefix. Cache only exact same observation/own-memory/world/route/protected-assets requests. Live timing limits not enforced.')
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for source in result['hashes']:
        dst = OUT / 'sources' / source
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((Scout.V.ROOT / source).read_bytes())
    return result


def timing():
    from kaggle_environments.utils import structify
    rows = []
    for point in T.load_points():
        if point['panel'] != 'historical':
            continue
        obs = structify(point['obs'])
        records = []
        # Reverse order in the middle case to reduce systematic warm-up bias.
        order = (Scout, Exact) if point['obs']['day'] == 15 else (Exact, Scout)
        for planner in order:
            cpu, wall = time.process_time(), time.perf_counter()
            selected, decision = planner.choose(obs, point['memory'])
            records.append(dict(planner=planner.__name__, selected=selected,
                cpu=time.process_time()-cpu, wall=time.perf_counter()-wall, decision=decision))
        exact = next(r for r in records if r['planner'] == Exact.__name__)
        scout = next(r for r in records if r['planner'] == Scout.__name__)
        assert exact['selected'] == scout['selected'] == point['decision']['selected']
        lookup = {r['route']:r for r in exact['decision']['candidates']}
        comparisons = 0
        for c in scout['decision']['candidates']:
            old = lookup[c['route']]['predictions']
            for a, b in zip(c['predictions'], old):
                assert json.loads(json.dumps(a)) == json.loads(json.dumps(b))
                comparisons += 1
        rows.append(dict(id=point['id'], forecasts_compared=comparisons, records=records))
        (ROOT / 'paired_scout_timing.json').write_text(json.dumps(dict(rows=rows), indent=2), encoding='utf-8')
        print(json.dumps(dict(id=point['id'], selected=scout['selected'],
            exact_cpu=exact['cpu'], scout_cpu=scout['cpu'], exact_wall=exact['wall'], scout_wall=scout['wall'])), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('freeze', 'fresh', 'timing'), default='fresh')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.mode == 'timing':
        timing()
        return
    design = freeze()
    if args.mode == 'freeze':
        print(json.dumps(dict(frozen=True, worlds=6, matchups=18, hashes=len(design['hashes']))), flush=True)
        return
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker, s) for s in design['specs']]):
            row = future.result()
            rows.append(row)
            print(json.dumps(row), flush=True)
    good = [r for r in rows if r['completed']]
    values = [r['margin_delta'] for r in good]
    result = dict(games=len(rows), completed=len(good), rows=rows, worlds=6,
        mean_margin=statistics.mean(values) if values else None,
        mean_cash=statistics.mean(r['cash_delta'] for r in good) if good else None,
        mean_rival=statistics.mean(r['rival_delta'] for r in good) if good else None,
        positive=sum(x>0 for x in values), negative=sum(x<0 for x in values),
        unchanged=sum(x==0 for x in values), exact_cash_equal=sum(r['versus_exact']==0 for r in good),
        all_shadow_selections_equal=all(r['shadow_selection_equal'] for r in good))
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}), flush=True)
    assert len(good) == len(rows)


if __name__ == '__main__':
    main()
