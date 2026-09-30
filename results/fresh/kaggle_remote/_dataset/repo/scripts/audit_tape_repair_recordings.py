"""Compare frozen R3 against hash-verified earlier replay controls."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import statistics
from audit_tape_repair_panel import read, digest, distribution, ROOT, STUDY

OLD = ROOT/'results/fresh/value_tape_wide_20260923_01a0'


def summarize(rows, reference):
    values=[r['candidate']-r[reference] for r in rows]
    return dict(n=len(rows),better=sum(v>0 for v in values),same=sum(v==0 for v in values),
                worse=sum(v<0 for v in values),margin_change=distribution(values))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');args=ap.parse_args()
    folder=STUDY/'r3record42';design=read(folder/'design.json');manifest=read(folder/'source_manifest.json')
    old_sources=read(OLD/'source_manifest.json')['sha256']
    for name, expected in manifest['sha256'].items():
        assert sha256((folder/'payload'/name).read_bytes()).hexdigest()==expected,name
    assert all(manifest['sha256'][k]==v for k,v in old_sources.items())
    assert sha256((folder/'run_panel.py').read_bytes()).hexdigest()==design['harness_sha256']
    assert manifest['sha256']['scripts/value_tape_repair_r3.py']==design['policy_sha256']
    old_hashes=read(OLD/'results_manifest.json')['sha256'];checks=Counter();rows=[];seconds=[];banks=[];funnel=Counter()
    def old_read(name):
        path=OLD/name
        assert sha256(path.read_bytes()).hexdigest()==old_hashes[name],name
        checks['reference_files_verified']+=1
        return read(path) if path.suffix=='.json' else None
    for spec in design['specs']:
        case=spec['id'];target=folder/'arms'/f'{case}-candidate.json'
        if not target.exists():
            assert args.partial,case
            continue
        candidate=read(target)
        base=old_read(f'arms/{case}-baseline.json');v9=old_read(f'arms/{case}-candidate.json');control=old_read(f'arms/{case}-recording.json')
        old_read(f'recordings/{spec["episode"]}.json.gz')
        assert control['completed'] and control['reproduced_exactly'] and all(all(x['equal']) for x in control['observation_checks'])
        checks['exact_source_reconstructions_verified']+=1
        assert candidate['completed'] and candidate['ledger_verified'] and candidate['spec']==spec
        for s,econ in enumerate(candidate['economics']):
            assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==candidate['cash_by_seat'][s]
        actions=read(folder/'actions'/f'{case}-candidate.json')
        assert all(len(a)==719 for a in actions) and digest(actions)==candidate['actions_sha256']
        assert digest([[actions[s][t] for s in range(2)] for t in range(288)])==candidate['prefix_sha256']
        assert base['prefix_sha256']==v9['prefix_sha256']==candidate['prefix_sha256']
        if candidate['actions_sha256']==v9['actions_sha256']:
            checks['candidate_v9_full_action_hashes_exact']+=1
        if spec.get('anchored'):
            assert control['actions_sha256']==base['actions_sha256']
            checks['exact_native_anchor_controls']+=1
        if candidate['selected']==[None,None,None]:
            assert candidate['actions_sha256']==base['actions_sha256']
            checks['native_no_intervention_exact']+=1
        assert not candidate['measured_bank_exhausted']
        assert not any(('error' in k.lower() or 'exception' in k.lower()) and v for k,v in candidate['native_telemetry'].items())
        expected_bank=60-sum(max(0,t['seconds']-1) for t in candidate['timings'])
        assert abs(expected_bank-candidate['remaining_overage_seconds'])<1e-8
        banks.append(candidate['remaining_overage_seconds']);seconds.extend(t['seconds'] for t in candidate['timings'] if t['searched'])
        decisions=[read(folder/'decisions'/f'{case}-candidate-d{d}.json') for d in (12,15,18)]
        assert [d['selected'] for d in decisions]==candidate['selected']
        for d in decisions:
            assert d['planner_sha256']==design['policy_sha256']
            checks['decisions']+=1;funnel['timeouts']+=d['timed_out'];funnel['selected']+=d['selected'] is not None
            if d['selected'] is not None:
                chosen=next(c for c in d['candidates'] if c['route']==d['selected'])
                assert chosen['admitted'] and chosen['fully_evaluated'] and not chosen['protection_failures']
            if d.get('repair_validation'):funnel['repair_validated']+=1
            if isinstance(d['selected'],list):
                v=d['repair_validation'];assert v['admitted'] and v['fully_evaluated'] and not v['timed_out']
                assert len(v['predictions'])==16 and len(v['stress'])==16
                assert not v['missing_cohorts'] and not v['protection_failures']
                assert v['stress_minimum_margin']>=-v['loss_budget']
                funnel['repair_selected']+=1
        broken={a:r['replay_divergence']['material_command_break'] for a,r in [('baseline',base),('v9',v9),('candidate',candidate)]}
        row=dict(id=case,episode=spec['episode'],anchored=spec.get('anchored',False),opponent=spec['opponent'],rating=spec['rating'],
                 baseline=base['margin'],v9=v9['margin'],candidate=candidate['margin'],
                 delta_v9=candidate['margin']-v9['margin'],delta_baseline=candidate['margin']-base['margin'],
                 own_cash_delta_v9=candidate['cash']-v9['cash'],rival_cash_delta_v9=candidate['rival_cash']-v9['rival_cash'],
                 selected=candidate['selected'],broken=broken,eligible=not any(broken.values()),
                 repair_execution=candidate['repair_execution'])
        rows.append(row)
    result=dict(complete=len(rows)==len(design['specs']),planned_games=len(design['specs']),games=len(rows),
                policy_sha256=design['policy_sha256'],frozen_files_verified=len(manifest['sha256']),checks=dict(checks),funnel=dict(funnel),
                remaining_bank=distribution(banks),reveal_seconds=distribution(seconds),groups={},rows=rows,
                excluded=[r['id'] for r in rows if not r['eligible']],
                limitation='Previously inspected recordings, frozen opponent commands, not live counterfactual policies. Same >40 additional failed-command exclusion as V9, applied to baseline/V9/R3 jointly. Passing this screen does not prove policy-level validity.')
    for label,predicate in [('native_anchors',lambda r:r['anchored']),('rated_all_diagnostic',lambda r:not r['anchored']),('rated_without_material_command_break',lambda r:not r['anchored'] and r['eligible'])]:
        selected=[r for r in rows if predicate(r)]
        result['groups'][label]={ref:summarize(selected,ref) for ref in ('v9','baseline')}
    destination=folder/('audit_partial.json' if args.partial else 'audit.json')
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':main()
