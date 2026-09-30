"""Extract Mother-Goose's strategy and sell points from her raw public replays, for the viewer page.

Sources: data/leaders_20260917 (30 games of her OLD deterministic policy, submission 56266758) and
data/leaders_20260919 (42 games of her two NEW closed-loop submissions). Output: results/fresh/mg_watch/data.json

Per game: opponent, result, the 8 shops, every product's price path (every 2 hours), every SELL she and her
opponent filled (step, product, units, price before the sale, engine-curve average over the lot), her board at each
day start (one character per tile), both farms' cash per day, and her purchases of land and animals.
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kaggle_environments.envs.kaggriculture import kaggriculture as E  # noqa: E402

PRODUCTS = ['WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON', 'FERTILIZER']
CODE = {'WHEAT': 'W', 'CARROT': 'C', 'TOMATO': 'T', 'STRAWBERRY': 'S', 'MELON': 'M',
        'SHEEP': 's', 'COW': 'c', 'GOOSE': 'g'}


def tile_code(t):
    if t == 'LOCKED':
        return 'L'
    if t is None:
        return '.'
    k = t.get('kind')
    if k == 'PLANT':
        return CODE.get(t.get('crop'), '?')
    if k == 'WEED':
        return 'x'
    if t.get('animal'):
        return CODE.get(t['animal'], '?')
    return 'p' if k == 'PASTURE' else 'o' if k == 'COOP' else '?'


def lot_average(item, inventory, n):
    """Engine price averaged over a lot of n units sold one after another (the rival's same-step sales ignored)."""
    return sum(E.market_price(item, inventory + i) for i in range(n)) / max(1, n)


def sells(steps, seat):
    out = []
    for i in range(1, len(steps)):
        act = steps[i][seat].get('action') or {}
        market = act.get('market') or [] if isinstance(act, dict) else []
        if not market:
            continue
        before = steps[i - 1]
        private = before[seat]['observation'].get('private') or {}
        shed = dict(private.get('shed') or {})
        mk = before[0]['observation']['market']
        # unit commands run BEFORE the market phase of the same step: she delivers and sells in one step, so the
        # stock on sale is the shed plus what her units DROP / PLACE at the shed (less what they PICK UP) this step
        farm = before[0]['observation']['farms'][seat]
        units = [farm['farmer']] + list(farm['hands'])
        invs = private.get('inventories') or []
        cmds = [act.get('farmer')] + list(act.get('hands') or [])
        for u, c in enumerate(cmds):
            if not c or u >= len(units) or not E._is_shed_adjacent(tuple(units[u]), 10):
                continue
            inv = invs[u] if u < len(invs) else {}
            if c[0] == 'DROP':
                for item, n in (inv or {}).items():
                    shed[item] = shed.get(item, 0) + int(n or 0)
            elif c[0] == 'PLACE' and len(c) > 1 and c[1] in PRODUCTS:
                n = min(int(c[2]) if len(c) > 2 else 1, int((inv or {}).get(c[1], 0) or 0))
                shed[c[1]] = shed.get(c[1], 0) + n
            elif c[0] == 'PICKUP' and len(c) > 1:
                n = min(int(c[2]) if len(c) > 2 else 1, int(shed.get(c[1], 0) or 0))
                shed[c[1]] = shed.get(c[1], 0) - n
        for o in market:
            if not (o and o[0] == 'SELL' and len(o) >= 3 and o[1] in PRODUCTS):
                continue
            n = min(int(o[2]), int(shed.get(o[1], 0) or 0))
            if n <= 0:
                continue
            shed[o[1]] -= n
            inv = mk['inventory'][o[1]]
            out.append([i - 1, PRODUCTS.index(o[1]), n, mk['prices'][o[1]], round(lot_average(o[1], inv, n), 1)])
    return out


def game(path, era):
    r = json.load(open(path))
    names = r['info']['TeamNames']
    seat = next(i for i, n in enumerate(names) if 'Mother' in (n or ''))
    steps = r['steps']
    obs = lambda i: steps[i][0]['observation']
    prices = {p: [obs(i)['market']['prices'][p] for i in range(0, len(steps), 2)] for p in PRODUCTS}
    boards, cash, rcash, hands = [], [], [], []
    for d in range(30):
        o = obs(min(d * 24, len(steps) - 1))
        boards.append(''.join(tile_code(t) for row in o['farms'][seat]['tiles'] for t in row))
        cash.append(round(o['farms'][seat]['money']))
        rcash.append(round(o['farms'][1 - seat]['money']))
        hands.append(max(len(obs(min(d * 24 + h, len(steps) - 1))['farms'][seat]['hands']) for h in (3, 8, 12)))
    events = []
    for i in range(1, len(steps)):
        act = steps[i][seat].get('action') or {}
        for o in (act.get('market') or []) if isinstance(act, dict) else []:
            if o and o[0] == 'BUY_LAND':
                events.append([i - 1, 'LAND', 1])
    # animals actually arriving on the board, by day
    prev = {}
    for d, b in enumerate(boards):
        cur = {c: b.count(c) for c in 'scg'}
        for c, name in (('s', 'SHEEP'), ('c', 'COW'), ('g', 'GOOSE')):
            if cur[c] > prev.get(c, 0):
                events.append([d * 24, name, cur[c] - prev.get(c, 0)])
        prev = cur
    shops = list(obs(len(steps) - 1)['town']['unlocked_shops'])
    return dict(id=int(r['info']['EpisodeId']), era=era, seat=seat, opp=names[1 - seat],
                reward=[r['rewards'][seat], r['rewards'][1 - seat]], shops=shops, prices=prices,
                sells=sells(steps, seat), rsells=sells(steps, 1 - seat), boards=boards, cash=cash + [round(r['rewards'][seat] or 0)],
                rcash=rcash + [round(r['rewards'][1 - seat] or 0)], hands=hands, events=sorted(events))


def main():
    games = []
    for d, era in (('data/leaders_20260917', 'old'), ('data/leaders_20260919', 'new')):
        for p in sorted(glob.glob(str(ROOT / d / '*.json'))):
            r_names = json.load(open(p))['info'].get('TeamNames') or []
            if not any('Mother' in (n or '') for n in r_names):
                continue
            g = game(p, era)
            games.append(g)
            print(g['id'], era, 'vs', g['opp'], g['reward'], 'sells', len(g['sells']), flush=True)
    out = ROOT / 'results/fresh/mg_watch'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'data.json').write_text(json.dumps(dict(products=PRODUCTS, games=games), separators=(',', ':')), encoding='utf-8')
    print('games', len(games), 'bytes', (out / 'data.json').stat().st_size)


if __name__ == '__main__':
    main()
