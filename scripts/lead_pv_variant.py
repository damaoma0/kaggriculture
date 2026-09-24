"""Make a plan-volume research variant of agents/mgt_lead_deploy_pv.py with DEP_CFG overrides.
usage: lead_pv_variant.py NAME '{"land_max": 3}'   -> agents/mgt_lpv_NAME.py"""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
name, over = sys.argv[1], json.loads(sys.argv[2])
s = (ROOT / 'agents/mgt_lead_deploy_pv.py').read_text(encoding='utf-8')
anchor = 'try:                                    # research overrides (ablations): DEP_CFG_JSON='
assert s.count(anchor) == 1
s = s.replace(anchor, f'DEP_CFG.update({over!r})   # variant {name}\n' + anchor)
out = ROOT / f'agents/mgt_lpv_{name}.py'
out.write_bytes(s.encode('utf-8'))
print(out)
