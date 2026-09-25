"""Build NEW copies of our executors with the rolling-horizon route-search dispatcher of
scripts/search_dispatch_block.py wired in behind CFG "dispatch_search" (default "off"). The sources are only read:
each target builds from a byte snapshot under results/fresh/search_dispatch_20260925/source/ whose sha256 is checked
(agents/mgt_lead.py and agents/mgt_lead_deploy.py belong to other threads and keep changing).

  lead    agents/mgt_lead_search.py  <- agents/mgt_lead.py (T: the leader's exact plan in the leader's world)
  deploy  agents/mgt_lpv_search.py   <- agents/mgt_lead_deploy.py (same executor section + the deploy target builder)

A copy = the source + (1) the block's CFG keys (end of the executor CFG dict), (2) five guarded hook lines (agent():
HOOK 1 before the greedy matching, HOOK 2 at the top of the per-unit command loop, HOOK 3 before the market; HOOK 4 /
HOOK 5 = step start / step end: inside agent() for lead, in the entry point for the deploy), (3) the block (lead: at
the end of the file; deploy: before the deploy section's end marker, so the entry point stays the LAST callable),
(4) a docstring note. With "off" every hook is a no-op (a None assignment and false tests): the diff against the
source is additions only (scripts/search_dispatch_check.py static verifies it).

usage: search_dispatch_build.py [lead|deploy|all]
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRCDIR = 'results/fresh/search_dispatch_20260925/source'
TARGETS = {
    'lead': dict(src=f'{SRCDIR}/mgt_lead_9e00c3a4.py', orig='agents/mgt_lead.py',
                 sha='9e00c3a449c029988666d281a0b5c625ab99468f83dc31db53cbe98ff60b6545', when='2026-09-25 ~15:00',
                 out='agents/mgt_lead_search.py', first='"""mgt_lead:', timing='agent', block='end'),
    'deploy': dict(src=f'{SRCDIR}/mgt_lead_deploy_e33d0459.py', orig='agents/mgt_lead_deploy.py',
                   sha='e33d0459486b947943109e664cae594136002f36392aefdcdebdffda2d778434', when='2026-09-25 14:31',
                   out='agents/mgt_lpv_search.py', first='"""mgt_lead_deploy:', timing='entry', block='deploy_end'),
}

CFG_KEYS = '''    # ---- SEARCH DISPATCH (mgt_lead_search / mgt_lpv_search only; scripts/search_dispatch_block.py) ---------
    "dispatch_search": "off", # "off" = the source's decisions | "shadow" = greedy acts, the planner runs and logs | "active" = planned units follow the plan
    "sd_days": None,          # [lo, hi] day window (inclusive) of the planner; None = every day
    "sd_budget0": 0.9,        # s: time cap of the day's first plan (hour 0; warm start of the day)
    "sd_budget": 0.3,         # s: time cap of a later step's re-plan
    "sd_evals0": 60000,       # route evaluations of the day's first plan (deterministic work budget)
    "sd_evals": 8000,         # route evaluations of a later step
    "sd_step_cap": 0.95,      # s: the planner stops when the whole step reaches this
    "sd_bank_stop": 20.0,     # s of the 60 s overage bank used -> planner off (greedy) for the rest of the game
    "sd_lambda": 0.5,         # coins per planned unit-step (tie-breaker toward short routes)
    "sd_late_frac": 0.5,      # share of an op's value kept when it is done after its deadline
    "sd_switch": 40.0,        # coins per step already walked toward a job the unit is taken off (the executor's step_value)
    "sd_vmin": 2.0,           # minimum value of an op (value-0 jobs save later visits)
    "sd_hard": 5000.0,        # bonus on survival ops (plant dies / animal escapes tonight): hard constraints
    "sd_cap": 100,            # midnight shed cap ...
    "sd_cap_margin": 0,       # ... minus this margin
    "sd_cap_w": 20.0,         # coins per projected midnight-load unit above the cap
    "sd_plan_jobs": 1,        # predicted jobs: plan plantings whose seeds are bought this step (release next hour)
    "sd_pairs": 1,            # predicted jobs: the deploy's same-day replant after a wheat / carrot harvest (order pair)
    "sd_replant_value": 400.0,
    "sd_k_units": 4,          # candidate routes per insertion (nearest) + the 2 nearest idle units
    "sd_rr_max": 8,           # ruin size (jobs)
    "sd_rr_noise": 30.0,      # regret noise of the recreate step (coins)
    "sd_rr_stall": 25,        # ruin-and-recreate attempts without improvement before the step's search stops
    "sd_seed": 7,
    "sd_hs_drop": 1,          # a planned unit at its pickup shed tile from hs_drop_hour places wheat above its route's need
    "sd_idle": "pass",        # a planned unit with an empty route: "pass" (deliver what it carries, else wait) | "greedy"
    "sd_deliv": 1,            # model the executor's delivery trigger inside the routes
    "sd_finish_tile": 1,      # active: a delivery started this step waits while a planned unit is on its current planned tile
    "sd_dv_frac": {},         # v2: product -> share of the current price credited per unit delivered by sd_dv_hour (sold the same day)
    "sd_dv_coins": {},        # v2: product -> coins per such unit (a number, or [[first_day, coins], ...])
    "sd_dv_hour": 22,         # v2: last DROP / PLACE hour that sells the same day (unit actions come before the market)
    "sd_dv_quota": 1,         # v2: with sell_source "leader" only products whose sell quota of the day has room get the credit
    "sd_final_trip": 0,       # v2: routes end with the walk of their products to the shed (credited when in time)
    "sd_hard_late_w": 0.0,    # v2: coins per hour a hard (survival) op is done after sd_hard_safe
    "sd_hard_safe": 20,
    "sd_hard_all": 0,         # v2: every unit is a candidate for a hard job
    "sd_hard_eject": 0,       # v2: a hard job nobody can take is inserted by dropping the least-value non-hard jobs
    "sd_cap_all": 0,          # v3: the midnight shed-load term also counts products staying in the shed overnight
    "sd_mr": 0,               # v3: maintenance job values at marginal revenue (price - slope x our units still to sell)
    "sd_mr_floor": 0.1,       # v3: ... floored at this share of the price
    "sd_surv_fb": None,       # v5: from this hour the executor's survival routes keep their units / tiles (None = off)
    "sd_hv_pref": {},         # v3: the leaders' harvest timing as soft bonuses on HARVEST ops (see the block header); {} = off
    "sd_keep": 0,             # research: keep the last plan object (static checks)
    "sd_log": None,           # research: directory for per-step jsonl records + the game summary
'''

HOOK1 = ('    _sd_run = _sd_pre(S, obs, me, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, '
         'assign, taken, surv_route, deliv_u, fert_keep, demand, prev) if CFG["dispatch_search"] != "off" else None   '
         '# SEARCH DISPATCH HOOK 1\n')
HOOK2 = ('        if _sd_run is not None and u in _sd_run["units"]:   # SEARCH DISPATCH HOOK 2\n'
         '            _sd_a = _sd_act(S, _sd_run, u, p, inv, tasks, tiles, shed_left, seeds_left, plant_count, carried, '
         'hour, usable_ops, deliv_u)\n'
         '            if _sd_a is not None:\n'
         '                actions[u] = _sd_a\n'
         '                continue\n')
HOOK3 = ('    if _sd_run is not None:   # SEARCH DISPATCH HOOK 3\n'
         '        _sd_post(S, _sd_run, obs, me, step, day, hour, last_day, tiles, pos, tasks, assign, actions)\n')
HOOK4 = ('    if CFG["dispatch_search"] != "off":   # SEARCH DISPATCH HOOK 4\n'
         '        _SD_T[:] = [t0]\n')
HOOK5 = ('    if CFG["dispatch_search"] != "off":   # SEARCH DISPATCH HOOK 5\n'
         '        _sd_step_end(step, t0)\n')


def insert_before(s, anchor, text, last=False):
    k = s.count(anchor)
    assert k == 1 or (last and k >= 1), f'anchor found {k} times: {anchor[:80]!r}'
    i = s.rfind(anchor) if last else s.find(anchor)
    return s[:i] + text + s[i:]


def insert_after(s, anchor, text):
    assert s.count(anchor) == 1, f'anchor found {s.count(anchor)} times: {anchor[:80]!r}'
    i = s.find(anchor) + len(anchor)
    return s[:i] + text + s[i:]


def build(name):
    T = TARGETS[name]
    raw = (ROOT / T['src']).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    assert sha == T['sha'], f"{T['src']} sha256 {sha} != {T['sha']}"
    s = raw.decode('utf-8').replace('\r\n', '\n')
    block = (ROOT / 'scripts/search_dispatch_block.py').read_text(encoding='utf-8').replace('\r\n', '\n')
    first = s.split('\n', 1)[0]
    assert first.startswith(T['first']), first
    out = T['out']
    note = ('\n%s (2026-09-25, built by scripts/search_dispatch_build.py from %s as of %s, sha256 %s, snapshot\n'
            '%s): the same agent plus a rolling-horizon route-search dispatcher behind CFG "dispatch_search" (default\n'
            '"off" = the source\'s decisions: every hook is guarded). See the SEARCH DISPATCH BLOCK.\n'
            % (Path(out).stem, T['orig'], T['when'], sha[:16], T['src']))
    s = first + note + s[len(first):]
    s = insert_after(s, '    "rm_late": 1,             # sem4: a removal stays open on the leader\'s removal day and this many days after\n', CFG_KEYS)
    s = insert_before(s, '    free = [u for u in range(n) if u not in assign] if CFG["dispatch"] != "route" else []\n', HOOK1)
    s = insert_before(s, '        idx = assign.get(u)\n        if CFG["cap_fix"] and CFG["cap_fix_hour"] <= hour <= 23', HOOK2)
    s = insert_before(s, '    # ---- market\n    orders = _market(', HOOK3)
    if T['timing'] == 'agent':
        s = insert_after(s, 'def agent(obs, config=None):\n    global _S\n    t0 = time.time()\n', HOOK4)
        s = insert_before(s, '    return {"farmer": actions[0], "hands": actions[1:], "market": orders}\n', HOOK5)
    else:
        s = insert_after(s, 'def mgt_lead_deploy_agent(obs, config=None):\n    t0 = time.time()\n', HOOK4)
        s = insert_before(s, '    return out\n', HOOK5, last=True)
    if T['block'] == 'end':
        s = s.rstrip('\n') + '\n\n\n' + block
    else:
        s = insert_before(s, '# ===== END DEPLOY SECTION; the entry point must stay the LAST callable in the file', block + '\n\n')
        tail = s[s.rfind('# ===== END DEPLOY SECTION'):]
        assert tail.count('\ndef ') == 1 and 'def mgt_lead_deploy_agent' in tail, 'the entry point must be the last def'
    compile(s, out, 'exec')
    (ROOT / out).write_bytes(s.encode('utf-8'))
    print(f'{out}: {len(s)} chars from {T["orig"]} snapshot sha256 {sha[:16]}; copy sha256 '
          f'{hashlib.sha256(s.encode()).hexdigest()}')


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    for n in (TARGETS if which == 'all' else [which]):
        build(n)
