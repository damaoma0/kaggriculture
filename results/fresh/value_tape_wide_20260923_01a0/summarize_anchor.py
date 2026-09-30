"""Separate follow-up results; never pool with the prespecified 96-pair panel."""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import json
import statistics
import summarize as S

OUT=Path(__file__).resolve().parent

def main():
    design=json.loads((OUT/'anchor_design.json').read_text())
    manifest=json.loads((OUT/'anchor_manifest.json').read_text())
    for name,expected in manifest['sha256'].items():
        assert sha256((OUT/name).read_bytes()).hexdigest()==expected,name
    rows=[json.loads(p.read_text()) for p in (OUT/'pairs').glob('anchor-*.json')]
    valid=[r for r in rows if r['completed']]
    for row in valid:
        case=row['spec']['id'];kinds=set()
        for p in (OUT/'decisions').glob(f'{case}-d*.json'):
            d=json.loads(p.read_text())
            if d['selected'] is not None:
                kinds.add('hold_incumbent' if d['selected']==d['candidates'][1]['route'] else 'change_tape')
        row['intervention_type']='+'.join(sorted(kinds)) if kinds else 'none'
    baseline=[json.loads(p.read_text()) for p in (OUT/'arms').glob('anchor-*-baseline.json')]
    controls=sum(r.get('completed',False) and r.get('control_exact',False) for r in baseline)
    result=dict(planned=len(design['selected']),complete=len(valid)==len(design['selected']),
        completed=len(valid),exact_native_controls=controls,
        stats=S.stats(valid,lambda r:r['spec']['opponent']),
        failed_pairs=[r for r in rows if not r['completed']],rows=valid,
        rating_range=[min(s['rating'] for s in design['selected']),max(s['rating'] for s in design['selected'])],
        opponents=sorted(set(r['opponent']['team'] for r in design['selected'])),
        additional_major_playback_failures=sum(r['candidate_divergence']['material_command_break'] for r in valid),
        candidate_board_divergences=sum(r['candidate_divergence']['first_board_difference'] is not None for r in valid),
        note='Follow-up diagnostic panel after discovery of playback failures. Candidate code unchanged; all ten qualifying recorded m1 games used without reward filtering. Ratings refer to each played submission at metadata fetch. Opponents still use frozen actions after intervention; exact baseline is necessary but does not establish closed-loop counterfactual validity.')
    S.write(OUT/'anchor_summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
