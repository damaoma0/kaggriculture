"""Observed paired output changes for the verified September 17 leader corpus."""
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from analyze_umg_shop_output_changes import PRODUCTS, SHOP_PRODUCTS, DAYS, summary, label

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/fresh/leader_segments'
OUT = ROOT / 'results/fresh/production_continuation'
LEADERS = {
    56266758: 'UMG',
    56216119: 'Majkel1337',
    56156662: 'Majkel1337 (earlier submission)',
    56254996: 'M & M & P & Q',
}
NAMES = {56266758:'Unknown Mother-Goose',56216119:'Majkel1337',56156662:'Majkel1337',56254996:'M & M & P & Q'}

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def bounds(s):
    if not s['n']:
        return '—'
    def num(v):
        return '0' if v == 0 else f'{v:+g}'
    return num(s['min']) if s['min'] == s['max'] else f"{num(s['min'])}…{num(s['max'])}"

def matrices(events):
    return [dict(day=d, shop=shop, n=len(rows), unique_episodes=len({r['episode'] for r in rows}),
                 submissions=dict(Counter(str(r['submission']) for r in rows)),
                 products={p:summary([r['delta'][p] for r in rows]) for p in PRODUCTS})
            for d in DAYS for shop in SHOP_PRODUCTS
            for rows in [[e for e in events if e['day']==d and e['shop']==shop]]]

def tables(groups):
    lines=[]
    for day in DAYS:
        lines += [f'### Day {day}: days {day}–{day+2} minus {day-3}–{day-1}', '',
                  '| New shop | n | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for g in groups:
            if g['day']==day:
                lines.append('| '+label(g['shop'])+' | '+str(g['n'])+' | '+' | '.join(bounds(g['products'][p]) for p in PRODUCTS)+' |')
        lines.append('')
    return lines

def main():
    sample=read(SOURCE/'sample.json')['sample']
    identity={e['id']:e['agents'] for e in sample}
    events=[]
    counts=Counter()
    hashes={}
    for path in sorted(SOURCE.glob('segments-*.json')):
        g=read(path)
        eid=g['episode']
        raw=ROOT/f'data/leaders_20260917/episode-{eid}-replay.json'
        digest=sha256(raw.read_bytes()).hexdigest()
        assert digest==g['replay_sha256'], eid
        hashes[str(eid)]=digest
        for seat in g['seats']:
            sub=identity[eid][seat['seat']]['sub']
            if sub not in LEADERS:
                continue
            assert seat['team']==NAMES[sub]
            assert seat['reward']==identity[eid][seat['seat']]['reward']
            assert len(seat['segments'])==10
            counts[sub]+=1
            for d in DAYS:
                s=d//3
                old=g['shops_by_segment'][str(s-1)]
                new=g['shops_by_segment'][str(s)]
                assert new[:-1]==old and len(new)==s
                before={p:seat['segments'][s-1]['physical'].get('produced:'+p,0) for p in PRODUCTS}
                after={p:seat['segments'][s]['physical'].get('produced:'+p,0) for p in PRODUCTS}
                assert all(x>=0 for x in list(before.values())+list(after.values()))
                events.append(dict(episode=eid,seat=seat['seat'],submission=sub,leader=LEADERS[sub],day=d,
                    shop=new[-1],previous_shops=old,before=before,after=after,
                    delta={p:after[p]-before[p] for p in PRODUCTS}))
    assert counts==Counter({56266758:30,56216119:30,56156662:8,56254996:8}), counts
    assert len({(e['episode'],e['seat'],e['day']) for e in events})==len(events)
    previous=read(OUT/'shop_output_changes.json')['events']
    for e in previous:
        match=[r for r in events if r['episode']==e['episode'] and r['submission']==56266758 and r['day']==e['day']]
        assert len(match)==1 and match[0]['delta']==e['delta'] and match[0]['shop']==e['shop']
    pooled=matrices(events)
    separated={str(sub):matrices([r for r in events if r['submission']==sub]) for sub in LEADERS}
    result=dict(source_snapshot='2026-09-17',measure='Calendar 3-day harvested/collected units after minus before; not sales or standing crops.',
                counts=dict(counts),leader_names=LEADERS,products=PRODUCTS,shops=list(SHOP_PRODUCTS),days=DAYS,
                unique_matches=len({e['episode'] for e in events}),farm_trajectories=sum(counts.values()),
                events=events,pooled=pooled,by_submission=separated,replay_sha256=hashes,
                verification={'raw_hashes_checked':len(hashes),'prior_umg_events_matched':len(previous),'original_engine_validation':'All 720 states of both seats matched by analyze_leader_segments.py before the source ledgers were saved.'})
    (OUT/'leader_shop_matrices.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Leader production-change matrices','',
        'Source: September 17 downloaded leader study. These are historical recorded versions, not a claim about current rankings.', '',
        '| Leader | Submission | Farm trajectories |','|---|---:|---:|']
    lines += [f'| {LEADERS[sub]} | {sub} | {counts[sub]} |' for sub in LEADERS]
    lines += ['',f"**{sum(counts.values())} farm trajectories from {result['unique_matches']} unique matches; {len(events)} reveal observations.** Two included leaders in the same match share a shop reveal and are not independent matches.", '',
        '**Cell = observed minimum…maximum of the within-game change.** n is farm observations in the row, shared by all nine products. 0 means observed zero movement; — means no sample. Single-sample cells are observations, not established intervals.', '',
        'Change = actual harvested/collected units on days D–D+2 minus days D−3–D−1. Purchases and sales are excluded; fertilizer is collected fertilizer. Full calendar windows are used. Groups pool different prior shops, crop ages, opponents and leader policies. These are descriptive envelopes, not causal shop effects or confidence intervals. Marginal product ranges need not occur together in a single feasible production plan.', '',
        '## Combined leaders','']+tables(pooled)
    for sub in LEADERS:
        lines += [f'## {LEADERS[sub]} — {sub} ({counts[sub]} trajectories)','']+tables(separated[str(sub)])
    lines += ['## Verification','',f"Checked all {len(hashes)} raw replay hashes against the previously exact-engine-validated ledgers; matched all {len(previous)} existing UMG reveal observations exactly. Each reveal extends the previous ordered shop list by one shop. Episode, seat, submission and day identify each observation uniquely.", '',
        'Source ledgers: `results/fresh/leader_segments/segments-*.json`; seat/submission identities: `results/fresh/leader_segments/sample.json`; original validation: `scripts/analyze_leader_segments.py`. Full paired observations, medians, means, group composition and replay hashes are in `results/fresh/production_continuation/leader_shop_matrices.json`.']
    report='\n'.join(lines)+'\n'
    (ROOT/'docs/leader_shop_matrices.md').write_text(report,encoding='utf-8')
    (OUT/'leader_shop_matrices_compact.md').write_text('\n'.join(tables(pooled)),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['counts','unique_matches','farm_trajectories','verification']}))
    print('\n'.join(tables(pooled)))

if __name__=='__main__':
    main()
