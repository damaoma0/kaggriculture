"""Read-only market-valuation diagnostic on saved development dawn observations."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import semantic_strategy_policy_20260928 as P
import semantic_strategy_persistent_value_20260928 as V

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'results/fresh/semantic_strategy_20260928'
GROUPS = dict(v2_fixed_B=BASE/'fixed_experiments/nearest_shops_v2/runs/strategy_v2_unlock',
              v3_natural=BASE/'runs/strategy_v3_modern4/development/live')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = dict(purpose=__doc__, interpretation='Model arithmetic diagnostic; no actions or gameplay counterfactuals.',
                  source_hashes={str(Path(m.__file__).relative_to(ROOT)):sha(Path(m.__file__)) for m in (P,V)},
                  input_hashes={}, groups={})
    cfg = deepcopy(P.DEFAULT_CONFIG)
    for group, folder in GROUPS.items():
        rows = []
        for path in sorted(folder.glob('live-*.json')):
            if path.name.endswith('.actions.json'):
                continue
            raw = json.loads(path.read_text())
            assert raw['completed'] and raw['ledger_verified']
            result['input_hashes'][str(path.relative_to(ROOT))] = sha(path)
            seat = int(raw['case']['seat'])
            own = {r['day']:r for r in raw['diagnostics'][seat]}
            rival = {r['day']:r for r in raw['diagnostics'][1-seat]}
            for day in range(6,30):
                saved = own[day]['current_observation']
                farms = [None,None]
                farms[seat] = saved['own_farm']
                farms[1-seat] = rival[day]['current_observation']['own_farm']
                obs = dict(day=day,player=seat,farms=farms,private=saved['private'],
                           market=saved['market'],town=saved['town'])
                state = P.public_state(obs)
                paths, rival_flow = P.forecast_market(state,cfg)
                old = {s:P.cohort_value(state,s,paths,rival_flow,cfg) for s in (*P.CROPS,*P.ANIMALS)}
                new = {s:V.cohort_value(state,s,paths,rival_flow,cfg) for s in old}
                alive = [s for s in old if day+(P.ANIMALS.get(s) or P.CROPS[s])['first']<=29]
                rows.append(dict(case=raw['case']['id'],day=day,
                    old={s:round(n,3) for s,n in old.items()},corrected={s:round(n,3) for s,n in new.items()},
                    sign_changes=[s for s in alive if (old[s]>0)!=(new[s]>0)],
                    best_before=max(alive,key=old.get) if alive else None,
                    best_after=max(alive,key=new.get) if alive else None))
        deltas = {s:[r['corrected'][s]-r['old'][s] for r in rows] for s in (*P.CROPS,*P.ANIMALS)}
        result['groups'][group] = dict(decisions=len(rows),
            best_species_changed=sum(r['best_before']!=r['best_after'] for r in rows),
            sign_change_counts=dict(Counter(s for r in rows for s in r['sign_changes'])),
            mean_value_correction={s:round(sum(v)/len(v),3) for s,v in deltas.items()},rows=rows)
    out = BASE/'persistent_market_value_diagnostic.json'
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:{f:v for f,v in g.items() if f!='rows'} for k,g in result['groups'].items()},indent=2))
    print(str(out))


if __name__ == '__main__':
    main()
