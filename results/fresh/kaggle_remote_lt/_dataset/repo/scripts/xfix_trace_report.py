"""xfix: day-11 trace comparison, leader vs T from the leader's exact morning state (stored traces only, no games).

Reads results/fresh/xfix_20260925/trace/{LEADER,<arm>}/<ep>.json (scripts/xfix_run.py trace) and writes
results/fresh/xfix_20260925/trace_report_<arm>.txt: per world and pooled
  - effective ops by command and crop / animal, PASS unit-steps by hour and the idle trace's reason, moves
  - harvests: tiles the leader harvests that T does not (crop, age, units; T's task on the tile, its priority, value)
  - fertilize: tiles the leader fertilizes vs T (crop, age; T's task ops / priority / value on the tile)
  - structural ops (PLANT / BUILD / animal PLACE / DIG): leader vs T per tile, T's plan job on the tile
  - market: sells by product, seeds / animals / products bought, per hour; midnight carried stock; next-morning cash
usage: xfix_trace_report.py [arm=T]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/xfix_20260925'
D = 11
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
LINES = []


def say(s=''):
    LINES.append(s)
    print(s)


def label(sig):
    return (sig or '.').split('@')[0]


def asset_of(sig):
    if not sig or sig in ('.', 'L', 'WEED'):
        return sig or '.'
    return sig.split('@')[0]


def age_of(sig):
    try:
        return D - int(sig.split('@')[1].split()[0])
    except Exception:
        return None


def yield_of(sig):
    try:
        return int(sig.split(' y')[1].split()[0])
    except Exception:
        return None


def ops_of(rec):
    """[(t, unit, cmd, arg, eff, tile, sig0, sig1, inv0, inv1)] of our seat on day D."""
    out = []
    for t, lst in rec['units'].items():
        for idx, p0, action, eff, s0, s1, i0, i1 in lst:
            cmd = action[0] if isinstance(action, list) and action else 'PASS'
            arg = action[1] if isinstance(action, list) and len(action) > 1 else None
            tile = p0[1] * 10 + p0[0] if p0 else None
            out.append((int(t), idx, cmd, arg, eff, tile, s0, s1, i0, i1))
    return sorted(out)


def passes_of(rec):
    """PASS unit-steps: from the actions (units with no hook record did nothing: PASS or missing)."""
    out = []
    for t, a in rec.get('actions', {}).items():
        cmds = [a.get('farmer') or ['PASS']] + list(a.get('hands') or [])
        n_units = len(rec['obs'].get(t, {}).get('pos', [])) or len(cmds)
        for u in range(n_units):
            c = cmds[u] if u < len(cmds) else ['PASS']
            if not c or c[0] == 'PASS':
                out.append((int(t), u))
    return out


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else 'T'
    eps = sorted(int(p.stem) for p in (OUT / 'trace' / 'LEADER').glob('*.json') if (OUT / 'trace' / arm / p.name).exists())
    say(f'day-11 trace: leader vs {arm} from the leader\'s exact morning state, {len(eps)} worlds')
    pooled = defaultdict(Counter)
    for ep in eps:
        L = json.loads((OUT / 'trace' / 'LEADER' / f'{ep}.json').read_text(encoding='utf-8'))
        T = json.loads((OUT / 'trace' / arm / f'{ep}.json').read_text(encoding='utf-8'))
        say(f'\n==================== {ep} ({L["game"]}): cash next morning leader {L["cash_next_morning"]:,.0f} / {arm} '
            f'{T["cash_next_morning"]:,.0f} ({T["cash_next_morning"] - L["cash_next_morning"]:+,.0f})')
        oL, oT = ops_of(L), ops_of(T)
        for side, ops, tag in (('L', oL, 'leader'), ('T', oT, arm)):
            c = Counter()
            for (t, u, cmd, arg, eff, tile, s0, s1, i0, i1) in ops:
                if cmd in MOVES:
                    c['MOVE'] += 1
                    continue
                if not eff:
                    c['noeff:' + cmd] += 1
                    continue
                if cmd == 'PLACE':
                    c['PLACE:' + ('shed' if tile is not None and (tile % 10, tile // 10) in SHED and arg not in ('GOOSE', 'COW', 'SHEEP') else str(arg))] += 1
                elif cmd in ('WATER', 'FERTILIZE', 'HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'DIG'):
                    c[cmd + ':' + asset_of(s0)] += 1
                else:
                    c[cmd + (':' + str(arg) if arg and cmd == 'PLANT' else '')] += 1
            c['PASS'] = len(passes_of(L if side == 'L' else T))
            pooled[side].update(c)
            say(f'  ops {tag:7s}: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))
        # ---- PASS reasons (T)
        pt = passes_of(T)
        byh = Counter(t % 24 for t, u in pt)
        say(f'  {arm} PASS by hour: ' + ' '.join(f'h{h}:{n}' for h, n in sorted(byh.items())))
        reasons = Counter()
        for t, info in T['tinfo'].items():
            for b in info.get('idle', []) or []:
                if b['kind'] == 'tile_noop':
                    reasons['tile_noop:' + ','.join(b['ops'])] += 1
                else:
                    cnt = Counter(v[0].split(':')[0] for v in b['why'].values())
                    reasons[b['kind'] + ' (' + ', '.join(f'{k} {v}' for k, v in sorted(cnt.items())) + ')'] += 1
        for r, n in reasons.most_common(8):
            say(f'     {n:3d} x {r}')
        for d_ in T.get('idle_day', []):
            say(f'  {arm} idle-trace day record: passes {d_.get("passes")}; work {d_.get("work")}')
        # ---- harvests
        hL = {(tile): (t, s0) for (t, u, cmd, arg, eff, tile, s0, s1, i0, i1) in oL if cmd == 'HARVEST' and eff}
        hT = {(tile): (t, s0) for (t, u, cmd, arg, eff, tile, s0, s1, i0, i1) in oT if cmd == 'HARVEST' and eff}
        say(f'  HARVEST tiles: leader {len(hL)}, {arm} {len(hT)}; leader-only:')
        for tile, (t, s0) in sorted(hL.items()):
            if tile in hT:
                continue
            task = [(int(tt) % 24, info.get('tasks', {}).get(str(tile)), info.get('tval', {}).get(str(tile)))
                    for tt, info in sorted(T['tinfo'].items(), key=lambda kv: int(kv[0]))
                    if str(tile) in (info.get('tasks') or {})]
            first = task[0] if task else None
            harv_task = [x for x in task if x[1] and any(o[0] == 'HARVEST' for o in x[1][0])]
            say(f'     tile {tile:2d} {s0:30s} leader h{t % 24:2d}; {arm}: task hours {len(task)}, with HARVEST {len(harv_task)}'
                + (f', first {first[1][0]} prio {first[1][2]} tval {first[2]}' if first else ', no task'))
            pooled['H'][asset_of(s0) + (' HARVEST in task' if harv_task else ' no HARVEST task')] += 1
        # ---- fertilize
        fL = [(t, tile, s0) for (t, u, cmd, arg, eff, tile, s0, s1, i0, i1) in oL if cmd == 'FERTILIZE' and eff]
        fT = {tile for (t, u, cmd, arg, eff, tile, s0, s1, i0, i1) in oT if cmd == 'FERTILIZE' and eff}
        say(f'  FERTILIZE: leader {len(fL)} ({Counter(asset_of(s) for _, _, s in fL)}), {arm} {len(fT)}')
        for t, tile, s0 in fL:
            if tile in fT:
                continue
            task = [(int(tt) % 24, info.get('tasks', {}).get(str(tile)), info.get('tval', {}).get(str(tile)))
                    for tt, info in sorted(T['tinfo'].items(), key=lambda kv: int(kv[0])) if str(tile) in (info.get('tasks') or {})]
            ft = [x for x in task if x[1] and any(o[0] == 'FERTILIZE' for o in x[1][0])]
            infert = any(tile in (info.get('fert') or []) for info in T['tinfo'].values())
            say(f'     tile {tile:2d} {s0:30s} leader h{t % 24:2d}; {arm}: in plan fert {infert}; task hours {len(task)}, with FERTILIZE '
                f'{len(ft)}' + (f' prio {ft[0][1][2]} tval {ft[0][2]} ops {ft[0][1][0]}' if ft else (f'; ops {task[0][1][0]} prio {task[0][1][2]}' if task else '')))
            pooled['F'][asset_of(s0) + (' FERT in task p%s' % ft[0][1][2] if ft else ' no FERT task') + (' planfert' if infert else '')] += 1
        # ---- structural
        for cmd in ('PLANT', 'BUILD_COOP', 'BUILD_PASTURE', 'DIG'):
            sL = [(t % 24, tile, arg, s0) for (t, u, c, arg, eff, tile, s0, s1, i0, i1) in oL if c == cmd and eff]
            sT = {tile: (t % 24, arg) for (t, u, c, arg, eff, tile, s0, s1, i0, i1) in oT if c == cmd and eff}
            if not sL and not sT:
                continue
            miss = [(h, tile, arg, s0) for h, tile, arg, s0 in sL if tile not in sT]
            say(f'  {cmd}: leader {len(sL)}, {arm} {len(sT)}; leader-only {len(miss)}: ' + '; '.join(
                f't{tile} {arg or ""} h{h} ({s0}); {arm} job {next((info.get("jobs", {}).get(str(tile)) for tt, info in sorted(T["tinfo"].items(), key=lambda kv: int(kv[0])) if str(tile) in (info.get("jobs") or {})), None)}'
                for h, tile, arg, s0 in miss[:6]))
            extra = [(tile, v) for tile, v in sT.items() if tile not in {x[1] for x in sL}]
            if extra:
                say(f'     {arm}-only {cmd}: ' + '; '.join(f't{tile} {v}' for tile, v in extra[:8]))
        aL = [(t % 24, tile, arg) for (t, u, c, arg, eff, tile, s0, s1, i0, i1) in oL if c == 'PLACE' and eff and arg in ('GOOSE', 'COW', 'SHEEP')]
        aT = [(t % 24, tile, arg) for (t, u, c, arg, eff, tile, s0, s1, i0, i1) in oT if c == 'PLACE' and eff and arg in ('GOOSE', 'COW', 'SHEEP')]
        say(f'  animal PLACE: leader {aL}; {arm} {aT}')
        # ---- market
        for tag, R in (('leader', L), (arm, T)):
            ev = Counter()
            rev = 0.0
            for t, lst in R['market'].items():
                for op, item, price, ok in lst:
                    if ok:
                        ev[op + ':' + item] += 1
                        if op == 'SELL':
                            rev += price
            say(f'  market {tag:7s}: revenue {rev:,.0f}; ' + ', '.join(f'{k} {v}' for k, v in sorted(ev.items())))
            pooled['M' + ('L' if tag == 'leader' else 'T')].update(ev)
        say(f'  midnight carried leader {sum((Counter(i) for i in L["midnight"]["carried"]), Counter())} shed {L["midnight"]["shed"]}')
        say(f'  midnight carried {arm}   {sum((Counter(i) for i in T["midnight"]["carried"]), Counter())} shed {T["midnight"]["shed"]}')
        # next-morning tile differences
        tl, tt = L['obs'][str(D * 24 + 24)].get('tiles'), T['obs'][str(D * 24 + 24)].get('tiles')
        if tl and tt:
            diff = [(i, tl[i], tt[i]) for i in range(100) if tl[i].split(' ')[0] != tt[i].split(' ')[0]]
            say(f'  next-morning tiles with another asset/planting day: {len(diff)}: ' + '; '.join(f't{i} {a} | {b}' for i, a, b in diff[:10]))
    say('\n==================== pooled over the worlds (totals)')
    for side, tag in (('L', 'leader'), ('T', arm)):
        say(f'  ops {tag}: ' + ', '.join(f'{k} {v}' for k, v in sorted(pooled[side].items())))
    say('  leader-only harvests by asset / T task status: ' + ', '.join(f'{k} {v}' for k, v in pooled['H'].most_common()))
    say('  leader-only fertilize by asset / T task status: ' + ', '.join(f'{k} {v}' for k, v in pooled['F'].most_common()))
    say('  market leader: ' + ', '.join(f'{k} {v}' for k, v in sorted(pooled['ML'].items())))
    say(f'  market {arm}: ' + ', '.join(f'{k} {v}' for k, v in sorted(pooled['MT'].items())))
    (OUT / f'trace_report_{arm}.txt').write_text('\n'.join(LINES) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
