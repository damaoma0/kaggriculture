"""Freeze aggregate results and verify all retained research cases."""
from collections import defaultdict
from statistics import mean
from hashlib import sha256
import json
from research_fourth_quadrant import OUT,ROOT,BASE

def main():
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'games').glob('*.json')]
    assert {p:sum(r['phase']==p for r in rows) for p in ('smoke','discovery','confirmation')}==dict(smoke=8,discovery=160,confirmation=96)
    for r in rows:
        assert r['tomato']['errors']==0
        assert r['tomato']['hire_shortfalls']==0 and r['tomato']['lost_plants']==0
        assert r['sheep']['sheep_hire_shortfalls']==0 and r['sheep']['sheep_purchase_shortfalls']==0
    trials=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'calendar_games').glob('*.json')]
    assert len(trials)==12 and all(r['adapter_version']==3 for r in trials)
    expected={'WHEAT':170,'CARROT':150,'TOMATO':80}
    for r in trials:
        assert r['stats']['harvested_units']==expected[r['crop']]
        assert r['stats']['hire_shortfalls']==r['stats']['infeasible_calendar']==r['stats']['budget_declines']==0
    summaries=[]
    for crop in expected:
        rr=[r for r in trials if r['crop']==crop]
        summaries.append(dict(crop=crop,games=len(rr),cash_delta=mean(r['cash_delta'] for r in rr),margin_delta=mean(r['margin_delta'] for r in rr),harvest_units=expected[crop],
            extra_hire_cost=mean(sum(p['extra_hire_cost'] for p in r['stats']['plans'].values()) for r in rr),hires=mean(r['stats']['hire_requests'] for r in rr)))
    paths=[ROOT/'scripts'/name for name in ['research_fourth_quadrant.py','confirm_fourth_quadrant.py','crop_plan_evaluator.py','trial_calendar_expansion.py','report_fourth_quadrant.py','finalize_fourth_quadrant.py']]+[BASE]
    result=dict(retained_mechanism_games=len(rows),paired_main_games=256,retained_calendar_trials=12,physical_plans=32,calendar_results=summaries,
        max_agent_seconds=max(r['max_seconds'] for r in rows),forecast_errors=sum(r['forecast'].get('errors',0) for r in rows),source_sha256={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths},
        notes='No policy promoted or submitted. Rejected calendar debug versions remain only in logs; retained calendar JSON is adapter version3. Grid cells are deliberately stratified and not natural-frequency samples. Seats share a seed and are not independent worlds.')
    (OUT/'final_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
