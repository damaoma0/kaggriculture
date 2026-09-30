"""Static held-out training-state sensitivity; never runs a game or gate world."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import semantic_strategy_policy_20260928 as P

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'


def main():
    model=json.loads((STUDY/'causal_daily_rows.json').read_text())
    split=json.loads((STUDY/'fidelity_v2/report.json').read_text())['split']
    held=set(split['heldout_episodes'])
    train=[r for r in model['rows'] if int(r['meta']['episode']) not in held]
    test=[r for r in model['rows'] if int(r['meta']['episode']) in held]
    common=dict(forecast=False,economics_weight=0,land_limit=3)
    base=P.SemanticStrategyPolicy({'rows':train},common)
    reserve=P.SemanticStrategyPolicy({'rows':train},dict(common,wheat_reserve_days=6,wheat_reserve_max_add=4))
    cache={};records=[]
    for r in test:
        source=ROOT/r['meta']['source']
        if str(source) not in cache:
            trace=json.load(gzip.open(source,'rt',encoding='utf-8'))
            cache[str(source)]={int(x['day']):x for x in trace['daily']}
        original=cache[str(source)][r['day']]
        obs=dict(day=r['day'],hour=0,step=24*r['day'],player=0,
            farms=[deepcopy(original['farm']),dict(tiles=[[None]*10 for _ in range(10)],money=0,unlocked_quadrants=['NW'])],
            private=deepcopy(original['private']),town={'unlocked_shops':original['shops']},
            market=dict(prices={p:P._MARKET[p][0] for p in P.PRODUCTS},inventory={p:10000 for p in P.PRODUCTS}))
        a=base.propose(obs)['today'];b=reserve.propose(obs)['today']
        displaced={sp:a['plant_counts'].get(sp,0)-b['plant_counts'].get(sp,0) for sp in P.CROPS if sp!='WHEAT'}
        displaced.update({sp:a['animal_add_counts'].get(sp,0)-b['animal_add_counts'].get(sp,0) for sp in P.ANIMALS})
        records.append(dict(episode=int(r['meta']['episode']),day=r['day'],
            observed_land=len(original['farm']['unlocked_quadrants']),
            actual_wheat=r['target'].get('plant_counts',{}).get('WHEAT',0),
            base_wheat=a['plant_counts'].get('WHEAT',0),reserve_wheat=b['plant_counts'].get('WHEAT',0),
            requested_extra=b['wheat_reserve_extra_requested'],base_free=a['modeled_free_tiles'],
            base_hands=a['hands'],reserve_hands=b['hands'],
            base_capital=a['estimated_capital_cost'],reserve_capital=b['estimated_capital_cost'],
            displaced={s:n for s,n in displaced.items() if n}))
    groups={}
    for name,rows in [('all',records),('land_at_most3',[r for r in records if r['observed_land']<=3]),
                      ('D6_11',[r for r in records if 6<=r['day']<=11]),
                      ('D12_18',[r for r in records if 12<=r['day']<=18]),
                      ('D19_25',[r for r in records if 19<=r['day']<=25])]:
        displaced=Counter()
        for r in rows:displaced.update(r['displaced'])
        groups[name]=dict(rows=len(rows),requests=sum(r['requested_extra']>0 for r in rows),
            requests_at_cap=sum(r['requested_extra']==4 for r in rows),
            requested_extra=sum(r['requested_extra'] for r in rows),
            accepted_extra=sum(r['reserve_wheat']-r['base_wheat'] for r in rows),
            actual_wheat=sum(r['actual_wheat'] for r in rows),base_wheat=sum(r['base_wheat'] for r in rows),
            reserve_wheat=sum(r['reserve_wheat'] for r in rows),displaced=dict(displaced),
            extra_hand_days=sum(r['reserve_hands']-r['base_hands'] for r in rows),
            extra_capital=sum(r['reserve_capital']-r['base_capital'] for r in rows))
    out=dict(purpose='Offline training holdout sensitivity; not gameplay evidence',
        feature_limits=['Exact own farm/private stock; absent market/rival replaced by base prices,inventory10000,empty rival.',
                        'Independent one-day predictions from actual held-out states; additions do not carry to future rows.',
                        'Reserve horizon includes exactly six feed nights, clipped at day28.',
                        'No gate cases; same fixed twenty training episodes as fidelity_v2.'],
        policy_sha256=hashlib.sha256((ROOT/'scripts/semantic_strategy_policy_20260928.py').read_bytes()).hexdigest(),
        configs=dict(base=common,reserve=dict(common,wheat_reserve_days=6,wheat_reserve_max_add=4)),
        summary=groups,rows=records)
    path=STUDY/'wheat_reserve_training_diagnostic_v2.json'
    path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(path),summary=groups),indent=2))


if __name__=='__main__':main()
