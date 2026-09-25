"""Write CFG-default variants of the search agents. Kaggle's loader (and the ladder-panel / lead_world_trace harnesses
that load agents by file name) calls the file's last callable without configure(), so the settings under test must be
the file's defaults. A variant = agents/mgt_lpv_search.py (deploy) or agents/mgt_lead_search.py (lead) with the CFG
default lines of the SEARCH DISPATCH keys replaced (each anchor asserted once); nothing else changes.

usage: search_dispatch_variants.py <variant>[,<variant>...] [deploy|lead]
       -> agents/mgt_lpv_sd_<variant>.py (deploy) / agents/mgt_lead_sd_<variant>.py (lead), sha256 printed
Variants (settings from scripts/search_dispatch_run.py, the leader-world arms):
  off    dispatch_search off (control: the source's decisions)
  v1a12  active, days 12-23 (v1: every v2+ option off)      v1all  active, every day (v1)
  v2a12  active, days 12-23 + V2      v2all  active, every day + V2
  v3a12  active, days 12-23 + V3      v3all  active, every day + V3
  v4a12  active, days 12-23 + V4      v4all  active, every day + V4 (measured credit)
  v1a12d / v1a12d2  v1 a12 with deterministic budgets (evals 60000 / 8000 bind; time caps 2 / 1 / 3 s as safety only)
  v1fa12d / v1fa12d2  v1 a12 + survival fallback, deterministic, evals 24000 / 8000 (caps 0.75 / 0.6 / 0.8 s safety)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


DET2 = dict(sd_evals0=24000, sd_evals=8000, sd_budget0=0.75, sd_budget=0.6, sd_step_cap=0.8)
DET = dict(sd_evals0=60000, sd_evals=8000, sd_budget0=2.0, sd_budget=1.0, sd_step_cap=3.0)   # evals = the v1 budgets; SDa12_w48 (+2,141) ran uncapped on a fast host


def settings():
    import search_dispatch_run as R
    return {
        'off': dict(dispatch_search='off'),
        'v1a12': dict(dispatch_search='active', sd_days=[12, 23]),
        'v1all': dict(dispatch_search='active'),
        'v1fa12': dict(dispatch_search='active', sd_days=[12, 23], sd_surv_fb=20),
        # deterministic budgets (coordinator 2026-09-25): the route-evaluation budgets bind, the wall-clock caps are safety
        # only (time_capped counts every firing; the 60 s overage bank absorbs a rare slow step)
        'v1a12d': dict(dispatch_search='active', sd_days=[12, 23], **DET),
        'v1a12d2': dict(dispatch_search='active', sd_days=[12, 23], **DET),     # identical twin: reproducibility check
        # the shipping candidate (coordinator): v1 a12 + survival fallback, deterministic, first plan calibrated so no step
        # passes ~0.8 s on a slow Kaggle host (60k evaluations took 1.52 s there -> 24k ~0.6 s); caps 0.75 / 0.6 / 0.8 s
        # are safety only (time_capped counts them)
        'v1fa12d': dict(dispatch_search='active', sd_days=[12, 23], sd_surv_fb=20, **DET2),
        'v1fa12d2': dict(dispatch_search='active', sd_days=[12, 23], sd_surv_fb=20, **DET2),   # identical twin
        'v2a12': dict(dispatch_search='active', sd_days=[12, 23], **R.V2),
        'v2all': dict(dispatch_search='active', **R.V2),
        'v3a12': dict(dispatch_search='active', sd_days=[12, 23], **R.V3),
        'v3all': dict(dispatch_search='active', **R.V3),
        'v4a12': dict(dispatch_search='active', sd_days=[12, 23], **R.V4),
        'v4all': dict(dispatch_search='active', **R.V4),
        'v5a12': dict(dispatch_search='active', sd_days=[12, 23], **R.V5),
        'v5all': dict(dispatch_search='active', **R.V5),
    }


def pyrepr(v):
    return repr(v)            # dicts / lists / numbers / strings / None: valid Python literals


def make(variant, target='deploy'):
    src = ROOT / ('agents/mgt_lpv_search.py' if target == 'deploy' else 'agents/mgt_lead_search.py')
    out = ROOT / (('agents/mgt_lpv_sd_%s.py' if target == 'deploy' else 'agents/mgt_lead_sd_%s.py') % variant)
    s = src.read_text(encoding='utf-8')
    cfg = settings()[variant]
    for k, v in cfg.items():
        pat = re.compile(r'^(    "%s": )(.*?)(,(?:\s*#.*)?)$' % re.escape(k), re.M)
        hits = pat.findall(s)
        assert len(hits) == 1, (k, len(hits))
        s = pat.sub(lambda m: m.group(1) + pyrepr(v) + m.group(3), s, count=1)
    first = s.split('\n', 1)[0]
    note = ('\n%s: variant "%s" of %s (sha256 %s) written by scripts/search_dispatch_variants.py: CFG defaults %s.\n'
            % (out.stem, variant, src.name, hashlib.sha256(src.read_bytes()).hexdigest()[:16],
               json.dumps(cfg, sort_keys=True)))
    s = first + note + s[len(first):]
    compile(s, str(out), 'exec')
    out.write_bytes(s.encode('utf-8'))       # LF line endings, as the built agents
    print(f'{out.relative_to(ROOT)}: sha256 {hashlib.sha256(s.encode()).hexdigest()}')
    return out


if __name__ == '__main__':
    tgt = sys.argv[2] if len(sys.argv) > 2 else 'deploy'
    for v in sys.argv[1].split(','):
        make(v, tgt)
