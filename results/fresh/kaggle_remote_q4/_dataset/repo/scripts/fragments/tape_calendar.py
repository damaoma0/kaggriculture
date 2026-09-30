# --------------------------------------------------------------------------- tape calendar
# Forward simulation of the native crew's positions from the route tape alone. The chassis replays unit
# commands by dead reckoning, so a unit's future position is its position now plus its tape moves, and a
# hand hired at step t spawns (after that step's moves) on the least-occupied shed-access tile, NWSE order,
# exactly as the engine's _spawn_hand does. At the end of every day the farmer returns to (4, 4) and all
# hands vanish. The result is the visit calendar: which unit stands on which tile at which step and what
# its tape command is there. Standard library only; no engine imports.
_TC_SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
_TC_MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}


def _tc_spawn(positions):
    occ = {p: 0 for p in _TC_SHED}
    for p in positions:
        if p in occ:
            occ[p] += 1
    return min(_TC_SHED, key=lambda p: (occ[p], _TC_SHED.index(p)))


def _tc_units(action):
    if not isinstance(action, dict):
        return [['PASS']]
    return [action.get('farmer') or ['PASS']] + [h or ['PASS'] for h in (action.get('hands') or [])]


def _tc_simulate(tape_at, start_step, end_step, positions, board=10):
    """tape_at(t) -> the route's action dict at step t. positions: tape-unit positions before step
    start_step's commands (farmer first). Returns {step: [(x, y, command), ...]} for start_step..end_step,
    one entry per tape unit present at that step (positions are BEFORE the step's command)."""
    pos = [tuple(p) for p in positions]
    out = {}
    for t in range(start_step, end_step + 1):
        action = tape_at(t)
        cmds = _tc_units(action)
        out[t] = [(p[0], p[1], cmds[i] if i < len(cmds) else ['PASS']) for i, p in enumerate(pos)]
        for i, p in enumerate(pos):
            c = cmds[i] if i < len(cmds) else ['PASS']
            if c and c[0] in _TC_MOVES:
                dx, dy = _TC_MOVES[c[0]]
                nx, ny = p[0] + dx, p[1] + dy
                if 0 <= nx < board and 0 <= ny < board:
                    pos[i] = (nx, ny)
        for o in (action.get('market') or []) if isinstance(action, dict) else []:
            if o and o[0] == 'HIRE':
                pos.append(_tc_spawn(pos))
        if (t + 1) % 24 == 0:
            pos = [_TC_SHED[0]]
    return out


def _tc_visits(sim):
    """{(x, y): [(step, unit, command), ...]} for every non-move, non-PASS tape command."""
    visits = {}
    for t in sorted(sim):
        for u, (x, y, c) in enumerate(sim[t]):
            if c and c[0] not in _TC_MOVES and c[0] != 'PASS':
                visits.setdefault((x, y), []).append((t, u, list(c)))
    return visits
