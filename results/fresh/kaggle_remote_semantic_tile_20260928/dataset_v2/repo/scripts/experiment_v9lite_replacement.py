"""Frozen 2x2 replacement-guard / wool-upturn experiment. One fresh process per game."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/v9lite_replacement_20260925'
BASE = ROOT / 'submissions/2026-09-24-mgt_v9lite/pkg'
ARMS = ('baseline', 'guard', 'upturn', 'combined')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding='utf-8')


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def modify(source, guard, upturn):
    if upturn:
        old = '    return min(today, _shp_price(item, x))'
        new = """    future = _shp_price(item, x)
    if item == 'WOOL' and 'YARN_STORE' in ((obs.get('town') or {}).get('unlocked_shops') or []):
        if future > today:
            _shp_count('wool_upturn_quotes')
        return future
    return min(today, future)"""
        assert source.count(old) == 1
        source = source.replace(old, new)
    if guard:
        old = 'def _shp_topups(state, obs, tape, day):'
        assert source.count(old) == 1
        source = source.replace(old, 'def _shp_topups_before_replacement(state, obs, tape, day):')
        anchor = '\ndef _shp_runs('
        assert source.count(anchor) == 1
        fragment = (ROOT / 'scripts/fragments/mgt_replacement_guard.py').read_text(encoding='utf-8')
        source = source.replace(anchor, '\n' + fragment + '\n\ndef _shp_runs(')
    compile(source, '<candidate>', 'exec')
    return source


def freeze():
    target = OUT / 'design.json'
    if target.exists():
        design = read(target)
        for arm, files in design['hashes'].items():
            for rel, expected in files.items():
                assert digest(OUT / 'packages' / arm / rel) == expected
        return design
    expected = read(BASE.parent / 'MANIFEST.json')['files']
    for rel, sha in expected.items():
        assert digest(BASE / rel) == sha, rel
    hashes = {}
    for arm in ARMS:
        pkg = OUT / 'packages' / arm
        for rel in expected:
            p = pkg / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE / rel, p)
        if arm != 'baseline':
            src = pkg / 'agents/mgt_y3.py'
            src.write_text(modify(src.read_text(encoding='utf-8'), arm in ('guard', 'combined'),
                                  arm in ('upturn', 'combined')), encoding='utf-8', newline='\n')
        hashes[arm] = {rel: digest(pkg / rel) for rel in expected}
        changed = [rel for rel in expected if hashes[arm][rel] != expected[rel]]
        assert changed == ([] if arm == 'baseline' else ['agents/mgt_y3.py']), changed
    opponent = OUT / 'opponent.py'
    shutil.copy2(ROOT / 'data/router_refresh_20260922/v56/main.py', opponent)
    rng = random.Random(int.from_bytes(os.urandom(16), 'big'))
    seeds = rng.sample(range(1, 2_000_000_000), 6)
    design = dict(created_utc=datetime.now(timezone.utc).isoformat(), arms=ARMS,
        hashes=hashes, opponent_sha256=digest(opponent), historical=[111261836, 111678108],
        pilot_seeds=seeds[:2], confirmation_seeds=seeds[2:], seats=[0, 1],
        protocol='Historical diagnostics: fixed recorded shops/opponent, full engine and ledgers. '
        'Pilot: all four arms, two fresh worlds, both seats, responsive V56, natural RNG, official time accounting. '
        'Select at most one unchanged candidate with positive paired margin and no errors; otherwise no promotion. '
        'Confirmation reserved: four more worlds, both seats, candidate and baseline. '
        'Report physical conversions, production, wages, uncertainty and lower tail. Small pilot cannot prove ladder strength.',
        no_submission=True)
    save(target, design)
    return design


def load_entry(arm):
    pkg = OUT / 'packages' / arm
    # Package modules own all search dependencies, not mutable workspace modules.
    sys.path.insert(0, str(pkg / 'scripts'))
    sys.path.append(str(pkg))
    from kaggle_environments.agent import get_last_callable
    source = pkg / 'main.py'
    return get_last_callable(source.read_text(encoding='utf-8'), path=str(source))


def telemetry(entry):
    g = entry.__globals__
    ours = g.get('_V9_STATE', {}).get('ours')
    return dict(search=g.get('_V9_REPORT'), sheep=ours.__globals__.get('_SHP_REPORT') if ours else None)


def historical(arm, episode):
    entry = load_entry(arm)
    from research_labour_profit import Simulator, engine, economic
    E = engine()
    with gzip.open(ROOT / f'data/ladder_panel/56395605/{episode}.json.gz', 'rt', encoding='utf-8') as f:
        g = json.load(f)
    seat = g['seat']
    actions = [None, None]
    actions[seat], actions[1-seat] = g['our_actions'], g['opp_actions']
    elapsed, recorded_actions = [], []
    with Simulator(g) as sim:
        old = E.interpreter
        def live(state, env):
            t = time.perf_counter()
            act = entry(deepcopy(state[seat].observation), None)
            elapsed.append(time.perf_counter() - t)
            recorded_actions.append(act)
            state[seat].action = act
            return old(state, env)
        E.interpreter = live
        try:
            result = sim.run(sim.initial, 0, 719, actions, capture=True)
        finally:
            E.interpreter = old
        econ = [economic(result['events'], i) for i in (seat, 1-seat)]
        for i, e in zip((seat, 1-seat), econ):
            assert 3000 + sum(e['revenue'].values()) - sum(e['spend'].values()) == result['money'][i]
        work = [w for w in result['work'] if w['seat'] == seat]
    save(OUT / 'traces' / f'{arm}-{episode}.json', dict(work=work, actions=recorded_actions))
    return dict(completed=len(recorded_actions) == 719, seat=seat, cash=result['money'][seat],
        rival_cash=result['money'][1-seat], margin=result['money'][seat]-result['money'][1-seat],
        economics=econ, telemetry=telemetry(entry), max_action_seconds=max(elapsed), ledger_verified=True,
        action_sha256=sha256(json.dumps(recorded_actions, sort_keys=True).encode()).hexdigest(),
        successful_plantings=[w for w in work if w['cmd'][0]=='PLANT' and w['t']>=24*24])


def live_game(arm, seed, seat):
    entry = load_entry(arm)
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from importlib.metadata import version
    assert version('kaggle-environments') == '1.32.7'
    opponent = OUT / 'opponent.py'
    rival = get_last_callable(opponent.read_text(encoding='utf-8'), path=str(opponent))
    players = [None, None]
    players[seat], players[1-seat] = entry, rival
    env = make('kaggriculture', configuration={'episodeSteps':720}, info={'seed':seed}, debug=False)
    steps = env.run(players)
    final = steps[-1]
    cash = [s['reward'] for s in final]
    good = len(steps)==720 and [s['status'] for s in final]==['DONE','DONE']
    save(OUT / 'logs' / f'{arm}-{seed}-{seat}-engine.json', getattr(env, 'logs', []))
    audited = {}
    if good:
        # Re-execute the actual actions, without either policy, to recover successful
        # work and both cash ledgers. Assert exact agreement with the timed live game.
        from research_labour_profit import Simulator, economic
        actions = [[steps[t+1][i]['action'] for t in range(719)] for i in (0,1)]
        shops = [list(steps[min(719,d*24)][0]['observation']['town']['unlocked_shops']) for d in range(31)]
        with Simulator(dict(seed=seed, seat=seat, shops=shops)) as sim:
            replay = sim.run(sim.initial,0,719,actions,capture=True)
            assert list(replay['money']) == cash, (replay['money'],cash)
            econ = [economic(replay['events'],i) for i in (seat,1-seat)]
            for i,e in zip((seat,1-seat),econ):
                assert 3000+sum(e['revenue'].values())-sum(e['spend'].values())==cash[i]
            own_work = [w for w in replay['work'] if w['seat']==seat]
        save(OUT/'traces'/f'{arm}-{seed}-{seat}.json',dict(work=own_work))
        audited = dict(economics=econ,ledger_verified=True,
            successful_plantings=[w for w in own_work if w['cmd'][0]=='PLANT' and w['t']>=24*24])
    return dict(completed=good, states=len(steps), statuses=[s['status'] for s in final],
        cash=cash[seat], rival_cash=cash[1-seat],
        margin=cash[seat]-cash[1-seat] if all(isinstance(v,(int,float)) for v in cash) else None,
        min_bank=[min(s[i]['observation'].get('remainingOverageTime',60) for s in steps) for i in (0,1)],
        shops=list(final[0]['observation']['town']['unlocked_shops']), telemetry=telemetry(entry),
        action_sha256=sha256(json.dumps([s[seat]['action'] for s in steps],sort_keys=True).encode()).hexdigest(),**audited)


def job(mode, arm, number, seat):
    start = time.perf_counter()
    row = dict(mode=mode, arm=arm, number=number, seat=seat, completed=False)
    try:
        row.update(historical(arm,number) if mode=='historical' else live_game(arm,number,seat))
    except Exception:
        row['error'] = traceback.format_exc()
    row['wall_seconds'] = time.perf_counter()-start
    save(OUT / mode / f'{arm}-{number}-{seat}.json', row)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('stage', choices=['freeze','historical','pilot','confirmation','job'])
    ap.add_argument('--args', nargs=4)
    ap.add_argument('--candidate', choices=ARMS[1:])
    opts=ap.parse_args()
    if opts.stage=='job':
        mode,arm,number,seat=opts.args
        job(mode,arm,int(number),int(seat));return
    d=freeze()
    if opts.stage=='freeze':
        print(json.dumps({k:v for k,v in d.items() if k!='hashes'},indent=2));return
    if opts.stage=='historical':
        jobs=[('historical',a,e,0) for e in d['historical'] for a in ARMS]
    else:
        arms=ARMS if opts.stage=='pilot' else ('baseline',opts.candidate)
        assert None not in arms
        if opts.stage=='confirmation':
            selection=read(OUT/'selection.json')
            assert selection['candidate']==opts.candidate, 'Freeze one candidate before opening confirmation'
        seeds=d['pilot_seeds'] if opts.stage=='pilot' else d['confirmation_seeds']
        jobs=[('live',a,s,p) for s in seeds for p in (0,1) for a in arms]
    for mode,arm,number,seat in jobs:
        dest=OUT/mode/f'{arm}-{number}-{seat}.json'
        if dest.exists():
            continue
        log=OUT/'logs'/f'{mode}-{arm}-{number}-{seat}.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('w',encoding='utf-8') as f:
            try:
                p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'job','--args',
                    mode,arm,str(number),str(seat)],stdout=f,stderr=subprocess.STDOUT,timeout=480)
                if not dest.exists():
                    save(dest,dict(completed=False,error=f'Child exited {p.returncode}'))
            except subprocess.TimeoutExpired:
                save(dest,dict(completed=False,error='480 second outer watchdog'))
        r=read(dest)
        print(json.dumps({k:r.get(k) for k in ('mode','arm','number','seat','completed','margin','wall_seconds','error')}),flush=True)
        if not r['completed']:
            break


if __name__=='__main__':
    main()
