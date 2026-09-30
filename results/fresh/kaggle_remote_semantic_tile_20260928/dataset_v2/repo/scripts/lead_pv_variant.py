"""Make a plan-volume research variant of agents/mgt_lead_deploy.py (or $PV_BASE) with DEP_CFG overrides and,
optionally, executor CFG overrides.

usage: lead_pv_variant.py NAME '{deploy DEP_CFG}' ['{executor CFG}']   -> agents/mgt_lpv_NAME.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
name, over = sys.argv[1], json.loads(sys.argv[2])
s = (ROOT / os.environ.get('PV_BASE', 'agents/mgt_lead_deploy.py')).read_text(encoding='utf-8')
anchor = 'try:                                    # research overrides (ablations): DEP_CFG_JSON='
assert s.count(anchor) == 1
s = s.replace(anchor, f'DEP_CFG.update({over!r})   # variant {name}\n' + anchor)
if len(sys.argv) > 3:                          # executor CFG overrides, applied right after the executor's CFG
    cfg = json.loads(sys.argv[3])
    a2 = '\n_SMNS = None\n'
    assert s.count(a2) == 1
    s = s.replace(a2, f'\nCFG.update({cfg!r})   # variant {name} (executor)\n_SMNS = None\n')
out = ROOT / f'agents/mgt_lpv_{name}.py'
out.write_bytes(s.encode('utf-8'))
print(out)
