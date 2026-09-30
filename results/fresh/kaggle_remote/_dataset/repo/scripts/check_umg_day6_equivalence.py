"""Distinguish 64 shop histories from observed production/action patterns."""
import gzip
import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path

from map_umg_shop_coverage import counts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/production_continuation/day6_equivalence.json'


def key(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def board(rows):
    return ''.join(rows).replace(' w', ' .')


def main():
    tapes = [json.load(gzip.open(p, 'rt', encoding='utf-8')) for sub in ('56266758', '56266899')
             for p in sorted((ROOT/'data/mg_tapes'/sub).glob('*.json.gz'))]
    rows = []
    for t in tapes:
        rows.append(dict(episode=t['episode'], submission=t['submission'], shops=t['shops'][6],
            day6_counts=counts(t['boards'][6]), day9_counts=counts(t['boards'][9]),
            signatures=dict(
                day6_counts=key(counts(t['boards'][6])),
                day6_layout=board(t['boards'][6]),
                days6_to9_count_path=key([counts(t['boards'][d]) for d in range(6,10)]),
                pre_day6_actions=sha256(key(t['actions'][:144]).encode()).hexdigest(),
                days6_to9_actions=sha256(key(t['actions'][144:216]).encode()).hexdigest())))
    def summarize(rs):
        groups = defaultdict(list)
        for r in rs:
            groups[tuple(r['shops'])].append(r)
        summary = dict(games=len(rs), ordered_shop_pairs=len(groups), metrics={})
        for m in rows[0]['signatures']:
            variants = [len({r['signatures'][m] for r in group}) for group in groups.values()]
            representatives = [Counter(r['signatures'][m] for r in group).most_common(1)[0][0] for group in groups.values()]
            summary['metrics'][m] = dict(distinct_over_all_games=len({r['signatures'][m] for r in rs}),
                shop_pairs_with_multiple_observed_patterns=sum(n>1 for n in variants),
                distinct_modal_patterns=len(set(representatives)))
        return summary
    pooled = summarize(rows)
    result = dict(pooled=pooled,
                  by_submission={str(s):summarize([r for r in rows if r['submission']==s]) for s in sorted({r['submission'] for r in rows})},
                  rows=rows,
                  limits=['Day6 snapshot precedes the actions responding to shop2.',
                          'Day9 snapshot is after day8 actions and before shop3 response.',
                          'Standing counts omit crop ages, cash, inputs and prices; equal counts are not proof of equivalent plans.',
                          'Exact actions include movement, market orders, servicing and execution differences.'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}, indent=2))
    for r in sorted(rows, key=lambda r:r['episode'])[:1]:
        print('example', {k:r[k] for k in ('episode','shops','day6_counts','day9_counts')})


if __name__=='__main__':
    main()
