"""Paired head-to-head report (her 128 held-out worlds, ladder case, her recorded tape opposes - frozen):
candidate vs mgt_m1, split by late-Yarn mismatch of m1's final tape. usage: report_h2h_layer.py <candidate> [baseline=mgt_m1]"""
import json, random, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
L = ROOT / 'results/fresh/mg_tape/loo'
cand = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else 'mgt_m1'
load = lambda a: {f.name.split('-')[-1][:-5]: json.loads(f.read_text()) for f in L.glob(f'mgtape_vs_{a}-mg_vs-*.json')}
A, Y = load(base), load(cand)
gap = {str(r['ep']): r for r in json.loads((ROOT / 'results/fresh/newphase_20260923/late_yarn_service_gap.json').read_text())}
eps = sorted(set(A) & set(Y))
def ci(xs, n=10000):
    rng = random.Random(7); m = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n)); return m[250], m[9750]
def show(lab, es):
    if not es: return
    d = [(-Y[e]['margin']) - (-A[e]['margin']) for e in es]
    lo, hi = ci(d)
    print(f"{lab:36s} n={len(es):3d} W {sum(-A[e]['margin'] > 0 for e in es):3d}->{sum(-Y[e]['margin'] > 0 for e in es):3d}  paired {sum(d)/len(d):+7,.0f} ({lo:+,.0f}..{hi:+,.0f}) "
          f"b/w/s {sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}/{sum(x == 0 for x in d)}  own {sum(Y[e]['rival_final'] - A[e]['rival_final'] for e in es)/len(es):+,.0f} "
          f"hers {sum(Y[e]['final'] - A[e]['final'] for e in es)/len(es):+,.0f}")
print(f'{cand} vs {base}, her 128 held-out worlds (ladder case), frozen opponent = her recorded tape')
show('ALL', eps)
show('world has MORE late Yarn than tape', [e for e in eps if gap.get(e, {}).get('mis', 0) > 0])
show('equal, world has late Yarn', [e for e in eps if e in gap and gap[e]['mis'] == 0 and gap[e]['world_late'] > 0])
show('equal, no late Yarn', [e for e in eps if e in gap and gap[e]['mis'] == 0 and gap[e]['world_late'] == 0])
show('world has FEWER', [e for e in eps if gap.get(e, {}).get('mis', 0) < 0])
fired = [e for e in eps if isinstance(Y[e].get('rival_sheep'), dict) and Y[e]['rival_sheep'].get('yarn_service', 0)]
print(f"layer fired in {len(fired)} games; expansion commits {base} {sum(1 for e in eps if (A[e].get('rival_sheep') or {}).get('commitments', 0))}, "
      f"{cand} {sum(1 for e in eps if (Y[e].get('rival_sheep') or {}).get('commitments', 0))}")
