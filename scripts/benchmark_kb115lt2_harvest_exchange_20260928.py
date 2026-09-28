"""Pure captured-call OFF parity / enabled exchange / timing diagnostic.

Run only outside timed game-worker windows. It never constructs an environment.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(r'C:\Users\xyygl\Documents\kaggriculture\results\fresh\semantic_strategy_20260928\polish_fixtures_v8_live01')
SOURCE_SHA = '5c2dfb70eaf68e1b415fe14fd6414774b467afa81b4f66f9d170e792e0dfe833'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def keep_ops(args, predicate):
    return Counter((x['tile'], tuple(o['c'])) for sg in args[1] for x in sg['stops'] for o in x['ops'] if predicate(o))


def fixed_stops(args):
    fixed = ('DELIVER', 'DROP', 'PLACE_HARVEST', 'PICKUP', 'PLACE', 'BUILD_COOP', 'BUILD_PASTURE')
    return {sg['u']: [x for x in sg['stops'] if any(x.get(k) for k in ('dawn','copy','sell_all','place','turn','deliver'))
                     or any(o['c'][0] in fixed for o in x['ops'])] for sg in args[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=FIXTURES)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT/'results/fresh/semantic_kb115lt2_recovery/harvest_exchange_fixtures_v1.json')
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    base_path = ROOT/'agents/mgt_lead_kb115lt2_routefix_fast.py'
    source_path = ROOT/'agents/mgt_lead_kb115lt2_harvestx.py'
    assert sha(base_path) == SOURCE_SHA
    base = load(base_path, '_strategy_kb115lt')
    experimental = load(source_path, '_harvest_exchange_fixture')
    manifest_path = args.fixtures/'manifest.json'
    manifest = json.loads(manifest_path.read_text()); assert manifest['verified']
    rows = []
    for record in manifest['fixtures']:
        path = args.fixtures/record['file']; assert sha(path) == record['sha256']
        payload = pickle.loads(gzip.decompress(path.read_bytes()))
        fixture = pickle.loads(payload['input_pickle'])
        reference = pickle.loads(payload['reference_output_pickle'])
        durations = {'off': [], 'on': [], 'exchange_only': []}
        off_equal = []
        enabled_first = None
        for repeat in range(args.repeats):
            for mode in (('off', 'on') if repeat%2 == 0 else ('on', 'off')):
                module = experimental
                for key, value in fixture['globals'].items(): setattr(module, key, deepcopy(value))
                module.CFG['sd_polish_harvest_exchange'] = int(mode == 'on')
                module.CFG['sd_polish_harvest_exchange_cap'] = 96
                inputs = pickle.loads(payload['input_pickle'])['args']
                old = module._tier_harvest_exchange
                def timed(*call_args):
                    start = time.perf_counter()
                    result = old(*call_args)
                    durations['exchange_only'].append(time.perf_counter()-start)
                    return result
                module._tier_harvest_exchange = timed
                start = time.perf_counter()
                try: module._tier_polish(*inputs)
                finally: module._tier_harvest_exchange = old
                durations[mode].append(time.perf_counter()-start)
                if mode == 'off':
                    off_equal.append(inputs == reference)
                    assert inputs == reference, ('OFF changed captured reference', record['file'])
                else:
                    if enabled_first is None: enabled_first = deepcopy(inputs)
                    else: assert inputs == enabled_first, ('Enabled nondeterminism', record['file'])
        before, after = reference, enabled_first
        decision = after[-1]['_polish_day']['harvest_exchange']
        assert keep_ops(before, lambda o:o['m']) == keep_ops(after, lambda o:o['m'])
        assert keep_ops(before, lambda o:o['c'][0] == 'FEED') == keep_ops(after, lambda o:o['c'][0] == 'FEED')
        assert not (keep_ops(before, lambda o:o['c'][0] == 'HARVEST') - keep_ops(after, lambda o:o['c'][0] == 'HARVEST'))
        assert fixed_stops(before) == fixed_stops(after)
        gained = keep_ops(after, lambda o:o['c'][0] == 'HARVEST') - keep_ops(before, lambda o:o['c'][0] == 'HARVEST')
        assert sum(gained.values()) == int(decision['accepted'])
        assert decision['examined'] <= 96
        changed = []
        for a, b in zip(before[1], after[1]):
            if a != b:
                hours = experimental._tier_eval(b, want_hours=True)
                changed.append(dict(unit=a['u'], before_stops=a['stops'], after_stops=b['stops'],
                    after_schedule=hours[4], after_end_exclusive=hours[0], after_lateness=hours[1], after_supply_failures=hours[3]))
        row = dict(day=fixture['args'][4], fixture=record['file'], fixture_sha256=record['sha256'],
            off_exact_output_checks=off_equal, enabled_repeated_outputs_identical=True,
            mandatory_feed_existing_harvest_fixed_delivery_checks=True, decision=decision,
            timings_seconds=durations, median_seconds={k:statistics.median(v) for k,v in durations.items()},
            changed_routes=changed, remaining_unassigned_before=before[2], remaining_unassigned_after=after[2])
        rows.append(row)
        print(json.dumps({k:row[k] for k in ('day','decision','median_seconds')}), flush=True)
    result = dict(scope='PURE_CAPTURED_POLISH_CALLS_NOT_GAMEPLAY', source_base_sha256=sha(base_path),
        experimental_sha256=sha(source_path), capture_manifest_sha256=sha(manifest_path),
        script_sha256=sha(Path(__file__)), rows=rows, no_environment_constructed=True,
        no_agent_or_opponent_called=True, repetitions=args.repeats,
        limitations=['Modeled exchange value, not profit.', 'Receipt is planned delivery or automatic midnight transfer; no engine success claim.',
                     'D26 old fixture has deferrals without tile provenance and is deliberately rejected.',
                     'Microbenchmark overhead is not a whole-season runtime result.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(args.output)


if __name__ == '__main__': main()
