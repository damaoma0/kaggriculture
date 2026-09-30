"""T tapes for the single-day upkeep scenarios (thread upkeep, 2026-09-25). RUN ON KAGGLE ONLY (full games).

Plays T (the xopen T source results/fresh/xopen_20260925/src/mgt_lead_8d578ef8099b.py, options p1_min_value 30,
release_stale_d, fert_hold 1; T from step 0, the xopen 'T' arm) in the leader's own world (recorded seed, forced shop
schedule, opponent = the tape's recorded opp_actions) through the official framework, exactly as scripts/lead_g1.py
does, and records every action dict T returns. Locally, scripts/upkeep_engine.py replays the recorded actions and
must reproduce the game's final cash (checked by `upkeep_ttape.py verify`), so T's hour-0 farm states can be rebuilt
without running T.

usage: upkeep_ttape.py run [team:ep,...|g1] [--workers 4]      (Kaggle)
       upkeep_ttape.py verify                                   (local: replay check of every tape)
Writes results/fresh/upkeep_20260925/ttape/<ep>.json.gz: {game, episode, seat, seed, shops, cfg, src, actions, final,
opp_final}.
"""
import copy
import gzip
import hashlib
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'results/fresh/upkeep_20260925/ttape'
T_SRC = ROOT / 'results/fresh/xopen_20260925/src/mgt_lead_8d578ef8099b.py'
T_CFG = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
G1 = ['16732748:112655730', '16732748:112661570', '16732748:112667461', '16732748:112673479',
      '16770421:112708229', '16770421:112714050', '16770421:112715010', '16770421:112721923',
      '16730612:112444381', '16730612:112445586', '16730612:112447950', '16730612:112449129']
SEM = ROOT / 'data/leader_semantics'
TAPES = ROOT / 'data/leader_tapes'


def play(game):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    team_id, ep = game.split(':')
    sem = json.load(gzip.open(SEM / team_id / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    tape_path = sorted(TAPES.glob(f'{team_id}_*/{ep}.json.gz'))[0]
    tape = json.load(gzip.open(tape_path, 'rt', encoding='utf-8'))
    seat, seed = tape['seat'], tape['seed']
    shops_by_day = [list(tape['shops'][:min(8, d // 3)]) for d in range(31)]
    opp = tape['opp_actions']
    spec = importlib.util.spec_from_file_location('upkeep_T_' + ep, str(T_SRC))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.configure(sem, **T_CFG)
    acts = []
    old_end = E._end_of_day

    def end_hook(state, environment, day):
        old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    def me_agent(obs):
        a = mod.agent(obs)
        acts.append(copy.deepcopy(a))
        return a

    def opp_agent(obs):
        t = int(obs['step'])
        a = opp[t] if t < len(opp) else {}
        return copy.deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}

    E._end_of_day = end_hook
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = [float(s.reward) for s in env.state]
    finally:
        E._end_of_day = old_end
    src_sha = hashlib.sha256(T_SRC.read_bytes()).hexdigest()
    return dict(game=game, episode=int(ep), seat=seat, seed=seed, shops=tape['shops'], cfg=T_CFG, src=str(T_SRC.name),
                src_sha256=src_sha, actions=acts, final=final[seat], opp_final=final[1 - seat])


def job(game):
    try:
        t0 = time.time()
        r = play(game)
        r['wall'] = time.time() - t0
        OUT.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT / f"{game.split(':')[1]}.json.gz", 'wt', encoding='utf-8') as fh:
            json.dump(r, fh, separators=(',', ':'))
        return game, r['final'], r['wall'], None
    except Exception as exc:
        return game, None, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}'


def verify():
    sys.path.insert(0, str(HERE))
    import upkeep_engine as UE
    for f in sorted(OUT.glob('*.json.gz')):
        tt = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        team = tt['game'].split(':')[0]
        tape = UE.load_tape(team, tt['episode'])
        w = UE.World(tape['seed'], tape['shops'])
        seat = tape['seat']
        while w.t < 719:
            t = w.t
            a = [None, None]
            a[seat] = UE.tape_action(tt['actions'], t)
            a[1 - seat] = UE.tape_action(tape['opp_actions'], t)
            w.step(a)
        m = [float(w.farms[i]['money']) for i in range(2)]
        ok = round(m[seat]) == round(tt['final']) and round(m[1 - seat]) == round(tt['opp_final'])
        print(tt['game'], 'replay', m[seat], m[1 - seat], 'game', tt['final'], tt['opp_final'], 'OK' if ok else 'MISMATCH')


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == 'verify':
        verify()
        return
    games = G1 if len(args) < 2 or args[1] in ('g1', '--workers') else args[1].split(',')
    workers = int(args[args.index('--workers') + 1]) if '--workers' in args else 4
    from multiprocessing import Pool
    with Pool(workers) as pool:
        for game, final, wall, err in pool.imap_unordered(job, games):
            print(f'completed {game} final={final} wall={wall} {err or ""}', flush=True)


if __name__ == '__main__':
    main()
