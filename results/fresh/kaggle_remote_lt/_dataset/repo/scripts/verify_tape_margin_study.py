"""Final source, control, artifact, and complete-study checks."""
import run_tape_margin_study as S

def main():
    manifest=S.read(S.OUT/'source_manifest.json')
    for rel,h in manifest['sha256'].items():assert S.sha256((S.OUT/'payload'/rel).read_bytes()).hexdigest()==h,rel
    for rel,record in S.read(S.OUT/'reference_manifest.json').items():
        assert S.sha256((S.OUT/rel).read_bytes()).hexdigest()==record['sha256'],rel
    for panel,n in [('development',50),('qualification',48)]:
        audit=S.read(S.OUT/panel/'audit.json');design=S.read(S.OUT/panel/'design.json')
        assert audit['completed']==audit['expected']==n and not audit['errors']
        assert S.sha256((S.OUT/panel/'run_panel.py').read_bytes()).hexdigest()==design['harness_sha256']
        assert audit['checks'].get('exhausted_bank',0)==0
    assert S.read(S.OUT/'functional_checks.json')['policy_sha256']==manifest['sha256']['scripts/value_tape_margin_r4.py']
    attribution=S.read(S.OUT/'forecast_regression_attribution.json')
    assert attribution['actual']['margin_delta']==-2530
    paths=[p for p in S.OUT.rglob('*.json') if p.name not in ('completion_manifest.json','audit_console.json')]
    paths += [S.ROOT/'docs/tape_margin_r4_20260924.md']
    paths += [S.ROOT/'scripts'/f for f in ('value_tape_margin_r4.py','run_tape_margin_study.py','check_tape_margin_r4.py',
        'audit_tape_margin_study.py','diagnose_margin_forecast_regression.py','verify_tape_margin_study.py')]
    summary=dict(completed=True,new_full_games=194,development_candidate_games=50,fresh_full_games=144,
        fresh_worlds=24,fresh_matchups=48,reused_controls=150,exact_action_replays_for_attribution=2,
        frozen_source_verified=True,reference_hashes_verified=True,
        artifacts={str(p.relative_to(S.ROOT)):S.sha256(p.read_bytes()).hexdigest() for p in paths})
    S.write(S.OUT/'completion_manifest.json',summary)
    print(S.json.dumps({k:v for k,v in summary.items() if k!='artifacts'}))

if __name__=='__main__':main()
