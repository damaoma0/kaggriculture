"""Final checks and artifact hashes for the completed local opportunity audit."""
import tape_opportunity_audit as A

def main():
    for path,h in A.read(A.OUT/'input_manifest.json')['sha256'].items():
        assert A.sha256(A.Path(path).read_bytes()).hexdigest()==h,path
    audit=A.read(A.OUT/'audit.json')
    assert len(audit['cases'])==8 and audit['completed']==133
    assert all(c['n']==c['expected'] for c in audit['cases'])
    confirmation=A.read(A.OUT/'confirmation_design.json')['jobs']
    assert len(confirmation)==25
    paths=list((A.OUT/'arms').glob('*.json'));assert len(paths)==158
    for p in paths:
        arm=A.read(p);assert arm['completed'] and arm['prefix_verified'] and arm['ledger_verified'],p
        actions=A.read(A.OUT/'actions'/f'{p.stem}-candidate.json')
        assert [len(a) for a in actions]==[719,719],p
        assert A.digest(actions)==arm['actions_sha256'],p
        for seat in range(2):
            e=arm['economics'][seat]
            assert 3000+sum(e['revenue'].values())-sum(e['spend'].values())==arm['cash_by_seat'][seat],p
    for case,cid,continuation in confirmation:
        assert (A.OUT/'arms'/f'{case}-{cid}-{continuation}.json').exists()
    for c in audit['cases']:
        assert (A.OUT/'attribution'/f"{c['case']}.json").exists()
        assert c['best']['delta']==c['best_original_plus_repairs']['delta']
    artifacts=[p for p in A.OUT.rglob('*.json') if p.name not in ('completion_manifest.json','progress.json')]
    artifacts += [A.ROOT/'docs/tape_opportunity_audit_20260924.md']
    artifacts += [A.ROOT/'scripts'/f for f in ('tape_opportunity_audit.py','report_tape_opportunity_audit.py',
        'attribute_tape_opportunity_forecasts.py','ablate_tape_own_cash_gate.py','verify_tape_opportunity_audit.py')]
    summary=dict(completed=True,full_games=158,native_continuation_branches=133,later_replanning_games=25,
        native_controls_exact=8,ledger_checks=316,action_stream_checks=316,attribution_worlds=8,
        input_freeze_unchanged=True,files={str(p.relative_to(A.ROOT)):A.sha256(p.read_bytes()).hexdigest() for p in artifacts})
    A.write(A.OUT/'completion_manifest.json',summary)
    print(A.json.dumps({k:v for k,v in summary.items() if k!='files'}))

if __name__=='__main__':main()
