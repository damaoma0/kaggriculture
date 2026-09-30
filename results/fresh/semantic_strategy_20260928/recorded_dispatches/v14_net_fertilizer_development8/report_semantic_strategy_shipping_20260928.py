"""Read-only shipping scores beside the unchanged original fragility screen.

No qualification release or simulation occurs here. The original independent
artifact audit must pass; a separate technical check never ignores a timeout,
software error, failed source control, or incomplete action/ledger artifact.
"""
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path

from audit_semantic_strategy_gate_20260928 import audit, read, sha, digest

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'


def technical_errors(row, actions):
    errors=[]
    def check(ok,message):
        if not ok: errors.append(message)
    check(row.get('completed') is True,'incomplete')
    check(not row.get('error') and not row.get('errors'),'software_error')
    check(row.get('ledger_verified') is True,'ledger_unverified')
    engine=row.get('engine_audit',{})
    check(engine.get('statuses')==['DONE','DONE'] and engine.get('steps')==720
          and engine.get('final_step')==719,'engine_completion')
    check(engine.get('act_timeout')==1,'engine_timeout_configuration')
    remaining=engine.get('remaining_overage',[])
    check(len(remaining)==2 and all(isinstance(v,(int,float)) and math.isfinite(v)
          and 0<=v<=60 for v in remaining),'engine_overage')
    check(len(actions)==2 and all(len(a)==719 for a in actions),'action_count')
    check([digest(a) for a in actions]==row.get('action_sha256'),'action_hash')
    timings=row.get('timings',[])
    check(len(timings)==2 and all(len(t)==719 and all(math.isfinite(v) and v>=0 for v in t)
          and sum(max(0,v-1) for v in t)<=60 for t in timings),'measured_runtime')
    cash=row.get('cash_by_seat',[]);daily=row.get('daily',[])
    check(len(cash)==2 and len(daily)==2,'ledger_shape')
    if len(cash)==2 and len(daily)==2:
        for seat in range(2):
            check(len(daily[seat])==31,'daily_count')
            for ledger in daily[seat]:
                check(3000+sum(ledger['revenue'].values())-sum(ledger['spend'].values())==ledger['money'],
                      'ledger_arithmetic')
            check(bool(daily[seat]) and daily[seat][-1]['money']==cash[seat],'final_cash')
    health=row.get('live_opponent_internal_health') or {}
    check(not row.get('opponent_health_failure') and all(not v.get('errors',0) for v in health.values()),
          'opponent_software_error')
    for diagnostics in row.get('final_diagnostics',{}).values():
        if isinstance(diagnostics,list):
            check(all(not d.get('executor_errors_cumulative',0) for d in diagnostics if isinstance(d,dict)),
                  'executor_caught_error')
    return sorted(set(errors))


def report(study,candidate,split):
    study=Path(study)
    independent=audit(study,candidate)
    if not independent['audit_pass']:
        raise ValueError('Independent artifact audit failed: '+str(independent['errors']))
    original=read(study/'protocol.json');addendum=read(study/'shipping_score_addendum.json')
    if addendum['original_protocol_sha256']!=sha(study/'protocol.json'):
        raise ValueError('Addendum protocol binding changed')
    if sha(ROOT/addendum['document'])!=addendum['document_sha256']:
        raise ValueError('Addendum document changed')
    if split=='qualification':
        release=read(study/'qualification_release.json')
        if (release.get('candidate_id')!=candidate or release.get('shipping_score_addendum_sha256')
                !=sha(study/'shipping_score_addendum.json')):
            raise ValueError('Qualification release lacks candidate/addendum binding')
    panels={}
    for mode in ('live','recorded'):
        cases=original[split][mode]
        if mode=='recorded' and (study/'selections'/f'{split}.json').exists():
            cases=read(study/'selections'/f'{split}.json')['cases']
        folder=study/'runs'/candidate/split/mode
        paths=[p for p in sorted(folder.glob('*.json')) if not p.name.endswith('.actions.json')]
        observed=Counter(read(p)['case']['id'] for p in paths)
        expected={r['id']:r for r in cases};valid=[];strict=[];failures={};breaks=[];hashes={}
        for path in paths:
            row=read(path);key=row['case']['id'];issues=[]
            actions=read(path.with_suffix('.actions.json'))
            issues.extend(technical_errors(row,actions))
            if expected.get(key)!=row['case'] or observed[key]!=1: issues.append('case_identity')
            if not row.get('source_module_audit'): issues.append('missing_import_audit')
            if mode=='live' and not row.get('eligible'): issues.append('live_ineligible')
            if mode=='recorded':
                control_path=study/'controls'/f'{key}.json'
                control=read(control_path)
                control_issues=technical_errors(control,read(control_path.with_suffix('.actions.json')))
                if control_issues or not control.get('recorded_cash_match'): issues.append('source_control')
                record_path=study/row['case']['file']
                if sha(record_path)!=row['case']['sha256']: issues.append('recording_hash')
                source=json.loads(gzip.decompress(record_path.read_bytes()))
                if control.get('cash_by_seat')!=source['rewards']: issues.append('source_cash')
                tape=source['opp_actions']
                normalized=[a or {'farmer':['PASS'],'hands':[],'market':[]} for a in tape[:719]]
                if actions[1-row['case']['seat']]!=normalized: issues.append('rival_script_changed')
                if row.get('recorded_rival_audit',{}).get('material_command_break'):
                    breaks.append(dict(case=key,margin=row['margin'],**row['recorded_rival_audit']))
                elif not row.get('eligible'): issues.append('unexplained_ineligibility')
            if issues: failures[key]=sorted(set(issues))
            else: valid.append(row)
            if not issues and row.get('eligible'): strict.append(row)
            hashes[key]=dict(result_sha256=sha(path),actions_sha256=sha(path.with_suffix('.actions.json')))
        missing=sorted(set(expected)-set(observed));complete=bool(expected) and not missing and not failures and len(paths)==len(expected)
        wins=sum(row['margin']>0 for row in valid)
        panels[mode]=dict(planned=len(cases),recorded=len(paths),technically_valid=len(valid),wins=wins,
            complete=complete,meets_30_of_40=complete and split=='qualification' and len(cases)==40 and wins>=30,
            mean_margin=sum(r['margin'] for r in valid)/len(valid) if complete else None,
            original_strict_wins=sum(r['margin']>0 for r in strict),original_strict_valid=len(strict),
            original_strict_complete=complete and len(strict)==len(cases),
            material_script_breaks=breaks,technical_failures=failures,missing_cases=missing,hashes=hashes)
    return dict(candidate=candidate,split=split,candidate_manifest_sha256=independent['candidate_manifest_sha256'],
        shipping_score_addendum_sha256=sha(study/'shipping_score_addendum.json'),
        original_independent_audit_pass=True,panels=panels,
        shipping_gate_pass=split=='qualification' and all(p['meets_30_of_40'] for p in panels.values()),
        note='Scripted and responsive scores remain separate. All planned slots retained; original strict artifacts unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True)
    p.add_argument('--study',type=Path,default=STUDY)
    p.add_argument('--split',choices=['development','qualification'],default='development')
    a=p.parse_args();result=report(a.study,a.candidate,a.split)
    out=a.study/'reports'/f'{a.candidate}-{a.split}-shipping-scores.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({mode:{k:v for k,v in row.items() if k not in ['hashes','material_script_breaks']}
                      for mode,row in result['panels'].items()},indent=2))
