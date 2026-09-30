"""sem4: leader SEMANTIC plans (counts and timing, not tiles) in the leader's own worlds, all four quadrants.

Worlds ("leader worlds"): the leader's recorded game -- recorded seed, the same forced shop sequence, the opponent
replaying its recorded actions (tape opp_actions); our agent (or the leader's own recorded actions) takes the leader's
seat. Only games where the leader holds all four quadrants by day 29 (no ' L' tile on the last board).

  lead_sem4.py worlds                        build results/fresh/lead_sem4_20260925/worlds.json (no games)
  lead_sem4.py check                         static checks, no games (Target counts, tile-leak audit, imports)
  lead_sem4.py smoke                         engine-free agent() calls on synthetic observations (no game)
  lead_sem4.py sync-s0                       regenerate agents/mgt_lead_sem0.py from agents/mgt_lead_sem.py
  lead_sem4.py run --arms A,B[,..] (--worlds FILE [--shard i/n] | --games team:ep,...) [--workers 4]
                   [--cfg 'k=v;k=v'] [--suffix X] [--skip-existing] [--force-local]
                                             play (arm, game) pairs; one JSON per pair under OUT/<arm><suffix>/<ep>.json
  lead_sem4.py repro [suffix]                reproduction check against stored results (see REPRO), OUT/<arm><suffix>/
  lead_sem4.py report [--worlds FILE] [--arms ...]   per-arm gap to the leader, per-quadrant tables -> OUT/report.md

Arms (ARMS below). EXEC_CFG = the deploy's executor defaults that agents/mgt_lead.py lacks (p1_min_value 30,
release_stale_d True, fert_hold 1); every arm that uses the mgt_lead executor gets it, D has them as defaults.
  LEADER  the leader's own recorded actions (tape['actions']) through the same hooks (must reproduce its recorded cash)
  T0      agents/mgt_lead_semT.py (byte copy of agents/mgt_lead.py, sha256 a1cd70e6..., git e1fa483) + EXEC_CFG:
          leader tiles, counts, timing; no removal of live plants (mgt_lead digs a crop only once it has finished)
  T       agents/mgt_lead_exact.py (= mgt_lead.py + exact removals, default on) + EXEC_CFG: the leader's DIGs of
          live plants on our tile for that cohort, harvest first
  S       agents/mgt_lead_sem.py + EXEC_CFG: leader counts/timing incl. removals as counts, OUR tiles (care order,
          cohort blocks, innermost)
  S0      agents/mgt_lead_sem0.py + EXEC_CFG: the same with the deploy's nearest-centre tiles
  D       agents/mgt_lead_semDx.py = the deploy as committed at 3f9798f (agents/mgt_lead_deploy.py, sha256 2bfca110...)
          with its one default-on option that mgt_lead.py lacks, tie_value, set to 0 (its other extra options
          hire_demand / maint_goal are off by default): the same executor settings as T0/T/S/S0; its own plan /
          market / hires; THIS episode excluded from retrieval (any seat); lead_ablation E2 'full' equivalent
  Dp      "D+": agents/mgt_lead_semDp.py = that deploy as is (byte copy, tie_value 1); reference only
reproduction / control arms (step 1 only): T0r / T0Lr (mgt_lead snapshot / live file, own defaults), T0ffr (fert_hold 1),
  Tc0r (mgt_lead_exact.py with exact_removals False, own defaults), Tc (mgt_lead_exact.py + EXEC_CFG, exact_removals
  False; must equal T0); optional: D4 (D with DEP_CFG land_max 3: the deploy may buy the fourth quadrant, land_max 2
  never buys SE), Snr (S without count removals).

Recorded per game and per quadrant (first NW free / second NE $1,000 / third SW $2,000 / fourth SE $4,000, by tile
position): unlocked tile-days and day-start occupancy by kind, harvested units by product (HARVEST and
COLLECT_FERTILIZER attributed to the tile the unit stood on), income = units x the game's realised average sale price
(fallback: the market price at the end, counted separately), effective ops by type, plantings, deaths (unwatered
plants, escaped animals) and units lost to decay; per game: final cash, the leader's recorded cash, moves, effective
maintenance ops, unit-steps, wages, shed pickups / items, deposits, items discarded by the 100-item shed cap at midnight.
"""
import gzip
import hashlib
import importlib.util
import json
import os
import random
import statistics as st
import sys
import time
import traceback
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1  # noqa: E402  (SEM / TAPES paths, _label, GAMES)

OUT = ROOT / 'results/fresh/lead_sem4_20260925'
WORLDS = OUT / 'worlds.json'
TEAMS = {'16732748': 'DSM', '16623559': 'DECEM', '16770421': 'Vadim', '16730612': 'MG'}
PER_TEAM = 12
KNOWN_COLLAPSE = {112708229: 'replayed opponent collapses (lead_ablation.COLLAPSED; G1 opp 24,078 vs recorded 82,753)'}
EXEC_CFG = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}   # deploy executor defaults (task brief)
MAIN_ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
ARMS = {
    'LEADER': dict(kind='leader'),
    'T0': dict(kind='module', path='agents/mgt_lead_semT.py', cfg=EXEC_CFG),
    'T': dict(kind='module', path='agents/mgt_lead_exact.py', cfg=EXEC_CFG),
    'S': dict(kind='module', path='agents/mgt_lead_sem.py', cfg=EXEC_CFG),
    'S0': dict(kind='module', path='agents/mgt_lead_sem0.py', cfg=EXEC_CFG),
    'D': dict(kind='deploy', path='agents/mgt_lead_semDx.py'),
    'Dp': dict(kind='deploy', path='agents/mgt_lead_semDp.py'),
    # reproduction / control only
    'T0r': dict(kind='module', path='agents/mgt_lead_semT.py', cfg={}),
    'T0Lr': dict(kind='module', path='agents/mgt_lead.py', cfg={}),
    'T0ffr': dict(kind='module', path='agents/mgt_lead_semT.py', cfg={'fert_hold': 1}),
    'Tc0r': dict(kind='module', path='agents/mgt_lead_exact.py', cfg={'exact_removals': False}),
    'Tc': dict(kind='module', path='agents/mgt_lead_exact.py', cfg=dict(EXEC_CFG, exact_removals=False)),
    # optional
    'D4': dict(kind='deploy', path='agents/mgt_lead_semDx.py', dep_cfg={'land_max': 3}),
    'Snr': dict(kind='module', path='agents/mgt_lead_sem.py', cfg=dict(EXEC_CFG, count_removals=False)),
}
ARM_LABEL = {'Dp': 'D+'}
# stored results the reproduction arms must match to the dollar (final cash and opponent cash)
REPRO = {
    'T0r': 'results/fresh/lead_agent_20260924/abl_Gbase2_remote',   # mgt_lead defaults (= abl_Gcut_remote = abl_Gtr_remote)
    'T0Lr': 'results/fresh/lead_agent_20260924/abl_Gbase2_remote',
    'Tc0r': 'results/fresh/lead_agent_20260924/abl_Gbase2_remote',  # exact_removals False = mgt_lead
    'T0ffr': 'results/fresh/lead_agent_20260924/abl_Gff1_remote',   # mgt_lead + fert_hold 1 (lead_ablation Gff1)
    'D': 'results/fresh/lead_agent_20260924/abl_E2ff1_remote',      # deploy before tie_value (mgt_lpv_ff1 = e1fa483 behaviour)
    'Dp': 'results/fresh/lead_agent_20260924/abl_E2dep8_remote',    # deploy with tie_value 1 (= abl_E2_tievalff)
}
CONTROL_PAIRS = [('Tc', 'T0'), ('Tc0r', 'T0r')]   # must be identical: final, opponent and every day-start cash
RUN_ONLY = ['T', 'S', 'S0']                        # step 1 engine smoke: result files, no FAILED
REPRO_ARMS = ['T0r', 'T0Lr', 'T0ffr', 'Tc0r', 'Tc', 'T0', 'T', 'S', 'S0', 'D', 'Dp', 'LEADER']
REPRO_GAMES = ['16732748:112655730', '16770421:112714050']
END_AGE = {'STRAWBERRY': 16, 'TOMATO': 11, 'WHEAT': 4, 'CARROT': 3, 'MELON': 12}   # last age in its life
FIRST_AGE = {'STRAWBERRY': 10, 'TOMATO': 8, 'WHEAT': 2, 'CARROT': 2, 'MELON': 10}
QUADS = ('NW', 'NE', 'SW', 'SE')
QNAME = {'NW': 'first', 'NE': 'second', 'SW': 'third', 'SE': 'fourth'}
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
MAINT = ('WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER')
TILE_OPS = MAINT + ('PLANT', 'DIG', 'BUILD_COOP', 'BUILD_PASTURE', 'PLACE_ANIMAL')
PRODUCT_OF = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}


def _quad(x, y):
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def _sha(path):
    p = ROOT / path
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _load_sem(team_id, ep):
    return json.load(gzip.open(lead_g1.SEM / str(team_id) / f'{ep}.json.gz', 'rt', encoding='utf-8'))


def _tape_path(team_id, ep):
    return next(p for p in sorted(lead_g1.TAPES.glob(f'{team_id}_*/{ep}.json.gz')))   # lead_g1.play's choice


def _kind(t):
    if t == 'LOCKED':
        return 'LOCKED'
    if t is None:
        return 'EMPTY'
    if not isinstance(t, dict):
        return str(t)
    if t.get('kind') == 'PLANT':
        return t.get('crop')
    if t.get('kind') == 'WEED':
        return 'WEED'
    if t.get('animal'):
        return t['animal']
    return 'S_' + str(t.get('kind'))


def _free_gb():
    try:
        if os.name == 'nt':
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 2 ** 30
        for line in open('/proc/meminfo'):
            if line.startswith('MemAvailable'):
                return int(line.split()[1]) / 2 ** 20
    except Exception:
        pass
    return None


# ============================================================================ worlds

def build_worlds():
    """four-quadrant leader games with both a semantics file and a tape; up to PER_TEAM per team: lead_g1.GAMES'
    four-quadrant games first, the rest evenly spaced over the sorted remaining episode ids (midpoint rule)."""
    g1 = {}
    for g in lead_g1.GAMES:
        t, e = g.split(':')
        g1.setdefault(t, []).append(e)
    worlds, by_team, excluded = [], {}, {}
    for team_id, name in TEAMS.items():
        sems = {p.name.split('.')[0] for p in (lead_g1.SEM / team_id).glob('*.json.gz')}
        tapes = {p.name.split('.')[0] for p in lead_g1.TAPES.glob(f'{team_id}_*/*.json.gz')}
        both = sorted(sems & tapes, key=int)
        four, not4 = [], []
        info = {}
        for ep in both:
            sem = _load_sem(team_id, ep)
            nl = sum(1 for x in sem['days'][29]['board'] if x == ' L')
            (four if nl == 0 else not4).append(ep)
            info[ep] = sem
        forced = [e for e in g1.get(team_id, []) if e in four]
        rest = [e for e in four if e not in forced]
        k = max(0, min(PER_TEAM, len(four)) - len(forced))
        picked = [rest[int((i + 0.5) * len(rest) / k)] for i in range(k)] if k and rest else []
        chosen = sorted(set(forced) | set(picked), key=int)
        excluded[name] = dict(semantics=len(sems), tapes=len(tapes), both=len(both), four_quadrant=len(four),
                              not_four_quadrant=len(not4), g1_games_not_four=[e for e in g1.get(team_id, []) if e not in four])
        for ep in chosen:
            sem = info[ep]
            tp = _tape_path(team_id, ep)
            tape = json.load(gzip.open(tp, 'rt', encoding='utf-8'))
            seat = sem['meta']['seat']
            assert tape['seat'] == seat and int(tape['episode']) == int(ep), (team_id, ep)
            land = {}
            for q in ('NE', 'SW', 'SE'):
                for d in range(30):
                    b = sem['days'][d + 1]['board'] if d + 1 < 30 else sem['days'][d]['board']
                    if any(b[y * 10 + x] != ' L' for y in range(10) for x in range(10) if _quad(x, y) == q):
                        land[q] = d
                        break
            flags = []
            if int(ep) in KNOWN_COLLAPSE:
                flags.append('opp_collapse_known: ' + KNOWN_COLLAPSE[int(ep)])
            if not sem['meta'].get('cash_match'):
                flags.append('semantics_cash_mismatch')
            worlds.append(dict(game=f'{team_id}:{ep}', team=name, team_id=team_id, episode=int(ep), seat=seat,
                               seed=tape['seed'], opponent=sem['meta'].get('opponent'),
                               semantics=str((lead_g1.SEM / team_id / f'{ep}.json.gz').relative_to(ROOT).as_posix()),
                               tape=str(tp.relative_to(ROOT).as_posix()), in_g1_games=ep in forced,
                               leader_final=sem['meta']['rewards'][seat], opp_final_recorded=sem['meta']['rewards'][1 - seat],
                               land_days=land, flags=flags))
        by_team[name] = len(chosen)
    out = dict(built=time.strftime('%Y-%m-%d %H:%M'), rule=(
        'four-quadrant leader games (no " L" tile on the day-29 board) with both data/leader_semantics/<team>/<ep>.json.gz '
        'and a tape data/leader_tapes/<team>_*/<ep>.json.gz; per team: lead_g1.GAMES four-quadrant games always, then '
        'evenly spaced picks (index int((i+0.5)*n/k)) over the sorted remaining ids, up to 12 per team'),
        teams=TEAMS, n=len(worlds), by_team=by_team, pool=excluded, worlds=worlds)
    OUT.mkdir(parents=True, exist_ok=True)
    WORLDS.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f'{len(worlds)} worlds -> {WORLDS.relative_to(ROOT)}', by_team)
    for name, v in excluded.items():
        print(' ', name, v)
    for w in worlds:
        if w['flags'] or w['in_g1_games']:
            print('  ', w['game'], w['team'], 'G1' if w['in_g1_games'] else '', w['flags'])
    return out


def sync_s0():
    """agents/mgt_lead_sem0.py = agents/mgt_lead_sem.py with place_rule "centre" (and its own first docstring lines)."""
    s = open(ROOT / 'agents/mgt_lead_sem.py', encoding='utf-8', newline='').read()
    a = ('"""mgt_lead_sem: follow a leader\'s SEMANTIC plan (counts and timing, NOT tile positions) with the\n'
         'mgt_lead executor (thread sem4, 2026-09-25; research arm S).')
    b = ('"""mgt_lead_sem0: arm S0 = agents/mgt_lead_sem.py with place_rule "centre" (the deploy\'s nearest-centre tile '
         'rule,\nno care order, no cohort blocks); everything else identical (thread sem4, 2026-09-25).')
    c = '    "place_rule": "care",     # sem4: "care" (arm S) | "centre" (arm S0, the deploy\'s nearest-centre rule)'
    d = '    "place_rule": "centre",   # sem4: "care" (arm S) | "centre" (arm S0, the deploy\'s nearest-centre rule)'
    assert s.count(a) == 1 and s.count(c) == 1
    open(ROOT / 'agents/mgt_lead_sem0.py', 'w', encoding='utf-8', newline='').write(s.replace(a, b).replace(c, d))
    print('agents/mgt_lead_sem0.py written from agents/mgt_lead_sem.py')


def load_worlds(path=None):
    return json.loads(Path(path or WORLDS).read_text(encoding='utf-8'))['worlds']


# ============================================================================ agents

def _load_module(path, tag):
    spec = importlib.util.spec_from_file_location(f'sem4_{tag}_{os.getpid()}_{time.time_ns()}', ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DeployArm:
    """the full deploy (lead_ablation._DeployAdapter 'full' mode, no swaps): its own target builder, market and
    hires; THIS episode is never retrieved (any seat); the day-0 exemplar is swapped if it is this very game."""

    def __init__(self, path, ep, dep_cfg=None):
        old = os.environ.get('DEP_CFG_JSON')
        if dep_cfg:
            os.environ['DEP_CFG_JSON'] = json.dumps(dep_cfg)
        try:
            self.mod = mod = _load_module(path, 'deploy')
        finally:
            if dep_cfg:
                if old is None:
                    os.environ.pop('DEP_CFG_JSON', None)
                else:
                    os.environ['DEP_CFG_JSON'] = old
        self.ep = int(ep)
        lpr = mod._dep_lpr
        orig = getattr(lpr, '_abl_orig_retrieve', None) or lpr.retrieve
        lpr._abl_orig_retrieve = orig
        ep_ = self.ep

        def retrieve(*a, **kw):
            kw['exclude_episode'] = ep_
            return orig(*a, **kw)
        lpr.retrieve = retrieve
        if mod._DEP_EXEMPLAR == self.ep:
            mod._DEP_EXEMPLAR = 112661570
            mod._DEP_BASE = None
        self.dep_cfg = dict(mod.DEP_CFG)

    @property
    def _S(self):
        return self.mod._S

    def configure(self, sem, **cfg):
        self.mod.CFG.update(cfg)          # the leader's semantics are NOT given to the deploy

    def agent(self, obs):
        return self.mod.mgt_lead_deploy_agent(obs)


# ============================================================================ play

def play(game, arm, cfg_extra=None):
    spec = ARMS[arm]
    team_id, ep = game.split(':')
    sem = _load_sem(team_id, ep)
    tape = json.load(gzip.open(_tape_path(team_id, ep), 'rt', encoding='utf-8'))
    seat, seed = tape['seat'], tape['seed']
    assert seat == sem['meta']['seat']
    shops_by_day = [list(tape['shops'][:min(8, d // 3)]) for d in range(31)]
    opp, mine = tape['opp_actions'], tape['actions']
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    cfg = {}
    mod = None
    if spec['kind'] == 'module':
        cfg = dict(spec.get('cfg') or {}, **(cfg_extra or {}))
        mod = _load_module(spec['path'], arm)
        mod.configure(sem, **cfg)
    elif spec['kind'] == 'deploy':
        cfg = dict(cfg_extra or {})
        mod = DeployArm(spec['path'], ep, spec.get('dep_cfg'))
        mod.configure(sem, **cfg)

    def newq():
        return dict(unlocked_tile_days=0, occ=Counter(), harvested=Counter(), ops=Counter(), noeff=Counter(),
                    plant=Counter(), deaths=Counter(), rot_units=Counter())
    Q = {q: newq() for q in QUADS}
    days = [dict(cash=None, board=None, hands=0, hires=0, wages=0.0, land=0.0, unit_steps=0, moves=0, passes=0,
                 eff=Counter(), noeff=Counter(), harv=Counter(), sold=Counter(), rev=Counter(), bought=Counter(),
                 spend=Counter(), failed=Counter(), plant=Counter(), deaths=Counter(), discards=Counter(),
                 pick_n=0, pick_items=0, picked=Counter(), deposit_n=0, deposited=Counter(), shed_mid=None,
                 carried_mid=None, unlocked=None, dug=Counter(), dug_ended=Counter(), dug_lost=Counter(),
                 dug_harv=Counter()) for _ in range(30)]
    harv_day = {}          # tile -> last day with an effective HARVEST there (harvest-before-dig detection)
    land_log = []
    farms_box, step_box = [], [0]
    olds = (E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day, E._do_buy_land, E._decay_plants)

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm):
            return olds[0](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        op = action[0] if isinstance(action, list) and action else None
        p0 = E._farmer_position(farm, idx)
        p0 = tuple(p0) if p0 is not None else None
        t = farm['tiles'][p0[1]][p0[0]] if p0 is not None else None
        t0 = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0 = dict(private['shed'])
        r = olds[0](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        d = days[min(29, day)]
        if op is None or op == 'PASS':
            d['passes'] += 1
            return r
        p1 = E._farmer_position(farm, idx)
        p1 = tuple(p1) if p1 is not None else None
        t = farm['tiles'][p1[1]][p1[0]] if p1 is not None else None
        t1 = dict(t) if isinstance(t, dict) else t
        inv1 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        eff = not (p0 == p1 and t0 == t1 and inv0 == inv1 and shed0 == private['shed'])
        if op in MOVES:
            if eff:
                d['moves'] += 1
            else:
                d['noeff']['MOVE'] += 1
            return r
        q = _quad(*p0) if p0 is not None else None
        key = op
        if op == 'PLACE' and isinstance(t1, dict) and t1.get('animal') and not (isinstance(t0, dict) and t0.get('animal')):
            key = 'PLACE_ANIMAL'
        if not eff:
            d['noeff'][key] += 1
            if q and key in TILE_OPS:
                Q[q]['noeff'][key] += 1
            return r
        d['eff'][key] += 1
        if q and key in TILE_OPS:
            Q[q]['ops'][key] += 1
        if op == 'HARVEST' or op == 'COLLECT_FERTILIZER':
            if op == 'HARVEST':
                harv_day[p0] = day
            for k, v in inv1.items():
                gain = v - inv0.get(k, 0)
                if gain > 0:
                    d['harv'][k] += gain
                    if q:
                        Q[q]['harvested'][k] += gain
        elif op == 'DIG' and isinstance(t0, dict) and t0.get('kind') == 'PLANT':
            # a plant dug up: live (age <= its last production / max-yield age) or ended (rotting), yield destroyed,
            # harvested on that tile earlier the same day
            crop = str(t0.get('crop'))
            age = day - int(t0.get('planted_day', day))
            (d['dug'] if age <= END_AGE.get(crop, 99) else d['dug_ended'])[crop] += 1
            if age >= FIRST_AGE.get(crop, 0) and int(t0.get('yield_units', 0) or 0) > 0:
                d['dug_lost'][crop] += int(t0['yield_units'])
            if harv_day.get(p0) == day:
                d['dug_harv'][crop] += 1
        elif op == 'PLANT' and len(action) > 1:
            d['plant'][str(action[1])] += 1
            if q:
                Q[q]['plant'][str(action[1])] += 1
        elif op == 'PICKUP':
            d['pick_n'] += 1
            for k, v in inv1.items():
                if v > inv0.get(k, 0):
                    d['pick_items'] += v - inv0.get(k, 0)
                    d['picked'][k] += v - inv0.get(k, 0)
        elif op in ('PLACE', 'DROP') and key != 'PLACE_ANIMAL' and p0 in SHED:
            dep = {k: v - inv1.get(k, 0) for k, v in inv0.items() if v > inv1.get(k, 0)}
            if dep:
                d['deposit_n'] += 1
                for k, v in dep.items():
                    d['deposited'][k] += v
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = olds[1](op, item, price, farm, private, market, shed_capacity)
        if is_me(farm):
            dd = days[min(29, step_box[0] // 24)]
            if not r and op != 'SELL':
                dd['failed'][f'{op}:{item}'] += 1
            elif r and op == 'SELL':
                dd['sold'][item] += 1
                dd['rev'][item] += price
            elif r:
                dd['bought'][item] += 1
                dd['spend'][item] += price
        return r

    def hire_hook(farm, private, board_size, mult=1):
        m0, n0 = farm['money'], len(farm['hands'])
        olds[2](farm, private, board_size, mult)
        if is_me(farm) and len(farm['hands']) > n0:
            dd = days[min(29, step_box[0] // 24)]
            dd['hires'] += 1
            dd['wages'] += m0 - farm['money']

    def land_hook(farm, board_size):
        m0, u0 = farm['money'], list(farm['unlocked_quadrants'])
        r = olds[4](farm, board_size)
        if is_me(farm) and len(farm['unlocked_quadrants']) > len(u0):
            dd = days[min(29, step_box[0] // 24)]
            dd['land'] += m0 - farm['money']
            land_log.append([farm['unlocked_quadrants'][-1], step_box[0] // 24, step_box[0] % 24, m0 - farm['money']])
        return r

    def decay_hook(farm, step):
        if not is_me(farm):
            return olds[5](farm, step)
        before = {}
        for y in range(10):
            for x in range(10):
                t = farm['tiles'][y][x]
                if isinstance(t, dict) and t.get('kind') == 'PLANT':
                    before[(x, y)] = (t['crop'], t.get('yield_units', 0))
        r = olds[5](farm, step)
        dd = days[min(29, step // 24)]
        for (x, y), (crop, by) in before.items():
            t = farm['tiles'][y][x]
            ay = t.get('yield_units', 0) if isinstance(t, dict) and t.get('kind') == 'PLANT' else 0
            lost = max(0, by) - max(0, ay)
            if lost > 0:
                Q[_quad(x, y)]['rot_units'][crop] += lost
                dd['deaths']['rot_units_' + crop] += lost
            if not (isinstance(t, dict) and t.get('kind') == 'PLANT'):
                Q[_quad(x, y)]['deaths'][('rotted_' if by > 0 else 'ended_') + crop] += 1
                dd['deaths'][('rotted_' if by > 0 else 'ended_') + crop] += 1
        return r

    def end_hook(state, environment, day):
        f = state[0].observation.farms[seat]
        before = [[dict(t) if isinstance(t, dict) else t for t in row] for row in f['tiles']]
        priv = state[seat].observation.private
        shed0 = Counter({k: int(v) for k, v in dict(priv['shed']).items() if v})
        carried = Counter()
        for inv in priv['inventories']:
            for k, v in dict(inv).items():
                if v:
                    carried[k] += int(v)
        days[min(29, day)]['hands'] = len(f['hands'])
        olds[3](state, environment, day)
        shed1 = Counter({k: int(v) for k, v in dict(state[seat].observation.private['shed']).items() if v})
        dd = days[min(29, day)]
        dd['shed_mid'], dd['carried_mid'] = sum(shed0.values()), sum(carried.values())
        for k in set(shed0) | set(carried):
            lost = shed0.get(k, 0) + carried.get(k, 0) - shed1.get(k, 0)
            if lost > 0:
                dd['discards'][k] += lost
        for y in range(10):
            for x in range(10):
                a, b = before[y][x], f['tiles'][y][x]
                q = _quad(x, y)
                if isinstance(a, dict) and a.get('kind') == 'PLANT' and not (isinstance(b, dict) and b.get('kind') == 'PLANT'):
                    Q[q]['deaths']['unwatered_' + a['crop']] += 1
                    dd['deaths']['unwatered_' + a['crop']] += 1
                if isinstance(a, dict) and a.get('animal') and not (isinstance(b, dict) and b.get('animal')):
                    Q[q]['deaths']['escaped_' + a['animal']] += 1
                    dd['deaths']['escaped_' + a['animal']] += 1
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, 'farms', None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, 'step', 0) or 0)
        return box['orig'](state, environment)

    times = []
    end_prices = {}

    def me_agent(obs):
        t = int(obs['step'])
        d, h = divmod(t, 24)
        f = obs['farms'][seat]
        if d < 30:
            days[d]['unit_steps'] += 1 + len(f['hands'])
            if h == 0:
                days[d]['cash'] = f['money']
                days[d]['board'] = ''.join(lead_g1._label(x) for row in f['tiles'] for x in row)
                days[d]['unlocked'] = list(f.get('unlocked_quadrants', []))
                for y in range(10):
                    for x in range(10):
                        k = _kind(f['tiles'][y][x])
                        if k != 'LOCKED':
                            qq = Q[_quad(x, y)]
                            qq['unlocked_tile_days'] += 1
                            qq['occ'][k] += 1
        if t >= 718:
            end_prices.update(dict(obs['market']['prices']))
        t0 = time.time()
        if spec['kind'] == 'leader':
            a = mine[t] if t < len(mine) else {}
            a = deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}
        else:
            a = mod.agent(obs)
        times.append(time.time() - t0)
        return a

    def opp_agent(obs):
        t = int(obs['step'])
        a = opp[t] if t < len(opp) else {}
        return deepcopy(a) if a else {'farmer': ['PASS'], 'hands': [], 'market': []}

    E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day, E._do_buy_land, E._decay_plants = (
        apply_hook, commit_hook, hire_hook, end_hook, land_hook, decay_hook)
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
        box['orig'] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = [float(s.reward) for s in env.state]
        statuses = [s.status for s in env.state]
    finally:
        (E._apply_unit_action, E._commit_unit, E._do_hire, E._end_of_day, E._do_buy_land, E._decay_plants) = olds

    # ---- totals, prices, per-quadrant income
    tot = defaultdict(Counter)
    num = Counter()
    for dd in days:
        for k in ('eff', 'noeff', 'harv', 'sold', 'rev', 'bought', 'spend', 'failed', 'plant', 'deaths', 'discards',
                  'picked', 'deposited', 'dug', 'dug_ended', 'dug_lost', 'dug_harv'):
            tot[k].update(dd[k])
        for k in ('hires', 'wages', 'land', 'unit_steps', 'moves', 'passes', 'pick_n', 'pick_items', 'deposit_n'):
            num[k] += dd[k]
    avg_price = {p: tot['rev'][p] / tot['sold'][p] for p in tot['sold'] if tot['sold'][p]}
    quads = {}
    for q in QUADS:
        qq = Q[q]
        inc = fb_units = fb_inc = 0.0
        for p, u in qq['harvested'].items():
            if p in avg_price:
                inc += u * avg_price[p]
            else:
                fb_units += u
                fb_inc += u * float(end_prices.get(p, 0))
        quads[QNAME[q]] = dict(quadrant=q, unlocked_tile_days=qq['unlocked_tile_days'], occ_tile_days=dict(qq['occ']),
                               harvested=dict(qq['harvested']), income=round(inc, 1), income_fallback=round(fb_inc, 1),
                               fallback_units=fb_units, ops=dict(qq['ops']), noeff=dict(qq['noeff']),
                               plant=dict(qq['plant']), deaths=dict(qq['deaths']), rot_units=dict(qq['rot_units']))
    target_cash = sem['meta']['rewards'][seat]
    target_opp = sem['meta']['rewards'][1 - seat]
    tdays = sem['days']
    agent_log, extra = {}, {}
    if mod is not None:
        S_ = getattr(mod, '_S', None)
        if S_:
            agent_log = {k: v for k, v in dict(S_.get('log', {})).items()}
            extra['pmap_n'] = len(S_.get('pmap', {}))
        if spec['kind'] == 'deploy':
            picks = list(mod.mod._DEP.get('picks', []))
            extra.update(deploy_picks=picks, retrieval_leak=any(int(e) == int(ep) for _, e in picks),
                         deploy_exemplar=mod.mod._DEP_EXEMPLAR, dep_cfg_land_max=mod.dep_cfg.get('land_max'),
                         deploy_errors=mod.mod._DEP.get('errors', 0))
    out = dict(
        arm=arm, game=game, team=TEAMS.get(team_id, team_id), episode=int(ep), seat=seat, cfg=cfg,
        agent_path=spec.get('path'), agent_sha=_sha(spec['path']) if spec.get('path') else None,
        final=final[seat], opp_final=final[1 - seat], target=target_cash, target_opp=target_opp,
        ratio=final[seat] / target_cash, gap=target_cash - final[seat], statuses=statuses,
        opp_collapse=final[1 - seat] < 0.8 * target_opp, collapse_known=int(ep) in KNOWN_COLLAPSE,
        tmax=max(times) if times else 0, tsum=sum(times), land=land_log,
        totals=dict(moves=num['moves'], maint_ops_eff=sum(tot['eff'].get(k, 0) for k in MAINT),
                    eff_ops=dict(tot['eff']), noeff=dict(tot['noeff']), passes=num['passes'], unit_steps=num['unit_steps'],
                    hires=num['hires'], wages=num['wages'], land_spend=num['land'], pickups=num['pick_n'],
                    pickup_items=num['pick_items'], picked=dict(tot['picked']), deposits=num['deposit_n'],
                    deposited=dict(tot['deposited']), discards=dict(tot['discards']),
                    discards_total=sum(tot['discards'].values()), harvested=dict(tot['harv']), sold=dict(tot['sold']),
                    rev=dict(tot['rev']), bought=dict(tot['bought']), spend=dict(tot['spend']), failed=dict(tot['failed']),
                    plant=dict(tot['plant']), deaths=dict(tot['deaths']), avg_price=avg_price, end_prices=end_prices,
                    dug_live=dict(tot['dug']), dug_ended=dict(tot['dug_ended']), dug_yield_lost=dict(tot['dug_lost']),
                    dug_after_harvest=dict(tot['dug_harv'])),
        quadrants=quads,
        days=[dict(day=i, cash=dd['cash'], target_cash=tdays[i]['cash_start'], hands=dd['hands'],
                   target_hands=tdays[i]['labour']['hands_present'], hires=dd['hires'], wages=dd['wages'],
                   unit_steps=dd['unit_steps'], moves=dd['moves'], maint=sum(dd['eff'].get(k, 0) for k in MAINT),
                   harv=dict(dd['harv']), plant=dict(dd['plant']), sold=dict(dd['sold']), rev=dict(dd['rev']),
                   dug=dict(dd['dug']), dug_ended=dict(dd['dug_ended']),
                   deaths=dict(dd['deaths']), discards=dict(dd['discards']), shed_mid=dd['shed_mid'],
                   carried_mid=dd['carried_mid'], unlocked=dd['unlocked'], board=dd['board'],
                   label_dist=(sum(abs(v) for v in (Counter(dd['board'][j:j + 2] for j in range(0, 200, 2))
                                                     - Counter(tdays[i]['board'])).values())
                               + sum(abs(v) for v in (Counter(tdays[i]['board'])
                                                      - Counter(dd['board'][j:j + 2] for j in range(0, 200, 2))).values())) // 2
                   if dd['board'] else None)
              for i, dd in enumerate(days)],
        agent_log=agent_log, **extra)
    return out


def job(args):
    arm, game, cfg_extra, suffix, skip = args
    o = OUT / f'{arm}{suffix}'
    f = o / f"{game.split(':')[1]}.json"
    if skip and f.exists():
        return (arm, game, 'skipped', None)
    try:
        t0 = time.time()
        r = play(game, arm, cfg_extra)
        r['wall'] = time.time() - t0
        o.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(r, default=str), encoding='utf-8')
        return (arm, game, r['ratio'], None)
    except Exception as exc:
        return (arm, game, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2500:]}')


def run(argv):
    arms, games, workers, cfg, suffix, skip, force = [], None, int(os.environ.get('LP_WORKERS', 4)), {}, '', False, False
    worlds_path, shard = None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--arms':
            arms = argv[i + 1].split(','); i += 2
        elif a == '--games':
            games = argv[i + 1].split(','); i += 2
        elif a == '--worlds':
            worlds_path = argv[i + 1]; i += 2
        elif a == '--shard':
            k, n = argv[i + 1].split('/'); shard = (int(k), int(n)); i += 2
        elif a == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif a == '--suffix':
            suffix = argv[i + 1]; i += 2
        elif a == '--skip-existing':
            skip = True; i += 1
        elif a == '--force-local':
            force = True; i += 1
        elif a == '--cfg':
            for kv in argv[i + 1].split(';'):
                k, v = kv.split('=', 1)
                try:
                    v = json.loads(v)
                except Exception:
                    pass
                cfg[k] = v
            i += 2
        else:
            raise SystemExit(f'unknown argument {a}')
    bad = [a for a in arms if a not in ARMS]
    assert arms and not bad, f'arms {bad} not in {sorted(ARMS)}'
    if games is None:
        games = [w['game'] for w in load_worlds(worlds_path)]
    if shard:
        games = games[shard[0]::shard[1]]
    jobs = [(a, g, cfg, suffix, skip) for a in arms for g in games]
    if not Path('/kaggle').exists():
        fg = _free_gb()
        if not force or fg is None or fg < 3.0 or len(jobs) > 1:
            raise SystemExit(f'not on Kaggle (free memory {fg} GB, {len(jobs)} jobs): games run remotely '
                             f'(scripts/kaggle_remote/remote_panel.py pushcmd); --force-local only for ONE game with >= 3 GB free')
        workers = 1
    print(f'{len(jobs)} jobs: arms {arms} x {len(games)} games, workers {workers}, cfg {cfg}', flush=True)
    manifest = dict(started=time.strftime('%Y-%m-%d %H:%M:%S'), arms=arms, games=games, cfg=cfg, suffix=suffix,
                    files={p: _sha(p) for p in ['agents/mgt_lead.py', 'agents/mgt_lead_semT.py', 'agents/mgt_lead_exact.py',
                                                'agents/mgt_lead_sem.py', 'agents/mgt_lead_sem0.py',
                                                'agents/mgt_lead_semDx.py', 'agents/mgt_lead_semDp.py',
                                                'agents/mgt_lead_deploy.py', 'scripts/lead_sem4.py', 'scripts/lead_g1.py',
                                                'scripts/leader_plan_retrieval.py', 'scripts/fragments/sem_maintenance.py',
                                                'scripts/fragments/sem_market.py']})
    t0 = time.time()
    errs = 0
    if workers <= 1:
        res = map(job, jobs)
    else:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(max_workers=workers)
        res = pool.map(job, jobs)
    for arm, game, ratio, err in res:
        print(arm, game, ratio if err is None else 'FAILED ' + err.splitlines()[0], flush=True)
        if err:
            errs += 1
            print(err, flush=True)
    manifest.update(wall=time.time() - t0, errors=errs)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{'_'.join(arms)}{suffix}_{shard[0]}of{shard[1]}" if shard else f"{'_'.join(arms)}{suffix}"
    (OUT / f'manifest_{tag[:80]}.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(f'completed {len(jobs)} games in {time.time() - t0:.0f}s, errors (FAILED) {errs}')


# ============================================================================ reproduction check

def repro(suffix=''):
    """on REPRO_GAMES, results read from OUT/<arm><suffix>/ (final cash and opponent cash to the dollar):
    - REPRO arms equal their stored results: T0r / T0Lr / Tc0r = abl_Gbase2_remote (mgt_lead own defaults; Tc0r is
      mgt_lead_exact.py with exact_removals False), T0ffr = abl_Gff1_remote, D = abl_E2ff1_remote, Dp =
      abl_E2dep8_remote; D arms with retrieval_leak False;
    - CONTROL_PAIRS identical (final, opponent, every day-start cash): Tc = T0 (EXEC_CFG), Tc0r = T0r (own defaults);
    - LEADER equals the recorded rewards;
    - RUN_ONLY arms (T, S, S0) have a result file (a FAILED game writes none)."""
    ok_all = True

    def load(arm, ep):
        f = OUT / f'{arm}{suffix}' / f'{ep}.json'
        return json.loads(f.read_text(encoding='utf-8')) if f.exists() else None
    for g in REPRO_GAMES:
        ep = g.split(':')[1]
        for arm, ref in list(REPRO.items()) + [('LEADER', None)]:
            r = load(arm, ep)
            if r is None:
                print(f'{arm:6s} {g}: no result')
                ok_all = False
                continue
            if ref is None:
                exp_f, exp_o, src = r['target'], r['target_opp'], 'recorded rewards (semantics meta)'
            else:
                s = json.loads((ROOT / ref / f'{ep}.json').read_text(encoding='utf-8'))
                exp_f, exp_o, src = s['final'], s['opp_final'], ref
            ok = round(r['final']) == round(exp_f) and round(r['opp_final']) == round(exp_o)
            if ARMS[arm]['kind'] == 'deploy':
                ok = ok and r.get('retrieval_leak') is False
            ok_all &= ok
            print(f"{arm:6s} {g}: final {r['final']:.0f} vs {exp_f:.0f}, opp {r['opp_final']:.0f} vs {exp_o:.0f} "
                  f"-> {'IDENTICAL' if ok else 'DIFFERENT'} ({src})"
                  + (f", retrieval_leak={r.get('retrieval_leak')}" if ARMS[arm]['kind'] == 'deploy' else ''))
        for a, b in CONTROL_PAIRS:
            ra, rb = load(a, ep), load(b, ep)
            if ra is None or rb is None:
                print(f'{a} vs {b} {g}: missing result')
                ok_all = False
                continue
            ca = [x['cash'] for x in ra['days']] + [round(ra['final']), round(ra['opp_final'])]
            cb = [x['cash'] for x in rb['days']] + [round(rb['final']), round(rb['opp_final'])]
            ok = ca == cb
            ok_all &= ok
            print(f"{a} vs {b} {g}: final {ra['final']:.0f} / {rb['final']:.0f}, opp {ra['opp_final']:.0f} / "
                  f"{rb['opp_final']:.0f}, day-start cash equal on "
                  f"{sum(1 for x, y in zip(ra['days'], rb['days']) if x['cash'] == y['cash'])}/30 days "
                  f"-> {'IDENTICAL' if ok else 'DIFFERENT'}")
        for arm in RUN_ONLY:
            r = load(arm, ep)
            ok = r is not None and all(s == 'DONE' for s in r['statuses'])
            ok_all &= ok
            print(f"{arm:6s} {g}: " + (f"final {r['final']:.0f} (leader {r['target']:.0f}), statuses {r['statuses']}, "
                                       f"dug live {r['totals'].get('dug_live')}, removal log "
                                       f"{ {k: v for k, v in r['agent_log'].items() if k.startswith('rm_')} }"
                                       if r else 'no result') + f" -> {'OK' if ok else 'MISSING / NOT DONE'}")
    print('REPRODUCTION', 'PASS' if ok_all else 'FAIL')
    return ok_all


# ============================================================================ static checks (no games)

def _perm_sem(sem, rng):
    """the same game with the leader's tiles permuted within each quadrant (quadrant membership, hence land days,
    is kept); every tile reference in boards / plantings / builds / digs / maintenance / harvests / animals moves."""
    perm = {}
    for q in QUADS:
        idx = [y * 10 + x for y in range(10) for x in range(10) if _quad(x, y) == q]
        sh = idx[:]
        rng.shuffle(sh)
        perm.update(dict(zip(idx, sh)))
    s = deepcopy(sem)
    for day in s['days']:
        b = day['board']
        nb = [None] * 100
        for i in range(100):
            nb[perm[i]] = b[i]
        day['board'] = nb
        day['planted'] = {c: [perm[t] for t in ts] for c, ts in day['planted'].items()}
        day['built'] = {k: [perm[t] for t in ts] for k, ts in day['built'].items()}
        day['dug'] = [perm[t] for t in day['dug']]
        day['maintenance'] = {k: [perm[t] for t in ts] for k, ts in day['maintenance'].items()}
        if isinstance(day.get('harvested'), dict) and 'tiles' in day['harvested']:
            day['harvested']['tiles'] = [perm[t] for t in day['harvested']['tiles']]
        if isinstance(day.get('animals'), dict):
            for k in ('placed', 'culled'):
                if k in day['animals']:
                    day['animals'][k] = [perm[t] for t in day['animals'][k]]
    return s, perm


def _target_dump(T, fields):
    def norm(v):
        if isinstance(v, Counter):
            return sorted((str(k), n) for k, n in v.items() if n)
        if isinstance(v, dict):
            return sorted((str(k), norm(x)) for k, x in v.items())
        if isinstance(v, (list, tuple)):
            return [norm(x) for x in v]
        return v
    return {f: norm(getattr(T, f)) for f in fields}


def _paper(mod, sem, cfg, hours=(0, 1, 2, 6, 12)):
    """planner-only 'paper execution' (NOT the engine): every job of _plan is done instantly and perfectly, one-time
    crops are harvested at their max-yield day, ongoing crops dug at the end of their life, land unlocked on the
    Target's land day. Returns per-day jobs and counts."""
    mod.configure(sem, **cfg)
    S = mod._new_state()
    mod._S = S
    T = mod._T
    tiles = [[None if _quad(x, y) == 'NW' else 'LOCKED' for x in range(10)] for y in range(10)]
    unlocked = ['NW']
    rec = []
    for day in range(30):
        while len(unlocked) < 4 and T.land_day.get(('NE', 'SW', 'SE')[len(unlocked) - 1], 99) <= day:
            q = ('NE', 'SW', 'SE')[len(unlocked) - 1]
            unlocked.append(q)
            for y in range(10):
                for x in range(10):
                    if _quad(x, y) == q:
                        tiles[y][x] = None
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get('kind') == 'PLANT':
                    c = mod.CROPS[t['crop']]
                    age = day - t['planted_day']
                    if (not c['ongoing'] and age >= c['maxday']) or (c['ongoing'] and age > mod._ongoing_last_age(t['crop'])):
                        tiles[y][x] = None
        planted, jobs_day, removed = Counter(), [], Counter()
        for h in hours:
            jobs, fert = mod._plan(None, S, tiles, day)
            for idx, job in sorted(jobs.items()):
                x, y = idx % 10, idx // 10
                jobs_day.append([h, idx, job[0], job[1], (list(job[2]) if isinstance(job[2], tuple) else job[2])
                                 if len(job) > 2 else None])
                prev_t = tiles[y][x]
                if isinstance(prev_t, dict) and prev_t.get('kind') == 'PLANT' and job[0] in ('REMOVE', 'PLANT', 'BUILD'):
                    c_ = mod.CROPS[prev_t['crop']]
                    if job[0] == 'REMOVE' or c_['ongoing'] or day - prev_t['planted_day'] < c_['first']:
                        removed[prev_t['crop']] += 1      # a plant DUG up by this job (a ripe one-time crop is harvested)
                if job[0] == 'REMOVE':
                    tiles[y][x] = None
                elif job[0] == 'PLANT':
                    tiles[y][x] = {'kind': 'PLANT', 'crop': job[1], 'planted_day': day, 'yield_units': 0,
                                   'fertilized_until_day': -1, 'watered_today': True, 'consecutive_unwatered': 0}
                    planted[job[1]] += 1
                elif job[0] == 'BUILD':
                    tiles[y][x] = {'kind': job[1]}
                    if job[2]:
                        tiles[y][x] = {'kind': job[1], 'animal': job[2]}
                elif job[0] == 'PLACE':
                    tiles[y][x] = {'kind': tiles[y][x]['kind'], 'animal': job[1]}
        st_ = Counter(t['kind'] for row in tiles for t in row if isinstance(t, dict) and t.get('kind') in ('COOP', 'PASTURE'))
        an_ = Counter(t['animal'] for row in tiles for t in row if isinstance(t, dict) and t.get('animal'))
        rec.append(dict(day=day, planted=dict(planted), struct=dict(st_), anim=dict(an_), jobs=jobs_day,
                        removed=dict(removed), board=[_kind(t) for row in tiles for t in row], log=dict(S['log'])))
    return rec


LAB_CROP = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
PRODS = {'STRAWBERRY': [10, 12, 14, 16], 'TOMATO': [8, 9, 10, 11]}      # production (visible) ages of ongoing crops
DEPLOY_COMMIT = '3f9798f'                                               # agents/mgt_lead_semDp.py = this commit's deploy


def leader_removals(sem):
    """independent recomputation from the semantics: per day, the leader's DIGs of a tile showing a crop on its own
    board that day -> [dict(tile, crop, pd = last planting of that crop on the tile before the day, age, live =
    age <= END_AGE, harvested = the tile also harvested that day, i.e. before the DIG)], plus unmatched digs."""
    out, unmatched = [], 0
    last_plant = {}
    for d, day in enumerate(sem['days']):
        rows, seen = [], set()
        harv = set(day['harvested']['tiles'])
        for t in day['dug']:
            crop = LAB_CROP.get(day['board'][t])
            if crop is None or t in seen:
                continue
            seen.add(t)
            pd, pc = last_plant.get(t, (None, None))
            if pc != crop:
                unmatched += 1
                continue
            rows.append(dict(tile=t, crop=crop, pd=pd, age=d - pd, live=d - pd <= END_AGE[crop], harvested=t in harv))
        out.append(rows)
        for c, ts in day['planted'].items():
            for t in ts:
                last_plant[t] = (d, c)
    return out, unmatched


def _leader_tiles(sem, d, struct_prev=None):
    """the leader's own day-d start board as engine-like tiles (no engine): plants with their planting day (the last
    planting of that crop on the tile) and yield (ongoing: productions visible since the tile's last harvest; one-time:
    1), animals / structures from the labels ('co' = an empty coop where mgt_lead's struct_by_day[d-1] has a COOP, else
    a cow), ' L' locked. Returns (tiles, cohorts {(pd, tile): crop} planted before day d)."""
    days = sem['days']
    last_plant, last_harv, cohorts = {}, {}, {}
    for dd in range(d):
        for t in days[dd]['harvested']['tiles']:
            last_harv[t] = dd
        for c, ts in days[dd]['planted'].items():
            for t in ts:
                last_plant[t] = (dd, c)
                cohorts[(dd, t)] = c
    tiles = [[None] * 10 for _ in range(10)]
    for i, lab in enumerate(days[d]['board']):
        x, y = i % 10, i // 10
        if lab == ' L':
            tiles[y][x] = 'LOCKED'
        elif lab in LAB_CROP:
            crop = LAB_CROP[lab]
            pd = last_plant[i][0]
            if crop in PRODS:
                h = last_harv.get(i, -1)
                yu = sum(1 for p in PRODS[crop] if h < pd + p <= d)
            else:
                yu = 1
            tiles[y][x] = {'kind': 'PLANT', 'crop': crop, 'planted_day': pd, 'yield_units': yu, 'watered_today': False,
                           'consecutive_unwatered': 0, 'fertilized_until_day': -1, 'max_lifespan_step': -1}
        elif lab == 'go':
            tiles[y][x] = {'kind': 'COOP', 'animal': 'GOOSE', 'placed_day': 0}
        elif lab == 'sh':
            tiles[y][x] = {'kind': 'PASTURE', 'animal': 'SHEEP', 'placed_day': 0}
        elif lab == 'co':
            if struct_prev and struct_prev.get(i) == 'COOP':
                tiles[y][x] = {'kind': 'COOP'}
            else:
                tiles[y][x] = {'kind': 'PASTURE', 'animal': 'COW', 'placed_day': 0}
        elif lab == 'pa':
            tiles[y][x] = {'kind': 'PASTURE'}
    return tiles, cohorts


def _cfg_literal(path, name='CFG'):
    import ast
    for node in ast.parse((ROOT / path).read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    return {}


def check():
    """static checks, no games."""
    import difflib
    import re
    import subprocess
    worlds = load_worlds()
    per_team = {}
    for w in worlds:
        per_team.setdefault(w['team'], w)
    sample = [per_team[t] for t in ('DSM', 'DECEM', 'MG') if t in per_team][:3]
    ok_all = True
    fg = _free_gb()
    print(f'free memory {fg:.2f} GB' if fg else 'free memory unknown')
    sem_mod = _load_module('agents/mgt_lead_sem.py', 'chk_s')
    sem0_mod = _load_module('agents/mgt_lead_sem0.py', 'chk_s0')
    ref_mod = _load_module('agents/mgt_lead_semT.py', 'chk_t')
    print('import ok: agents/mgt_lead_sem.py, agents/mgt_lead_sem0.py, agents/mgt_lead_semT.py, agents/mgt_lead_exact.py')
    live_same = _sha('agents/mgt_lead_semT.py') == _sha('agents/mgt_lead.py')
    print(f"mgt_lead_semT.py sha {_sha('agents/mgt_lead_semT.py')[:12]} vs live mgt_lead.py {_sha('agents/mgt_lead.py')[:12]} "
          f"({'identical' if live_same else 'LIVE FILE CHANGED since the snapshot'})")
    # ---------------------------------------------------------------- T: mgt_lead_exact.py vs mgt_lead.py (text)
    a = (ROOT / 'agents/mgt_lead.py').read_text(encoding='utf-8').splitlines()
    b = (ROOT / 'agents/mgt_lead_exact.py').read_text(encoding='utf-8').splitlines()
    dl = [l for l in difflib.unified_diff(a, b, lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
    removed = [l for l in dl if l.startswith('-')]
    print(f'mgt_lead.py -> mgt_lead_exact.py: {sum(1 for l in dl if l.startswith("+"))} lines added, {len(removed)} '
          f'changed/removed:')
    for l in removed:
        print('     ', l[:150])
    xc = _cfg_literal('agents/mgt_lead_exact.py')
    lc = _cfg_literal('agents/mgt_lead.py')
    extra = {k: v for k, v in xc.items() if k not in lc}
    diffk = {k for k in lc if lc[k] != xc.get(k)}
    print(f'   CFG keys added: {extra}; mgt_lead keys changed: {sorted(diffk) or "none"}')
    ok_all &= extra == {'exact_removals': True, 'rm_late': 1} and not diffk
    # ---------------------------------------------------------------- S / S0
    assert sem_mod.CFG['place_rule'] == 'care' and sem0_mod.CFG['place_rule'] == 'centre'
    diff_cfg = {k for k in set(sem_mod.CFG) | set(sem0_mod.CFG) if sem_mod.CFG.get(k) != sem0_mod.CFG.get(k)}
    assert diff_cfg == {'place_rule'}, diff_cfg
    a = (ROOT / 'agents/mgt_lead_sem.py').read_text(encoding='utf-8').splitlines()
    b = (ROOT / 'agents/mgt_lead_sem0.py').read_text(encoding='utf-8').splitlines()
    dl = [l for l in difflib.unified_diff(a, b, lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
    code_diff = [l for l in dl if 'place_rule' in l]
    print(f'mgt_lead_sem.py vs mgt_lead_sem0.py: {len(dl)} differing lines, code lines: {code_diff}')
    print(f"   S removal defaults: count_removals {sem_mod.CFG['count_removals']}, rm_late {sem_mod.CFG['rm_late']}")
    # ---- grep audit: every Target attribute the S/S0 code reads is a semantic (count/timing) field
    for path in ('agents/mgt_lead_sem.py', 'agents/mgt_lead_sem0.py'):
        attrs = Counter()
        lines = (ROOT / path).read_text(encoding='utf-8').splitlines()
        c0 = next(i for i, l in enumerate(lines) if l.startswith('class Target'))
        c1 = next(i for i, l in enumerate(lines) if l.startswith('def configure'))
        outside = []
        for i, line in enumerate(lines):
            code = line.split('#', 1)[0]
            if not (c0 <= i < c1):
                outside.append(code)
            for m in re.finditer(r'\b_?T\.(\w+)', code):
                attrs[m.group(1)] += 1
        body = '\n'.join(outside)
        bad = {k for k in attrs if k not in sem_mod.TARGET_FIELDS}
        forbidden = [p for p in ('struct_by_day', 'animals_by_day', 'board[', '.plant[', 'lmaint"] =', 'smap"].get(',
                                 'smap"][', '_free_tile(', 'T.fert[', 'T.maint', "['planted']", '["planted"]',
                                 '"maintenance"', "'maintenance'", 'T.removals', '["dug"]', "['dug']") if p in body]
        print(f'{path}: Target attributes read by code {dict(attrs)}; non-semantic: {sorted(bad) or "none"}; '
              f'leader-tile idioms outside Target.__init__: {forbidden or "none"}')
        ok_all &= not bad and not forbidden
    # ---------------------------------------------------------------- per world
    tot_rm = defaultdict(Counter)
    for w in sample:
        team_id, ep = w['team_id'], w['episode']
        sem = _load_sem(team_id, ep)
        days = sem['days']
        T = sem_mod.Target(sem)
        R = ref_mod.Target(sem)          # mgt_lead's own per-tile Target (reference derivation)
        LR, unmatched = leader_removals(sem)
        errs = []
        extra_f = set(vars(T)) ^ set(sem_mod.TARGET_FIELDS)
        if extra_f:
            errs.append(f'Target fields {extra_f}')
        for d in range(30):
            want = Counter({c: len(ts) for c, ts in days[d]['planted'].items() if ts})
            if T.plant_n[d] != want:
                errs.append(f'plant_n d{d} {T.plant_n[d]} vs {want}')
            if Counter(c for (pd, c, k) in T.events if pd == d) != want:
                errs.append(f'events d{d}')
            if T.struct_n[d] != Counter(R.struct_by_day[d].values()):
                errs.append(f'struct_n d{d} vs mgt_lead')
            if T.anim_n[d] != Counter(R.animals_by_day[d].values()):
                errs.append(f'anim_n d{d} vs mgt_lead')
            if d < 29:              # independent: the leader's day d+1 board labels ('co' = cow or empty coop)
                lab = Counter(days[d + 1]['board'])
                if T.anim_n[d]['GOOSE'] != lab['go'] or T.anim_n[d]['SHEEP'] != lab['sh']:
                    errs.append(f'anim labels d{d}')
                if T.struct_n[d]['PASTURE'] != lab['pa'] + T.anim_n[d]['SHEEP'] + T.anim_n[d]['COW']:
                    errs.append(f'pasture labels d{d}')
                if T.struct_n[d]['COOP'] != lab['go'] + lab['co'] - T.anim_n[d]['COW']:
                    errs.append(f'coop labels d{d}')
            if T.hands[d] != int(days[d]['labour']['hands_present']):
                errs.append(f'hands d{d}')
            if T.fert_n[d] != len(set(days[d]['maintenance'].get('FERTILIZE', []))):
                errs.append(f'fert_n d{d}')
            if sum(T.fert_cohort[d].values()) > T.fert_n[d]:
                errs.append(f'fert_cohort d{d}')
            alive = Counter()
            for (pd, tt, c) in R.events:
                if pd < d and R.board[d][tt] == ref_mod.CROP_LABEL[c]:
                    alive[(pd, c)] += 1
            if +alive != +T.alive[d]:
                errs.append(f'alive d{d}')
            if +T.rm_n[d] != Counter(r['crop'] for r in LR[d] if r['live']) \
                    or +T.rm_ended_n[d] != Counter(r['crop'] for r in LR[d] if not r['live']):
                errs.append(f'rm_n d{d}')
        if T.land_day != R.land_day or T.land_day != {q: w['land_days'][q] for q in w['land_days']}:
            errs.append(f'land {T.land_day} vs {R.land_day} vs {w["land_days"]}')
        if len(T.land_day) != 3:
            errs.append('not all four quadrants')
        for d in range(30):
            run_ = Counter()
            for i_, day in enumerate(days):
                if (1 if i_ == 0 else i_ + 1) <= d:
                    run_.update(day['market']['sold_units'])
            if +T.cum_sold[d] != +run_ or T.cum_sold[d] != R.cum_sold[d]:
                errs.append(f'cum_sold d{d}')
        tot_sold = Counter()
        for day in days[:29]:
            tot_sold.update(day['market']['sold_units'])
        if +T.cum_sold[29] != +tot_sold:
            errs.append('cum_sold total')
        rng = random.Random(20260925 + int(ep))
        psem, perm = _perm_sem(sem, rng)
        Tp = sem_mod.Target(psem)
        if _target_dump(T, sem_mod.TARGET_FIELDS) != _target_dump(Tp, sem_mod.TARGET_FIELDS):
            errs.append('Target changes under a within-quadrant tile permutation')
        moved = sum(1 for k, v in perm.items() if k != v)
        print(f"world {w['game']} ({w['team']}): Target {'OK' if not errs else 'ERRORS ' + '; '.join(errs[:6])}; "
              f"land {T.land_day}; plantings {len(T.events)}; tiles moved by the permutation {moved}")
        ok_all &= not errs
        # ---- (4) the leader's removals by day and kind
        L_all, L_live, L_harv = Counter(), Counter(), Counter()
        for rows in LR:
            for r in rows:
                L_all[r['crop']] += 1
                if r['live']:
                    L_live[r['crop']] += 1
                    L_harv[r['crop']] += r['harvested']
        print(f'   leader removals (DIG of a plant, semantics): all {dict(L_all)}, live {dict(L_live)} (harvested the '
              f'same day first: {dict(L_harv)}); digs whose label does not match the last planting: {unmatched}')
        # ---- (4a) T on the leader's own boards: the removals mgt_lead_exact issues == the leader's, tile-exact
        xm = _load_module('agents/mgt_lead_exact.py', 'chk_x_' + str(ep))
        xm.configure(sem, **EXEC_CFG)
        n_want = n_got = n_match = 0
        first_ops, job_kinds, harv_agree, day_err = Counter(), Counter(), Counter(), []
        for d in range(30):
            tiles, cohorts = _leader_tiles(sem, d, R.struct_by_day[d - 1] if d > 0 else None)
            S = xm._new_state()
            xm._S = S
            for (pd, t), c in cohorts.items():
                S['done'].add((pd, t))
                S['owner'][(pd, t)] = (t, pd)
                S['owned'].add((t, pd))
            jobs, fert = xm._plan(None, S, tiles, d)
            want = {(r['tile'], r['crop']) for r in LR[d]}
            got = set(S['rm'].items())
            n_want += len(want)
            n_got += len(got)
            n_match += len(want & got)
            if want != got:
                day_err.append(f'd{d}: leader {sorted(want)} T {sorted(got)}')
            hv = {r['tile']: (r['harvested'], 'live' if r['live'] else 'ended') for r in LR[d]}
            for idx in S['rm']:
                t_ = tiles[idx // 10][idx % 10]
                ops = xm._tile_ops(idx, t_, jobs.get(idx), fert, d, 29, Counter({c: 99 for c in xm.CROPS}))[0]
                job_kinds[jobs.get(idx, ('none',))[0]] += 1
                first = ops[0][0] if ops else 'none'
                first_ops[first] += 1
                if idx in hv:
                    hf = first == 'HARVEST' or ops[:2] == [['WATER'], ['HARVEST']]
                    harv_agree[hv[idx][1] + ('_agree' if hf == hv[idx][0] else '_disagree')] += 1
        ok_t = n_want == n_got == n_match
        ok_all &= ok_t
        print(f'   (4a) T (mgt_lead_exact.py) on the leader\'s own boards, all 30 days: leader removals {n_want}, T issues '
              f'{n_got}, identical (tile, crop) {n_match} -> {"MATCH" if ok_t else "MISMATCH"}; job on the tile '
              f'{dict(job_kinds)}; first op {dict(first_ops)}; harvest-first vs the leader\'s same-day harvest '
              f'{dict(harv_agree)} (ended = past its life: the static board cannot show the rot the engine applies at the day-start step)')
        for e in day_err[:4]:
            print('       ', e)
        # ---- (4b) S / S0 on the leader's own boards: removal counts per day and crop == the leader's live removals
        for nm, path in (('S', 'agents/mgt_lead_sem.py'), ('S0', 'agents/mgt_lead_sem0.py')):
            sm = _load_module(path, f'chk_{nm}rm_{ep}')
            sm.configure(sem, **dict(EXEC_CFG, rm_late=0))
            n_w = n_g = days_ok = overlap = 0
            for d in range(30):
                tiles, cohorts = _leader_tiles(sem, d, R.struct_by_day[d - 1] if d > 0 else None)
                S = sm._new_state()
                sm._S = S
                rm = sm._count_removals(S, tiles, d, d)
                want = Counter(r['crop'] for r in LR[d] if r['live'])
                got = Counter(rm.values())
                n_w += sum(want.values())
                n_g += sum(got.values())
                days_ok += got == want
                overlap += sum(1 for m in rm if m in {r['tile'] for r in LR[d] if r['live']})
            ok_s = days_ok == 30
            ok_all &= ok_s
            print(f'   (4b) {nm} on the leader\'s own boards: removal counts = the leader\'s live removals on {days_ok}/30 '
                  f'days ({n_g} vs {n_w}) -> {"MATCH" if ok_s else "MISMATCH"}; our oldest-first picks are the leader\'s '
                  f'own dug tiles in {overlap}/{n_g}')
        # ---- paper execution (planner only, NOT the engine): S / S0 permutation invariance, counts; T and T0 removals
        pap = {}
        for nm, mod in (('S', sem_mod), ('S0', sem0_mod)):
            p1 = _paper(mod, sem, dict(EXEC_CFG, rm_late=1))
            p2 = _paper(mod, psem, dict(EXEC_CFG, rm_late=1))
            same = all(x['jobs'] == y['jobs'] for x, y in zip(p1, p2))
            if not same:
                errs.append(f'{nm} planner jobs change under the tile permutation')
            ev_ok = sum(1 for d in range(30) if Counter(p1[d]['planted']) == Counter(
                {c: n for c, n in T.plant_n[d].items() if d <= mod.CFG['plant_cutoff'].get(c, 99)}))
            st_ok = sum(1 for d in range(30) if Counter(p1[d]['struct']) == +T.struct_n[d])
            an_ok = sum(1 for d in range(30) if Counter(p1[d]['anim']) == +T.anim_n[d])
            pap[nm] = (same, ev_ok, st_ok, an_ok, p1)
            ok_all &= same
        for nm, path in (('T', 'agents/mgt_lead_exact.py'), ('T0', 'agents/mgt_lead_semT.py')):
            pap[nm] = (None, None, None, None, _paper(_load_module(path, f'chk_p{nm}_{ep}'), sem, EXEC_CFG))
        for nm, (same, ev_ok, st_ok, an_ok, p1) in pap.items():
            rem = Counter()
            dok = 0
            for d in range(30):
                rem.update(p1[d]['removed'])
                dok += Counter(p1[d]['removed']) == Counter(r['crop'] for r in LR[d] if r['live'])
            tot_rm[nm].update(rem)
            head = (f'jobs identical under permutation {same}; days with planting counts = leader (after cutoffs) '
                    f'{ev_ok}/30, structures {st_ok}/30, animals {an_ok}/30; ' if same is not None else '')
            print(f'   {nm:2s} paper execution: {head}plants dug {dict(rem)} vs leader live {dict(L_live)}; '
                  f'days with removal counts = leader {dok}/30')
        tot_rm['LEADER live'].update(L_live)
    print('   paper totals over the 3 worlds (plants dug by job): ' + '; '.join(f'{k} {dict(v)}' for k, v in tot_rm.items()))
    # ---------------------------------------------------------------- control: exact_removals False == mgt_lead (planner)
    for w in sample:
        sem = _load_sem(w['team_id'], w['episode'])
        for cfg in ({}, EXEC_CFG):
            pa = _paper(_load_module('agents/mgt_lead_semT.py', 'ctl_a'), sem, cfg)
            pb = _paper(_load_module('agents/mgt_lead_exact.py', 'ctl_b'), sem, dict(cfg, exact_removals=False))
            same = all(x['jobs'] == y['jobs'] and x['board'] == y['board'] for x, y in zip(pa, pb))
            ok_all &= same
            print(f"control {w['game']} cfg {cfg or 'own defaults'}: mgt_lead_exact.py (exact_removals False) planner "
                  f"jobs and boards = mgt_lead.py on every day: {same}")
    # ---------------------------------------------------------------- deploy copies
    dx = (ROOT / 'agents/mgt_lead_semDx.py').read_text(encoding='utf-8').splitlines()
    dp = (ROOT / 'agents/mgt_lead_semDp.py').read_text(encoding='utf-8').splitlines()
    dl = [l for l in difflib.unified_diff(dp, dx, lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('+++', '---')]
    print(f'mgt_lead_semDp.py -> mgt_lead_semDx.py: {len(dl)} differing lines:')
    for l in dl:
        print('     ', l[:110])
    ok_all &= len(dl) == 2 and all('"tie_value":' in l for l in dl)
    try:
        head = subprocess.run(['git', 'show', f'{DEPLOY_COMMIT}:agents/mgt_lead_deploy.py'], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8').stdout.replace('\r', '')
        same_c = head == (ROOT / 'agents/mgt_lead_semDp.py').read_text(encoding='utf-8').replace('\r', '')
        live = (ROOT / 'agents/mgt_lead_deploy.py').read_text(encoding='utf-8').replace('\r', '')
        print(f'mgt_lead_semDp.py = agents/mgt_lead_deploy.py at {DEPLOY_COMMIT}: {same_c}; live deploy file now '
              f'{"identical" if live == head else "DIFFERENT (edited since; D / D+ keep the " + DEPLOY_COMMIT + " version)"}')
        ok_all &= same_c
    except Exception as exc:
        print('git not available for the deploy snapshot check:', exc)
    dxc, dpc = _cfg_literal('agents/mgt_lead_semDx.py'), _cfg_literal('agents/mgt_lead_semDp.py')
    lc = _cfg_literal('agents/mgt_lead.py')
    only = {k: dxc[k] for k in dxc if k not in lc}
    shared = {k: (lc[k], dxc[k]) for k in dxc if k in lc and lc[k] != dxc[k]}
    print(f'   deploy-only executor options in D: {only} (D+: tie_value {dpc.get("tie_value")}); keys shared with '
          f'mgt_lead.py with other defaults: {shared}')
    ok_all &= only.get('tie_value') == 0 and only.get('hire_demand') == 'off' and only.get('maint_goal') == 'value' \
        and set(shared) == set(EXEC_CFG) | {'sell_source'} and all(dxc[k] == v for k, v in EXEC_CFG.items())
    for path in ('agents/mgt_lead_semDx.py', 'agents/mgt_lead_semDp.py'):
        dep = _load_module(path, 'chk_d')
        print(f'import ok: {path} (entry {dep.mgt_lead_deploy_agent.__name__}, tie_value {dep.CFG["tie_value"]}, land_max '
              f'{dep.DEP_CFG["land_max"]}, corpus {len(dep._dep_lpr._CORPUS)} games)')
        del dep
    print('STATIC CHECKS', 'PASS' if ok_all else 'FAIL')
    return ok_all


def smoke():
    """engine-free agent calls (NOT a game): the T0 / T / Tc / S / S0 agents' full agent() (planner, maintenance
    module, dispatcher, market) on synthetic observations built with the engine's own constructors -- day 0 (empty
    farm) and a synthetic day-12 farm from the leader's day-12 board labels with hands; checks the action format and
    that Tc (mgt_lead_exact.py, exact_removals False) returns exactly T0's actions."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    w = load_worlds()[0]
    sem = _load_sem(w['team_id'], w['episode'])
    seat = w['seat']
    lab_crop = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}
    ok_all = True
    acts = {}
    LR, _ = leader_removals(sem)
    # the day with the most live leader removals whose previous day has none (rm_late 1 keeps a day open one more day)
    rm_day = max((d for d in range(1, 29) if not any(r['live'] for r in LR[d - 1])),
                 key=lambda d: (sum(1 for r in LR[d] if r['live']), -d))
    rm_tiles = [r['tile'] for r in LR[rm_day] if r['live']]
    Rt = _load_module('agents/mgt_lead_semT.py', 'smk_ref').Target(sem)
    smoke_rm = {}
    for arm in ('T0', 'T', 'Tc', 'S', 'S0'):
        spec = ARMS[arm]
        mod = _load_module(spec['path'], 'smk_' + arm)
        mod.configure(sem, **spec['cfg'])
        farms = [E._new_farm(10, 3000), E._new_farm(10, 3000)]
        privs = [E._new_private(), E._new_private()]
        market = E._new_market()
        town = {'unlocked_shops': []}
        worst, n_calls, errs, orders = 0.0, 0, [], Counter()
        seq = acts[arm] = []

        def call(step):
            nonlocal worst, n_calls
            obs = {'step': step, 'player': seat, 'farms': farms, 'private': privs[seat], 'market': market,
                   'town': town, 'day': step // 24, 'hour': step % 24, 'remainingOverageTime': 60}
            t0 = time.time()
            a = mod.agent(obs)
            worst = max(worst, time.time() - t0)
            n_calls += 1
            seq.append(json.dumps(a, sort_keys=True))
            nh = len(farms[seat]['hands'])
            if not (isinstance(a, dict) and isinstance(a.get('farmer'), list) and len(a.get('hands', [])) == nh
                    and isinstance(a.get('market'), list) and len(a['market']) <= 10):
                errs.append((step, a))
            for o in a.get('market', []):
                orders[o[0]] += 1
            return a
        for step in range(0, 26):
            call(step)
        # synthetic day-12 farm: every quadrant unlocked, the leader's day-12 labels as live assets, 10 hands
        f = farms[seat]
        f['unlocked_quadrants'] = ['NW', 'NE', 'SW', 'SE']
        b = sem['days'][12]['board']
        for i, l in enumerate(b):
            x, y = i % 10, i // 10
            if l in lab_crop:
                f['tiles'][y][x] = E._new_plant(lab_crop[l], 9 if l in ('WH', 'CA') else 4, 24)
            elif l in ('sh', 'go', 'co'):
                f['tiles'][y][x] = E._new_animal({'sh': 'SHEEP', 'go': 'GOOSE', 'co': 'COW'}[l], 3)
            elif l == 'pa':
                f['tiles'][y][x] = {'kind': 'PASTURE'}
            else:
                f['tiles'][y][x] = None
        f['money'] = 5000.0
        f['hands'] = [[4, 4] for _ in range(10)]
        privs[seat]['inventories'] = [{} for _ in range(11)]
        privs[seat]['shed'].update({'WHEAT': 30, 'FERTILIZER': 10})
        for step in range(12 * 24, 12 * 24 + 26):
            call(step)
        # removal day: the leader's own start board of the day with the most live removals (plants with their
        # planting days / yields, engine animals), seeds in stock, one hand standing on each tile the leader digs
        n_before = len(seq)
        mod._S = None                    # fresh game state for this farm (no planting records from the phases above)
        tl, _ = _leader_tiles(sem, rm_day, Rt.struct_by_day[rm_day - 1])
        for y in range(10):
            for x in range(10):
                t_ = tl[y][x]
                if isinstance(t_, dict) and t_.get('animal'):
                    t_ = dict(E._new_animal(t_['animal'], 0), kind=t_['kind'])
                f['tiles'][y][x] = t_
        f['hands'] = [[t % 10, t // 10] for t in rm_tiles[:10]] + [[4, 4]] * max(0, 10 - len(rm_tiles))
        privs[seat]['inventories'] = [{} for _ in range(11)]
        privs[seat]['seeds'] = {c: 30 for c in lab_crop.values()}
        f['money'] = 8000.0
        ops_here = Counter()
        for step in range(rm_day * 24 + 1, rm_day * 24 + 13):
            a = call(step)
            for u, act in enumerate(a['hands'][:len(rm_tiles)]):
                ops_here[act[0]] += 1
        rm_now = dict(getattr(mod, '_S', {}).get('rm', {}))
        smoke_rm[arm] = (rm_now, ops_here, len(seq) - n_before)
        lg = dict(getattr(mod, '_S', {}).get('log', {}))
        print(f"{arm}: {n_calls} agent calls, max {worst:.3f} s, bad actions {len(errs)}, market orders {dict(orders)}, "
              f"planner log {({k: v for k, v in lg.items() if k.startswith(('place_', 'plant_un', 'struct_un', 'mj_', 'replace', 'rm_'))})}")
        print(f"    removal day {rm_day}: open removals {sorted(rm_now.items())}; actions of the hands on the leader's "
              f"dug tiles {dict(ops_here)}")
        ok_all &= not errs
    same = acts['Tc'] == acts['T0']
    ok_all &= same
    print(f"Tc (exact_removals False) actions = T0 actions on all {len(acts['T0'])} calls: {same}; T (exact_removals on) "
          f"differs from T0 on {sum(1 for x, y in zip(acts['T'], acts['T0']) if x != y)} calls")
    want = Counter(r['crop'] for r in LR[rm_day] if r['live'])
    t_ok = set(smoke_rm['T'][0]) >= set(rm_tiles) and not smoke_rm['T0'][0] and not smoke_rm['Tc'][0]
    s_ok = all(Counter(smoke_rm[a][0].values()) == want for a in ('S', 'S0'))
    ok_all &= t_ok and s_ok
    print(f"removal day {rm_day} ({len(rm_tiles)} live leader removals {dict(want)}): T opens a removal on every leader tile "
          f"and T0 / Tc on none: {t_ok}; S / S0 open the leader's count: {s_ok}")
    print('SMOKE', 'PASS' if ok_all else 'FAIL')
    return ok_all


# ============================================================================ report

def _ci(xs):
    if len(xs) < 2:
        return (xs[0] if xs else 0.0, None, None)
    m = st.mean(xs)
    rng = random.Random(1)
    bs = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(2000))
    return m, bs[49], bs[1949]


def report(argv):
    worlds_path, arms = None, None
    i = 0
    while i < len(argv):
        if argv[i] == '--worlds':
            worlds_path = argv[i + 1]; i += 2
        elif argv[i] == '--arms':
            arms = argv[i + 1].split(','); i += 2
        else:
            i += 1
    worlds = {w['episode']: w for w in load_worlds(worlds_path)}
    arms = arms or [a for a in MAIN_ARMS + ['D4', 'Snr'] if (OUT / a).exists()]
    rows = {a: {} for a in arms}
    for a in arms:
        for f in sorted((OUT / a).glob('1*.json')):
            r = json.loads(f.read_text(encoding='utf-8'))
            if r['episode'] in worlds:
                rows[a][r['episode']] = r
    common = sorted(set.intersection(*[set(v) for v in rows.values()])) if rows else []
    if not common:
        print(f'no world has results for every arm {arms} under {OUT.relative_to(ROOT)}')
        return
    collapse ={e for e in common if worlds[e]['flags'] or any(rows[a][e]['opp_collapse'] for a in arms)}
    clean = [e for e in common if e not in collapse]
    L = []
    L.append(f'# sem4 report ({time.strftime("%Y-%m-%d %H:%M")})\n')
    L.append(f'worlds with every arm: {len(common)} (clean, no replayed-opponent collapse in any arm: {len(clean)}); '
             f'arms {arms}\n')
    if 'LEADER' in rows:
        rep = [e for e in common if round(rows['LEADER'][e]['final']) == round(rows['LEADER'][e]['target'])]
        L.append(f'LEADER replay reproduces the recorded cash: {len(rep)}/{len(common)}\n')
    L.append('| arm | n | mean final | gap to leader (95% CI) | ratio | gap clean | ratio clean | W vs leader |')
    L.append('|---|---:|---:|---|---:|---|---:|---:|')
    for a in arms:
        g = [rows[a][e]['target'] - rows[a][e]['final'] for e in common]
        gc = [rows[a][e]['target'] - rows[a][e]['final'] for e in clean]
        m, lo, hi = _ci(g)
        mc, loc, hic = _ci(gc) if gc else (0, None, None)
        L.append(f"| {ARM_LABEL.get(a, a)} | {len(g)} | {st.mean(rows[a][e]['final'] for e in common):,.0f} | {m:+,.0f} "
                 f"({lo if lo is None else f'{lo:+,.0f}'} .. {hi if hi is None else f'{hi:+,.0f}'}) | "
                 f"{st.mean(rows[a][e]['ratio'] for e in common):.3f} | {mc:+,.0f} | "
                 f"{(st.mean(rows[a][e]['ratio'] for e in clean) if clean else 0):.3f} | "
                 f"{sum(1 for e in common if rows[a][e]['final'] > rows[a][e]['target'])} |")
    for a, b in (('T', 'T0'), ('S', 'T'), ('S', 'S0'), ('S0', 'T'), ('D', 'S'), ('Dp', 'D'), ('D4', 'D'), ('S', 'Snr')):
        if a in rows and b in rows:
            dlt = [rows[a][e]['final'] - rows[b][e]['final'] for e in common]
            m, lo, hi = _ci(dlt)
            L.append(f'\n{ARM_LABEL.get(a, a)} - {ARM_LABEL.get(b, b)}: {m:+,.0f} (95% CI {lo:+,.0f} .. {hi:+,.0f}), '
                     f'better in {sum(1 for x in dlt if x > 0)}/{len(dlt)}, n={len(dlt)}')
    L.append('\n## removals of plants (DIG of a plant; live = age <= its last production / max-yield age), mean per game\n')
    L.append('| arm | live strawberry | live tomato | live wheat | live carrot | live melon | ended (rotting) | dug after a '
             'same-day harvest | yield units destroyed | agent log (rm_*) |')
    L.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|---|')
    for a in arms:
        n = max(1, len(common))
        t_ = [rows[a][e]['totals'] for e in common]
        live = Counter()
        for x in t_:
            live.update(x.get('dug_live', {}))
        rml = Counter()
        for e in common:
            rml.update({k: v for k, v in rows[a][e].get('agent_log', {}).items() if k.startswith('rm_')})
        L.append(f"| {ARM_LABEL.get(a, a)} | " + ' | '.join(f"{live[c] / n:.1f}" for c in ('STRAWBERRY', 'TOMATO', 'WHEAT', 'CARROT', 'MELON'))
                 + f" | {sum(sum(x.get('dug_ended', {}).values()) for x in t_) / n:.1f} | "
                 f"{sum(sum(x.get('dug_after_harvest', {}).values()) for x in t_) / n:.1f} | "
                 f"{sum(sum(x.get('dug_yield_lost', {}).values()) for x in t_) / n:.1f} | "
                 + ', '.join(f'{k} {v / n:.1f}' for k, v in sorted(rml.items())) + ' |')
    L.append('\n## by team (mean gap to leader)\n')
    teams = sorted({worlds[e]['team'] for e in common})
    L.append('| arm | ' + ' | '.join(f'{t} (n)' for t in teams) + ' |')
    L.append('|---|' + '---:|' * len(teams))
    for a in arms:
        cells = []
        for t in teams:
            es = [e for e in common if worlds[e]['team'] == t]
            cells.append(f"{st.mean(rows[a][e]['target'] - rows[a][e]['final'] for e in es):+,.0f} ({len(es)})")
        L.append(f'| {ARM_LABEL.get(a, a)} | ' + ' | '.join(cells) + ' |')
    L.append('\n## per quadrant, mean per game (all common worlds)\n')
    L.append('| arm | quadrant | unlocked tile-days | occupied tile-days | harvested units | income | ops (W/F/H/FE/C/CF/P) | unwatered / escaped / rot units |')
    L.append('|---|---|---:|---:|---:|---:|---|---|')
    for a in arms:
        n = max(1, len(common))
        for qn in ('first', 'second', 'third', 'fourth'):
            qs = [rows[a][e]['quadrants'][qn] for e in common]
            occ = sum(sum(v for k, v in q['occ_tile_days'].items() if k not in ('EMPTY', 'WEED')) for q in qs) / n
            ops = Counter()
            dth = Counter()
            for q in qs:
                ops.update(q['ops'])
                for k, v in q['deaths'].items():
                    dth[k.split('_')[0]] += v
            rot = sum(sum(q['rot_units'].values()) for q in qs) / n
            L.append(f"| {ARM_LABEL.get(a, a)} | {qn} | {sum(q['unlocked_tile_days'] for q in qs) / n:.0f} | {occ:.0f} | "
                     f"{sum(sum(q['harvested'].values()) for q in qs) / n:.0f} | {sum(q['income'] for q in qs) / n:,.0f} | "
                     + '/'.join(f"{ops[k] / n:.0f}" for k in ('WATER', 'FEED', 'HARVEST', 'FERTILIZE', 'CARE', 'COLLECT_FERTILIZER', 'PLANT'))
                     + f" | {dth['unwatered'] / n:.1f} / {dth['escaped'] / n:.1f} / {rot:.1f} |")
    L.append('\n## work ledger, mean per game\n')
    L.append('| arm | moves | eff. maintenance ops | unit-steps | wages | shed pickups (items) | deposits | midnight discards | hires |')
    L.append('|---|---:|---:|---:|---:|---|---:|---:|---:|')
    for a in arms:
        n = max(1, len(common))
        t_ = [rows[a][e]['totals'] for e in common]
        L.append(f"| {ARM_LABEL.get(a, a)} | {sum(x['moves'] for x in t_) / n:,.0f} | {sum(x['maint_ops_eff'] for x in t_) / n:,.0f} | "
                 f"{sum(x['unit_steps'] for x in t_) / n:,.0f} | {sum(x['wages'] for x in t_) / n:,.0f} | "
                 f"{sum(x['pickups'] for x in t_) / n:.0f} ({sum(x['pickup_items'] for x in t_) / n:.0f}) | "
                 f"{sum(x['deposits'] for x in t_) / n:.0f} | {sum(x['discards_total'] for x in t_) / n:.1f} | "
                 f"{sum(x['hires'] for x in t_) / n:.0f} |")
    L.append('\n## per-world gap to leader\n')
    L.append('| world | team | leader | ' + ' | '.join(ARM_LABEL.get(a, a) for a in arms if a != 'LEADER') + ' | flags |')
    L.append('|---|---|---:|' + '---:|' * len([a for a in arms if a != 'LEADER']) + '---|')
    for e in common:
        tgt = rows[arms[0]][e]['target']
        L.append(f"| {e} | {worlds[e]['team']} | {tgt:,.0f} | " + ' | '.join(
            f"{rows[a][e]['final'] - tgt:+,.0f}" for a in arms if a != 'LEADER')
            + f" | {'collapse' if e in collapse else ''} |")
    txt = '\n'.join(L)
    (OUT / 'report.md').write_text(txt, encoding='utf-8')
    print(txt)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    if cmd == 'worlds':
        build_worlds()
    elif cmd == 'sync-s0':
        sync_s0()
    elif cmd == 'check':
        sys.exit(0 if check() else 1)
    elif cmd == 'smoke':
        sys.exit(0 if smoke() else 1)
    elif cmd == 'run':
        run(argv[1:])
    elif cmd == 'repro':
        sys.exit(0 if repro(argv[1] if len(argv) > 1 else '') else 1)
    elif cmd == 'report':
        report(argv[1:])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
