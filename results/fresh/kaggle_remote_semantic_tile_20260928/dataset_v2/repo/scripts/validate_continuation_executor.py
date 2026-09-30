"""Official-engine native reconstruction gate; writes separate versioned results."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import fragments.continuation_executor as executor
import validate_segment_executor as validator
from check_segment_v3 import sales

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='results/fresh/continuation_executor/native_v1.json')
    parser.add_argument('--indices', default='')
    args = parser.parse_args()
    path = ROOT / args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): raise RuntimeError('use a new output path; retain previous evidence')
    sys.modules['fragments.segment_job_executor'] = executor
    validator.add_capacity_sales = sales
    nodes = validator.selected_nodes(validator.read(validator.LIBRARY)['segments'])
    if args.indices: nodes = [nodes[int(i)] for i in args.indices.split(',')]
    raws, rows = validator.raw_lookup(), []
    sources = ['scripts/fragments/continuation_executor.py', 'scripts/fragments/segment_job_executor_v3.py',
               'scripts/validate_continuation_executor.py', 'scripts/validate_segment_executor.py']
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}
    call_times = []
    original = executor.segment_executor_action
    def timed(obs, state):
        start = time.perf_counter()
        try: return original(obs, state)
        finally: call_times.append(time.perf_counter() - start)
    executor.segment_executor_action = timed
    for node in nodes:
        attempts = []
        for workers in (11, 12, 13):
            start = time.perf_counter()
            try: row = validator.run_node(node, raws[int(node['episode'])], workers)
            except Exception:
                import traceback
                row = {'error': traceback.format_exc(), 'hire_to': workers, 'started': False}
            row['wall_seconds'] = time.perf_counter() - start
            attempts.append(row)
            if row.get('started') and not row.get('rejected_window'): break
            if row.get('error'): break
        rows.append({'id': node['id'], 'attempts': attempts})
        accepted = [r['attempts'][-1] for r in rows if r['attempts'][-1].get('started') and not r['attempts'][-1].get('rejected_window')]
        payload = {'complete': len(rows) == len(nodes), 'source_hashes': hashes, 'rows': rows,
                   'summary': {'requested': len(nodes), 'accepted': len(accepted),
                               'exact_output': sum(not r['output_difference'] for r in accepted),
                               'exact_tiles': sum(not r['end_tile_state_differences'] for r in accepted),
                               'errors': sum('error' in r['attempts'][-1] for r in rows),
                               'max_action_seconds': max(call_times, default=0),
                               'calls_over_1s': sum(t > 1 for t in call_times)}}
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        last = attempts[-1]
        print(json.dumps({'id': node['id'], 'workers': last['hire_to'], 'failure': last.get('rejected_window'),
                          'difference': last.get('output_difference'), 'error': last.get('error')}), flush=True)
    print(json.dumps(payload['summary']), flush=True)


if __name__ == '__main__': main()
