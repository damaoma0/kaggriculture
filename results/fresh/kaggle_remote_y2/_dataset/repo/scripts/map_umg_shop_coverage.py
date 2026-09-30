"""Find missing shop-history branches before designing a production executor.

Read-only analysis of the frozen two-submission UMG library. Exact-prefix
coverage and current aggregate demand coverage are deliberately separate.
No future shop or end-game score is used to rank candidate donor plans.
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from mgt_late_choice import DEMAND, PRODUCTS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/production_continuation'
SHOPS = sorted(DEMAND)
LABELS = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY',
          'ME': 'MELON', 'sh': 'SHEEP', 'co': 'COW', 'go': 'GOOSE'}


def demand(shops):
    return tuple(sum(DEMAND[s].get(p, 0) for s in shops) for p in PRODUCTS)


def counts(board):
    text = ''.join(board)
    c = Counter(text[i:i+2] for i in range(0, len(text), 2))
    return {crop: c[label] for label, crop in LABELS.items()}


def main():
    files = sorted(p for sub in ('56266758', '56266899') for p in (ROOT / 'data/mg_tapes' / sub).glob('*.json.gz'))
    tapes = [json.load(gzip.open(p, 'rt', encoding='utf-8')) for p in files]
    assert len({t['episode'] for t in tapes}) == len(tapes)
    by_prefix = defaultdict(list)
    by_demand = defaultdict(list)
    for i, t in enumerate(tapes):
        s = t['shops'][30]
        assert len(s) == 8, (t['episode'], s)
        for k in range(1, 9):
            by_prefix[tuple(s[:k])].append(i)
            by_demand[k, demand(s[:k])].append(i)
    levels = []
    for k in range(1, 9):
        occupied = sum(len(prefix) == k for prefix in by_prefix)
        levels.append(dict(reveal=k, elapsed_day=3*k, observed_exact_prefixes=occupied,
                           possible_prefixes=8**k, uniform_exact_coverage=occupied/(8**k)))
    # Remove the test episode itself. This measures sample coverage, not whether
    # the current agent's actual board remains compatible with the donor.
    first_exact, first_demand = Counter(), Counter()
    for t in tapes:
        s = t['shops'][30]
        a = next((k for k in range(1, 9) if len(by_prefix[tuple(s[:k])]) == 1), None)
        b = next((k for k in range(1, 9) if len(by_demand[k, demand(s[:k])]) == 1), None)
        first_exact[str(a)] += 1
        first_demand[str(b)] += 1
    # First exact gaps are all children of prefixes still present in the library.
    gaps = []
    prefixes = {()} | {p for p in by_prefix if len(p) < 8}
    for prefix in prefixes:
        observed_next = {p[-1] for p in by_prefix if len(p) == len(prefix)+1 and p[:-1] == prefix}
        for new_shop in SHOPS:
            if new_shop not in observed_next:
                target = prefix + (new_shop,)
                k = len(target)
                ids = by_demand.get((k, demand(target)), [])
                gaps.append(dict(prefix=list(prefix), new_shop=new_shop, reveal=k, elapsed_day=3*k,
                                 uniform_first_gap_mass=8.0**(-k),
                                 same_current_demand_donors=[tapes[i]['episode'] for i in ids]))
    gaps.sort(key=lambda g: (g['reveal'], -len(g['same_current_demand_donors']), g['prefix'], g['new_shop']))
    assert abs(sum(g['uniform_first_gap_mass'] for g in gaps) + levels[-1]['uniform_exact_coverage'] - 1) < 1e-9
    # Illustrative whole-farm target curves at the earliest missing branches.
    # Counts are observed; age cohorts are unavailable in compact board labels.
    examples = []
    for gap in gaps[:6]:
        k = gap['reveal']; day = gap['elapsed_day']; target = gap['prefix'] + [gap['new_shop']]
        parents = [tapes[i] for i in by_prefix.get(tuple(gap['prefix']), [])]
        anchor = min(parents, key=lambda t: t['episode'])
        board = counts(anchor['boards'][day])
        def rank(t):
            ds = t['shops'][day]
            b = counts(t['boards'][day])
            return (sum(abs(x-y) for x,y in zip(demand(ds), demand(target))),
                    int(ds[-1] != gap['new_shop']),
                    sum(abs(b[c]-board[c]) for c in board), t['episode'])
        donors = []
        for t in sorted(tapes, key=rank)[:3]:
            next_day = min(day+3, 30)
            donors.append(dict(episode=t['episode'], submission=t['submission'],
                revealed_shops=t['shops'][day], rank_components=rank(t)[:3],
                count_targets=[dict(day=d, crops_and_animals=counts(t['boards'][d])) for d in range(day, 30)],
                next_shop_day=next_day, source_future_is_contingent=True))
        examples.append(dict(gap=gap, illustrative_anchor_episode=anchor['episode'],
                             anchor_counts=board, donors=donors))
    result = dict(tapes=len(tapes), products=PRODUCTS, levels=levels,
                  leave_one_episode_out_first_exact_gap=dict(first_exact),
                  leave_one_episode_out_first_current_demand_gap=dict(first_demand),
                  first_gap_branches=gaps, examples=examples,
                  limitations=['Current demand equality does not imply equal historical prices, ages or board compatibility.',
                               'Example anchor is a recorded pre-reveal board, not our live router board.',
                               'Targets are aggregate standing counts; age cohorts and effective daily outputs still need reconstruction.',
                               'Donor actions after its next shop reveal depend on its own future shops; not unconditional instructions.'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'shop_coverage.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k,v in result.items() if k not in ('first_gap_branches', 'examples')}, indent=2))
    print('gap branches', len(gaps), 'candidate examples', len(examples))


if __name__ == '__main__':
    main()
