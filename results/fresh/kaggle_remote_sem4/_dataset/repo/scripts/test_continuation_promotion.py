"""Synthetic gate regressions. These are NOT game/qualification results."""
from copy import deepcopy
import json
from check_continuation_promotion import OUT,read,load_protocol,evaluate

def main():
    p=read(OUT/'promotion_protocol.json');candidate='a'*64;repair='b'*64
    data=dict(candidate_sha256=candidate,opening_repair_sha256=repair,rows=[])
    for flag in ('raw_tape_reproduction_verified','repair_frozen_before_run','panels_frozen_before_run',
                 'tape_breakage_review_passed','stress_panel_passed','missing_tape_subset_review_passed'):data[flag]=True
    def row(panel,world,seat,policy,digest,tape=None):
        return dict(panel=panel,world_id=world,seat=seat,policy=policy,source_sha256=digest,tape_sha256=tape,
            opponent_sha256=p['opponent']['sha256'],margin=100 if policy=='candidate' else -100,
            statuses=['DONE','DONE'],states=720,ledger_verified=True,timeout_validated=True,official_framework=True,candidate_errors=0)
    for seed in p['natural_qualification']['seeds']:
        for seat in (0,1):
            data['rows']+=[row('natural',seed,seat,'candidate',candidate),row('natural',seed,seat,'mgt_m1',p['current_baseline']['sha256'])]
    for w in p['umg_qualification']['worlds']:
        for policy,digest in [('candidate',candidate),('umg_raw',w['compact_sha256']),('umg_opening_repaired',repair)]:
            data['rows'].append(row('umg',w['episode'],w['seat'],policy,digest,w['compact_sha256']))
    checks=[]
    assert evaluate(p,data)['status']=='PASS';checks.append('complete synthetic overwhelming improvement passes')
    d=deepcopy(data);d['rows'].pop();assert evaluate(p,d)['status']=='NOT_READY';checks.append('missing game cannot pass')
    d=deepcopy(data);d['rows'].append(d['rows'][0]);assert evaluate(p,d)['status']=='NOT_READY';checks.append('duplicate game cannot inflate results')
    d=deepcopy(data);d['rows'][0]['source_sha256']='c'*64;assert evaluate(p,d)['status']=='NOT_READY';checks.append('mixed candidate build rejected')
    d=deepcopy(data);d['rows'][0]['candidate_errors']=1;assert evaluate(p,d)['status']=='NOT_READY';checks.append('failed candidate game not silently excluded')
    d=deepcopy(data)
    for r in d['rows']:r['margin']=100
    assert evaluate(p,d)['status']=='FAIL';checks.append('winning without outperforming controls fails')
    d=deepcopy(data);d['rows'][0]['timeout_validated']=False;assert evaluate(p,d)['status']=='NOT_READY';checks.append('untimed diagnostic cannot qualify')
    # Synthetic only: 100/128 clustered wins is 78.125%.  It clears the v1
    # 60% mean / >50% lower-CI improvement gate, yet cannot clear the 3000
    # target's 80.831767...% mean and lower-CI requirements.
    v2=load_protocol(OUT/'promotion_protocol_3000_v2.json')
    assert evaluate(v2,data)['status']=='PASS';checks.append('synthetic all-win result clears 3000 numeric gate')
    d=deepcopy(data)
    losing=set(p['natural_qualification']['seeds'][100:])
    for r in d['rows']:
        if r['panel']=='natural' and r['policy']=='candidate' and r['world_id'] in losing:
            r['margin']=-100
    old=evaluate(p,d);new=evaluate(v2,d)
    assert old['checks']['v56'] is True and new['checks']['v56'] is False
    checks.append('synthetic 78.125% V56 score clears v1 numeric gate but fails 3000 gate')
    # 108/128 = 84.375% exceeds the 3000 mean threshold, while its clustered
    # lower interval remains below it. This catches an accidental hard-coded
    # v1 (>0.5) lower-CI threshold in the v2 evaluation path.
    d=deepcopy(data)
    losing=set(p['natural_qualification']['seeds'][108:])
    for r in d['rows']:
        if r['panel']=='natural' and r['policy']=='candidate' and r['world_id'] in losing:
            r['margin']=-100
    old=evaluate(p,d);new=evaluate(v2,d)
    assert old['checks']['v56'] is True
    assert new['metrics']['v56']['win_score']['mean'] > v2['gates']['v56']['minimum_win_score']
    assert new['metrics']['v56']['win_score']['ci95'][0] < v2['gates']['v56']['win_score_ci95_lower_strictly_above']
    assert new['checks']['v56'] is False
    checks.append('synthetic 84.375% V56 score fails v2 lower-CI threshold despite clearing its mean')
    result=dict(passed=True,synthetic_only=True,gameplay_evidence=False,checks=checks)
    (OUT/'promotion_gate_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
