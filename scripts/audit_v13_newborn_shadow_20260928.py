"""Read-only accounting of the hash-bound V13 development live05 shadow."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'results/fresh/semantic_kb115lt2_recovery/v13_newborn_shadow_live05_v1'
OUT=ROOT/'results/fresh/semantic_kb115lt2_recovery/diagnostics/v13_newborn_feed'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((BUNDLE/'manifest.json').read_text())
    source=Path(manifest['source']);original=json.loads(source.read_text())
    capture=BUNDLE/'capture.json.gz';r=json.load(gzip.open(capture,'rt'))
    assert r['verified'] and r['own_actions_matched']==192
    assert r['manifest_sha256']==sha(BUNDLE/'manifest.json')
    assert r['source_sha256']==sha(source)
    assert r['actions_sha256']==sha(source.with_suffix('.actions.json'))
    c=r['captures'];day=7;seat=original['case']['seat']
    core=next(x for x in c['cores'] if x['day']==day)
    dawn=next(x for x in c['dawn_plans'] if x['day']==day);tier=dawn['final_tier']
    feeds=[]
    for u,route in tier['routes'].items():
        for i,item in enumerate(route['items']):
            for op,mand in zip(item.get('ops',[]),item.get('mand',[])):
                if op[0]=='FEED':feeds.append(dict(unit=int(u),tile=item['tile'],mandatory=mand,item_index=i))
    assert len(feeds)==11 and sum(x['mandatory'] for x in feeds)==7
    target_owners={str(tile):[x['unit'] for x in feeds if x['tile']==tile] for tile in (5,15,36)}
    assert target_owners=={'5':[9],'15':[9],'36':[9]}
    for tile in ('5','15','36'):
        assert any(o['c']==['FEED'] and o['m'] for o in core['rec_before'][tile]['ops'])
    assert not core['retirements'] and not dawn['retirements_after']
    dispatch=[x for x in c['dispatches'] if x['day']==day]
    actual_feeds=[dict(unit=x['unit'],hour=x['hour'],tile=x['position'][1]*10+x['position'][0],
        wheat_before=x['inventory'].get('WHEAT',0)) for x in dispatch if x['command']==['FEED']]
    assert len(actual_feeds)==9 and not any(x['tile'] in (5,15) for x in actual_feeds)
    assert {x['tile'] for x in feeds if not x['mandatory']}<={x['tile'] for x in actual_feeds}
    unit9=[dict(hour=x['hour'],position=x['position'],inventory=x['inventory'],shed_left=x['shed_left_before'],
        cursor_before=[x['route_before']['k'],x['route_before']['sub']],command=x['command'],
        cursor_after=[x['route_after']['k'],x['route_after']['sub']],new_log=x['new_log'],checks=x['checks'])
        for x in dispatch if x['unit']==9]
    assert unit9[0]['command']==['PICKUP','WHEAT',1]
    assert any(log[2]=='wheat_retry_reserved_stock' and log[4]=='0' for x in unit9 for log in x['new_log'])
    skips=[log for x in unit9 for log in x['new_log'] if log[2]=='skip' and log[4]=='FEED']
    assert [(x[0]%24,x[3]) for x in skips]==[(22,15),(23,5)]
    market=[]
    for x in c['markets']:
        if x['day']!=day or x['hour']>3:continue
        snapshot=next(y for y in c['snapshots'] if y['step']==x['step'])
        pickup=sum(int(a[2]) for a in [snapshot['command']['farmer']]+snapshot['command']['hands']
            if a[:2]==['PICKUP','WHEAT'])
        actual_carried=sum(inv.get('WHEAT',0) for inv in x['inventories'])
        market.append(dict(hour=x['hour'],money=x['money'],observed_shed_wheat=x['shed'].get('WHEAT',0),
            observed_carried_wheat=actual_carried,market_carried_argument=x['carried'].get('WHEAT',0),
            issued_wheat_pickups=pickup,market_demand=x['demand'].get('WHEAT',0),
            raw_wheat_gap=x['demand'].get('WHEAT',0)-x['carried'].get('WHEAT',0)-x['shed'].get('WHEAT',0),
            wheat_buy=x['wheat_buy_before'],wheat_bought_before=x['wheat_bought_before'],
            wheat_bought_after=x['wheat_bought_after'],raw_market_orders=x['orders'],final_market_orders=snapshot['command']['market'],
            pending_route_claims=x['route_claims']))
    assert market[1]['issued_wheat_pickups']==4 and market[1]['observed_shed_wheat']==4
    assert market[1]['market_carried_argument']==4 and market[1]['observed_carried_wheat']==0
    assert market[1]['raw_wheat_gap']==5
    before,after=original['daily'][seat][day:day+2]
    ledger={k:{p:after[k].get(p,0)-before[k].get(p,0) for p in sorted(set(after[k])|set(before[k]))
        if after[k].get(p,0)!=before[k].get(p,0)} for k in ('spend','revenue','sold_units','physical')}
    assert before['money']+sum(ledger['revenue'].values())-sum(ledger['spend'].values())==after['money']
    before_farm=original['diagnostics'][seat][day]['current_observation']['own_farm']
    after_farm=original['diagnostics'][seat][day+1]['current_observation']['own_farm']
    animals=[]
    for tile in (5,15,36):
        a=before_farm['tiles'][tile//10][tile%10];b=after_farm['tiles'][tile//10][tile%10]
        animals.append(dict(tile=tile,before=a,after=b))
    assert all(not animals[i]['after'].get('animal') for i in (0,1))
    result=dict(scope='DECLARED_DEVELOPMENT_LIVE05_EXACT_SHADOW_NO_INTERVENTION',case=original['case'],day=day,
        hashes={str(p):sha(p) for p in (Path(__file__),capture,BUNDLE/'manifest.json',BUNDLE/'driver.py',source,source.with_suffix('.actions.json'))},
        candidate_manifest_sha256=r['candidate_manifest_sha256'],verified_prefix_calls=r['own_actions_matched'],
        final_ledger_checks=r['final_ledger_checks'],dawn_checks=r['dawn_checks'],
        runtime=dict(max_call_seconds=max(x['seconds'] for x in r['call_timings']),sum_call_seconds=sum(x['seconds'] for x in r['call_timings']),
            remaining_overage_bank=r['remaining_overage_bank'],instrumentation_seconds=r['clock']['capture_seconds']),
        targets=animals,core_target_rec={t:core['rec_before'][t] for t in ('5','15','36')},
        feed_assignments=feeds,actual_feeds=actual_feeds,unit9_route=tier['routes']['9'],unit9_execution=unit9,
        market_early=market,dawn_money=before['money'],next_dawn_money=after['money'],day_ledger=ledger,
        observed_invariants=dict(mandatory_feeds_planned=7,optional_feeds_planned=4,mandatory_feeds_executed=5,
            optional_feeds_executed=4,initial_shed_wheat=3,wheat_bought=6,wheat_picked=9,
            mandatory_feeds_skipped_for_local_stock=2,retirement_map_empty=True),
        limitations=['No altered command, source, policy, execution or profit counterfactual.',
            'Current capture proves lost feed ownership/material prerequisites, not that every dawn job can be financed.',
            'Available nine wheat could cover seven mandatory feeds; preserving all eleven feeds, nine hires and seed purchases needs additional funding or changed admission.',
            'Original natural full-season outcome remains untouched. Fresh smoke cases did not enter this replay or any fit.'])
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'audit.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),sha256=sha(path),verified=True,feed_owner=target_owners,observed=result['observed_invariants'])))


if __name__=='__main__':main()
