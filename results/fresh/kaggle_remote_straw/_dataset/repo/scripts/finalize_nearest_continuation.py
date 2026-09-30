"""Cross-check final artifacts after corpus bookkeeping corrections."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,indent=2),encoding='utf-8')

def main():
    data=read(OUT/'dataset_primary.json');analysis=read(OUT/'local_transfer_analysis.json')
    transfer=read(OUT/'local_transfer.json');audit=read(OUT/'independent_audit.json')
    plans=read(OUT/'pilot/certificate_audit.json');windows=read(OUT/'nearest_donor_windows.json')
    assert data['verified_games']==86 and not data['failures']
    games={g['episode']:g for g in data['games']}
    for row in analysis['rows']:
        game=games[row['episode']]
        actual=next(s['output'] for s in game['segments'] if s['days'][0]==row['day'])
        assert actual==row['actual'],(row['episode'],row['day'])
    for case in transfer['cases']:
        assert case['checkpoint']==games[case['episode']]['checkpoints'][str(case['day'])]
    assert len(analysis['rows'])==430 and len(transfer['cases'])==10
    assert plans['passed'] and plans['plans_checked']==20 and plans['all_solver_optimal']
    assert windows['cases_completed']==10 and not windows['failures']
    assert all(r['donor_raw_matches_compact_window'] for r in windows['results'])
    assert audit['identity']['all_compact_hash_and_reward_match']
    baseline=sha256((ROOT/'agents/mgt_m1.py').read_bytes()).hexdigest()
    assert baseline=='1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'
    # Only bookkeeping and chart formatting changed since the analysis run.
    # Checkpoints, production labels and all ten plan inputs are asserted above.
    analysis['summary']['source_sha256'][str((OUT/'dataset_primary.json').relative_to(ROOT))]=sha256((OUT/'dataset_primary.json').read_bytes()).hexdigest()
    analysis['summary']['finalization']='Rebuilt corpus animal-purchase counters; all430 analysis labels and ten complete checkpoint inputs rechecked unchanged. Plot-only formatting changed after the original analysis code hash.'
    save(OUT/'local_transfer_analysis.json',analysis)
    files=[ROOT/'docs/nearest_umg_continuation_research.md',
        *[ROOT/'scripts'/n for n in ('analyze_own_umg_tape_gaps.py','research_nearest_continuation.py','compile_nearest_continuation_plans.py','audit_nearest_continuation.py','audit_tape_gap_pilot.py','test_nearest_donor_windows.py','finalize_nearest_continuation.py')],
        *[OUT/n for n in ('dataset_primary.json','local_transfer_analysis.json','local_transfer.json','local_transfer_protocol.json','independent_audit.json','primary_candidates.json','nearest_donor_windows.json','zero_difference_economics.json','pilot/certificate_audit.json')]]
    result=dict(complete=True,verified_games=86,checkpoint_rows=430,missing_prefix_rows=422,
        resource_checked_plan_variants=20,engine_action_transfer_controls=10,
        changed_competition_agent=False,submitted=False,baseline_sha256=baseline,
        scope='Nearest whole-farm production-target research and diagnostic windows. Synthesized aggregate plans have not been executed as a full-season adaptive agent.',
        sha256={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files})
    save(OUT/'completion_manifest.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='sha256'},indent=2))

if __name__=='__main__':main()
