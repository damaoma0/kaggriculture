"""Evaluate the frozen continuation promotion rules; missing/invalid games never pass.

Input JSON contains candidate_sha256, opening_repair_sha256, and rows. Each row
has panel (natural/umg), policy, world_id, seat, source_sha256, opponent_sha256,
margin, statuses, states, ledger_verified, timeout_validated, candidate_errors.
Historical rows also have tape_sha256. An official-framework runner must supply
these validation fields; short custom-simulator diagnostics cannot qualify.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def _merge(parent, overlay):
    """Apply a small protocol overlay without mutating its frozen parent."""
    merged=deepcopy(parent)
    for key,value in overlay.items():
        if key in ('inherits', 'parent_protocol_sha256'):
            continue
        if isinstance(value,dict) and isinstance(merged.get(key),dict):
            merged[key]=_merge(merged[key],value)
        else:
            merged[key]=deepcopy(value)
    return merged

def load_protocol(path):
    """Load a standalone protocol or an auditable overlay of a frozen parent."""
    path=Path(path); protocol=read(path); inherited=protocol.get('inherits')
    if not inherited:
        return protocol
    parent_path=path.parent/inherited
    expected=protocol.get('parent_protocol_sha256')
    actual=sha256(parent_path.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError(f'Parent protocol hash mismatch: expected {expected}, got {actual}')
    return _merge(load_protocol(parent_path),protocol)
def score(margin):return float(margin>0)+.5*float(margin==0)

def interval(values,seed):
    v=np.asarray(values,dtype=float);rng=np.random.default_rng(seed)
    samples=v[rng.integers(0,len(v),(10000,len(v)))].mean(axis=1)
    return dict(mean=float(v.mean()),ci95=[float(x) for x in np.quantile(samples,[.025,.975])],world_clusters=len(v))

def evaluate(protocol,data):
    errors=[];rows={};expected={};worlds={str(w['episode']):w for w in protocol['umg_qualification']['worlds']}
    hashes={'candidate':data.get('candidate_sha256'),'mgt_m1':protocol['current_baseline']['sha256'],
            'umg_opening_repaired':data.get('opening_repair_sha256')}
    for k in ('candidate','umg_opening_repaired'):
        if not isinstance(hashes[k],str) or len(hashes[k])!=64:errors.append('Missing frozen source hash: '+k)
    for s in protocol['natural_qualification']['seeds']:
        for seat in (0,1):
            for policy in ('candidate','mgt_m1'):expected[('natural',str(s),seat,policy)]=hashes[policy]
    for eid,w in worlds.items():
        for policy in ('candidate','umg_raw','umg_opening_repaired'):
            expected[('umg',eid,w['seat'],policy)]=w['compact_sha256'] if policy=='umg_raw' else hashes[policy]
    for r in data.get('rows',[]):
        key=r.get('panel'),str(r.get('world_id')),r.get('seat'),r.get('policy')
        if key not in expected:errors.append('Unexpected result '+str(key));continue
        if key in rows:errors.append('Duplicate result '+str(key));continue
        rows[key]=r
        if r.get('source_sha256')!=expected[key]:errors.append('Mixed/unfrozen policy '+str(key))
        if r.get('opponent_sha256')!=protocol['opponent']['sha256']:errors.append('Wrong V56 '+str(key))
        if key[0]=='umg' and r.get('tape_sha256')!=worlds[key[1]]['compact_sha256']:errors.append('Wrong historical tape '+str(key))
        if r.get('statuses')!=['DONE','DONE'] or r.get('states')!=720:errors.append('Incomplete game '+str(key))
        for flag in ('ledger_verified','timeout_validated','official_framework'):
            if r.get(flag) is not True:errors.append('Unvalidated '+flag+' '+str(key))
        if r.get('candidate_errors')!=0:errors.append('Policy/plan error '+str(key))
        if not isinstance(r.get('margin'),(int,float)) or not np.isfinite(r['margin']):errors.append('Invalid margin '+str(key))
    absent=sorted(set(expected)-set(rows))
    if absent:errors.append(f'Missing {len(absent)} of {len(expected)} required results')
    if errors:return dict(status='NOT_READY',passed=False,errors=errors,expected_games=len(expected),received_games=len(rows))
    checks={};metrics={};seed=protocol['statistics']['bootstrap_seed']
    def paired(panel,baseline,minimum=0):
        grouped=defaultdict(list)
        for key,r in rows.items():
            if key[0]!=panel or key[3]!='candidate':continue
            b=rows[(key[0],key[1],key[2],baseline)]
            grouped[key[1]].append((score(r['margin'])-score(b['margin']),r['margin']-b['margin']))
        values=np.array([np.mean(v,axis=0) for _,v in sorted(grouped.items())])
        result={'win_score_gain':interval(values[:,0],seed),'margin_gain':interval(values[:,1],seed)}
        okay=result['win_score_gain']['mean']>=minimum and result['win_score_gain']['ci95'][0]>0 and result['margin_gain']['ci95'][0]>0
        return result,bool(okay)
    grouped=defaultdict(list)
    for key,r in rows.items():
        if key[0]=='natural' and key[3]=='candidate':grouped[key[1]].append((score(r['margin']),r['margin']))
    values=np.array([np.mean(v,axis=0) for _,v in sorted(grouped.items())])
    metrics['v56']={'win_score':interval(values[:,0],seed),'margin':interval(values[:,1],seed)}
    v=metrics['v56'];g=protocol['gates']['v56']
    lower_win=g.get('win_score_ci95_lower_strictly_above',.5)
    lower_margin=g.get('mean_margin_ci95_lower_strictly_above',0)
    checks['v56']=bool(v['win_score']['mean']>=g['minimum_win_score'] and
                       v['win_score']['ci95'][0]>lower_win and v['margin']['ci95'][0]>lower_margin)
    metrics['current_m1'],checks['current_m1']=paired('natural','mgt_m1')
    for base in ('umg_raw','umg_opening_repaired'):
        metrics[base],checks[base]=paired('umg',base,protocol['gates']['original_umg']['minimum_paired_win_score_gain'])
    # These source/physical-validity prerequisites are not inferable from a
    # cash result. Keep them explicit rather than silently declaring success.
    for flag in ('raw_tape_reproduction_verified','repair_frozen_before_run','panels_frozen_before_run',
                 'tape_breakage_review_passed','stress_panel_passed','missing_tape_subset_review_passed'):
        checks[flag]=data.get(flag) is True
    passed=all(checks.values())
    return dict(status='PASS' if passed else 'FAIL',passed=passed,checks=checks,metrics=metrics,
                expected_games=len(expected),received_games=len(rows),scope='Named frozen V56 and historical tape controls; no live UMG-source claim.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path);p.add_argument('--out',type=Path,default=OUT/'promotion_status.json')
    p.add_argument('--protocol',type=Path,default=OUT/'promotion_protocol.json',
                   help='Frozen protocol, or a hash-checked overlay of one.')
    a=p.parse_args()
    path=a.protocol;protocol=load_protocol(path)
    result=evaluate(protocol,read(a.results)) if a.results else dict(status='NOT_RUN',passed=False,
        reason='Executable integrated continuation and validated full qualification panels are not available.',
        blockers=protocol['readiness_blockers'])
    result['protocol_sha256']=sha256(path.read_bytes()).hexdigest()
    a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
