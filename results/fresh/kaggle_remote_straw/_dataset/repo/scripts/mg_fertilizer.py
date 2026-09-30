"""Mother-Goose's fertilizer economy, read off her 30 recorded replays.

Where her fertilizer comes from (animal collection / market buys), when she spends it (crop, plant
age, hour), and what each application is worth (marginal units the engine would not have produced
without it, priced against what the fertilizer would have sold for).

The engine rules this leans on (kaggle_environments .../kaggriculture.py):
  * one-time crops start at yield_units = 1; each watered day with window_start <= age <= max_yield_day
    adds +1, or +2 when fertilized_until_day >= day, capped at max_yield;
    window_start = (max_yield_day + 1) // 2.
  * ongoing crops produce at END of day: days_since = (day+1) - planted_day - first_yield_day, a
    production when days_since >= 0 and days_since % interval == 0 and count <= max_yield;
    +2 when watered AND fertilized that day, else +1, capped at max_yield held on the tile.
  * FERTILIZE takes 1 FERTILIZER from the ACTING UNIT's inventory and sets
    fertilized_until_day = max(old, day + 2)  -> covers day, day+1, day+2.
  * COLLECT_FERTILIZER needs tile['fertilizer_available']; every fed animal offers exactly 1 per day.
  * BUY_PRODUCT FERTILIZER lands in the SHED, so it needs a PICKUP before it can be applied.

Usage: python mg_fertilizer.py        (from scripts/)
Output: results/fresh/mg_executor/fertilizer.json
"""
from collections import Counter, defaultdict
import json
import sys

from market_corpus import ROOT
from tape_vs_bench import mg_games

OUT = ROOT / 'results/fresh/mg_executor'
OURS = ROOT / 'results/fresh/labour_idle'

CROPS = {
    'WHEAT':      dict(seed=10, first_yield_day=2, max_yield_day=4, interval=0, max_yield=6, ongoing=False),
    'CARROT':     dict(seed=20, first_yield_day=2, max_yield_day=3, interval=0, max_yield=4, ongoing=False),
    'TOMATO':     dict(seed=50, first_yield_day=8, max_yield_day=8, interval=1, max_yield=4, ongoing=True),
    'STRAWBERRY': dict(seed=100, first_yield_day=10, max_yield_day=10, interval=2, max_yield=4, ongoing=True),
    'MELON':      dict(seed=80, first_yield_day=10, max_yield_day=12, interval=0, max_yield=6, ongoing=False),
}


def window_days(crop):
    """Ages at which a watering adds yield (one-time crops) or a production fires (ongoing)."""
    cd = CROPS[crop]
    if not cd['ongoing']:
        start = (cd['max_yield_day'] + 1) // 2
        return list(range(start, cd['max_yield_day'] + 1))
    # end-of-day production on day d needs (d+1) - planted - first >= 0, % interval == 0
    out, k = [], 0
    age = cd['first_yield_day'] - 1
    while k < cd['max_yield']:
        out.append(age)
        age += cd['interval']
        k += 1
    return out


WINDOW = {c: window_days(c) for c in CROPS}
# Ceiling reachable with perfect watering and no fertilizer at all.
UNFERT_MAX = {c: (min(CROPS[c]['max_yield'], 1 + len(WINDOW[c])) if not CROPS[c]['ongoing']
                  else CROPS[c]['max_yield']) for c in CROPS}


def simulate(crop, planted_day, day_info, last_day):
    """Replay one plant's observed day log twice: as it happened, and with the fertilizer removed.
    day_info[day] = dict(watered=bool, fert=bool, harvest=bool). Returns (produced, banked) pairs."""
    cd = CROPS[crop]
    win = set(WINDOW[crop])
    cap, cap_cf = cd['max_yield'], (cd['max_yield'] if cd['ongoing'] else UNFERT_MAX[crop])
    y = 1 if not cd['ongoing'] else 0
    y_cf = 1 if not cd['ongoing'] else 0
    prod, prod_cf = y, y_cf
    bank, bank_cf = 0, 0
    per_day = {}
    for day in range(planted_day, last_day + 1):
        age = day - planted_day
        info = day_info.get(day) or {}
        watered, fert = bool(info.get('watered')), bool(info.get('fert'))
        gain = 0
        if not cd['ongoing']:
            if age in win and watered:
                b = 2 if fert else 1
                gain = min(cap, y + b) - y
                y += gain
                prod += gain
                g = min(cap_cf, y_cf + 1) - y_cf
                y_cf += g
                prod_cf += g
        if info.get('harvest'):
            bank += y
            bank_cf += y_cf
            if not cd['ongoing']:
                per_day[day] = gain
                break  # one-time harvest removes the tile
            y, y_cf = 0, 0
        if cd['ongoing'] and age in win:
            # Production is unconditional on a scheduled day; watering only gates the bonus.
            b = 2 if (fert and watered) else 1
            gain = min(cap, y + b) - y
            y += gain
            prod += gain
            g = min(cap_cf, y_cf + 1) - y_cf
            y_cf += g
            prod_cf += g
        per_day[day] = gain
    return dict(produced=prod, banked=bank, produced_cf=prod_cf, banked_cf=bank_cf,
                left=y, left_cf=y_cf, per_day=per_day)


def analyse(path, eid, seat):
    steps = json.load(open(path, encoding='utf-8'))['steps']
    plants = {}           # (x, y, planted_day, crop) -> record
    apps = []             # every FERTILIZE command
    collects = []         # every COLLECT_FERTILIZER command
    pickups = []          # PICKUP FERTILIZER from shed
    buys, sells = [], []  # market orders
    stock_series = []
    leaks = []
    day_src = defaultdict(lambda: Counter())
    last_collect = {}     # unit index -> step
    last_pickup = {}
    prev_stock = None

    for t in range(719):
        obs = steps[t][seat]['observation']
        day, hour = obs['day'], obs['hour']
        farm = obs['farms'][seat]
        tiles = farm['tiles']
        priv = obs['private']
        invs = priv['inventories']
        pos = [tuple(farm['farmer'])] + [tuple(h) for h in farm['hands']]
        price_f = obs['market']['prices'].get('FERTILIZER', 0)

        stock = priv['shed'].get('FERTILIZER', 0) + sum(i.get('FERTILIZER', 0) for i in invs)
        stock_series.append(stock)

        act = steps[t + 1][seat].get('action') or {}
        ops = [act.get('farmer')] + list(act.get('hands') or [])

        # ---- plant bookkeeping (before the unit loop, so records exist) --------
        for yy in range(len(tiles)):
            row = tiles[yy]
            for xx in range(len(row)):
                tile = row[xx]
                if not (isinstance(tile, dict) and tile.get('kind') == 'PLANT'):
                    continue
                key = (xx, yy, tile['planted_day'], tile['crop'])
                if key not in plants:
                    plants[key] = dict(x=xx, y=yy, crop=tile['crop'], planted_day=tile['planted_day'],
                                       days={}, first_step=t, last_day=day, apps=[],
                                       seen_yield={}, harvest_prices={})
                p = plants[key]
                p['last_day'] = day
                di = p['days'].setdefault(day, dict(watered=False, fert=False, harvest=False))
                if tile.get('watered_today'):
                    di['watered'] = True
                if tile.get('fertilized_until_day', -1) >= day:
                    di['fert'] = True
                p['seen_yield'][day] = max(p['seen_yield'].get(day, 0), tile.get('yield_units', 0))

        taken = set()
        n_collect_ok = n_fert_ok = 0
        shed_fert = priv['shed'].get('FERTILIZER', 0)   # running, as unit actions touch it
        for u, op in enumerate(ops):
            if not op or u >= len(pos):
                continue
            x, y = pos[u]
            tile = tiles[y][x]
            name = op[0]
            inv_f = invs[u].get('FERTILIZER', 0) if u < len(invs) else 0
            pl = None
            if isinstance(tile, dict) and tile.get('kind') == 'PLANT':
                pl = plants.get((x, y, tile['planted_day'], tile['crop']))
            if name == 'WATER' and pl is not None and not tile.get('watered_today'):
                pl['days'].setdefault(day, dict(watered=False, fert=False, harvest=False))['watered'] = True
            elif name == 'HARVEST' and pl is not None and tile.get('yield_units', 0) > 0 \
                    and day - tile['planted_day'] >= CROPS[tile['crop']]['first_yield_day']:
                pl['days'].setdefault(day, dict(watered=False, fert=False, harvest=False))['harvest'] = True
                pl['harvest_prices'][day] = obs['market']['prices'].get(tile['crop'], 0)
            if name == 'COLLECT_FERTILIZER':
                ok = (isinstance(tile, dict) and 'animal' in tile
                      and tile.get('fertilizer_available') and (x, y) not in taken)
                if ok:
                    taken.add((x, y))
                    n_collect_ok += 1
                    last_collect[u] = t
                collects.append(dict(step=t, day=day, hour=hour, unit=u, x=x, y=y, ok=bool(ok),
                                     animal=(tile.get('animal') if isinstance(tile, dict) else None)))
            elif name == 'PICKUP' and len(op) > 1 and op[1] == 'FERTILIZER':
                n = min(int(op[2]) if len(op) > 2 else 1, shed_fert)
                shed_fert -= n
                if n > 0:
                    last_pickup[u] = t
                pickups.append(dict(step=t, day=day, hour=hour, unit=u, n=n))
            elif name == 'PLACE' and len(op) > 1 and op[1] == 'FERTILIZER':
                shed_fert += min(int(op[2]) if len(op) > 2 else 1, inv_f)
            elif name == 'FERTILIZE':
                ok = isinstance(tile, dict) and tile.get('kind') == 'PLANT' and inv_f >= 1
                rec = dict(step=t, day=day, hour=hour, unit=u, x=x, y=y, ok=bool(ok),
                           fert_price=price_f,
                           crop=(tile.get('crop') if isinstance(tile, dict) else None),
                           age=(day - tile['planted_day']) if (isinstance(tile, dict) and tile.get('kind') == 'PLANT') else None,
                           already=(tile.get('fertilized_until_day', -1) >= day) if isinstance(tile, dict) else None,
                           since_collect=(t - last_collect[u]) if u in last_collect else None,
                           since_pickup=(t - last_pickup[u]) if u in last_pickup else None,
                           key=None)
                if ok:
                    n_fert_ok += 1
                    rec['key'] = [x, y, tile['planted_day'], tile['crop']]
                    if pl is not None:
                        pl['apps'].append(len(apps))
                        for d2 in (day, day + 1, day + 2):
                            pl['days'].setdefault(d2, dict(watered=False, fert=False, harvest=False))['fert'] = True
                apps.append(rec)

        # Sales are capped by what is actually in the shed when the order runs, which the queue
        # order decides; buys land in the shed and are only limited by money / shed room, which
        # conservation on the total held then pins down exactly.
        req_buy = req_sell = got_sell = 0
        avail = shed_fert
        for order in (act.get('market') or [])[:10]:
            if not isinstance(order, list) or len(order) < 3 or order[1] != 'FERTILIZER':
                continue
            n = int(order[2])
            if order[0] == 'BUY_PRODUCT':
                req_buy += n
                avail += n          # optimistic: a later SELL could resell what was just bought
            elif order[0] == 'SELL':
                req_sell += n
                s = max(0, min(n, avail))
                got_sell += s
                avail -= s

        nxt = steps[t + 1][seat]['observation']
        npriv = nxt['private']
        nstock = npriv['shed'].get('FERTILIZER', 0) + sum(i.get('FERTILIZER', 0) for i in npriv['inventories'])
        flow = nstock - stock - n_collect_ok + n_fert_ok
        got_buy = max(0, min(req_buy, flow + got_sell))
        got_sell = min(got_sell, max(0, got_buy - flow))
        if req_buy:
            buys.append(dict(step=t, day=day, hour=hour, req=req_buy, got=got_buy, price=price_f))
        if req_sell:
            sells.append(dict(step=t, day=day, hour=hour, req=req_sell, got=got_sell, price=price_f))
        if not req_buy and not req_sell and flow:
            leaks.append([t, hour, flow])
        d = day_src[day]
        d['collect_try'] += sum(1 for o in ops if o and o[0] == 'COLLECT_FERTILIZER')
        d['collect_ok'] += n_collect_ok
        d['apply_try'] += sum(1 for o in ops if o and o[0] == 'FERTILIZE')
        d['apply_ok'] += n_fert_ok
        d['buy_req'] += req_buy
        d['buy_got'] += got_buy
        d['sell_req'] += req_sell
        d['sell_got'] += got_sell

    # ---- per plant: what the fertilizer bought ---------------------------------
    plant_out = []
    for key, p in plants.items():
        sim = simulate(p['crop'], p['planted_day'], p['days'], p['last_day'] + 1)
        n_app = len(p['apps'])
        marg_prod = sim['produced'] - sim['produced_cf']
        marg_bank = sim['banked'] - sim['banked_cf']
        px = (sum(p['harvest_prices'].values()) / len(p['harvest_prices'])) if p['harvest_prices'] else 0
        obs_bank = sum(p['seen_yield'].get(d, 0) for d, v in p['days'].items() if v['harvest'])
        rec = dict(key=list(key), crop=p['crop'], planted_day=p['planted_day'], n_apps=n_app,
                   observed_banked=obs_bank, sim_ok=(obs_bank == sim['banked']),
                   produced=sim['produced'], banked=sim['banked'],
                   produced_cf=sim['produced_cf'], banked_cf=sim['banked_cf'],
                   marginal_produced=marg_prod, marginal_banked=marg_bank,
                   water_days=sorted(d for d, v in p['days'].items() if v['watered']),
                   harvest_days=sorted(d for d, v in p['days'].items() if v['harvest']),
                   mean_harvest_price=round(px, 1), apps=p['apps'])
        plant_out.append(rec)
        for ai in p['apps']:
            apps[ai]['plant_marginal_produced'] = marg_prod
            apps[ai]['plant_marginal_banked'] = marg_bank
            apps[ai]['plant_apps'] = n_app
            apps[ai]['plant_produced'] = sim['produced']
            apps[ai]['plant_price'] = round(px, 1)
            apps[ai]['share_marginal'] = marg_bank / n_app if n_app else 0
            apps[ai]['share_value'] = (marg_bank / n_app) * px if n_app else 0

    # window / production context per application
    for a in apps:
        if not a['ok'] or a['crop'] is None:
            continue
        crop, age = a['crop'], a['age']
        cd, win = CROPS[crop], WINDOW[crop]
        pk = tuple(a['key'])
        p = plants.get(pk)
        covered = [w for w in win if age <= w <= age + 2]
        a['window'] = win
        a['covered_window_ages'] = covered
        if p:
            wd = sorted(d - p['planted_day'] for d, v in p['days'].items() if v['watered'])
            a['covered_watered_ages'] = [w for w in covered if w in wd]
            a['window_ages_remaining'] = [w for w in win if w >= age]
        if cd['ongoing']:
            a['productions_ahead'] = len([w for w in win if w >= age])
            a['productions_coverable'] = len(covered)
        else:
            a['in_window'] = age in win
            a['window_days_remaining'] = len([w for w in win if w >= age])

    ok_apps = [a for a in apps if a['ok']]
    out = dict(
        episode=eid, seat=seat,
        final_money=steps[-1][seat]['observation']['farms'][seat]['money'],
        n_apply_try=len(apps), n_apply_ok=len(ok_apps),
        n_collect_try=len(collects), n_collect_ok=sum(1 for c in collects if c['ok']),
        collect_by_animal=dict(Counter(c['animal'] for c in collects if c['ok'])),
        buy_req=sum(b['req'] for b in buys), buy_got=sum(b['got'] for b in buys),
        resid=sum(1 for b in buys if b['got'] < b['req']),
        buy_spend=sum(b['got'] * b['price'] for b in buys),
        sell_req=sum(s['req'] for s in sells), sell_got=sum(s['got'] for s in sells),
        sell_revenue=sum(s['got'] * s['price'] for s in sells),
        sim_mismatch=sum(1 for p in plant_out if not p['sim_ok'] and p['harvest_days']),
        n_plants=len(plant_out),
        apps=apps, collects=collects, pickups=pickups, buys=buys, sells=sells,
        plants=plant_out,
        by_day={str(d): dict(v) for d, v in sorted(day_src.items())},
        stock_max=max(stock_series), stock_end=stock_series[-1], leaks=leaks,
    )
    return out


CODE = {'WH': 'WHEAT', 'CA': 'CARROT', 'TO': 'TOMATO', 'ST': 'STRAWBERRY', 'ME': 'MELON'}


def ours():
    """Our benchmark's applications, from the recorded unit ops + day-start boards.
    The tapes carry no inventories, so this measures placement only: crop, age at application, and
    how many yield-window days (and watered ones) the 3-day window it opens actually covers."""
    rows = []
    for f in sorted(OURS.glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        boards = d['boards']
        # pass 1: plant instances per tile (a PLANT op opens one), and the days each was watered
        planted = {}     # (x, y) -> most recent PLANT day
        instance = {}    # (x, y, planted_day) -> dict(crop, waters=set())
        raw = []
        collects = []
        for t, units in enumerate(d['units']):
            day = t // 24
            for (x, y, op) in units:
                if op == 'PLANT':
                    planted[(x, y)] = day
                    instance[(x, y, day)] = dict(crop=None, waters=set())
                    continue
                pd = planted.get((x, y))
                inst = instance.get((x, y, pd)) if pd is not None else None
                if op == 'WATER' and inst is not None:
                    inst['waters'].add(day)
                    if inst['crop'] is None and day + 1 < len(boards):
                        inst['crop'] = CODE.get(boards[day + 1][y][x])
                elif op == 'COLLECT_FERTILIZER':
                    collects.append(dict(step=t, day=day, hour=t % 24))
                elif op == 'FERTILIZE':
                    code = boards[day][y][x] if day < len(boards) else None
                    raw.append((t, day, x, y, pd, CODE.get(code)))
        # pass 2: score each application against the window it opens
        apps = []
        for t, day, x, y, pd, crop in raw:
            inst = instance.get((x, y, pd)) or dict(crop=crop, waters=set())
            crop = crop or inst['crop']
            age = (day - pd) if pd is not None else None
            win = WINDOW.get(crop, [])
            cov = [w for w in win if age is not None and age <= w <= age + 2]
            cw = [w for w in cov if pd is not None and pd + w in inst['waters']]
            apps.append(dict(step=t, day=day, hour=t % 24, x=x, y=y, crop=crop, age=age,
                             covered=len(cov), covered_ages=cov, covered_watered=len(cw),
                             remaining=len([w for w in win if age is not None and w >= age])))
        nfert = Counter()
        for _, _, x, y, pd, _ in raw:
            nfert[(x, y, pd)] += 1
        for (x, y, pd), inst in instance.items():
            if inst['crop'] is None and pd + 1 < len(boards):
                inst['crop'] = CODE.get(boards[pd + 1][y][x])
        rows.append(dict(episode=d['episode'], seat=d['seat'], final=d['final'],
                         n_apply=len(apps), n_collect=len(collects), apps=apps,
                         by_crop=dict(Counter(a['crop'] for a in apps)),
                         by_crop_age=dict(Counter(f"{a['crop']}@{a['age']}" for a in apps)),
                         plants_by_crop=dict(Counter(i['crop'] for i in instance.values())),
                         fert_plants_by_crop=dict(Counter(
                             inst['crop'] for k, inst in instance.items() if nfert.get(k)))))
    return rows


def report(data):
    """Console tables + a machine-readable summary block."""
    G, O = data['games'], data['ours']
    n, m = len(G), len(O)
    ok = [a for g in G for a in g['apps'] if a['ok']]
    P = [p for g in G for p in g['plants']]
    OA = [a for o in O for a in o['apps']]
    crops = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON']

    def avg(v):
        return sum(v) / len(v) if v else 0.0

    print(f"\nHER FERTILIZER, per game (n={n} replays)")
    print(f"  collected {avg([g['n_collect_ok'] for g in G]):6.1f}   bought {avg([g['buy_got'] for g in G]):5.1f}"
          f" (of {avg([g['buy_req'] for g in G]):.1f} ordered, {avg([g['buy_spend'] for g in G]):.0f} coins)")
    print(f"  applied   {avg([g['n_apply_ok'] for g in G]):6.1f}   sold   {avg([g['sell_got'] for g in G]):5.1f}"
          f" (of {avg([g['sell_req'] for g in G]):.1f} ordered, {avg([g['sell_revenue'] for g in G]):.0f} coins)")
    print(f"  every FERTILIZE and COLLECT_FERTILIZER command she issues succeeds: "
          f"{sum(g['n_apply_ok'] for g in G)}/{sum(g['n_apply_try'] for g in G)} and "
          f"{sum(g['n_collect_ok'] for g in G)}/{sum(g['n_collect_try'] for g in G)}")

    print("\nPLACEMENT AND YIELD, hers")
    print("  crop         plants  fert%  apps/plant  age(s)          apps/game  banked  no-fert  marginal  "
          "crop px  value  fert px")
    summary = {}
    for c in crops:
        sub = [a for a in ok if a['crop'] == c]
        pl = [p for p in P if p['crop'] == c]
        fp = [p for p in pl if p['n_apps'] and p['harvest_days']]
        up = [p for p in pl if not p['n_apps'] and p['harvest_days']]
        ages = Counter(a['age'] for a in sub).most_common(2)
        astr = ' '.join(f"{a}({100*k/max(1,len(sub)):.0f}%)" for a, k in ages) or '-'
        row = dict(
            plants_per_game=len(pl) / n, fert_share=(sum(1 for p in pl if p['n_apps']) / len(pl)) if pl else 0,
            apps_per_plant=avg([p['n_apps'] for p in pl if p['n_apps']]), apps_per_game=len(sub) / n,
            banked_fert=avg([p['banked'] for p in fp]), banked_nofert_sim=avg([p['banked_cf'] for p in fp]),
            banked_unfert_observed=avg([p['banked'] for p in up]),
            marginal_per_app=avg([a['share_marginal'] for a in sub]),
            crop_price=avg([a['plant_price'] for a in sub]), value_per_app=avg([a['share_value'] for a in sub]),
            fert_price=avg([a['fert_price'] for a in sub]), ages=dict(Counter(a['age'] for a in sub)))
        summary[c] = row
        print(f"  {c:<11} {row['plants_per_game']:6.1f} {100*row['fert_share']:5.0f}% "
              f"{row['apps_per_plant']:10.2f}  {astr:<15} {row['apps_per_game']:8.1f} "
              f"{row['banked_fert']:7.2f} {row['banked_nofert_sim']:8.2f} {row['marginal_per_app']:9.2f} "
              f"{row['crop_price']:8.0f} {row['value_per_app']:6.0f} {row['fert_price']:8.0f}")

    print("\nOURS vs HERS (ours: 8 of her worlds, her seat, benchmark tape)")
    print("  crop         plants h/o      fert%  h/o      apps/game h/o     window-days covered h/o")
    comp = {}
    for c in crops:
        hp = len([p for p in P if p['crop'] == c]) / n
        hf = sum(1 for p in P if p['crop'] == c and p['n_apps']) / max(1, len([p for p in P if p['crop'] == c]))
        ha = len([a for a in ok if a['crop'] == c]) / n
        hc = avg([len(a['covered_window_ages']) for a in ok if a['crop'] == c])
        op_ = sum(o['plants_by_crop'].get(c, 0) for o in O) / m
        of = sum(o['fert_plants_by_crop'].get(c, 0) for o in O) / max(1e-9, sum(o['plants_by_crop'].get(c, 0) for o in O))
        oa = len([a for a in OA if a['crop'] == c]) / m
        oc = avg([a['covered'] for a in OA if a['crop'] == c])
        comp[c] = dict(her_plants=hp, our_plants=op_, her_fert_share=hf, our_fert_share=of,
                       her_apps=ha, our_apps=oa, her_covered=hc, our_covered=oc)
        print(f"  {c:<11} {hp:6.1f} /{op_:6.1f}   {100*hf:4.0f}% /{100*of:4.0f}%   "
              f"{ha:6.1f} /{oa:6.1f}       {hc:4.2f} /{oc:4.2f}")
    print(f"  TOTAL       apps/game {avg([g['n_apply_ok'] for g in G]):.1f} / {avg([o['n_apply'] for o in O]):.1f}"
          f"   collected/game {avg([g['n_collect_ok'] for g in G]):.1f} / {avg([o['n_collect'] for o in O]):.1f}")

    data['summary'] = dict(per_game=dict(
        collected=avg([g['n_collect_ok'] for g in G]), bought=avg([g['buy_got'] for g in G]),
        applied=avg([g['n_apply_ok'] for g in G]), sold=avg([g['sell_got'] for g in G]),
        buy_spend=avg([g['buy_spend'] for g in G]), sell_revenue=avg([g['sell_revenue'] for g in G]),
        final_money=avg([g['final_money'] for g in G])),
        by_crop=summary, vs_ours=comp,
        ours_per_game=dict(applied=avg([o['n_apply'] for o in O]), collected=avg([o['n_collect'] for o in O]),
                           final_money=avg([o['final'] for o in O])))
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    games = []
    for i, (path, eid, seat) in enumerate(mg_games()):
        g = analyse(path, eid, seat)
        games.append(g)
        print(f"[{i+1}/30] {eid} seat {seat}: apply {g['n_apply_ok']}/{g['n_apply_try']} "
              f"collect {g['n_collect_ok']}/{g['n_collect_try']} buy {g['buy_got']} sell {g['sell_got']}",
              flush=True)
    data = report(dict(games=games, ours=ours()))
    (OUT / 'fertilizer.json').write_text(json.dumps(data), encoding='utf-8')
    print('\nwrote', OUT / 'fertilizer.json')


if __name__ == '__main__':
    main()
