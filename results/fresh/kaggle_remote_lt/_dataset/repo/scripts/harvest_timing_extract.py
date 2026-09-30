"""Harvest timing, stage 1: extraction from the leaders' STORED action streams (no games, no engine run).

usage: .venv/Scripts/python.exe scripts/harvest_timing_extract.py [--limit N] [--teams id,id] [--tag NAME]

Per game of data/leader_semantics (the leader's seat) with its tape data/leader_tapes/<team>_<sub>/<ep>.json.gz:
  1. unit positions rebuilt from the engine's spawn rules and the recorded moves (the scripts/lead_route_order.py rule);
  2. every tile op in engine order (hour, then farmer, then hands 1..n; market orders after the unit actions);
  3. plant lifecycles simulated with the rules of kaggriculture.py 1.32.7: PLANT and FERTILIZE effects are taken from
     the corpus (ground truth: `planted`, `maintenance.FERTILIZE`); WATER (growth credited at the moment of watering,
     +2 only if fertilized_until_day >= day at that moment), HARVEST, DIG, weeding (2 unwatered days), ongoing
     productions (day end, +2 if watered and fertilized that day, held units capped at 4) and decay (-1 unit every 2
     steps from the lifespan step) are simulated and checked against the corpus (harvested tiles + units per day,
     WATER lists, next day-start board);
  4. every harvested crop unit followed to the shed (the harvesting unit's DROP / PLACE at the shed, else the midnight
     dump) and to the leader's SELL orders (FIFO per product, 10-order cap), checked against the corpus's daily sold
     units (corpus market index d holds day d+1; index 0 holds days 0 and 1: README KNOWN ISSUE).
Writes results/fresh/harvest_timing_20260925/<tag>/: harvests.jsonl.gz (one row per crop harvest), plants.jsonl.gz
(one row per planting), days.jsonl.gz (per game-day: realised units / revenue per product, cash), validation.json.
"""
import argparse
import gzip
import json
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEM = ROOT / 'data/leader_semantics'
TAPES = ROOT / 'data/leader_tapes'
OUT = ROOT / 'results/fresh/harvest_timing_20260925'

MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHED_SET = set(SHED)
# engine CROPS (kaggriculture.py 1.32.7); window = [(M + 1) // 2, M] for one-time crops
CROP = {
    'WHEAT': dict(F=2, M=4, I=0, cap=6, ongoing=False, code='WH'),
    'CARROT': dict(F=2, M=3, I=0, cap=4, ongoing=False, code='CA'),
    'TOMATO': dict(F=8, M=8, I=1, cap=4, ongoing=True, code='TO'),
    'STRAWBERRY': dict(F=10, M=10, I=2, cap=4, ongoing=True, code='ST'),
    'MELON': dict(F=10, M=12, I=0, cap=6, ongoing=False, code='ME'),
}
CODE2CROP = {v['code']: k for k, v in CROP.items()}
TEAMS = {'16623559': 'DECEM', '16681125': 'MMPQ', '16730612': 'UMG', '16732748': 'DSM', '16770421': 'Vadim',
         '16915014': 'Boey'}


def spawn(pos):
    occ = {t: 0 for t in SHED}
    for p in pos:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    return list(sorted(occ.items(), key=lambda kv: (kv[1], SHED.index(kv[0])))[0][0])


def rebuild(actions):
    """per day: unit events [(hour, unit, op, args, (x, y))] in engine order, market orders {hour: orders[:10]},
    hands seen per day."""
    ev = [[] for _ in range(30)]
    mk = [dict() for _ in range(30)]
    nh = [0] * 30
    pos = []
    for t, a in enumerate(actions[:719]):
        d, h = divmod(t, 24)
        if h == 0:
            pos = [[4, 4]]
        a = a if isinstance(a, dict) else {}
        hands = a.get('hands') or []
        if not isinstance(hands, list):
            hands = []
        while len(pos) - 1 < len(hands):
            pos.append(spawn(pos))
        nh[d] = max(nh[d], len(pos) - 1)
        units = [a.get('farmer') or ['PASS']] + list(hands)
        for u, act in enumerate(units):
            op = act[0] if isinstance(act, list) and act else 'PASS'
            p = tuple(pos[u])
            if op in MOVES:
                dx, dy = MOVES[op]
                pos[u] = [min(9, max(0, p[0] + dx)), min(9, max(0, p[1] + dy))]
            elif op != 'PASS':
                ev[d].append((h, u, op, list(act[1:]), p))
        m = a.get('market') or []
        if isinstance(m, list) and m:
            mk[d][h] = m[:10]
    return ev, mk, nh


def sem_market_day(days, D):
    """corpus market entry for TRUE day D (index D-1 for D >= 2; index 0 holds days 0 + 1, attributed to day 1)."""
    if D == 0:
        return {}
    return days[D - 1].get('market') or {}


class Game:
    def __init__(self, team, ep, sem, tape):
        self.team, self.ep, self.sem, self.tape = team, ep, sem, tape
        self.days = sem['days']
        self.plants = {}            # tile -> live plant (dict)
        self.all_plants = []
        self.harvests = []          # crop harvest records (batch id = index)
        self.last_harvest = {}      # tile -> harvest index of the last one-time harvest on the tile (for replant)
        self.val = Counter()
        self.miss = defaultdict(list)
        # flows
        self.inv = None
        self.shed = defaultdict(deque)          # product -> deque [bid, n]
        self.batch = {}                          # bid -> {'deliv': [(step, n)], 'sold': [(step, n)], 'fed': n}
        self.sim_sold = [Counter() for _ in range(30)]

    # ------------------------------------------------------------------ plants
    def kill(self, p, why, step):
        p['end'] = [why, step, max(0, p['y'])]
        if self.plants.get(p['tile']) is p:
            del self.plants[p['tile']]

    def decay_to(self, p, step):
        """apply the decay steps strictly before `step` (unit actions of a step come before that step's decay)."""
        if p['mls'] < 0 or p['end'] is not None:
            return
        nd = p['nd'] if p['nd'] is not None else p['mls']
        while nd < step and p['end'] is None:
            if p['y'] >= 1:
                p['decay_loss'] += 1
            p['y'] -= 1
            if p['y'] <= 0:
                self.kill(p, 'decay', nd)
            nd += 2
        p['nd'] = nd

    def new_plant(self, tile, crop, d, h):
        c = CROP[crop]
        p = {'id': len(self.all_plants), 'tile': tile, 'crop': crop, 'pd': d, 'ph': h,
             'y': 0 if c['ongoing'] else 1, 'wt': False, 'cu': 1, 'fu': -1,
             'mls': -1 if c['ongoing'] else (d + c['M'] + 1) * 24, 'nd': None, 'waters': [], 'ferts': [],
             'harv': [], 'prods': [], 'yend': {}, 'end': None, 'decay_loss': 0, 'npc': 0}
        self.plants[tile] = p
        self.all_plants.append(p)
        lh = self.last_harvest.pop(tile, None)
        if lh is not None:
            self.harvests[lh]['replant'] = [d, h, crop]
        return p

    # ------------------------------------------------------------------ flows
    def inv_add(self, u, prod, bid, n):
        q = self.inv[u][prod]
        q.append([bid, n])

    def move_units(self, src, dst, n, step=None, deliver=False):
        """FIFO move of n units from deque src to deque dst; returns moved."""
        moved = 0
        while n > 0 and src:
            b = src[0]
            k = min(n, b[1])
            dst.append([b[0], k])
            if deliver and b[0] >= 0:
                self.batch[b[0]]['deliv'].append((step, k))
            b[1] -= k
            n -= k
            moved += k
            if b[1] == 0:
                src.popleft()
        return moved

    def deliver_all(self, u, step):
        for prod, q in self.inv[u].items():
            self.move_units(q, self.shed[prod], sum(b[1] for b in q), step, deliver=True)
        self.inv[u] = defaultdict(deque)

    def sell(self, prod, n, step, d):
        q = self.shed[prod]
        while n > 0 and q:
            b = q[0]
            k = min(n, b[1])
            if b[0] >= 0:
                self.batch[b[0]]['sold'].append((step, k))
            b[1] -= k
            n -= k
            self.sim_sold[d][prod] += k
            if b[1] == 0:
                q.popleft()

    # ------------------------------------------------------------------ main
    def run(self):
        ev, mk, nh = rebuild(self.tape['actions'])
        days = self.days
        for d in range(30):
            dd = days[d]
            board = dd['board']
            # hands check
            hp = (dd.get('labour') or {}).get('hands_present')
            if hp is not None:
                self.val['hands_days'] += 1
                self.val['hands_match'] += int(hp == nh[d])
            # day-start board check (sim plants vs corpus labels)
            if d > 0:
                for t in range(100):
                    lab = board[t]
                    simc = self.plants[t]['crop'] if t in self.plants else None
                    semc = CODE2CROP.get(lab)
                    self.val['board_tiles'] += 1
                    if simc != semc:
                        self.val['board_mismatch'] += 1
                        if len(self.miss['board']) < 20:
                            self.miss['board'].append((d, t, simc, lab))
            planted_left = Counter()
            for crop, tiles in (dd.get('planted') or {}).items():
                for t in tiles:
                    planted_left[(crop, t)] += 1
            maint = dd.get('maintenance') or {}
            fert_left = Counter(maint.get('FERTILIZE') or [])
            fed_left = Counter(maint.get('FEED') or [])
            sem_water = Counter(maint.get('WATER') or [])
            sim_water = Counter()
            harv = dd.get('harvested') or {}
            sem_ctiles = Counter(t for t in harv.get('tiles', []) if board[t] in CODE2CROP)
            sem_cunits = {k: v for k, v in (harv.get('units') or {}).items() if k in CROP}
            sim_ctiles = Counter()
            sim_cunits = Counter()
            sem_dug = Counter(dd.get('dug') or [])
            cash = dd.get('cash_start')
            self.inv = [defaultdict(deque) for _ in range(nh[d] + 1)]
            by_hour = defaultdict(list)
            for e in ev[d]:
                by_hour[e[0]].append(e)
            for h in range(24):
                step = d * 24 + h
                for (_, u, op, args, (x, y)) in by_hour.get(h, ()):
                    t = y * 10 + x
                    if op == 'PLANT':
                        crop = args[0] if args else None
                        if planted_left.get((crop, t), 0) > 0:
                            if t in self.plants:
                                self.decay_to(self.plants[t], step)
                            if t in self.plants:
                                self.val['plant_on_occupied'] += 1
                                self.miss['plant_occ'].append((d, h, t, crop, self.plants[t]['crop']))
                                self.kill(self.plants[t], 'overwritten', step)
                            planted_left[(crop, t)] -= 1
                            self.new_plant(t, crop, d, h)
                            self.val['plant_tape'] += 1
                    elif op == 'WATER':
                        p = self.plants.get(t)
                        if p is not None:
                            self.decay_to(p, step)
                        p = self.plants.get(t)
                        if p is not None and not p['wt']:
                            p['wt'] = True
                            sim_water[t] += 1
                            c = CROP[p['crop']]
                            bonus = 0
                            if not c['ongoing']:
                                age = d - p['pd']
                                if (c['M'] + 1) // 2 <= age <= c['M']:
                                    bonus = 2 if p['fu'] >= d else 1
                                    p['y'] = min(c['cap'], p['y'] + bonus)
                            p['waters'].append((d, h, bonus))
                    elif op == 'FERTILIZE':
                        p = self.plants.get(t)
                        if p is not None and fert_left.get(t, 0) > 0:
                            fert_left[t] -= 1
                            p['fu'] = max(p['fu'], d + 2)
                            p['ferts'].append((d, h))
                    elif op == 'HARVEST':
                        p = self.plants.get(t)
                        if p is not None:
                            self.decay_to(p, step)
                        p = self.plants.get(t)
                        if p is None:
                            continue
                        c = CROP[p['crop']]
                        age = d - p['pd']
                        if age < c['F'] or p['y'] <= 0:
                            continue
                        units = p['y']
                        rec = {'bid': len(self.harvests), 'plant': p['id'], 'crop': p['crop'], 'tile': t,
                               'pd': p['pd'], 'd': d, 'h': h, 'u': u, 'age': age, 'units': units,
                               'wt_before': p['wt'], 'cash': cash, 'decay_loss': p['decay_loss'],
                               'fu': p['fu'], 'replant': None}
                        if c['ongoing']:
                            since = p['prods'][p['npc']:]
                            rec['prod_no'] = len(p['prods'])
                            rec['n_since'] = len(since)
                            rec['wasted_since'] = sum(x[2] for x in since)
                            rec['added_since'] = sum(x[1] for x in since)
                            p['npc'] = len(p['prods'])
                            p['y'] = 0
                        else:
                            self.kill(p, 'harvest', step)
                            p['end'][2] = 0
                            self.last_harvest[t] = rec['bid']
                        p['harv'].append((d, h, units))
                        self.harvests.append(rec)
                        self.batch[rec['bid']] = {'deliv': [], 'sold': [], 'fed': 0}
                        self.inv_add(u, p['crop'], rec['bid'], units)
                        sim_ctiles[t] += 1
                        sim_cunits[p['crop']] += units
                    elif op == 'DIG':
                        p = self.plants.get(t)
                        if p is not None:
                            self.decay_to(p, step)
                        p = self.plants.get(t)
                        if p is not None:
                            self.val['dig_plant'] += 1
                            self.val['dig_plant_sem'] += int(sem_dug.get(t, 0) > 0)
                            self.kill(p, 'dug', step)
                    elif op == 'DROP':
                        if (x, y) in SHED_SET:
                            self.deliver_all(u, step)
                    elif op == 'PLACE':
                        item = args[0] if args else None
                        if item in CROP and (x, y) in SHED_SET:
                            n = int(args[1]) if len(args) >= 2 else 1
                            q = self.inv[u][item]
                            self.move_units(q, self.shed[item], min(n, sum(b[1] for b in q)), step, deliver=True)
                    elif op == 'PICKUP':
                        item = args[0] if args else None
                        if item in CROP and (x, y) in SHED_SET:
                            n = int(args[1]) if len(args) >= 2 else 1
                            self.move_units(self.shed[item], self.inv[u][item], n)
                    elif op == 'FEED':
                        if fed_left.get(t, 0) > 0:
                            q = self.inv[u]['WHEAT']
                            if sum(b[1] for b in q) > 0:
                                fed_left[t] -= 1
                                b = q[0]
                                if b[0] >= 0:
                                    self.batch[b[0]]['fed'] += 1
                                b[1] -= 1
                                if b[1] == 0:
                                    q.popleft()
                            else:
                                self.val['feed_no_wheat_model'] += 1
                # market orders of this step (after all unit actions)
                for o in mk[d].get(h, ()):
                    if not isinstance(o, list) or len(o) < 3:
                        continue
                    try:
                        n = int(o[2])
                    except (TypeError, ValueError):
                        continue
                    if n <= 0:
                        continue
                    if o[0] == 'SELL' and o[1] in CROP:
                        self.sell(o[1], n, step, d)
                    elif o[0] == 'BUY_PRODUCT' and o[1] == 'WHEAT':
                        self.shed['WHEAT'].append([-1, n])
            # plantings in the corpus that the tape did not show on that tile (position rebuild failure)
            for (crop, t), k in planted_left.items():
                for _ in range(k):
                    self.val['plant_missing_in_tape'] += 1
                    self.miss['plant_missing'].append((d, t, crop))
                    if t in self.plants:
                        self.kill(self.plants[t], 'overwritten', d * 24)
                    self.new_plant(t, crop, d, -1)
            # end of day: decay through step d*24+23, then the refresh
            for p in list(self.plants.values()):
                self.decay_to(p, (d + 1) * 24)
            for p in list(self.plants.values()):
                c = CROP[p['crop']]
                was = p['wt']
                p['cu'] = 0 if was else p['cu'] + 1
                p['wt'] = False
                if p['cu'] >= 2:
                    self.kill(p, 'weed', (d + 1) * 24)
                    continue
                if c['ongoing']:
                    nd_ = d + 1
                    dsf = nd_ - p['pd'] - c['F']
                    if dsf >= 0 and dsf % c['I'] == 0:
                        pc = dsf // c['I'] + 1
                        if pc <= 4:
                            add = 2 if (was and p['fu'] >= d) else 1
                            new = min(c['cap'], p['y'] + add)
                            p['prods'].append((nd_, add, p['y'] + add - new, pc))
                            p['y'] = new
                            if pc == 4:
                                p['mls'] = (nd_ + 1) * 24
                p['yend'][d] = p['y']
            # midnight dump: all unit inventories reach the shed for the next day
            for u in range(len(self.inv)):
                self.deliver_all(u, (d + 1) * 24)
            # validation of the day
            self.val['water_sem'] += sum(sem_water.values())
            self.val['water_sim'] += sum(sim_water.values())
            self.val['water_common'] += sum((sem_water & sim_water).values())
            self.val['harv_tiles_sem'] += sum(sem_ctiles.values())
            self.val['harv_tiles_sim'] += sum(sim_ctiles.values())
            self.val['harv_tiles_common'] += sum((sem_ctiles & sim_ctiles).values())
            for crop in CROP:
                a, b = sem_cunits.get(crop, 0), sim_cunits.get(crop, 0)
                if a or b:
                    self.val[f'hu_days_{crop}'] += 1
                    self.val[f'hu_match_{crop}'] += int(a == b)
                    self.val[f'hu_sem_{crop}'] += a
                    self.val[f'hu_sim_{crop}'] += b
                    if a != b and len(self.miss['hunits']) < 30:
                        self.miss['hunits'].append((d, crop, a, b))
            self.val['fert_left'] += sum(v for v in fert_left.values() if v > 0)
        # plants alive at the end
        for p in list(self.plants.values()):
            self.kill(p, 'alive_end', 720)
        # sales validation (sim day D vs corpus index D-1; days 0 + 1 pooled)
        for crop in CROP:
            for D in range(1, 30):
                semu = (sem_market_day(self.days, D).get('sold_units') or {}).get(crop, 0)
                simu = self.sim_sold[D][crop] + (self.sim_sold[0][crop] if D == 1 else 0)
                if semu or simu:
                    self.val[f'sold_days_{crop}'] += 1
                    self.val[f'sold_match_{crop}'] += int(semu == simu)
                    self.val[f'sold_sem_{crop}'] += semu
                    self.val[f'sold_sim_{crop}'] += simu
                # the alternative alignment (index D) for the offset check
                semu2 = (self.days[D].get('market') or {}).get('sold_units', {}).get(crop, 0)
                if semu2 or simu:
                    self.val[f'sold_days_alt_{crop}'] += 1
                    self.val[f'sold_match_alt_{crop}'] += int(semu2 == simu)

    def records(self):
        team_name = TEAMS.get(self.team, self.team)
        hr = []
        for rec in self.harvests:
            b = self.batch[rec['bid']]
            r = dict(rec)
            r.update(team=team_name, ep=self.ep, deliv=b['deliv'], sold=b['sold'], fed=b['fed'])
            hr.append(r)
        pr = []
        for p in self.all_plants:
            pr.append({'team': team_name, 'ep': self.ep, 'id': p['id'], 'tile': p['tile'], 'crop': p['crop'],
                       'pd': p['pd'], 'ph': p['ph'], 'waters': p['waters'], 'ferts': p['ferts'], 'harv': p['harv'],
                       'prods': p['prods'], 'yend': p['yend'], 'end': p['end'], 'decay_loss': p['decay_loss']})
        dr = []
        for D in range(30):
            m = sem_market_day(self.days, D)
            dr.append({'team': team_name, 'ep': self.ep, 'd': D, 'cash': self.days[D].get('cash_start'),
                       'sold_units': {k: v for k, v in (m.get('sold_units') or {}).items()},
                       'sold_revenue': {k: v for k, v in (m.get('sold_revenue') or {}).items()},
                       'sim_sold': dict(self.sim_sold[D]),
                       'shops': [s['shop'] for s in self.sem['shops'] if s['reveal_day'] <= D]})
        return hr, pr, dr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--teams', default='')
    ap.add_argument('--tag', default='leaders')
    args = ap.parse_args()
    out = OUT / args.tag
    out.mkdir(parents=True, exist_ok=True)
    teams = [t for t in sorted(TEAMS) if not args.teams or t in args.teams.split(',')]
    fh = gzip.open(out / 'harvests.jsonl.gz', 'wt', encoding='utf-8')
    fp = gzip.open(out / 'plants.jsonl.gz', 'wt', encoding='utf-8')
    fd = gzip.open(out / 'days.jsonl.gz', 'wt', encoding='utf-8')
    val_all = Counter()
    per_game = []
    miss_examples = {}
    t0 = time.time()
    n = 0
    for team in teams:
        files = sorted((SEM / team).glob('*.json.gz'))
        for f in files:
            if args.limit and n >= args.limit:
                break
            ep = f.name.split('.')[0]
            sem = json.load(gzip.open(f, 'rt', encoding='utf-8'))
            if not sem['meta'].get('cash_match', True):
                val_all['skipped_cash_mismatch'] += 1
                continue
            tps = sorted(TAPES.glob(f'{team}_*/{ep}.json.gz'))
            if not tps:
                val_all['skipped_no_tape'] += 1
                continue
            tape = json.load(gzip.open(tps[0], 'rt', encoding='utf-8'))
            if tape['seat'] != sem['meta']['seat']:
                val_all['skipped_seat'] += 1
                continue
            g = Game(team, int(ep), sem, tape)
            g.run()
            hr, pr, dr = g.records()
            for r in hr:
                fh.write(json.dumps(r, separators=(',', ':')) + '\n')
            for r in pr:
                fp.write(json.dumps(r, separators=(',', ':')) + '\n')
            for r in dr:
                fd.write(json.dumps(r, separators=(',', ':')) + '\n')
            val_all.update(g.val)
            val_all['games'] += 1
            per_game.append({'team': TEAMS.get(team, team), 'ep': int(ep), **{k: v for k, v in g.val.items()}})
            if g.miss and len(miss_examples) < 40:
                miss_examples[f'{team}:{ep}'] = {k: v[:10] for k, v in g.miss.items()}
            n += 1
            del g, sem, tape, hr, pr, dr
        if args.limit and n >= args.limit:
            break
    fh.close()
    fp.close()
    fd.close()
    json.dump({'total': dict(val_all), 'per_game': per_game, 'miss_examples': miss_examples,
               'seconds': round(time.time() - t0, 1)}, open(out / 'validation.json', 'w'), indent=1)
    v = val_all
    print(f"games {v['games']} in {time.time() - t0:.0f}s; skipped: cash {v['skipped_cash_mismatch']} "
          f"no tape {v['skipped_no_tape']} seat {v['skipped_seat']}")
    print(f"hands per day match {v['hands_match']}/{v['hands_days']}; board tiles mismatch "
          f"{v['board_mismatch']}/{v['board_tiles']}")
    print(f"plantings via tape {v['plant_tape']}, missing in tape {v['plant_missing_in_tape']}, on occupied "
          f"{v['plant_on_occupied']}; fert effects unmatched {v['fert_left']}")
    print(f"WATER sem {v['water_sem']} sim {v['water_sim']} common {v['water_common']}")
    print(f"crop HARVEST tiles sem {v['harv_tiles_sem']} sim {v['harv_tiles_sim']} common {v['harv_tiles_common']}")
    for crop in CROP:
        print(f"  {crop}: harvested units day-match {v['hu_match_' + crop]}/{v['hu_days_' + crop]} "
              f"(units sem {v['hu_sem_' + crop]} sim {v['hu_sim_' + crop]}); sold day-match "
              f"{v['sold_match_' + crop]}/{v['sold_days_' + crop]} (units sem {v['sold_sem_' + crop]} sim "
              f"{v['sold_sim_' + crop]}); alt alignment {v['sold_match_alt_' + crop]}/{v['sold_days_alt_' + crop]}")
    print(f"digs of plants {v['dig_plant']} (in corpus dug {v['dig_plant_sem']}); feed w/o wheat in model "
          f"{v['feed_no_wheat_model']}")


if __name__ == '__main__':
    main()
