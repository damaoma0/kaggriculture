"""Day-11 measurements in one inspected world, all by replaying the official engine (upkeep_engine.World):

  1. the leader's day 11-13 and an arm's day 11-12: every HARVEST (tile, crop, units), PLANT (tile, crop, hour),
     WATER and FERTILIZE per tile -> harvest amounts and replant exactness, arm vs leader;
  2. the value of ONE fertilize on day 11 for every plant on the board at the day-11 morning: a copy of the leader's
     world at step 264 where that plant is marked fertilized (fertilized_until_day = 13, what a FERTILIZE on day 11
     sets), then the leader's own recorded actions to the day-14 morning (step 336); extra units = (units harvested
     from that tile + units still on it at step 336) with minus without. Priced at the day-11 market price.

usage: day11_fert_value.py <team:episode> <arm stream dir key, e.g. k2f60> -> results/fresh/day12_viz/fert_value_<ep>.json
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

D11, D12, D14 = 264, 288, 336


def own_cmds(a):
    return [a.get('farmer')] + list(a.get('hands') or []) if a else []


def replay(seed, shops, seat, provider, lo, hi, snap_at=None):
    """events per step in [lo, hi): (t, unit, cmd, tile index, tile state before the command); snapshot at snap_at."""
    w = UE.World(seed, shops)
    ev, snap = [], None
    while w.t < hi:
        if snap_at is not None and w.t == snap_at:
            snap = w.snapshot()
        own, opp = provider(w.t)
        if w.t >= lo and own:
            farm = w.farms[seat]
            units = [farm['farmer']] + list(farm['hands'])
            for u, c in enumerate(own_cmds(own)):
                if c and u < len(units) and c[0] in ('HARVEST', 'PLANT', 'WATER', 'FERTILIZE', 'DIG'):
                    x, y = units[u]
                    ev.append((w.t, u, list(c), y * 10 + x, copy.deepcopy(farm['tiles'][y][x])))
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, opp
        w.step(acts)
    return ev, snap, w


def summarize(ev, days):
    out = {d: {'harvest': {}, 'plant': {}, 'water': [], 'fert': []} for d in days}
    for t, u, c, i, tile in ev:
        d = t // 24
        if d not in out:
            continue
        if c[0] == 'HARVEST' and isinstance(tile, dict) and int(tile.get('yield_units', 0) or 0) > 0:
            crop = tile.get('crop') or tile.get('animal')
            out[d]['harvest'][i] = [crop, int(tile['yield_units']), t % 24]
        elif c[0] == 'PLANT' and tile is None:
            out[d]['plant'][i] = [c[1], t % 24]
        elif c[0] == 'WATER' and isinstance(tile, dict) and tile.get('kind') == 'PLANT' and not tile.get('watered_today'):
            out[d]['water'].append(i)
        elif c[0] == 'FERTILIZE' and isinstance(tile, dict) and tile.get('kind') == 'PLANT':
            out[d]['fert'].append(i)
    return out


def tile_units(w0, seat, idx, provider, fert):
    """units a tile yields from step 264 to 336 under the given actions, with / without a day-11 fertilize."""
    w = UE.World.restore(w0)
    x, y = idx % 10, idx // 10
    t0 = w.farms[seat]['tiles'][y][x]
    if fert:
        t0['fertilized_until_day'] = max(int(t0.get('fertilized_until_day', -1)), 13)
    got = 0
    while w.t < D14:
        own, opp = provider(w.t)
        farm = w.farms[seat]
        units = [farm['farmer']] + list(farm['hands'])
        if not fert and own and w.t // 24 == 11:        # without: the leader's own day-11 fertilize on this tile is dropped
            cm = own_cmds(own)
            if any(c and c[0] == 'FERTILIZE' and u < len(units) and tuple(units[u]) == (x, y) for u, c in enumerate(cm)):
                own = copy.deepcopy(own)
                if own.get('farmer') and own['farmer'][0] == 'FERTILIZE' and tuple(units[0]) == (x, y):
                    own['farmer'] = ['PASS']
                for k, h in enumerate(own.get('hands') or []):
                    if h and h[0] == 'FERTILIZE' and k + 1 < len(units) and tuple(units[k + 1]) == (x, y):
                        own['hands'][k] = ['PASS']
        for u, c in enumerate(own_cmds(own)):
            if c and c[0] == 'HARVEST' and u < len(units) and tuple(units[u]) == (x, y):
                tl = farm['tiles'][y][x]
                if isinstance(tl, dict) and tl.get('kind') == 'PLANT':
                    got += int(tl.get('yield_units', 0) or 0)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, opp
        w.step(acts)
    tl = w.farms[seat]['tiles'][y][x]
    left = int(tl.get('yield_units', 0) or 0) if isinstance(tl, dict) and tl.get('kind') == 'PLANT' else 0
    return got, left


def main():
    game, arm = sys.argv[1], sys.argv[2]
    team, ep = game.split(':')
    tape = UE.load_tape(int(team), ep)
    seat, seed, shops = tape['seat'], tape['seed'], tape['shops']

    def lead(t):
        return UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
    stream = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm}_streams' / f'{ep}.json').read_text(encoding='utf-8'))

    def ours(t):
        if D11 <= t < D11 + 48:
            return stream['actions'][t], UE.tape_action(tape['opp_actions'], t)
        return lead(t)
    ev_l, snap, _ = replay(seed, shops, seat, lead, D11, D14, snap_at=D11)
    ev_o, _, _ = replay(seed, shops, seat, ours, D11, D11 + 48)
    L, O = summarize(ev_l, (11, 12, 13)), summarize(ev_o, (11, 12))
    # ---- fertilize value per plant (leader's own actions, days 11-13)
    farm0 = snap['farms'][seat]
    prices = snap['market']
    fv = []
    for idx in range(100):
        t = farm0['tiles'][idx // 10][idx % 10]
        if not (isinstance(t, dict) and t.get('kind') == 'PLANT'):
            continue
        g0, l0 = tile_units(snap, seat, idx, lead, False)
        g1, l1 = tile_units(snap, seat, idx, lead, True)
        fv.append(dict(tile=[idx % 10, idx // 10], crop=t['crop'], age=11 - int(t['planted_day']),
                       yield0=int(t.get('yield_units', 0) or 0), units_without=g0 + l0, units_with=g1 + l1,
                       extra=(g1 + l1) - (g0 + l0), leader_fertilized_d11=idx in L[11]['fert'],
                       leader_waters=[d for d in (11, 12, 13) if idx in L[d]['water']],
                       leader_harvest={d: L[d]['harvest'][idx][1:] for d in (11, 12, 13) if idx in L[d]['harvest']}))
    res = dict(game=game, arm=arm, leader=L, ours=O, fert_value=fv, prices=prices)
    out = ROOT / 'results/fresh/day12_viz' / f'fert_value_{ep}.json'
    out.write_text(json.dumps(res, default=str), encoding='utf-8')
    print('wrote', out)


if __name__ == '__main__':
    main()
