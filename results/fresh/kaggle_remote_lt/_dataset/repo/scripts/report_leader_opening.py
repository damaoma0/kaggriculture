"""Summarize observed leader openings without treating tapes as live agents."""
import json
from statistics import mean
from market_corpus import ROOT

OUT=ROOT/'results/fresh/leader_opening'
def main():
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('audit-*.json'))]
    assert len(rows)==6
    result=dict(team='Majkel1337',team_id=16718819,submission_id=56156662,leaderboard_score_snapshot=3209.3,
                episodes=[r['episode'] for r in rows],first_shops=sorted({r['leader']['snapshots'][6]['shops'][0] for r in rows}),daily={})
    for d in (1,3,6,8,10,12):
        result['daily'][d]={}
        for policy in ('leader','v45'):
            snapshots=[r[policy]['snapshots'][d] for r in rows]
            result['daily'][d][policy]=dict(cash=mean(s['cash'] for s in snapshots),
                crops={p:mean(s['crops'].get(p,0) for s in snapshots) for p in ('WHEAT','MELON','STRAWBERRY','TOMATO')},
                animals={p:mean(s['animals'].get(p,0) for s in snapshots) for p in ('COW','SHEEP','GOOSE')},
                hire_spend=mean(s['ledger']['spend'].get('HIRE',0) for s in snapshots),
                fertilizer_sold=mean(s['ledger']['sold_units'].get('FERTILIZER',0) for s in snapshots),
                fertilizer_revenue=mean(s['ledger']['revenue'].get('FERTILIZER',0) for s in snapshots))
    lines=['# Current leader: opening audit','',
        'Snapshot: 2026-09-16. Rank 1 was **Majkel1337**, team 16718819, at **3209.3**. Its higher-rated active submission was **56156662**; the newer active submission 56216119 was at 3187.2. Rankings move. [Leaderboard](https://www.kaggle.com/competitions/kaggriculture/leaderboard).','',
        '## Evidence','',
        'Downloaded six recent public games of submission 56156662, spanning both seats and four first-shop types: Bakery, Ice Cream Shop, Farmers Market and Yarn Store. Reproduced every farm, market, town and private state for all 720 states of all six replays with the installed official engine; cash ledgers reconcile exactly. These are observed action traces, not the leader\'s source code. A public-notebook search for Majkel found no matching notebook; this does not prove none exists.','',
        'For comparison, ran our submitted V45 event candidate in the leader\'s seat against each original opponent\'s fixed recorded actions, with the same seed and observed shop sequence. Its first six days use the V45 opening. Changes in farming can still change weeds and market prices. This is an opening diagnostic, not live head-to-head evidence or an isolated estimate of opening value.','',
        '## Main differences','',
        'At the end of the first in-game day, the leader consistently has 2 cows, 3 sheep, 10 wheat and 6 melons. Our V45 has 2 cows, 2 sheep, 7 wheat and 12 melons. The leader prioritizes one extra sheep and more wheat while staging melon investment across the first three days. Six deferred melon seeds cost 480; the extra sheep costs 500. This describes a capital-allocation tradeoff, not an accounting identity for the entire opening.','',
        'The leader reaches 12 melons by the three-day checkpoint and has already planted 2 strawberries. V45 has 12 melons from day one but no strawberries at three days. By six days, leader strawberry count is 7-8 versus 4, while its herd is 2 cows/3 sheep versus 4 cows/2 sheep. Early wheat is largely replaced by strawberries.','',
        'The first leader strawberries were planted on zero-based day 2 in the representative replay, versus day 5 for V45. Their first production eligibility is therefore three days earlier under the crop rules, conditional on survival and maintenance. Earlier planting does not by itself prove higher total seasonal yield or profit.','',
        '## Quantitative comparison','',
        'Rows use elapsed days (step = days × 24); cash and counts below are six-game averages.','',
        '| Elapsed days | Policy | Cash | Wheat | Melons | Strawberries | Cows | Sheep | Geese | Hire spend to date |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for d in (1,3,6,8,10,12):
        for p in ('leader','v45'):
            v=result['daily'][d][p];c=v['crops'];a=v['animals']
            lines.append(f"| {d} | {p} | {v['cash']:.1f} | {c['WHEAT']:.1f} | {c['MELON']:.1f} | {c['STRAWBERRY']:.1f} | {a['COW']:.1f} | {a['SHEEP']:.1f} | {a['GOOSE']:.1f} | {v['hire_spend']:.1f} |")
    l=result['daily'][6]['leader'];v=result['daily'][6]['v45']
    lines += ['',f"By six days the leader sells {l['fertilizer_sold']:.0f} fertilizer units versus {v['fertilizer_sold']:.0f} for V45, earning about {l['fertilizer_revenue']:.0f} versus {v['fertilizer_revenue']:.0f}. It spends {l['hire_spend']:.0f} on workers versus {v['hire_spend']:.0f}. The extra early animal accelerates fertilizer cash flow; the leader also pays for more labor. End-of-day-one cash averages {result['daily'][1]['leader']['cash']:.1f} versus {result['daily'][1]['v45']['cash']:.1f}; both invest most starting capital.",'',
        'The representative replay begins with one cow and five wheat, followed next turn by four hire requests, a second cow and three sheep. Wheat is sold and repurchased in small amounts; fertilizer is subsequently sold unit by unit as it is collected. It does not use V45\'s large opening wheat round trip in the inspected games. Market requests may fail when cash or stock is insufficient; economic totals above count successful transactions, not requested orders.','',
        '## Conditional continuation','',
        'The core first-three-day board is identical across all six games, before or just as the first shop is revealed. At six days it remains nearly identical. Later expansion differs substantially: by eight elapsed days the Yarn/Pizza replay has 4 cows and 9 sheep; Ice Cream/Pizza has 8 cows and 3 sheep; Bakery/Brunch has 4 cows, 3 sheep and 4 geese. The Bakery/Pizza replay delays expansion and still has its original five animals at eight days. Shop dependence is plausible, but these observations do not identify the exact rule or distinguish shop, price, opponent and execution effects.','',
        '## What the replay controls do and do not show','',
        '| Episode | First two shops | Leader original final cash | V45 replacement final cash |','|---|---|---:|---:|']
    for r in rows:
        eid=r['episode'];url=f'https://www.kaggle.com/competitions/kaggriculture/leaderboard?submissionId=56156662&episodeId={eid}'
        lines.append(f"| [{eid}]({url}) | {', '.join(r['leader']['snapshots'][6]['shops'])} | {r['leader']['cash'][r['seat']]:.0f} | {r['v45']['cash'][r['seat']]:.0f} |")
    lines += ['',
        'V45 achieves higher final cash in five of these six replacement runs. This does NOT establish that it beats the leader: it faces fixed actions from the leader\'s original opponent, while replacing the leader changes the shared market. The leader is not reacting to V45, and V45 is not playing against the leader. Nor does this isolate the opening from the rest of either policy. The result is a warning against attributing the rank-1 rating to this opening alone.','',
        '## Ideas worth testing','',
        '1. Move one sheep purchase into day one, financing it by staging melon seed purchases. Measure fertilizer cash flow, feed cost and lost early melon revenue together.',
        '2. Advance the wheat-to-strawberry conversion by roughly three days, measuring first production timing and full-season output.',
        '3. Treat the six-day board as the start of a matching continuation, not a drop-in prefix for V45. Different tile locations, crop ages, animals and worker routes make a blind tape splice invalid.',
        '4. Evaluate those mechanisms across all first-shop types and multiple opponents with held-out seeds. A six-day cash balance alone misses the value of earlier-maturing crops and animal production.', '',
        'No agent or submission was changed. This audit identifies a testable alternative opening; it does not claim a proven improvement.','',
        '## Reproduction','',
        '- `scripts/analyze_leader_opening.py`: exact replay validation plus fixed-stream V45 controls.',
        '- `scripts/report_leader_opening.py`: this report and aggregate summary.',
        '- `results/fresh/leader_opening/`: leaderboard/submission snapshots, public replays, detailed action logs and audits.','']
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'docs/leader_opening.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
