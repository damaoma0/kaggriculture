"""Economic admission after cohort protection, without matching feed counts.

Feeding fewer times is not itself evidence of starvation. The exact projected
cohort survival check remains mandatory, and the full-season value simulation
charges for any resulting loss of yield. This policy was developed using only
the historical diagnostic/validation replays, before inspecting live candidate
outcomes. The live seeds are its small independent confirmation panel.
"""
from copy import deepcopy
import statistics


def cohort_policy(decision):
    decision=deepcopy(decision)
    decision['strict_selected']=decision['selected']
    allowed=[]
    for row in decision['candidates']:
        unresolved=[f for f in row['protection_failures'] if 'lost_feed_actions' not in f]
        row['cohort_admitted']=(not unresolved and row['minimum_margin']>=-500
            and statistics.mean(row['cash_deltas'])>0 and row['risk_score']>350)
        if row['cohort_admitted']:
            allowed.append(row)
    best=max(allowed,key=lambda r:r['risk_score']) if allowed else decision['candidates'][0]
    decision.update(selected=best['route'],selected_episode=best['episode'],admission='cohort_survival_and_economics')
    return best['route'],decision


if __name__=='__main__':
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'results/fresh/value_tape_search_20260923'
    for folder in ('revised_development','frozen_validation'):
        rows=[]
        for path in (root/folder).glob('*.json'):
            if path.name.endswith('.decision.json') or path.name=='summary.json':continue
            row=json.loads(path.read_text(encoding='utf-8'))
            if not row['completed']:continue
            selected,decision=cohort_policy(row['decision'])
            actual=row['evaluations'][str(selected)]
            rows.append(dict(episode=row['episode'],selected=selected,delta=actual['margin_delta']))
        print(json.dumps(dict(panel=folder,n=len(rows),mean=statistics.mean(r['delta'] for r in rows),rows=rows),indent=2))
