"""Light in-process driver for the official kaggriculture engine (thread upkeep, 2026-09-25).

The engine module (kaggle_environments/envs/kaggriculture/kaggriculture.py, 1.32.7) is loaded BY PATH with a stub
for kaggle_environments.utils, so the heavy kaggle_environments package (OpenSpiel etc.) is never imported. The
driver reproduces what the framework does per step for this interpreter: state[i].action = action, interpreter(state,
env), state[0].observation.step = step + 1; the forced shop schedule of a recording is applied after each day end, as
scripts/lead_g1.py does (the engine's own RNG draw still runs, so the weed stream is unchanged).
Checked by replay_check(): both seats' recorded actions reproduce the tape's final cash.

World(seed, shops).step(actions) / .obs(seat) (agent observation, a deep copy) / .snapshot() / World.restore(snap)
"""
import copy
import gzip
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(r'C:/Users/xyygl/Documents/kaggriculture')
ENGINE_PATH = ROOT / '.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py'
SEM = ROOT / 'data/leader_semantics'
TAPES = ROOT / 'data/leader_tapes'
PASS = {'farmer': ['PASS'], 'hands': [], 'market': []}
CFG = dict(episodeSteps=720, actTimeout=1, boardSize=10, startingMoney=3000, maxMarketOrdersPerTurn=10, turnsPerDay=24,
           shedCapacity=100, weedSpawnChance=0.005, townShopUnlockInterval=3, townShopSellInterval=4,
           townCenterSellInterval=24, farmHandCostMult=1, marketParams={})


class A(dict):
    """dict with attribute access (the framework's Struct, enough for this interpreter)."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


def _resolve_seed(env, *, config_key='seed', fallback=None):
    if not hasattr(env, 'info') or env.info is None:
        env.info = {}
    seed = env.info.get('seed')
    if seed is None:
        seed = env.configuration.get(config_key)
    env.info['seed'] = seed
    return seed


_E = None


def engine():
    global _E
    if _E is None:
        saved = {k: sys.modules.get(k) for k in ('kaggle_environments', 'kaggle_environments.utils')}
        pkg = types.ModuleType('kaggle_environments')
        pkg.__path__ = []
        ut = types.ModuleType('kaggle_environments.utils')
        ut.resolve_episode_seed = _resolve_seed
        pkg.utils = ut
        sys.modules['kaggle_environments'], sys.modules['kaggle_environments.utils'] = pkg, ut
        try:
            spec = importlib.util.spec_from_file_location('upkeep_kgr_engine', str(ENGINE_PATH))
            E = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(E)
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        E._upkeep_shops = None
        orig_end = E._end_of_day

        def end_of_day(state, env, day):
            orig_end(state, env, day)
            sh = E._upkeep_shops
            if sh is not None:
                state[0].observation.town['unlocked_shops'][:] = sh[min(30, day + 1)]
        E._end_of_day = end_of_day
        _E = E
    return _E


class World:
    def __init__(self, seed, shops_flat):
        E = engine()
        self.E = E
        self.shops = [list(shops_flat[:min(8, d // 3)]) for d in range(31)]
        self.env = A(configuration=A(CFG), info={'seed': seed}, done=False)
        self.state = [A(observation=A(step=0, player=i, remainingOverageTime=60.0), action={}, status='ACTIVE',
                        reward=0) for i in range(2)]
        E._upkeep_shops = self.shops
        E.interpreter(self.state, self.env)
        self.state[0].observation['step'] = 0

    @property
    def t(self):
        return int(self.state[0].observation['step'])

    @property
    def farms(self):
        return self.state[0].observation['farms']

    def private(self, seat):
        return self.state[seat].observation['private']

    @property
    def market(self):
        return self.state[0].observation['market']

    def step(self, actions):
        t = self.t
        for i in range(2):
            a = actions[i]
            self.state[i]['action'] = a if isinstance(a, dict) else {}
        self.E._upkeep_shops = self.shops
        self.E.interpreter(self.state, self.env)
        self.state[0].observation['step'] = t + 1

    def obs(self, seat):
        o0 = self.state[0].observation
        t = self.t
        return copy.deepcopy(dict(step=t, day=t // 24, hour=t % 24, farms=o0['farms'], market=o0['market'],
                                  town=o0['town'], player=seat, private=self.state[seat].observation['private'],
                                  remainingOverageTime=60.0))

    def snapshot(self):
        o0 = self.state[0].observation
        return copy.deepcopy(dict(t=self.t, farms=o0['farms'], market=o0['market'], town=o0['town'],
                                  privates=[self.state[i].observation['private'] for i in range(2)],
                                  seed=self.env.info['seed'], shops=self.shops))

    @classmethod
    def restore(cls, snap):
        w = cls.__new__(cls)
        w.E = engine()
        w.shops = snap['shops']
        w.env = A(configuration=A(CFG), info={'seed': snap['seed']}, done=False)
        s = copy.deepcopy(snap)
        obs = []
        for i in range(2):
            o = A(step=s['t'], player=i, remainingOverageTime=60.0, farms=s['farms'], market=s['market'],
                  town=s['town'], private=s['privates'][i], day=s['t'] // 24, hour=s['t'] % 24)
            obs.append(o)
        w.state = [A(observation=obs[i], action={}, status='ACTIVE', reward=0) for i in range(2)]
        return w


def load_tape(team, ep):
    p = sorted(TAPES.glob(f'{team}_*/{ep}.json.gz'))[0]          # lead_g1 / lead_ledger's choice
    return json.load(gzip.open(p, 'rt', encoding='utf-8'))


def load_sem(team, ep):
    return json.load(gzip.open(SEM / str(team) / f'{ep}.json.gz', 'rt', encoding='utf-8'))


def tape_action(actions, t):
    a = actions[t] if t < len(actions) and isinstance(actions[t], dict) else {}
    return copy.deepcopy(a) if a else copy.deepcopy(PASS)


def replay_check(team, ep):
    tape = load_tape(team, ep)
    w = World(tape['seed'], tape['shops'])
    seat = tape['seat']
    while w.t < 719:
        t = w.t
        acts = [None, None]
        acts[seat] = tape_action(tape['actions'], t)
        acts[1 - seat] = tape_action(tape['opp_actions'], t)
        w.step(acts)
    money = [float(w.farms[i]['money']) for i in range(2)]
    return money, [float(x) for x in tape['rewards']]


if __name__ == '__main__':
    import time
    t0 = time.time()
    games = sys.argv[1:] or ['16730612:112444381']
    for g in games:
        team, ep = g.split(':')
        m, r = replay_check(team, ep)
        print(g, m, r, 'OK' if [round(x) for x in m] == [round(x) for x in r] else 'MISMATCH', '%.1fs' % (time.time() - t0))
