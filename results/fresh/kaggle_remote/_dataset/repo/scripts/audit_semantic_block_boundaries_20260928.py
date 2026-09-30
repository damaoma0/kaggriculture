"""Read-only audit of uncompleted crop requests at reveal-block boundaries."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT/'results/fresh/semantic_strategy_20260928'


def audit(candidate):
    rows = []
    sources = {}
    for path in sorted((STUDY/'runs'/candidate/'development/live').glob('live-*.json')):
        if path.name.endswith('.actions.json'):
            continue
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        game = json.loads(path.read_text())
        seat = game['case']['seat']
        dawns = {r['day']: r for r in game['diagnostics'][seat]}
        for end in range(8, 29, 3):
            start = end+1
            prev = next(x for x in dawns[end]['diagnostics'] if x['day']==end)
            now = next(x for x in dawns[start]['diagnostics'] if x['day']==start)
            obs = dawns[start]['current_observation']
            actual = Counter()
            for line in obs['own_farm']['tiles']:
                for tile in line:
                    if isinstance(tile,dict) and tile.get('crop') and tile.get('planted_day')==end:
                        actual[tile['crop']] += 1
            admitted = prev['realized_plan']['plant_counts']
            requested = prev['policy']['requested']['plant_counts']
            pending = {s: max(0,n-actual[s]) for s,n in requested.items() if n>actual[s]}
            admitted_pending = {s: max(0,n-actual[s]) for s,n in admitted.items() if n>actual[s]}
            seeds = obs['private'].get('seeds',{})
            totals = now['policy']['totals']
            paid = {s:min(n,seeds.get(s,0)) for s,n in pending.items() if seeds.get(s,0)}
            uncovered = {s:n-totals.get(s,0) for s,n in paid.items() if n>totals.get(s,0)}
            rows.append(dict(case=game['case']['id'],old_end=end,new_start=start,
                requested_last_day=requested,admitted_last_day=admitted,
                actual_last_day=dict(actual),pending=pending,admitted_pending=admitted_pending,
                held_seeds=seeds,paid_pending=paid,new_block_totals=totals,
                paid_pending_above_new_block_total=uncovered,
                next_day_admitted=now['realized_plan']['plant_counts'],
                old_block_totals=prev['policy']['totals']))
    def sums(field):
        total=Counter()
        for row in rows: total.update(row[field])
        return dict(total)
    return dict(candidate=candidate,scope='READ_ONLY_DEVELOPMENT_DIAGNOSTIC',sources=sources,
        boundaries=len(rows),pending=sums('pending'),admitted_pending=sums('admitted_pending'),paid_pending=sums('paid_pending'),
        paid_pending_above_new_block_total=sums('paid_pending_above_new_block_total'),
        caveats=['Seed stocks are fungible; this does not identify which purchase funded which later crop.',
                 'New block forecasts may legitimately abandon prior requests after a shop reveal.',
                 'No profit estimate or conclusion that all pending jobs should carry.'],rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',default='strategy_v5_blocks100_finance')
    args=p.parse_args(); result=audit(args.candidate)
    output=STUDY/(args.candidate+'_block_boundary_audit.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','rows')},indent=2))
