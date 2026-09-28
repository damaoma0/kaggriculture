"""Pure four-fixture parity for the fixed-timestamp revision; no gameplay."""
import ast
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(r'C:\Users\xyygl\Documents\kaggriculture\results\fresh\semantic_strategy_20260928\polish_fixtures_v8_live01')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def defs(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
def fixed_schedule(m,sg):
    fixed=('DELIVER','DROP','PLACE_HARVEST','PICKUP','PLACE','BUILD_COOP','BUILD_PASTURE')
    first=next((i for i,s in enumerate(sg['stops']) if not s.get('dawn')),len(sg['stops']))
    hours=iter(m._tier_eval(sg,want_hours=True)[4]);out=[]
    for i,s in enumerate(sg['stops']):
        protected=i==first or any(s.get(k) for k in ('dawn','copy','sell_all','place','turn','deliver')) or any(o['c'][0] in fixed for o in s['ops'])
        for op in s['ops']:
            b,c,h=next(hours)
            if protected:out.append((b,c,h))
    return out

def main():
    oldp=ROOT/'agents/mgt_lead_kb115lt2_harvestx_fast.py';newp=ROOT/'agents/mgt_lead_kb115lt2_harvestx2_fast.py'
    assert sha(oldp)=='1770e5ab8edf4ae1c7bdd50959349579acba6f1226a0fad8951700e5e4e3119e'
    a,b=defs(oldp),defs(newp)
    assert {n for n in a if a[n]!=b[n]}=={'_tier_harvest_exchange'} and set(a)==set(b)
    old=load(oldp,'_strategy_kb115lt');new=load(newp,'harvest_fixedtime')
    manifest=json.loads((FIXTURES/'manifest.json').read_text());assert manifest['verified']
    rows=[]
    for rec in manifest['fixtures']:
        p=FIXTURES/rec['file'];assert sha(p)==rec['sha256']
        payload=pickle.loads(gzip.decompress(p.read_bytes()))
        ref=pickle.loads(payload['reference_output_pickle']);outputs={}
        for label,module,enabled in [('old_on',old,True),('new_off',new,False),('new_on',new,True)]:
            fixture=pickle.loads(payload['input_pickle'])
            for key,value in fixture['globals'].items():setattr(module,key,deepcopy(value))
            module.CFG['sd_polish_harvest_exchange']=int(enabled)
            module.CFG['sd_polish_harvest_exchange_cap']=96
            module._tier_polish(*fixture['args']);outputs[label]=fixture['args']
        assert outputs['new_off']==ref
        x,y=outputs['old_on'],outputs['new_on']
        # Diagnostics may report more rejected alternatives; actual state and
        # routes, chosen action, rest work and accepted detail must match here.
        assert x[:-1]==y[:-1],rec['file']
        dx=deepcopy(x[-1]);dy=deepcopy(y[-1])
        dx['_polish_day']['harvest_exchange'].pop('rejected',None)
        dy['_polish_day']['harvest_exchange'].pop('rejected',None)
        assert dx==dy
        for before,after in zip(ref[1],y[1]):
            baseline=fixed_schedule(new,before);chosen=fixed_schedule(new,after)
            # A first-visit added harvest is allowed if no original job shifts.
            assert all(row in chosen for row in baseline)
        rows.append(dict(day=ref[4],fixture_sha256=sha(p),off_exact=True,
            actual_output_equal_v1_except_rejection_diagnostics=True,
            fixed_timestamps_preserved=True,decision=y[-1]['_polish_day']['harvest_exchange']))
    tests=load(ROOT/'tests/test_kb115lt2_harvest_exchange_fixedtime_20260928.py','harvest_fixedtime_tests')
    tests.EX=new;tests.CFG=dict(new.CFG)
    # Fixture CFG restored captured ON state; test default uses source config.
    pristine=load(newp,'harvest_fixedtime_pristine');tests.CFG=dict(pristine.CFG)
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    assert result.wasSuccessful()
    out=ROOT/'results/fresh/semantic_kb115lt2_recovery/harvest_exchange_fixedtime_audit.json'
    if out.exists():raise FileExistsError(out)
    value=dict(scope='PURE_FIXED_TIMESTAMP_REVISION_VALIDATION',no_engine=True,
        hashes={str(p.relative_to(ROOT)):sha(p) for p in (oldp,newp,ROOT/'agents/mgt_lead_kb115lt2_harvestx2.py',ROOT/'agents/mgt_lead_kb115lt2_harvestx2_eval.py')},
        changed_definitions=['_tier_harvest_exchange'],tests_run=result.testsRun,tests_passed=True,rows=rows,
        prior_component_evidence='V1 fixed-shop recorded-rival component remains valid for its captured D18 route; all four actual fixture outputs match this revision. No new game was run.')
    out.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(dict(path=str(out),sha256=sha(out),source_sha256=sha(newp),rows=rows),indent=2))

if __name__=='__main__':main()
