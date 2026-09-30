"""Diagnostic control: same plans and constraints, current-price valuation.

This extra control is not eligible for promotion. It isolates future-price
valuation from the changed tour shortlist on the frozen confirmation panel.
"""
import json
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
from evaluate_delivery_inputs import ROOT,OUT,PATHS,jobs,run

OVERRIDE='''
# Diagnostic ablation: no future inventory change, identical marginal pricing.
def _delivery_value(obs,lots,scenarios):
    added={'WHEAT':0,'CARROT':0};value=0
    for sale,item,qty in lots:
        for _ in range(qty):
            quote=_r37_market_price(item,obs['market']['inventory'][item]+added[item])
            value+=max(1,quote-2)
            added[item]+=int(quote>1)
    return value
'''
PATHS['ablation']=ROOT/'agents/v45_delivery_current_control.py'

def main():
    path=PATHS['ablation']
    content=PATHS['candidate'].read_text(encoding='utf-8')+OVERRIDE
    if path.exists():assert path.read_text(encoding='utf-8')==content
    else:path.write_text(content,encoding='utf-8')
    panel=[(phase,s,i,'ablation',o) for phase,s,i,p,o in jobs('confirmation') if p=='candidate']
    manifest=dict(jobs=panel,sha256=sha256(path.read_bytes()).hexdigest(),
                  purpose='Diagnostic only; not part of promotion selection. Same shortlist and economic guards; current-price marginal proceeds.')
    dest=OUT/'ablation_manifest.json'
    if dest.exists():assert json.loads(dest.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:dest.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in panel if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()
