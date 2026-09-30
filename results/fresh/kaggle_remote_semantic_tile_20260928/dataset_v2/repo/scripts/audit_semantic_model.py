"""Leave an entire leader family out, including shared episodes, for diagnostics."""
from collections import defaultdict
from pathlib import Path
import json,statistics
from semantic_farm.model import DecisionModel,distance
from semantic_farm.common import SPECIES
ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'results/fresh/semantic_architecture_20260924'
    study=json.loads((folder/'study.json').read_text(encoding='utf8'))
    families={int(s):r['team'] for s,r in study['eligible_submissions'].items()}
    rows=[r for r in DecisionModel().rows if r['day']>=6]
    results={}
    for family in sorted(set(families.values())):
        held=[r for r in rows if families[r['submission']]==family]
        episodes={r['episode'] for r in held}
        training=[r for r in rows if families[r['submission']]!=family and r['episode'] not in episodes]
        nearest_errors=[];median_errors=[]
        for row in held:
            candidates=[r for r in training if r['day']==row['day']]
            if not candidates:continue
            neighbor=min(candidates,key=lambda r:(distance(row['features'],r['features']),r['episode']))
            for s in SPECIES:
                actual=row['additions'].get(s,0)
                nearest_errors.append(abs(actual-neighbor['additions'].get(s,0)))
                median_errors.append(abs(actual-statistics.median(r['additions'].get(s,0) for r in candidates)))
        results[family]=dict(held_seasons=len(held)//24,held_episodes=len(episodes),
            training_seasons=len(training)//24,nearest_mae=statistics.mean(nearest_errors),
            calendar_median_mae=statistics.mean(median_errors))
    result=dict(split='leave_family_and_shared_episodes_out',families=results,
        limitation='Imitation diagnostic only; sparse and unequal families; no policy performance claim.')
    (folder/'family_holdout.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
