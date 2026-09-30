"""Register and test small, marked changes to individual UMG action sequences.

The first variant redirects one care action from cow to sheep while preserving
all remaining work, travel and hires. Historical tests use the official engine,
recorded opponent actions and recorded shops. No historical result is a live
qualification. A registry keeps unchanged tapes and untested candidates explicit.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
OUT = ROOT / 'results/fresh/tape_variants_20260922'
REGISTRY = ROOT / 'data/tape_variants'
BASE = 'mgt_m1'
CANDIDATE = 'mgt_tape_care_v1'
BASE_SHA = '1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470'
TAPE = 109740300
CASE = 111678108


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf8')


def digest(data):
    return sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def raw_tape():
    path = next((ROOT/'data/mg_tapes').glob(f'*/{TAPE}.json.gz'))
    with gzip.open(path, 'rt', encoding='utf8') as stream:
        return path, json.load(stream)


def freeze():
    if (OUT/'design.json').exists():
        design = read(OUT/'design.json')
        for arm, hashed in design['source_hashes'].items():
            assert digest((OUT/'sources'/f'{arm}.py').read_bytes()) == hashed
        return design
    source = (ROOT/'agents/mgt_m1.py').read_bytes()
    assert digest(source) == BASE_SHA
    tape_path, raw = raw_tape()
    actions = raw['actions']
    calendar = runpy.run_path(str(ROOT/'scripts/fragments/tape_calendar.py'))
    spec = dict(id=f'{TAPE}-milk-care-to-wool-v1', base_tape_episode=TAPE,
                first_repurpose_day=26, days={})
    contracts = []
    for day in (15, 17, 19, 21, 23):
        start = day * 24
        sim = calendar['_tc_simulate'](lambda t: actions[t], start, start+23, [(4, 4)])
        unit = 8
        old = [actions[start+h]['hands'][unit-1] for h in (1, 2, 3, 4)]
        assert old == [['CARE'], ['PICKUP', 'WHEAT', 2], ['COLLECT_FERTILIZER'], ['WEST']]
        assert sim[start+1][unit][:2] == (4, 4)
        assert sim[start+5][unit][:2] == (3, 4)
        assert any((x, y) == (3, 4) and c == ['FEED']
                   for row in sim.values() for x, y, c in row)
        assert not any((x, y) == (3, 4) and c == ['CARE']
                       for row in sim.values() for x, y, c in row)
        new = [old[1], old[2], old[3], old[0]]
        edits = [dict(hour=h, before=b, after=a) for h, b, a in zip((1,2,3,4),old,new)]
        changed = deepcopy(actions[start:start+24])
        for e in edits:
            changed[e['hour']]['hands'][unit-1] = e['after']
        patched = calendar['_tc_simulate'](lambda t: changed[t-start], start, start+23, [(4,4)])
        # Concrete routing contract: everyone rejoins by h5, preserving all
        # subsequent commands, market orders, hires and non-care work.
        assert all(sim[t] == patched[t] for t in range(start+5,start+24))
        before_work = Counter((x,y,tuple(c)) for t,row in sim.items() for u,(x,y,c) in enumerate(row)
                              if c[0] not in ('NORTH','SOUTH','EAST','WEST','PASS','CARE'))
        after_work = Counter((x,y,tuple(c)) for t,row in patched.items() for u,(x,y,c) in enumerate(row)
                             if c[0] not in ('NORTH','SOUTH','EAST','WEST','PASS','CARE'))
        assert before_work == after_work
        assert all(changed[h]['market'] == actions[start+h]['market'] for h in range(24))
        spec['days'][str(day)] = {'unit': unit, 'edits': edits}
        contracts.append(dict(day=day, same_route_from_hour=5, same_non_care_work=True,
                              same_hires_and_orders=True, care_from=[4,4], care_to=[3,4]))
    fragment = (ROOT/'scripts/fragments/tape_variant_care.py').read_text(encoding='utf8')
    fragment = fragment.replace('__TAPE_VARIANT_SPEC__', repr(spec))
    marker = b'def mgt_kaggle_entry(observation, configuration=None):'
    assert source.count(marker) == 1
    newline = '\r\n' if b'\r\n' in source else '\n'
    addition = (fragment.strip()+'\n\n\n').replace('\n', newline).encode()
    candidate = source.replace(marker, addition+marker)
    for arm, body in ((BASE,source), (CANDIDATE,candidate)):
        (OUT/'sources').mkdir(parents=True, exist_ok=True)
        (OUT/'sources'/f'{arm}.py').write_bytes(body)
    target = ROOT/'agents'/f'{CANDIDATE}.py'
    if target.exists():
        assert target.read_bytes() == candidate
    target.write_bytes(candidate)
    diff = ''.join(difflib.unified_diff(source.decode().splitlines(True),candidate.decode().splitlines(True),
                                      fromfile=f'{BASE}.py',tofile=f'{CANDIDATE}.py',n=2))
    (OUT/'candidate.diff').write_text(diff,encoding='utf8')
    mark = dict(spec, status='registered_untested', source=str(tape_path.relative_to(ROOT)),
        base_actions_sha256=digest(canonical(actions)), parent_agent_sha256=BASE_SHA,
        source_sha256=digest(candidate), discovery_episode=CASE,
        production_change='Redirect one already funded cow CARE to an existing sheep. No new animal, hire or travel.',
        trigger='Selected donor 109740300; specified days; revealed Yarn Store; milk <= 40; wool >= milk + 20; original animal cohorts and bank; next wool harvest strictly before D26 pasture conversion.',
        retirement_note='D23 has the same legal routing opportunity but must be rejected: its next wool harvest conflicts with D26 conversion.',
        evidence=[], contracts=contracts)
    write(REGISTRY/f'{spec["id"]}.json',mark)
    design = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        variant_id=spec['id'], source_hashes={BASE:BASE_SHA,CANDIDATE:digest(candidate)},
        diagnostic_episodes=[CASE,111261836,111743130,111262874],
        purpose='One per-tape sequence revision, measured separately from the prior wool-forecast change.',
        advance_rule='Keep a diagnostic improvement marked as diagnostic-only until it also survives applicable responsive-opponent confirmation. Keep failed trials and regressions.',
        counterfactual='Official engine, complete 719-step continuation, fixed recorded opponents and shops; both cash ledgers reconcile.',
        no_claim='The discovery case is not held-out evidence or an Elo estimate.', contracts=contracts)
    write(OUT/'design.json',design)
    return design


def run_job(job):
    arm, episode, design = job
    path = OUT/'historical'/f'{arm}-{episode}.json'
    if path.exists():
        cached = read(path)
        assert cached['source_sha256'] == design['source_hashes'][arm]
        return {k:cached.get(k) for k in ('arm','episode','completed','margin','variant_report')}
    row = dict(arm=arm,episode=episode,completed=False,source_sha256=design['source_hashes'][arm])
    log = OUT/'logs'/f'{arm}-{episode}.log'
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('w',encoding='utf8') as stream:
        saved = os.dup(1),os.dup(2)
        try:
            os.dup2(stream.fileno(),1);os.dup2(stream.fileno(),2)
            from research_labour_profit import Simulator, engine, economic
            from kaggle_environments.agent import get_last_callable
            E = engine()
            with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as stream2:
                game=json.load(stream2)
            source=OUT/'sources'/f'{arm}.py'
            assert digest(source.read_bytes())==design['source_hashes'][arm]
            entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source))
            assert entry.__name__=='mgt_kaggle_entry'
            seat=game['seat'];actions=[None,None]
            actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
            elapsed=[];changes=[];days=[]
            with Simulator(game) as sim:
                interpreter=E.interpreter
                def live(state,env):
                    obs=state[seat].observation
                    if sim.t%24==0:
                        days.append(dict(day=sim.t//24, prices=deepcopy(obs.market.prices),
                            cow=deepcopy(obs.farms[seat].tiles[4][4]),
                            sheep=deepcopy(obs.farms[seat].tiles[4][3])))
                    tick=time.perf_counter()
                    action=entry(deepcopy(obs),None)
                    elapsed.append(time.perf_counter()-tick)
                    if action!=game['our_actions'][sim.t]:changes.append(sim.t)
                    state[seat].action=action
                    return interpreter(state,env)
                E.interpreter=live
                try:
                    result=sim.run(sim.initial,0,719,actions,capture=True)
                finally:
                    E.interpreter=interpreter
                economics=[economic(result['events'],s) for s in (seat,1-seat)]
                for s,econ in zip((seat,1-seat),economics):
                    assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==result['money'][s]
                if arm==BASE:
                    assert not changes and result['money']==game['rewards']
                globs=entry.__globals__
                work=[w for w in result['work'] if w['seat']==seat]
                harvest=Counter()
                for w in work:
                    if w['cmd'][0]=='HARVEST':harvest.update({k:v for k,v in w['delta'].items() if v>0})
                row.update(completed=True,seed=game['seed'],seat=seat,cash=result['money'][seat],
                    opponent_cash=result['money'][1-seat],margin=result['money'][seat]-result['money'][1-seat],
                    baseline_cash=game['rewards'][seat],baseline_margin=game['rewards'][seat]-game['rewards'][1-seat],
                    economics=economics,harvested=dict(harvest),work=work,days=days,
                    action_changes=len(changes),changed_steps=changes,
                    history=globs.get('_MGT_HISTORY'),variant_report=globs.get('_TV_REPORT'),
                    overlay=globs.get('_SHP_REPORT'),router=globs.get('_MGT_REPORT'),
                    chassis=globs['_MGT_IMPL'].chassis.diagnostics,
                    max_action_seconds=max(elapsed),actions_over_1s=sum(t>1 for t in elapsed),ledger_verified=True)
        except Exception:
            row['error']=traceback.format_exc()
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            os.close(saved[0]);os.close(saved[1])
    write(path,row)
    return {k:row.get(k) for k in ('arm','episode','completed','margin','variant_report','error')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['freeze','historical'])
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    design=freeze()
    if args.stage=='freeze':
        print(json.dumps(design,indent=2));return
    jobs=[(arm,ep,design) for ep in design['diagnostic_episodes'] for arm in (BASE,CANDIDATE)]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run_job,j) for j in jobs]):
            print(json.dumps(f.result()),flush=True)


if __name__=='__main__':
    main()
