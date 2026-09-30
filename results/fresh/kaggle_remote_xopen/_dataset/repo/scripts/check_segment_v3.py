"""Independent check of midnight-aware routing on a deterministic native node."""
import json
import sys
from collections import Counter
import fragments.segment_job_executor_v3 as executor
import validate_segment_executor as validator


def sales(action, obs, state):
    day = int(obs['day']) - state['start_day']
    need = Counter()
    for job in state['jobs']:
        if job['day'] != day or job['id'] in state['issued']: continue
        op = job['cmd'][0]
        if op == 'FEED': need['WHEAT'] += 1
        elif op == 'FERTILIZE': need['FERTILIZER'] += 1
    orders = list(action.get('market', []))
    sell = []
    for p in validator.PRODUCTS:
        qty = max(0, obs['private']['shed'].get(p, 0) - need[p])
        if qty and len(sell) + len(orders) < 10: sell.append(['SELL', p, qty])
    action['market'] = sell + orders
    return action


if __name__ == '__main__':
    sys.modules['fragments.segment_job_executor'] = executor
    validator.add_capacity_sales = sales
    nodes = validator.selected_nodes(validator.read(validator.LIBRARY)['segments'])
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    node = nodes[index]
    rows = []
    for workers in (11, 12, 13):
        row = validator.run_node(node, validator.raw_lookup()[int(node['episode'])], workers)
        rows.append(row)
        print(workers, row.get('rejected_window'), row.get('output_difference'))
        if row.get('started') and not row.get('rejected_window'): break
    validator.OUT.with_name('native_v3_node_%s.json' % index).write_text(json.dumps(rows, indent=2))
