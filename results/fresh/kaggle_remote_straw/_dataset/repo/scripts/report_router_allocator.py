"""Summarize frozen allocation experiments without selecting on test seeds."""
from collections import Counter
from hashlib import sha256
import json
from statistics import mean
from evaluate_boards import ROOT

OUT=ROOT/'results/fresh/router_allocator'


def main():
    rows=json.loads((OUT/'results.json').read_text())
    assert len(rows)==144
    manifest=json.loads((OUT/'manifest.json').read_text())
    for path,digest in manifest.items():assert sha256((ROOT/path).read_bytes()).hexdigest()==digest
    ix={(r['seed'],r['seat'],r['perturbed'],r['kind']):r for r in rows}
    pairs=[(s,i) for s in range(94101,94108) for i in (0,1)]
    allpairs=[(s,i) for s in range(94100,94108) for i in (0,1)]
    for s,i in allpairs:
        ref=ix[s,i,'normal','router']
        for k in ('scheduler','allocator'):
            r=ix[s,i,'normal',k]
            assert r['cash']==ref['cash'] and r['ledger']==ref['ledger']
            assert r['stats']['late_tasks']==0
            if k=='allocator':assert r['stats'].get('chain_swaps',0)==0
    lib=json.loads((ROOT/'data/router_work_orders.json').read_text())
    lines=['# Inventory-constrained worker allocation','',
           '## Result','',
           'The allocator preserves the public router’s normal terminal cash and full sales/spending ledger in every seed-seat comparison. It exchanges remaining daily job sequences between workers when their inventories match and the exchange reduces predicted missed tasks or lateness.','',
           '144 full-season continuations were evaluated: eight seeds, both seats, three position conditions and three controllers. Seed 94100 was a smoke test; 94101–94107 were held out until the implementation was frozen. No configuration search or test-set tuning was performed. Each controller faces the same public-router opponent from a native-router checkpoint at turn 224, using natural shop randomness.','',
           '## Held-out terminal cash','',
           '| Condition | Public router | Fixed-worker scheduler | Allocator | Allocator minus fixed |',
           '|---|---:|---:|---:|---:|']
    summary={}
    for condition in ('normal','displaced','permuted'):
        av={k:mean(ix[s,i,condition,k]['cash'] for s,i in pairs) for k in ('router','scheduler','allocator')}
        deltas=[ix[s,i,condition,'allocator']['cash']-ix[s,i,condition,'scheduler']['cash'] for s,i in pairs]
        summary[condition]={'mean_cash':av,'delta_mean':mean(deltas),'wins':sum(d>0 for d in deltas),'ties':sum(d==0 for d in deltas),'losses':sum(d<0 for d in deltas),'delta_range':[min(deltas),max(deltas)]}
        lines.append(f"| {condition} | {av['router']:,.1f} | {av['scheduler']:,.1f} | {av['allocator']:,.1f} | {mean(deltas):+,.1f} |")
    lines+=['','## Execution diagnostics','',
            '| Condition | Fixed: late task attempts | Allocator: late task attempts | Allocator chain swaps |',
            '|---|---:|---:|---:|']
    for condition in summary:
        late={k:mean(ix[s,i,condition,k]['stats']['late_tasks'] for s,i in pairs) for k in ('scheduler','allocator')}
        swaps=mean(ix[s,i,condition,'allocator']['stats'].get('chain_swaps',0) for s,i in pairs)
        lines.append(f"| {condition} | {late['scheduler']:.1f} | {late['allocator']:.1f} | {swaps:.1f} |")
    matches=sum(ix[s,i,'permuted','allocator']['ledger']==ix[s,i,'normal','router']['ledger'] for s,i in pairs)
    lines+=['',f'For permuted workers, the allocator matches the complete unperturbed-router accounting ledger in {matches}/14 held-out comparisons.',
            f"Against the fixed-worker scheduler in that condition, it earns more cash in {summary['permuted']['wins']}/14 pairs and less in {summary['permuted']['losses']}/14; differences range from {summary['permuted']['delta_range'][0]:+,.0f} to {summary['permuted']['delta_range'][1]:+,.0f}. Restoring production does not guarantee higher cash on every market path.",
            'Late attempts measure schedule execution, not whether each operation succeeded or the economic cost of missing it. Predictions assume remaining task durations and Manhattan travel; they do not simulate shared stock or changing crop state.','',
            '## Position conditions','',
            '- **Normal:** identical original router state.',
            '- **Displaced:** move the farmer and first two hired workers two Manhattan steps away to unlocked tiles, with row-major tie-breaking. Keep inventories attached to their workers.',
            '- **Permuted:** reverse worker positions within groups carrying identical inventories. This deliberately tests whether interchangeable workers can take over one another’s routes. It is an artificial, favorable test of reassignment, not a random disruption distribution.',
            '- Positions are changed only once, at turn 224. Cash, crops, animals, inventories and the opponent are unchanged at the checkpoint. Later RNG and market outcomes may diverge. The two seats share a seed and are not independent samples.','',
            '## Allocation method','',
            'At each turn, after the day’s last planned hire, predict completion times for each worker and each remaining job sequence. Preserve job ordering, travel time and preferred execution times. Compare pairwise sequence exchanges only among workers with identical carried inventories. Accept an exchange only if it reduces the number of tasks predicted to run past midnight, or, at equal missed-task count, total lateness. Repeat until no improving pair remains. Reset assignment when the next day starts.',
            'This is a greedy local allocation method, not a globally optimal assignment solver. It leaves an on-time allocation unchanged. Retaining complete sequences preserves within-worker pickup/use/delivery order; inventory equality is conservative and does not establish every shared-resource interaction is safe. Future hires freeze allocation because worker positions determine new spawn locations.','',
            '## Validation and limits','',
            '- Every game reached 720 states without invalid/error status; both players’ cash reconciles with recorded revenue and spending.',
            '- Normal cash and full ledgers match in all 16 seed-seat pairs, including the smoke seed. No normal-game worker exchanges or late attempts are expected; the reported diagnostics verify this behavior.',
            '- Focused checks cover different-inventory rejection, future-hire rejection, completed tasks, and midnight deadline accounting.',
            f"- Held-out normal final branches: {dict(Counter(lib['templates'][ix[s,i,'normal','router']['route']]['name'] for s,i in pairs))}.",
            '- Reassignment still uses the router’s crop calendar and markets. It does not optimize investments, split job sequences, transfer inventory, prioritize jobs by economic value, or recover arbitrary farm layouts.','',
            '## Decision and next step','',
            'Keep the conditional public router as the competitive baseline. The allocator is a useful experimental execution layer, with no demonstrated advantage in normal play. Next, introduce task-level repair for overdue watering and harvesting: let a nearby worker cover a single urgent job if travel, carried resources and its own commitments permit. Evaluate job success and product quantities alongside cash so price-path changes are not mistaken for production improvements.','',
            '[Raw results](../results/fresh/router_allocator/results.json) · [Frozen source hashes](../results/fresh/router_allocator/manifest.json) · [Prior scheduler study](router_scheduler.md)','']
    (ROOT/'docs/router_allocator.md').write_text('\n'.join(lines),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2));print('Permuted ledger matches',matches,'/14')


if __name__=='__main__':main()
