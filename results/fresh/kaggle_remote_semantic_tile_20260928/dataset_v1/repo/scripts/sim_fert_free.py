"""SIMULATION ONLY (user 2026-09-27, path-planner thread): a PICKUP FERTILIZER n at the shed always gets n, even
when the shed holds fewer - the shortfall is created in the shed just before the pickup. It measures what the path
planner (sd_path_planner) does when fertilizer supply is no constraint. It can never run in a real game: it patches
the engine module in THIS process (the kaggle_environments engine and upkeep_engine's by-path copy).

Scope, so the day-11 start and the rival stay exactly as recorded:
  - only the seat mapped to the game's seed (SEAT_BY_SEED, {seed: our seat}),
  - only from step START (264 = the day-11 morning; before it the leader's tape plays our seat),
  - only while ACTIVE (the harness switches it per arm: on for arms with sd_sim_fert_free, off for DSM's replay).
INJECTED counts the units created (per process; the harness reads it after each game / replay).
The seat and step come from the engine's interpreter frame (its locals i, env, step), found by walking up the stack,
so wrappers other scripts put around _apply_unit_action (season_gap's recorder) do not matter.
"""
import sys

ACTIVE = {'on': False}
SEAT_BY_SEED = {}
START = 264
INJECTED = {'n': 0, 'events': 0}
_DONE = set()


def _frame_ctx():
    f = sys._getframe(2)
    while f is not None:
        if f.f_code.co_name == 'interpreter' and 'i' in f.f_locals and 'env' in f.f_locals:
            loc = f.f_locals
            env = loc['env']
            info = getattr(env, 'info', None)
            if info is None and isinstance(env, dict):
                info = env.get('info')
            seed = info.get('seed') if isinstance(info, dict) else None
            return loc['i'], seed, int(loc.get('step', 0) or 0)
        f = f.f_back
    return None, None, None


def patch(E):
    """wrap E._apply_unit_action of one engine module object (idempotent)."""
    if id(E) in _DONE or getattr(E, '_sim_fert_free', False):
        return
    orig = E._apply_unit_action

    def _apply_unit_action(farm, private, idx, action, board_size, *a, **k):
        if (ACTIVE['on'] and isinstance(action, list) and len(action) >= 2 and action[0] == 'PICKUP'
                and action[1] == 'FERTILIZER'):
            seat, seed, step = _frame_ctx()
            if seat is not None and step >= START and SEAT_BY_SEED.get(seed) == seat:
                pos = E._farmer_position(farm, idx)
                if pos is not None and E._is_shed_adjacent((pos[0], pos[1]), board_size):
                    n = int(action[2]) if len(action) >= 3 else 1
                    have = int(private['shed'].get('FERTILIZER', 0) or 0)
                    if n > have:
                        private['shed']['FERTILIZER'] = n
                        INJECTED['n'] += n - have
                        INJECTED['events'] += 1
        return orig(farm, private, idx, action, board_size, *a, **k)

    E._apply_unit_action = _apply_unit_action
    E._sim_fert_free = True
    _DONE.add(id(E))


def install():
    """patch both engine copies this process may use."""
    try:
        import kaggle_environments.envs.kaggriculture.kaggriculture as KE_E
        patch(KE_E)
    except Exception:
        pass
    try:
        import upkeep_engine as UE
        patch(UE.engine())
    except Exception:
        pass
