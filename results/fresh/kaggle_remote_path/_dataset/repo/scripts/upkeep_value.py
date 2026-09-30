"""Marginal value of upkeep jobs, the fertilizer shadow value by day, and a retirement rule (thread upkeep, step 2).

Stored data only: the leader asset-day records of scripts/upkeep_skips.py plus a fast exact replay of each tape (no DP)
for the shed stock at hour 0, both seats' fertilizer sales per day and the hour-0 prices.

1. FERTILIZER VALUE BY DAY (per leader game-day, days 8-28)
   crop-use value: every live crop tile at hour 0 is an opportunity; its gain g1 = product units added by ONE
   application today (engine-exact day model of sem_maintenance: today with FERTILIZE, then the best no-new-fertilizer
   plan, minus the best no-fertilizer plan; watering is re-optimized, so a fertilized production day gets its water),
   worth g1 x the hour-0 product price, minus the extra ops it needs x STEP_VALUE. Supply = fertilizer in the shed at
   hour 0 + the animals whose fertilizer is ready. Marginal crop-use value = value of the supply-th best opportunity
   (0 when opportunities < supply).
   sale value (own cash) = p(d) - 0.2 x our fertilizer units sold after day d; margin: + 0.2 x the rival's units sold
   after day d (each unit we sell lowers every later rival sale by 0.2).
   shadow value = max(marginal crop-use value, sale value).
2. JOB RULE: benefit = units lost x hour-0 price (margin: + rival slope per unit) - inputs (wheat at market; fertilizer
   at the shadow value); labour = (1 op + VISIT_STEPS if the tile has no other job today) x STEP_VALUE. Rule: do the
   job when benefit > labour. Compared with the leader's done / skipped (upkeep_skips classes, RP jobs).
3. RETIREMENT (animals): the module's day DP per animal from hour 0 of each day with the product at its hour-0 price
   (margin: + slope), the daily fertilizer at the shadow value (collect), wheat at market and VISIT_COST per visit;
   the rule retires the animal on the first day the optimal plan stops feeding it for good. Compared with the leader's
   last feed day (animal lives from the records).

usage: upkeep_value.py [teams=...] [--limit N] > results/fresh/upkeep_20260925/value_report.txt
"""
import gzip
import json
import statistics as stt
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import upkeep_engine as UE  # noqa: E402

SK = ROOT / 'results/fresh/upkeep_20260925/skips'
OUT = ROOT / 'results/fresh/upkeep_20260925'
TEAM = {'16732748': 'DSM', '16770421': 'Vadim', '16730612': 'UMG'}
BASE = {'WHEAT': 25, 'CARROT': 35, 'TOMATO': 60, 'STRAWBERRY': 120, 'MELON': 250, 'EGG': 50, 'MILK': 160, 'WOOL': 200,
        'FERTILIZER': 100}
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
# rival revenue gained per unit we withhold (docs/lead_agent_progress.md, 185 p2750 worlds; by season third)
RIVAL = {'MILK': (1, 91, 100), 'WOOL': (3, 85, 18), 'MELON': (0, 83, 7), 'STRAWBERRY': (0, 34, 43), 'TOMATO': (0, 0, 19),
         'FERTILIZER': (6, 21, 13), 'WHEAT': (7, 1, 10), 'CARROT': (0, 0, 12), 'EGG': (2, 2, 3)}
STEP_VALUE = 10.0          # coins per unit-step at the margin (fib wage of the 12th-13th hand / ~22 steps: 6.5-10.6)
VISIT_STEPS = 1.0          # extra walking for a tile with no other job that day (leader: 0.6 moves between consecutive ops)


def rival(prod, d):
    return RIVAL.get(prod, (0, 0, 0))[0 if d <= 9 else 1 if d <= 19 else 2]


def load_sm():
    ns = {}
    exec(compile((ROOT / 'scripts/fragments/sem_maintenance.py').read_text(encoding='utf-8'), 'sem_maintenance', 'exec'), ns)
    return ns


SM = load_sm()


def replay_facts(team, ep):
    """hour-0 shed / prices per day, fertilizer sales per day for both seats (exact replay, no DP)."""
    E = UE.engine()
    tape = UE.load_tape(team, ep)
    seat = tape['seat']
    w = UE.World(tape['seed'], tape['shops'])
    farms = w.farms
    sales = [[Counter() for _ in range(31)] for _ in range(2)]
    oc = E._commit_unit

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        ok = oc(op, item, price, farm, private, market, shed_capacity)
        if ok and op == 'SELL' and item == 'FERTILIZER':
            s = 0 if farm is farms[0] else 1
            sales[s][min(30, w.t // 24)]['n'] += 1
        return ok
    E._commit_unit = commit_hook
    shed0, price0 = [], []
    try:
        while w.t < 719:
            t = w.t
            if t % 24 == 0:
                shed0.append(dict(w.private(seat)['shed']))
                price0.append(dict(w.market['prices']))
            a = [None, None]
            a[seat] = UE.tape_action(tape['actions'], t)
            a[1 - seat] = UE.tape_action(tape['opp_actions'], t)
            w.step(a)
    finally:
        E._commit_unit = oc
    own = [sales[seat][d]['n'] for d in range(30)]
    opp = [sales[1 - seat][d]['n'] for d in range(30)]
    return dict(shed0=shed0, price0=price0, fert_sold_own=own, fert_sold_opp=opp, seat=seat)


def g1_fert(kind, st, d):
    """(units added by one fertilizer today, extra ops of that plan) - engine-exact day model, inputs free."""
    if d > SM['SM_LAST_REFRESH_DAY']:
        return 0, 0
    S0 = SM['_sm_solver'](kind, False, 0, 0, 0)
    base = S0.today(st, d, 0)
    if base is None:
        return 0, 0
    b_units, b_turns = base[0][1], -base[0][3]
    best = None
    cd = SM['SM_CROPS'][kind]
    can_h = st[2] > 0 and d - st[0] >= cd['first_yield_day']
    for w_ in ((0, 1) if not st[5] else (0,)):
        for h in ((0, 1) if can_h else (0,)):
            st2, u = SM['_sm_crop_day'](kind, st, d, w_, 1, h, 0, 0)
            fut = S0.value(st2, d + 1)[0]
            tot = (u + fut[1], w_ + 1 + h - fut[3])
            if best is None or tot[0] > best[0] or (tot[0] == best[0] and tot[1] < best[1]):
                best = tot
    return max(0, best[0] - b_units), max(0, best[1] - b_turns)


def fert_days(rec, facts):
    """per day: opportunities, supply, marginal crop-use value, sale values, shadow."""
    by_day = defaultdict(list)
    anim_ready = Counter()
    for a in rec['assets']:
        d = a['d']
        if a['k'] in PROD:
            anim_ready[d] += a.get('fa', 0)
            continue
        if not (8 <= d <= 28):
            continue
        st = tuple(a['st'])
        if st[3] >= d + 1:            # already fertilized through tomorrow: a new application adds (almost) nothing
            pass
        g, extra = g1_fert(a['k'], st, d)
        if g > 0:
            lab = max(0, extra - 1) * STEP_VALUE          # extra ops beyond the FERTILIZE itself (charged in the job rule)
            val = g * float(a['p'] or 0) - lab
            val_m = g * (float(a['p'] or 0) + rival(a['k'], d)) - lab
            by_day[d].append((val, g, a['k'], val_m))
    out = {}
    own, opp = facts['fert_sold_own'], facts['fert_sold_opp']
    for d in range(8, 29):
        opps = sorted(by_day.get(d, []), reverse=True)
        supply = int(facts['shed0'][d].get('FERTILIZER', 0)) + anim_ready[d]

        def marginal(vals):
            vals = sorted(vals, reverse=True)
            if not vals:
                return 0.0
            if supply <= 0:
                return vals[0]
            return vals[supply - 1] if supply <= len(vals) else 0.0
        crop_v = marginal([o[0] for o in opps])
        crop_vm = marginal([o[3] for o in opps])
        p = float(facts['price0'][d].get('FERTILIZER', 100))
        own_after = sum(own[d + 1:])
        opp_after = sum(opp[d + 1:])
        sale_own = p - 0.2 * own_after
        sale_margin = sale_own + 0.2 * opp_after
        out[d] = dict(n_opp=len(opps), supply=supply, crop_v=crop_v, best=opps[0][0] if opps else 0.0,
                      p=p, sale_own=sale_own, sale_margin=sale_margin, shadow_own=max(crop_v, sale_own),
                      crop_vm=crop_vm, shadow_margin=max(crop_vm, sale_margin), own_after=own_after, opp_after=opp_after,
                      opp_by_crop=Counter(o[2] for o in opps))
    return out


def job_rule(rec, fd, margin):
    """per RP job: (class key, leader done, rule do, benefit, labour)."""
    rows = []
    for a in rec['assets']:
        d = a['d']
        if not (12 <= d <= 28):
            continue
        kind = a['k']
        prod = PROD.get(kind, kind)
        p = float(a['p'] or 0)
        ops = {o[0] for o in a['ops']}
        mj = [j for j in a['mj'] if not j[5]]
        n_jobs_tile = len(mj)
        shadow = (fd.get(d) or {}).get('shadow_margin' if margin else 'shadow_own', None)
        fert_p = (fd.get(d) or {}).get('p', 100.0)
        for cmd, val, u, jk, dl, opt, held in mj:
            if cmd == 'COLLECT_FERTILIZER' or u <= 0:
                continue
            unit_v = p + (rival(prod, d) if margin else 0.0)
            if cmd == 'FERTILIZE':
                ben = u * unit_v - (shadow if shadow is not None else fert_p)
            elif cmd == 'FEED':
                # module value = u x p - wheat at market: keep its input term, re-price the units
                ben = u * unit_v - max(0.0, u * p - val)
            else:
                ben = u * unit_v
            steps = 1.0 + (VISIT_STEPS if n_jobs_tile <= 1 else 0.0)
            lab = steps * STEP_VALUE
            grp = kind if kind in PROD else 'crop:' + kind
            rows.append(((grp, cmd, jk), cmd in ops, ben > lab, ben, steps, d))
    return rows


STEP_GRID = (0, 10, 20, 40, 80)


def animal_lives(rec):
    """per animal life from the asset-day records: days fed, last feed day, end day, escape."""
    lives = {}
    for a in rec['assets']:
        if a['k'] not in PROD:
            continue
        key = (a['i'], a['k'], a['s'])
        L = lives.setdefault(key, dict(tile=a['i'], sp=a['k'], start=a['s'], days=[], fed=[], recs=[]))
        L['days'].append(a['d'])
        L['recs'].append(a)
        if any(o[0] == 'FEED' for o in a['ops']):
            L['fed'].append(a['d'])
    return list(lives.values())


def retire_day(L, fd, margin, visit_cost):
    """first day d >= 12 where the DP (collect at the shadow value) plans no further feeding."""
    for a in L['recs']:
        d = a['d']
        if d < 12 or d > 26:
            continue
        kind = a['k']
        prod = PROD[kind]
        f = fd.get(min(28, d)) or {}
        fert_v = f.get('shadow_margin' if margin else 'shadow_own', f.get('p', 50.0))
        p = float(a['p'] or 0) + (rival(prod, d) if margin else 0.0)
        wheat_p = float(f.get('wheat', 30.0))
        st = tuple(a['st'])
        r = SM['sm_tile_plan'](kind, st, d, 0, max(1.0, p), wheat_p, False, 8, visit_cost,
                               collect_price=max(0.0, fert_v), avail=bool(a.get('fa')))
        combo = r.get('combo')
        feeds_today = bool(combo and combo[0])
        # the plan keeps the animal if it feeds today or its future plan is productive / kept for fertilizer
        keep = feeds_today or r.get('kept_for_fertilizer') or (r.get('units', 0) > r.get('held', 0))
        if not keep:
            return d
    return None


def main():
    args = dict(a.split('=') for a in sys.argv[1:] if '=' in a)
    teams = args.get('teams', '16732748,16770421,16730612').split(',')
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    files = [f for f in sorted(SK.glob('*.json.gz')) if f.name.split('_')[0] in teams]
    if limit:
        files = files[:limit]
    t0 = time.time()
    fert_rows = defaultdict(list)
    rule_rows = {False: defaultdict(lambda: Counter()), True: defaultdict(lambda: Counter())}
    grid = defaultdict(Counter)
    ret = defaultdict(list)
    n = 0
    per_game_fd = {}
    for f in files:
        rec = json.load(gzip.open(f, 'rt', encoding='utf-8'))
        if not rec.get('cash_match'):
            continue
        SM['_SM_SOLVERS'].clear()
        SM['_SM_PLAN_CACHE'].clear()
        team, ep = rec['team'], rec['episode']
        facts = replay_facts(team, ep)
        fd = fert_days(rec, facts)
        for d, x in fd.items():
            x['wheat'] = float(facts['price0'][d].get('WHEAT', 30))
            fert_rows[d].append(x)
        per_game_fd[f'{team}:{ep}'] = {d: {k: v for k, v in x.items() if k != 'opp_by_crop'} for d, x in fd.items()}
        for margin in (False, True):
            for key, done, do, ben, steps, d in job_rule(rec, fd, margin):
                for sv in STEP_GRID:
                    g = grid[(margin, sv)]
                    rdo = ben > steps * sv
                    g['n'] += 1
                    g['leader_skip'] += int(not done)
                    g['rule_skip'] += int(not rdo)
                    g['both_skip'] += int((not done) and (not rdo))
                    g['agree'] += int(done == rdo)
                c = rule_rows[margin][key]
                c['n'] += 1
                c['leader_do'] += int(done)
                c['rule_do'] += int(do)
                c['agree'] += int(done == do)
                c['both_skip'] += int((not done) and (not do))
                c['rule_skip_leader_do'] += int(do is False and done)
                c['rule_do_leader_skip'] += int(do and not done)
        for L in animal_lives(rec):
            last_feed = max(L['fed']) if L['fed'] else None
            end = max(L['days'])
            if L['start'] > 22 or end < 12:
                continue
            # leader retirement = stopped feeding with >= 3 days left (as scripts/lead_retirement.py): stop day 12..26
            leader_stop = (last_feed + 1) if (last_feed is not None and last_feed <= 25 and last_feed < end) else None
            if leader_stop is not None and leader_stop < 12:
                continue
            row = dict(sp=L['sp'], start=L['start'], leader_stop=leader_stop, end=end)
            for name, margin, vc in (('own_v0', False, 0.0), ('own_v15', False, 15.0), ('own_v30', False, 30.0),
                                     ('margin_v15', True, 15.0)):
                row[name] = retire_day(L, fd, margin, vc)
            ret[L['sp']].append(row)
        n += 1
        if n % 25 == 0:
            print(f'# {n} games {time.time() - t0:.0f}s', file=sys.stderr, flush=True)
    (OUT / 'fert_value_by_game_day.json').write_text(json.dumps(per_game_fd, separators=(',', ':')), encoding='utf-8')
    print(f'Marginal value model (thread upkeep, step 2): {n} leader games (teams {teams}); STEP_VALUE {STEP_VALUE}, VISIT_STEPS {VISIT_STEPS}')
    print()
    print('== 1. Fertilizer value by day (medians over leader games; coins per unit)')
    print('| day | fert price | own units sold after d | rival units sold after d | sale value own | sale value margin | crop opportunities (g1>0) | supply (shed + ready animals) | best crop use | marginal crop use (own / margin) | shadow own | shadow margin | share of games crop use > sale (own) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for d in range(8, 29):
        L = fert_rows.get(d, [])
        if not L:
            continue
        m = lambda k: stt.median(x[k] for x in L)
        share = sum(1 for x in L if x['crop_v'] > x['sale_own']) / len(L)
        print(f"| {d} | {m('p'):.0f} | {m('own_after'):.0f} | {m('opp_after'):.0f} | {m('sale_own'):.0f} | {m('sale_margin'):.0f} | {m('n_opp'):.0f} | {m('supply'):.0f} | "
              f"{m('best'):.0f} | {m('crop_v'):.0f} / {m('crop_vm'):.0f} | {m('shadow_own'):.0f} | {m('shadow_margin'):.0f} | {share:.0%} |")
    tot = Counter()
    for d, L in fert_rows.items():
        for x in L:
            tot.update(x['opp_by_crop'])
    print('  opportunities by crop (all game-days 8-28, per game): ' + ', '.join(f'{k} {v / max(1, n):.0f}' for k, v in tot.most_common()))
    print()
    print('== 2. Job rule (do when benefit > steps x step value) vs the leader, all production-affecting jobs, days 12-28')
    print('| benefit | step value | rule skips | leader skips | both skip | agreement | share of leader skips the rule also skips | share of rule skips the leader also skips |')
    print('|---|---|---|---|---|---|---|---|')
    for margin in (False, True):
        for sv in STEP_GRID:
            g = grid[(margin, sv)]
            if not g['n']:
                continue
            print(f"| {'margin' if margin else 'own'} | {sv} | {g['rule_skip'] / g['n']:.1%} | {g['leader_skip'] / g['n']:.1%} | {g['both_skip'] / g['n']:.1%} | "
                  f"{g['agree'] / g['n']:.1%} | {g['both_skip'] / max(1, g['leader_skip']):.0%} | {g['both_skip'] / max(1, g['rule_skip']):.0%} |")
    print(f'(per-class tables below at step value {STEP_VALUE})')
    print()
    for margin in (False, True):
        print(f"== 2{'b' if margin else 'a'}. Job rule vs the leader ({'margin: + rival slope per unit' if margin else 'own cash'}; RP jobs, days 12-28)")
        print('| asset | cmd | job kind | jobs / game | leader does | rule does | agreement | both skip | rule skips, leader does | rule does, leader skips |')
        print('|---|---|---|---|---|---|---|---|---|---|')
        R = rule_rows[margin]
        for key in sorted(R, key=lambda k: -R[k]['n']):
            c = R[key]
            if c['n'] < n:
                continue
            print(f"| {key[0]} | {key[1]} | {key[2]} | {c['n'] / n:.1f} | {c['leader_do'] / c['n']:.0%} | {c['rule_do'] / c['n']:.0%} | {c['agree'] / c['n']:.0%} | "
                  f"{c['both_skip'] / n:.1f} | {c['rule_skip_leader_do'] / n:.1f} | {c['rule_do_leader_skip'] / n:.1f} |")
        print()
    print('== 3. Retirement: leader stop day (last feed + 1, stopped before day 27) vs the rule (first day the DP plan stops feeding)')
    print('| species | lives | leader retires | rule variant | rule retires | both retire | |rule - leader| days (median, both) | rule retires, leader feeds on | leader retires, rule keeps |')
    print('|---|---|---|---|---|---|---|---|---|')
    for sp in ('COW', 'SHEEP', 'GOOSE'):
        L = ret.get(sp, [])
        if not L:
            continue
        nl = sum(1 for x in L if x['leader_stop'] is not None)
        for name in ('own_v0', 'own_v15', 'own_v30', 'margin_v15'):
            nr = sum(1 for x in L if x[name] is not None)
            both = [x for x in L if x['leader_stop'] is not None and x[name] is not None]
            dd = [abs(x[name] - x['leader_stop']) for x in both]
            r_only = sum(1 for x in L if x[name] is not None and x['leader_stop'] is None)
            l_only = sum(1 for x in L if x[name] is None and x['leader_stop'] is not None)
            print(f"| {sp} | {len(L) / n:.2f}/game | {nl / n:.2f} | {name} | {nr / n:.2f} | {len(both) / n:.2f} | {(stt.median(dd) if dd else float('nan')):.0f} | {r_only / n:.2f} | {l_only / n:.2f} |")
    print(f'# {time.time() - t0:.0f}s', file=sys.stderr)


if __name__ == '__main__':
    main()
