"""Check the new seed panels against saved seed and experiment manifests."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/rotation_experiments'
design=json.loads((OUT/'design.json').read_text())
wanted=set(design['smoke']+design['development']+design['validation'])
hits=[];checked=0
for p in (ROOT/'results').rglob('*.json'):
    if OUT in p.parents or not any(s in p.name.lower() for s in ('manifest','seed','protocol')):
        continue
    if p.stat().st_size>5_000_000:
        continue
    checked+=1
    overlap=wanted & {int(s) for s in re.findall(r'\b\d{9,10}\b',p.read_text(encoding='utf-8'))}
    if overlap:hits.append({'path':str(p.relative_to(ROOT)),'seeds':sorted(overlap)})
result={'files_checked':checked,'new_seeds':len(wanted),'overlaps':hits,
        'reserved_block_overlap':sorted(s for s in wanted if 93021000<=s<=93023999)}
(OUT/'seed_overlap_audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
assert not hits and not result['reserved_block_overlap']
