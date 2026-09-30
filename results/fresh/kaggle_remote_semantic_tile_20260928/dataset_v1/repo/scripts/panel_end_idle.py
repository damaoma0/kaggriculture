"""Why hands stand idle at the end of the day (arm over the 40-world panel, days 11-28, hands only): for every hand-day
with idle hours after its last work op, at the first idle hour: hours left (to hour 23), whether the plan ended the route
there (planned end < 24) or the hand skipped planned work, what it carries, and what useful work was within reach
(walk + 1 hour <= hours left): fertilizes that add yield (the agent's own _tier_fert_gain), and whether the hand could do
one - fertilizer in hand, or via a COLLECT at a pen with fertilizer on the way, or via the shed; unwatered plants; pens
with fertilizer waiting / unfed / uncared animals; harvestable tiles.
usage: panel_end_idle.py <ARM> [--workers 4]"""
import importlib.util
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

_spec = importlib.util.spec_from_file_location('agentmod', str(ROOT / 'agents/mgt_lead_sector_search.py'))
AG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AG)

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')
NONWORK = MOVES + ('PASS', 'DROP', 'PICKUP', 'PLACE')


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dsh(p):
    return min(d(p, s) for s in SHED)


def assess(c, dd, h, p, inv, tiles, shed, pe):
    left = 23 - h + 1
    c['idle_days'] += 1
    c['idle_hours'] += left
    c['left_%d' % min(left, 4)] += 1
    c['dist_shed'] += dsh(p)
    if pe is not None and pe < 24:
        c['plan_end_lt24'] += 1
    else:
        c['plan_end_24'] += 1
        c['plan_full_idle_hours'] += left
    fert_n = int(inv.get('FERTILIZER', 0) or 0)
    c['carry_fert'] += fert_n > 0
    fert_t, water_t, coll_t, feed_t, harv_t = [], [], [], [], []
    for y in range(10):
        for x in range(10):
            tl = tiles[y][x]
            if not isinstance(tl, dict):
                continue
            q = (x, y)
            if d(p, q) + 1 > left:
                continue
            if tl.get('kind') == 'PLANT':
                if AG._tier_fert_gain(y * 10 + x, tl, dd) > 0:
                    fert_t.append(q)
                if not tl.get('watered_today'):
                    water_t.append(q)
                cr = AG.CROPS.get(tl.get('crop'))
                if cr and int(tl.get('yield_units', 0) or 0) > 0 and dd - int(tl.get('planted_day', dd)) >= cr['first']:
                    harv_t.append(q)
            elif 'animal' in tl:
                if tl.get('fertilizer_available'):
                    coll_t.append(q)
                if not tl.get('fed_today') or not tl.get('cared_today'):
                    feed_t.append(q)
                if int(tl.get('yield_units', 0) or 0) > 0:
                    harv_t.append(q)
    c['fert_in_reach'] += bool(fert_t)
    if fert_t:
        c['fert_tiles_in_reach'] += len(fert_t)
        if fert_n > 0:
            c['fert_possible_in_hand'] += 1
        elif any(d(p, a) + 1 + d(a, b) + 1 <= left for a in coll_t for b in fert_t):
            c['fert_possible_via_collect'] += 1
        elif shed.get('FERTILIZER', 0) > 0 and any(d(p, sh) + 1 + d(sh, b) + 1 <= left for sh in SHED for b in fert_t):
            c['fert_possible_via_shed'] += 1
        else:
            c['fert_no_supply'] += 1
    c['water_in_reach'] += bool(water_t)
    c['collect_in_reach'] += bool(coll_t)
    c['feedcare_in_reach'] += bool(feed_t)
    c['harvest_in_reach'] += bool(harv_t)
    c['nothing_in_reach'] += not (fert_t or water_t or coll_t or feed_t or harv_t)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    plan_end = {}
    for day, v in res['tier_days'].items():
        for r in (v or {}).get('units') or []:
            plan_end[(int(day), r['u'])] = r['end']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    first_idle = {}                                       # (day, u) -> snapshot at the first PASS after the last work so far
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            invs = w.private(seat)['inventories']
            for u, p in enumerate(units):
                if u == 0:
                    continue
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op not in NONWORK:
                    first_idle.pop((dd, u), None)         # worked again: the earlier idle was not the end
                elif op == 'PASS' and (dd, u) not in first_idle and h >= 6:
                    first_idle[(dd, u)] = (h, p, dict(invs[u] if u < len(invs) else {}),
                                           json.loads(json.dumps(farm['tiles'])), dict(w.private(seat)['shed']))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if t >= 264 and h == 23:
            for (d0, u), (hh, p, inv, tiles, shed) in list(first_idle.items()):
                if d0 == dd:
                    assess(c, dd, hh, p, inv, tiles, shed, plan_end.get((dd, u)))
                    del first_idle[(d0, u)]
    return dict(c)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (__import__('os').environ.get('PANEL_GAMES') or (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text()).replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for c in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(c)
    n = len(games)
    m = max(1, tot['idle_days'])

    def g(k):
        return tot[k] / n
    print(f'{arm}: hand-days idle after their last job {g("idle_days"):.1f} a world, {g("idle_hours"):.0f} idle hours ({tot["idle_hours"] / m:.1f} each; '
          + ', '.join(f'{k[5:]}{"+" if k == "left_4" else ""} h: {g(k):.1f}' for k in sorted(tot) if k.startswith('left_'))
          + f'), {tot["dist_shed"] / m:.1f} steps from the shed')
    print(f'   plan: route planned to end before 24 {g("plan_end_lt24"):.1f}, planned to 24 but finished early (skipped / faster) '
          f'{g("plan_end_24"):.1f} ({g("plan_full_idle_hours"):.0f} h)')
    print(f'   within reach at the first idle hour: yield-adding fertilize {g("fert_in_reach"):.1f} '
          f'({tot["fert_tiles_in_reach"] / max(1, tot["fert_in_reach"]):.1f} tiles), water {g("water_in_reach"):.1f}, collect {g("collect_in_reach"):.1f}, '
          f'feed / care {g("feedcare_in_reach"):.1f}, harvest {g("harvest_in_reach"):.1f}, nothing {g("nothing_in_reach"):.1f}')
    print(f'   the fertilize: fertilizer in hand {g("fert_possible_in_hand"):.1f}, via a collect on the way {g("fert_possible_via_collect"):.1f}, '
          f'via the shed {g("fert_possible_via_shed"):.1f}, no supply in time {g("fert_no_supply"):.1f} | hands carrying fertilizer when idle {g("carry_fert"):.1f}')
