"""Build independent tape/lifecycle experiments without editing mgt_m1."""
import base64
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import runpy
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/rotation_experiments'
BASE = ROOT / 'agents/mgt_m1.py'
EXPECTED = '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'
PATTERN = r"(_MGT_LIB = _mgt_json.loads\(_mgt_zlib.decompress\(_mgt_b64.b85decode\(')([^']+)('\)\)\))"


def pack(obj):
    return base64.b85encode(zlib.compress(json.dumps(obj, separators=(',', ':')).encode(), 9)).decode()


def label(t):
    if t is None: return ' .'
    if t == 'LOCKED': return ' L'
    if t.get('crop'): return t['crop'][:2]
    if t.get('animal'): return t['animal'][:2].lower()
    return ' .' if t.get('kind') == 'WEED' else t['kind'][:2].lower()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assert sha256(BASE.read_bytes()).hexdigest() == EXPECTED
    source = BASE.read_text(encoding='utf-8')
    match = re.search(PATTERN, source)
    lib = json.loads(zlib.decompress(base64.b85decode(match[2])))
    sim = runpy.run_path(str(ROOT/'scripts/fragments/tape_calendar.py'))['_tc_simulate']
    # Expected cohort birth days inferred from the donor's requested establishment
    # calendar. Validate this separately against all 105 full-state UMG donors.
    births = {}
    for tape in lib['tapes']:
        actions = [lib['actions'][i] for i in tape['ids']]
        visits = sim(lambda t: actions[t], 0, 718, [(4, 4)])
        last = {}; days = []
        for t in range(720):
            if t % 24 == 0:
                codes = [tape['boards'][t//24][i:i+2] for i in range(0,200,2)]
                days.append([last.get(i, (None,-1))[1] if last.get(i,(None,-1))[0] == code else -1 for i,code in enumerate(codes)])
            for x,y,cmd in visits.get(t, ()):
                if cmd and len(cmd)>1 and cmd[0] in ('PLANT','PLACE') and cmd[1] in ('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','COW','SHEEP','GOOSE'):
                    name=cmd[1];last[y*10+x]=(name[:2] if cmd[0]=='PLANT' else name[:2].lower(),t//24)
        births[str(tape['ep'])]=days
    (OUT/'donor_birth_days.json').write_text(json.dumps(births,separators=(',',':')))
    cohort = source + '\n' + (ROOT/'scripts/fragments/rotation_cohort_router.py').read_text().replace('__COHORT_BLOB__',pack(births))
    variants={'mgt_exp_cohort':cohort}
    # DSM library: complete recorded calendars with the existing m1 chassis and
    # feed/care/sale protections. No UMG-to-DSM mid-season coordinate splice.
    manifest=json.loads((ROOT/'results/fresh/leader_library_refresh_20260922/inventory.json').read_text())
    entry=next(x for x in manifest if x['team']=='DSM');unique=[];idx={};tapes=[]
    for eid in entry['completed_episode_ids']:
        r=json.loads((ROOT/f'data/dsm_replays/episode-{eid}-replay.json').read_text(encoding='utf-8'))
        seat=r['info']['TeamNames'].index('DSM');ids=[]
        for step in r['steps'][1:]:
            a=step[seat].get('action') or {};a={'farmer':a.get('farmer') or ['PASS'],'hands':a.get('hands') or [],'market':a.get('market') or []}
            k=json.dumps(a,sort_keys=True,separators=(',',':'))
            if k not in idx: idx[k]=len(unique);unique.append(a)
            ids.append(idx[k])
        boards=[''.join(label(t) for row in r['steps'][d*24][0]['observation']['farms'][seat]['tiles'] for t in row) for d in range(30)]
        tapes.append(dict(ids=ids,shops=r['steps'][-1][0]['observation']['town']['unlocked_shops'],boards=boards,ep=eid))
    modal=Counter(tuple(t['ids'][:72]) for t in tapes).most_common(1)[0][0]
    for t in tapes:t['modal']=tuple(t['ids'][:72])==modal
    dsm_blob=pack(dict(actions=unique,tapes=tapes))
    variants['mgt_exp_dsm']=source[:match.start(2)]+dsm_blob+source[match.end(2):]
    fragment=(ROOT/'scripts/fragments/rotation_calendar_overlay.py').read_text()
    for mode in ('rotate','hold'):
        variants['mgt_exp_'+mode]=source+'\n'+fragment.replace('__ROT_MODE__',repr(mode))
    result={}
    for name,code in variants.items():
        compile(code,name,'exec');p=ROOT/'agents'/f'{name}.py';p.write_text(code,encoding='utf-8');result[name]={'sha256':sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    (OUT/'build.json').write_text(json.dumps({'baseline_sha256':EXPECTED,'variants':result},indent=2))
    print(json.dumps(result),flush=True)


if __name__ == '__main__':build()
