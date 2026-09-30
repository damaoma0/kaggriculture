"""Check the browser-exported timing rows against the notebook summary."""
import json
from pathlib import Path
import statistics

here=Path(__file__).resolve().parent
data=json.loads((here/'timing_samples_browser.json').read_text())
rows=data['rows']
assert len(rows)==42
expected=[184,0,None,197,23,None]
seen=set()
for case,policy,repeat,wall,cpu,selected,rollouts,turns in rows:
    key=case,policy,repeat
    assert key not in seen
    seen.add(key)
    assert wall>0 and cpu>0 and rollouts>=0 and turns>=0
    assert selected is None if repeat == -1 else selected==expected[case]
    if repeat == -1:
        assert policy=='v8' and .8 <= wall <= .902
metrics={p:{phase:dict(n=len(values),mean=statistics.mean(values),median=statistics.median(values),
    minimum=min(values),maximum=max(values)) for phase,values in
    [('cold',[r[3] for r in rows if r[1]==p and r[2]==0]),
     ('warm',[r[3] for r in rows if r[1]==p and r[2]>0])]}
    for p in ('v7','v8')}
assert abs(metrics['v7']['warm']['mean']-9.274888291249985)<1e-12
assert abs(metrics['v8']['warm']['mean']-6.832226466749991)<1e-12
reduction=1-metrics['v8']['warm']['mean']/metrics['v7']['warm']['mean']
assert abs(reduction-.2633629374064185)<1e-12
print(json.dumps(dict(samples=len(rows),metrics=metrics,warm_reduction=reduction),indent=2))
