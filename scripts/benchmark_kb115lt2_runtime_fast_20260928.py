"""Verified pure-call fixture comparison for exact executor speed changes."""
from copy import deepcopy
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--polish-fixtures',type=Path,required=True)
    parser.add_argument('--eval-search-fixtures',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Append-only evidence'
    manifest_path = args.polish_fixtures/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['verified']
    source_paths = {'original':ROOT/'agents/mgt_lead_kb115lt2.py',
                    'polishcache':ROOT/'agents/mgt_lead_kb115lt2_routefix_fast.py',
                    'runtime_fast':ROOT/'agents/mgt_lead_kb115lt2_runtime_fast.py'}
    modules = {name:load('_strategy_kb115lt' if name=='original' else '_runtime_bench_'+name,path)
               for name,path in source_paths.items()}
    rows = []
    hashes = {row['file']:row['sha256'] for row in manifest['fixtures']}
    for path in sorted(args.polish_fixtures.glob('*.pickle.gz')):
        assert sha(path)==hashes[path.name]
        payload = pickle.loads(gzip.decompress(path.read_bytes()))
        expected = pickle.loads(payload['reference_output_pickle'])
        timings = {name:[] for name in modules}
        for repeat in range(3):
            order = list(modules)
            order = order[repeat:]+order[:repeat]
            for name in order:
                fixture = pickle.loads(payload['input_pickle'])
                module = modules[name]
                for key,value in fixture['globals'].items():
                    setattr(module,key,value)
                tick = time.perf_counter()
                returned = module._tier_polish(*fixture['args'])
                seconds = time.perf_counter()-tick
                assert fixture['args']==expected and returned==payload.get('return_value'),(path.name,name,repeat)
                timings[name].append(seconds)
        row = dict(fixture=path.name,sha256=sha(path),all9_output_value_comparisons_equal=True,
                   times=timings,medians={name:statistics.median(v) for name,v in timings.items()})
        rows.append(row)
        print(json.dumps(dict(fixture=path.name,medians=row['medians'])),flush=True)
    output = dict(scope='PURE_CALL_COMPONENT_BENCHMARK_NOT_RUNTIME_GATE',
                  source_hashes={name:sha(path) for name,path in source_paths.items()},
                  script_sha256=sha(Path(__file__)),capture_manifest_sha256=sha(manifest_path),rows=rows)
    other_manifest_path = args.eval_search_fixtures/'manifest.json'
    other_manifest = json.loads(other_manifest_path.read_text())
    # Keep strict action-order verification failed. Require the separately
    # checkable narrower evidence: complete same-state replay, with only
    # within-limit permutations of pure SELL orders on distinct products.
    assert other_manifest['error'] is None and other_manifest['engine_steps']==720
    assert other_manifest['engine_statuses']==['DONE','DONE']
    assert other_manifest['replay_cash_equal'] and other_manifest['replay_complete_ledgers_equal']
    assert all(all(v for k,v in day.items() if k!='day') for day in other_manifest['dawn_checks'])
    for mismatch in other_manifest['shadow_mismatches']:
        before,after = deepcopy(mismatch['expected']),deepcopy(mismatch['shadow'])
        orders1,orders2 = before.pop('market'),after.pop('market')
        assert before==after and len(orders1)<=10
        assert sorted(orders1)==sorted(orders2)
        assert all(order[0]=='SELL' for order in orders1)
        assert len({order[1] for order in orders1})==len(orders1)
    fixture_path = args.eval_search_fixtures/'eval_search_fixtures.pickle.gz'
    assert sha(fixture_path)==other_manifest['fixtures_sha256']
    captured = pickle.loads(gzip.decompress(fixture_path.read_bytes()))
    evaluations,searches = captured['evaluations'],captured['searches']
    eval_rows,search_rows = [],[]
    for name,module in modules.items():
        for fixture in evaluations:
            for key,value in fixture['globals'].items():
                setattr(module,key,deepcopy(value))
            inputs,kwargs=deepcopy((fixture['args'],fixture['kwargs']))
            assert module._tier_eval(*inputs,**kwargs)==fixture['expected_result']
            assert inputs==fixture['expected_args'] and kwargs==fixture['expected_kwargs']
        for hours in (False,True):
            subset=[f for f in evaluations if bool(f['kwargs'].get('want_hours',f['args'][2] if len(f['args'])>2 else False))==hours]
            assert all(f['globals']==subset[0]['globals'] for f in subset)
            for key,value in subset[0]['globals'].items():
                setattr(module,key,deepcopy(value))
            timings=[]
            for repeat in range(3):
                tick=time.perf_counter()
                for _ in range(500):
                    for f in subset:
                        module._tier_eval(*f['args'],**f['kwargs'])
                timings.append(time.perf_counter()-tick)
            eval_rows.append(dict(implementation=name,want_hours=hours,distinct_inputs=len(subset),
                                 calls_per_repeat=500*len(subset),seconds=timings,median=statistics.median(timings)))
    for index,fixture in enumerate(searches):
        for name,module in modules.items():
            timings=[]
            for repeat in range(3):
                for key,value in fixture['globals'].items():
                    setattr(module,key,deepcopy(value))
                inputs,kwargs=deepcopy((fixture['args'],fixture['kwargs']))
                tick=time.perf_counter()
                returned=module._tier_search(*inputs,**kwargs)
                timings.append(time.perf_counter()-tick)
                assert returned==fixture['expected_result'],(index,name)
                assert inputs[:3]==fixture['expected_args'][:3] and kwargs==fixture['expected_kwargs']
                assert inputs[3].getstate()==fixture['rng_state_after']
            search_rows.append(dict(index=index,implementation=name,all3_result_input_rng_checks_equal=True,
                                    seconds=timings,median=statistics.median(timings)))
    output.update(eval_search_capture_manifest_sha256=sha(other_manifest_path),
                  capture_strict_verified=other_manifest['verified'],
                  capture_order_only_mismatches=[m['step'] for m in other_manifest['shadow_mismatches']],
                  evaluation_results=eval_rows,search_results=search_rows,
                  all_captured_evaluator_outputs_and_inputs_equal=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,indent=2)+'\n')


if __name__=='__main__':
    main()
