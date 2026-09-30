"""Read-only audit of cached ladder games and current-agent benchmark losses."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/heavy_loss_audit'
OUT.mkdir(exist_ok=True)
cohorts = []
for sub, label in [('56368334', 't10 ladder'), ('56395605', 'm1 ladder')]:
    rows = []
    for p in (ROOT / 'data/ladder_panel' / sub).glob('*.json.gz'):
        g = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        s = g['seat']
        rows.append(dict(id=g['episode'], seat=s, margin=g['rewards'][s]-g['rewards'][1-s], opponent=g['opponent']['team'], date=g['created']))
    cohorts.append(dict(label=label, rows=sorted(rows, key=lambda r:r['margin'])))
for pattern, label in [('results/fresh/selfplay/games/mgt_m1-*-vs-v50_public.json', 'm1 vs live V50'), ('results/fresh/tape_gap_plans/v56_baseline_smoke/mgt_m1-v56-*.json', 'm1 vs live V56')]:
    rows = []
    for p in ROOT.glob(pattern):
        r = json.loads(p.read_text())
        rows.append(dict(id=r['seed'], seat=r['seat'], margin=r['margin'], opponent=r.get('rival',r.get('opponent')), source=str(p.relative_to(ROOT))))
    cohorts.append(dict(label=label, rows=sorted(rows,key=lambda r:r['margin'])))
for c in cohorts:
    rs = c['rows']
    c['summary'] = dict(n=len(rs), losses=sum(r['margin']<0 for r in rs), heavy=sum(r['margin']<=-20000 for r in rs), worst=min(r['margin'] for r in rs))
r = json.loads((ROOT / 'results/fresh/selfplay/games/mgt_m1-176079-1-vs-v50_public.json').read_text())
a,b = r['ledger_candidate'],r['ledger_benchmark']
parts = [dict(label=k.title(), value=a['revenue'].get(k,0)-b['revenue'].get(k,0)) for k in sorted(a['revenue'].keys()|b['revenue'].keys())]
parts.append(dict(label='Lower spending',value=sum(b['spend'].values())-sum(a['spend'].values())))
assert sum(x['value'] for x in parts)==r['margin']
parts.sort(key=lambda x:x['value'])
audit = dict(cohorts=cohorts, decomposition=parts, final=r['margin'])
(OUT / 'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
for c in cohorts: print(c['label'], c['summary'])
print('Decomposition reconciled:',sum(x['value'] for x in parts))
