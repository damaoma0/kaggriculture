"""Write CFG-default variants of the search agents. Kaggle's loader (and the ladder-panel / lead_world_trace harnesses
that load agents by file name) calls the file's last callable without configure(), so the settings under test must be
the file's defaults. A variant = agents/mgt_lpv_search.py (deploy) or agents/mgt_lead_search.py (lead) with the CFG
default lines of the SEARCH DISPATCH keys replaced (each anchor asserted once); nothing else changes.

usage: search_dispatch_variants.py <variant>[,<variant>...] [deploy|lead]
       -> agents/mgt_lpv_sd_<variant>.py (deploy) / agents/mgt_lead_sd_<variant>.py (lead), sha256 printed
Variants (settings from scripts/search_dispatch_run.py, the leader-world arms):
  off    dispatch_search off (control: the source's decisions)
  v2a12  active, days 12-23 + V2      v2all  active, every day + V2
  v3a12  active, days 12-23 + V3      v3all  active, every day + V3
  v4a12  active, days 12-23 + V4      v4all  active, every day + V4 (measured credit)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def settings():
    import search_dispatch_run as R
    return {
        'off': dict(dispatch_search='off'),
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
