"""Hold-one-out ablation harness around G1 (the leader game's own world: recorded seed, forced shops,
opponent = the tape's recorded opp_actions; our agent in the leader's seat). Each cell swaps ONE component
of agents/mgt_lead.py for the leader's version (or ours), everything else fixed:

  A  baseline      leader plan + leader tiles + leader sell schedule + our maintenance + our hires/dispatch
  B2 = B plus a survival net (water plants / feed animals that would die tonight)
  B  maintenance   LEADER EXACT: WATER/FEED/CARE/FERTILIZE only on the leader's per-tile per-day lists
                   (data/leader_semantics maintenance, correctly dated), executed by our dispatcher
  C  market        OURS: mgt_lead_deploy's sell-as-it-reaches-the-shed rule (wheat the herd eats is kept)
  D  hires         LEADER EXACT: the leader's HIRE orders at the leader's own steps (from the tape). Note: A
                   already hires the leader's exact daily count (hands_present == corrected hires_arrived on
                   every day), so D isolates hire TIMING only
  E  plan          OURS: mgt_lead_deploy's target builder (family-A opening, retrieval at days 3/6/9, count
                   model from day 12) with THIS episode excluded from retrieval (and a different exemplar if it
                   is the exemplar); hires and sell schedule stay the leader's (as A), no no-feed hook
  E2 plan+market+hires OURS: the full mgt_lead_deploy agent (reference), same exclusion

usage: lead_ablation.py run CELL[,CELL...] [--workers 2] [--games ep,...]
       lead_ablation.py report CELL[,CELL...]
Results: results/fresh/lead_agent_20260924/abl_<cell>/<ep>.json
"""
import gzip
import importlib.util
import json
import statistics as st
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1  # noqa: E402

OUT = ROOT / 'results/fresh/lead_agent_20260924'
import os as _os
_SUFFIX = _os.environ.get('ABL_SUFFIX', '')   # separate result dirs per research variant (abl_<cell><suffix>)
COLLAPSED = 112708229      # the replayed opponent collapses in this world: report means with and without it
CLEAN9 = {112444381, 112445586, 112447950, 112449129, 112655730, 112661570, 112667461, 112714050, 112721923}

CELLS = {
    'A': dict(cfg={}),
    'B': dict(cfg={'maint_source': 'leader'}),
    'B2': dict(cfg={'maint_source': 'leader', 'maint_safety': True}),
    'C': dict(cfg={'sell_source': 'shed'}),
    'D': dict(cfg={'hire_source': 'leader_steps', 'hires_first': False}, hire_steps=True),
    'Dp': dict(cfg={'hires_first': False}),
    'A29': dict(cfg={'hands_d29_fix': True}),
    'S1': dict(cfg={'sched_maint': True}),
    'S2': dict(cfg={'sched_maint': True, 'sched_dispatch': True}),
    'S3': dict(cfg={'sched_maint': True, 'sched_dispatch': True, 'sched_hire': True}),
    'S2d': dict(cfg={'sched_dispatch': True}),
    'S2p20': dict(cfg={'sched_maint': True, 'sched_dispatch': True, 'sched_cost': 'prize', 'step_value': 20.0}),
    'S2p80': dict(cfg={'sched_maint': True, 'sched_dispatch': True, 'sched_cost': 'prize', 'step_value': 80.0}),
    'S3h': dict(cfg={'sched_hire': True}),
    'S1h': dict(cfg={'sched_maint': True, 'sched_hire': True}),
    'S1x': dict(cfg={'sched_maint': True, 'mj_collect': False}),
    'S1f': dict(cfg={'sched_maint': True}),
    'CUR': dict(cfg={}),
    'R16': dict(cfg={'surv_reserve': True, 'surv_hour': 16}),
    'R12': dict(cfg={'surv_reserve': True, 'surv_hour': 12}),
    'R19': dict(cfg={'surv_reserve': True, 'surv_hour': 19}),
    'X': dict(cfg={'hands_d29_fix': True, 'maint_source': 'leader', 'maint_safety': True}),
    'E': dict(cfg={}, deploy='plan'),
    'E2': dict(cfg={}, deploy='full'),
    'E2s': dict(cfg={}, deploy='full', swap={'sell': 'leader'}),
    'E2sem': dict(cfg={}, deploy='full', path='agents/mgt_lpv_sem.py'),
    'E2rpc1': dict(cfg={}, deploy='full', path='agents/mgt_lpv_rpc1.py'),
    'E2rpc1h': dict(cfg={}, deploy='full', path='agents/mgt_lpv_rpc1h.py'),
    'E2sh': dict(cfg={}, deploy='full', path='agents/mgt_lpv_sh.py'),
    'E2base3': dict(cfg={}, deploy='full', path='agents/mgt_lpv_base3.py'),
    'E2ar4': dict(cfg={}, deploy='full', path='agents/mgt_lpv_ar4.py'),
    'E2ar8': dict(cfg={}, deploy='full', path='agents/mgt_lpv_ar8.py'),
    'E2cut': dict(cfg={}, deploy='full', path='agents/mgt_lpv_cut.py'),
    'Gcut': dict(cfg={'plant_cutoff': {'STRAWBERRY': 13, 'TOMATO': 18, 'MELON': 19, 'WHEAT': 25, 'CARROT': 26}}),
    'Gar4': dict(cfg={'atrisk_bonus': 4}),
    'Gbase': dict(cfg={}),
    'E2base4': dict(cfg={}, deploy='full', path='agents/mgt_lpv_base4.py'),
    'E2um1': dict(cfg={}, deploy='full', path='agents/mgt_lpv_um1.py'),
    'E2me2': dict(cfg={}, deploy='full', path='agents/mgt_lpv_me2.py'),
    'E2me3': dict(cfg={}, deploy='full', path='agents/mgt_lpv_me3.py'),
    'E2cur5': dict(cfg={}, deploy='full', path='agents/mgt_lpv_cur5.py'),
    'E2fl1': dict(cfg={}, deploy='full', path='agents/mgt_lpv_fl1.py'),
    'E2fl2': dict(cfg={}, deploy='full', path='agents/mgt_lpv_fl2.py'),
    'E2c27': dict(cfg={}, deploy='full', path='agents/mgt_lpv_c27.py'),
    'E2c27f': dict(cfg={}, deploy='full', path='agents/mgt_lpv_c27f.py'),
    'E2trg': dict(cfg={}, deploy='full', path='agents/mgt_lpv_trg.py'),
    'Gtr': dict(cfg={'idle_trace': 'results/fresh/lead_idle/g1lead'}),
    'E2h2': dict(cfg={}, deploy='full', path='agents/mgt_lpv_h2.py'),
    'E2z2': dict(cfg={}, deploy='full', path='agents/mgt_lpv_z2.py'),
    'E2z4': dict(cfg={}, deploy='full', path='agents/mgt_lpv_z4.py'),
    'E2fx1': dict(cfg={}, deploy='full', path='agents/mgt_lpv_fx1.py'),
    'E2pv30': dict(cfg={}, deploy='full', path='agents/mgt_lpv_pv30.py'),
    'E2pv60': dict(cfg={}, deploy='full', path='agents/mgt_lpv_pv60.py'),
    'E2nd': dict(cfg={}, deploy='full', path='agents/mgt_lpv_nd.py'),
    'E2hs1': dict(cfg={}, deploy='full', path='agents/mgt_lpv_hs1.py'),
    'E2hp': dict(cfg={}, deploy='full', path='agents/mgt_lpv_hp.py'),
    'E2hs2': dict(cfg={}, deploy='full', path='agents/mgt_lpv_hs2.py'),
    'Gc27': dict(cfg={'plant_cutoff': {'STRAWBERRY': 13, 'TOMATO': 18, 'MELON': 19, 'WHEAT': 27, 'CARROT': 27}}),
    'E2h': dict(cfg={}, deploy='full', swap={'hires': 'leader'}),
    'E2p': dict(cfg={}, deploy='full', swap={'plan': 'leader'}),
    'E2d': dict(cfg={}, deploy='full', swap={'plan': 'leader_to11'}),
}


def _hire_steps(team_id, ep):
    tape = json.load(gzip.open(next(sorted((ROOT / 'data/leader_tapes').glob(f'{team_id}_*/{ep}.json.gz')).__iter__()),
                               'rt', encoding='utf-8'))
    out = {}
    for t, a in enumerate(tape['actions']):
        n = sum(1 for o in (a.get('market') or [])[:10] if o and o[0] == 'HIRE')
        if n:
            out[t] = n
    return out


class _DeployAdapter:
    """module-like wrapper so lead_g1.play can drive mgt_lead_deploy in the held-out world."""

    def __init__(self, mode, ep, swap=None, path=None):
        import os
        spec = importlib.util.spec_from_file_location(
            'mgt_lead_deploy_abl', (ROOT / path) if path else (os.environ.get('LEAD_DEPLOY_PATH') or (ROOT / 'agents/mgt_lead_deploy.py')))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.mod, self.mode, self.ep = mod, mode, int(ep)
        # swap (mode 'full' only): {'plan': 'deploy'|'leader'|'leader_to11', 'sell': 'deploy'|'leader',
        #                           'hires': 'deploy'|'leader'}; the no-feed hook stays the deploy's
        self.swap = dict({'plan': 'deploy', 'sell': 'deploy', 'hires': 'deploy'}, **(swap or {}))
        lpr = mod._dep_lpr
        orig = getattr(lpr, '_abl_orig_retrieve', None) or lpr.retrieve
        lpr._abl_orig_retrieve = orig

        def retrieve(*a, **kw):          # no leakage: this episode (any seat) is never retrieved
            kw['exclude_episode'] = self.ep
            return orig(*a, **kw)
        lpr.retrieve = retrieve
        if mod._DEP_EXEMPLAR == self.ep:  # the day-0 exemplar is this very game: use the next family-A game
            mod._DEP_EXEMPLAR = 112661570
            mod._DEP_BASE = None
        self.leader = None
        ex = mod.agent
        adapter = self

        sw = self.swap
        if sw['plan'] in ('leader', 'leader_to11'):
            mod.DEP_CFG['switch_days'] = ()           # no retrieval switches: the leader's own game is the plan
            mod.DEP_CFG['land_max'] = 3               # the leader's land through its plan (all quadrants it buys)
            if sw['plan'] == 'leader':
                mod.DEP_CFG['compose_from'] = 99      # no count-model phase either
            ini = mod._dep_init

            def dep_init():
                ini()
                mod._T = mod._DepTarget(adapter.leader)
                mod._DEP['lead_t'] = adapter.leader
                mod._MGT_HISTORY[:] = [(0, adapter.ep)]
            mod._dep_init = dep_init

        def executor(obs, config=None):
            d = min(int(obs['step']) // 24, 29)
            if adapter.mode == 'plan':
                mod._T.hands[d] = adapter.leader.hands[d]
                mod._T.cum_sold[d] = Counter(adapter.leader.cum_sold[d])
                mod._DEP['nofeed'] = set()
            else:
                if sw['plan'] == 'leader' and d >= 12:
                    # the deploy's own hires and no-feed rule on the leader's plan (normally set by its compose step)
                    if d not in adapter._composed:
                        adapter._composed.add(d)
                        if sw['hires'] == 'deploy':
                            me = int(obs['player'])
                            tl = obs['farms'][me]['tiles']
                            crops = sum(1 for row in tl for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT')
                            crops += len(mod._T.plant[d])
                            anim = sum(1 for row in tl for t in row if isinstance(t, dict) and t.get('animal'))
                            b0, b1, b2 = mod.DEP_CFG['hands_coef']
                            mod._T.hands[d] = max(0, min(14, int(b0 + b1 * crops + b2 * anim + 0.5) + mod.DEP_CFG['hands_add']))
                        mod._DEP['nofeed'] = mod._dep_nofeed(obs, d)
                if sw['sell'] == 'leader':
                    mod._T.cum_sold[d] = Counter(adapter.leader.cum_sold[d])
                if sw['hires'] == 'leader':
                    mod._T.hands[d] = adapter.leader.hands[d]
                    if d == 29 and adapter.leader.hands[d] == 0:
                        mod._T.hands[d] = adapter.leader.hands[28]   # the corpus' last-day artifact (A29)
            return ex(obs, config)
        mod.agent = executor
        self._composed = set()

    @property
    def _S(self):
        return self.mod._S

    def configure(self, sem, **cfg):
        self.mod.CFG.update(cfg)
        self.leader = self.mod.Target(sem)

    def agent(self, obs):
        return self.mod.mgt_lead_deploy_agent(obs)


def play_cell(game, cell):
    spec = CELLS[cell]
    team_id, ep = game.split(':')
    orig_load = lead_g1._load_agent

    def load(cfg):
        if spec.get('deploy'):
            return _DeployAdapter(spec['deploy'], ep, spec.get('swap'), spec.get('path'))
        mod = orig_load(cfg)
        if spec.get('hire_steps'):
            conf = mod.configure
            steps = _hire_steps(team_id, ep)

            def configure(sem, **c):
                conf(sem, **c)
                mod._T.hire_steps = steps
            mod.configure = configure
        return mod
    lead_g1._load_agent = load
    try:
        return lead_g1.play(game, dict(spec['cfg']))
    finally:
        lead_g1._load_agent = orig_load


def job(args):
    game, cell = args
    try:
        t0 = time.time()
        r = play_cell(game, cell)
        r['wall'] = time.time() - t0
        r['cell'] = cell
        o = OUT / f'abl_{cell}{_SUFFIX}'
        o.mkdir(parents=True, exist_ok=True)
        (o / f"{game.split(':')[1]}.json").write_text(json.dumps(r, default=str), encoding='utf-8')
        return (game, cell, r['ratio'], None)
    except Exception as exc:
        return (game, cell, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}')


def _load(cell):
    return {int(f.stem): json.load(open(f)) for f in sorted((OUT / f'abl_{cell}{_SUFFIX}').glob('1*.json'))}


def _board_cells(b):
    return [b[i:i + 2] for i in range(0, 200, 2)]


def report(cells):
    base = _load('A') if (OUT / 'abl_A').exists() else {}
    sems = {}
    lines = ['| cell | n | mean12 | mean11 | d mean12 vs A | revenue gap vs leader (k$/game, top) | failed buys | no-effect | '
             'Hamming to leader d6/d12/d20 | hires (leader) | plants died | animals lost | diverges from A (median day >0 / >5 tiles) |',
             '|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|']
    allrows = {c: _load(c) for c in cells}
    clean = None
    for c, rows_c in allrows.items():
        ok = {e for e, r in rows_c.items() if r['opp_final'] >= 0.8 * r['target_opp']}
        clean = ok if clean is None else clean & ok
    clean = clean or set()
    lines[0] = lines[0].replace('| mean11 |', '| mean11 | clean9 |')
    lines[1] = '|---|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|'
    for cell in cells:
        rows = allrows[cell]
        if not rows:
            continue
        rs = [r['ratio'] for r in rows.values()]
        rnc = [r['ratio'] for e, r in rows.items() if e in CLEAN9]
        r11 = [r['ratio'] for e, r in rows.items() if e != COLLAPSED]
        dA = ''
        if base and cell != 'A':
            common = [e for e in rows if e in base]
            dA = f"{st.mean(rows[e]['ratio'] - base[e]['ratio'] for e in common):+.3f}"
        R, TR = Counter(), Counter()
        fails = noeff = hires = thires = died = lost = 0
        ham = {6: [], 12: [], 20: []}
        div0, div5 = [], []
        for e, r in rows.items():
            team = r['game'].split(':')[0]
            if e not in sems:
                sems[e] = json.load(gzip.open(ROOT / f'data/leader_semantics/{team}/{e}.json.gz', 'rt'))
            sem = sems[e]
            for d, dd in enumerate(r['days']):
                R.update(dd['rev'])
                fails += sum(dd['failed'].values())
                noeff += sum(dd['noeff'].values())
                hires += dd['hires']
                thires += dd['target_hands']
                died += sum(v for k, v in dd['died'].items() if k.startswith('unw'))
                lost += sum(v for k, v in dd['died'].items() if k.startswith('esc'))
            for dd in sem['days']:
                TR.update(dd['market']['sold_revenue'])
            for d in ham:
                ham[d].append(r['days'][d]['hamming'])
            if base and cell != 'A' and e in base:
                f0 = f5 = 30
                for d in range(30):
                    a, b = r['days'][d]['board'], base[e]['days'][d]['board']
                    if not a or not b:
                        continue
                    h = sum(1 for x, y in zip(_board_cells(a), _board_cells(b)) if x != y)
                    if h > 0 and f0 == 30:
                        f0 = d
                    if h > 5 and f5 == 30:
                        f5 = d
                div0.append(f0)
                div5.append(f5)
        n = len(rows)
        gap = sorted(((R[p] - TR[p]) / n / 1000, p) for p in set(R) | set(TR))
        gaps = ', '.join(f'{p[:5].lower()} {g:+.1f}' for g, p in gap[:4])
        tot = (sum(R.values()) - sum(TR.values())) / n / 1000
        div = f"{st.median(div0):.0f} / {st.median(div5):.0f}" if div0 else '-'
        lines.append(f"| {cell} | {n} | {st.mean(rs):.3f} | {st.mean(r11):.3f} | {(st.mean(rnc) if rnc else 0):.3f} | {dA} | total {tot:+.1f}: {gaps} | "
                     f"{fails / n:.1f} | {noeff / n:.1f} | {st.mean(ham[6]):.0f}/{st.mean(ham[12]):.0f}/{st.mean(ham[20]):.0f} | "
                     f"{hires / n:.0f} ({thires / n:.0f}) | {died / n:.1f} | {lost / n:.1f} | {div} |")
    lines.append(f'clean9 = the fixed 9 games of the ablation (no cell A-X collapses the opponent there); games where no '
                 f'listed cell has the opponent below 0.8x: {len(clean)}')
    return '\n'.join(lines)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd, cells = argv[0], argv[1].split(',')
    if cmd == 'report':
        print(report(cells))
        return
    workers, games = 2, lead_g1.GAMES
    i = 2
    while i < len(argv):
        if argv[i] == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif argv[i] == '--games':
            sel = argv[i + 1].split(',')
            games = [g for g in lead_g1.GAMES if any(g.endswith(s) for s in sel)]
            i += 2
        else:
            i += 1
    jobs = [(g, c) for c in cells for g in games]
    t0 = time.time()
    if workers <= 1:
        res = map(job, jobs)
    else:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(max_workers=workers)
        res = pool.map(job, jobs)
    for game, cell, ratio, err in res:
        print(cell, game, ratio if err is None else err.splitlines()[0], flush=True)
        if err:
            print(err, flush=True)
    print(f'wall {time.time() - t0:.0f}s')
    print(report(sorted(set(cells) | ({'A'} if (OUT / 'abl_A').exists() else set()), key=lambda c: 'A A29 X CUR R16 R12 R19 E2 E2s E2h E2p E2d S1 S1f S1h S1x S2 S2p20 S2p80 S3 S2d S3h B B2 E E2 C D Dp F'.split().index(c) if c in 'A A29 X S1 S1h S1x S2 S2p20 S2p80 S3 S2d S3h B B2 E E2 C D Dp F'.split() else 9)))


if __name__ == '__main__':
    main()
