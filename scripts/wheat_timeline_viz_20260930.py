"""Wheat timeline viewer data (2026-09-30, user on the wool / milk viewer: "This visualizer is actually great, you should
build another one for wheat"). Sibling of scripts/goods_timeline_viz_20260930.py: same games, same look.

Source: the back-to-back games in results/fresh/semantic_h2h_20260929/b2b/ - DSM's recorded game against a strong recorded
opponent ('dsm') and our arm playing DSM's seat against the SAME frozen opponent ('<arm>.p0'). WORLDS / ARM_ORDER /
ARM_LABEL / available() are imported from the wool / milk builder, so both viewers list the same games. Frame t = after
step t's unit actions, before its market phase (engine order: strawberry_market_20260930's docstring).

WHEAT is a crop, a tradable input (BUY_PRODUCT) and the animals' feed, so strawberry_market_20260930.load_market (sell-only
goods) does not cover it; everything is reconstructed here per tick (interpreter step t = 0..718) for our seat:
  land       wheat tiles, empty tiles (None = unlocked and bare; "LOCKED" = not bought) and weeds at the START of each hour,
             i.e. the board the units see before acting - the same sampling as the ledger's tile_hours
  planted    tiles that became wheat in step t (a new PLANT with planted_day = today)
  harvested  units a HARVEST took off a wheat tile. kaggriculture.py 1.32.7 CROPS["WHEAT"]: yield 1 at planting, +1 per
             watered day at age 2..4 (+2 while fertilized), max 6; harvestable from age 2; from day planted+5 the yield
             decays by 1 every 2 steps and the tile turns to weed at 0; a plant with two unwatered day ends in a row (the
             planting day counts as one) turns to weed. Amount = the tile's yield before step t (frame t-1 less step t-1's
             decay) plus any WATER an earlier unit gave it in step t. 'wasted' = wheat tiles lost to weeds or dug up
  delivered  wheat entering the shed: DROP / PLACE by a hand during the day ('drop') and the midnight dump of every
             inventory (end of day d, shown at hour 0 of day d+1); 'picked up' = PICKUP WHEAT out of the shed
  fed        successful FEEDs (an animal's fed_today turns on in step t): 1 wheat each from that unit's inventory
  bought / sold   executed units in an exact lockstep replay of the wheat market (both seats, order index by index,
             both quote the same pre-commit inventory, BUY quotes inventory - 1). Our sells = min(order, shed). Our buys
             run out of cash in the opening: the count is solved from the step's cash change (m[t+1] - m[t] = wheat
             revenue - wheat spend + the cash of our other orders, bounded by other_cash) where exactly one count fits,
             else the order less what the next frame's shed shows missing (and, when a pickup emptied the shed, less what
             the hands are later seen to lack at a drop / the midnight dump).
             The opponent (its commands, weeds and purchase counts are frozen in every game of a world): in DSM's own
             game its executed units per order come from the commit sequence of the engine-hooked trace of that game
             (item_trace x_n18rc8x_src). In our games its purchases are credited at its real per-step counts
             (leader_commits) and fill in order-index order, and its sells are limited by its shed, simulated from its
             hands: the trace's unit events (harvests, pickups, feeds, drops) replayed with pickups capped by this game's
             shed, feeds needing wheat in the hand and the midnight dump of what the hands hold; units DSM's game proves
             absent (a short sell with the tracked shed above 0, e.g. overflow lost at a full shed) are removed there.
  lost       wheat that did not fit into the shed (cap 100 across all goods) at a DROP or at the midnight dump
  shed / carried   shed stock at the frame (after the units act, before the market) and wheat in hands
Checks printed per game (and embedded): recomputed price == frame price per tick; per day vs the game's own ledger for
both seats (produced:WHEAT, sold units and revenue, BUY_PRODUCT:WHEAT spend, effective FEEDs = op:FEED - no_effect:FEED,
tile_hours crop:WHEAT / empty / weed); the stock balance start + harvested + bought - sold - fed - lost - end = 0 per
side; DSM's game also tick by tick against the engine trace (both seats' trades, our harvests / feeds / pickups /
drops / dumps).

usage: .venv/Scripts/python.exe scripts/wheat_timeline_viz_20260930.py  [writes viz/wheat_timeline.html]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import strawberry_market_20260930 as SM  # noqa: E402
import goods_timeline_viz_20260930 as GV  # noqa: E402  (WORLDS, ARM_ORDER, ARM_LABEL, available)

H = ROOT / "results/fresh/semantic_h2h_20260929"
TRACE = H / "item_trace/x_n18rc8x_src"          # engine-hooked source-control runs of DSM's games
TEMPLATE = ROOT / "viz/wheat_timeline_template.html"
OUT = ROOT / "viz/wheat_timeline.html"
ITEM = "WHEAT"
KP = SM.GOODS.index(ITEM)
CROP = dict(first_yield_day=2, max_yield_day=4, max_yield=6)           # kaggriculture.py 1.32.7 CROPS["WHEAT"]
WINDOW = ((CROP["max_yield_day"] + 1) // 2, CROP["max_yield_day"])     # WATER adds yield at ages 2..4
SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}                          # _shed_access_tiles(10)
MOVES = {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}
BUYERS = sorted(s for s, prods in SM.SHOPS.items() if ITEM in prods)
TPD = 24
DAYS = 30
INITIAL = [None if (k % 10 < 5 and k // 10 < 5) else "LOCKED" for k in range(100)]   # _initial_tile: NW unlocked


def sparse(xs):
    return {str(t): v for t, v in enumerate(xs) if v}


def _int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def is_wheat(x):
    return isinstance(x, dict) and x.get("kind") == "PLANT" and x.get("crop") == ITEM


def wheat_orders(action):
    """per order index (the first 10, as the engine cuts them): ('S' | 'B', units) for a SELL / BUY_PRODUCT WHEAT order
    that _parse_order accepts (units > 0), else None (another order, or one the engine skips)"""
    out = []
    for o in SM._orders(action):
        v = None
        if isinstance(o, list) and len(o) >= 3 and o[1] == ITEM and o[0] in ("SELL", "BUY_PRODUCT"):
            n = _int(o[2])
            if n > 0:
                v = ("S" if o[0] == "SELL" else "B", n)
        out.append(v)
    return out


def unit_cmds(fr):
    """the command each existing unit executed in this step (farmer first, then hands in index order); a hand command
    past the hands list is a no-op in the engine (and a hand hired this step acts from the next one)"""
    a = fr.get("a") if isinstance(fr.get("a"), dict) else {}
    hands = a.get("hands") if isinstance(a.get("hands"), list) else []
    cmds = [a.get("farmer", ["PASS"])] + list(hands)
    return [c if (j < len(cmds) and isinstance(c, list) and c and isinstance(c[0], str)) else None
            for j, c in enumerate(cmds[:len(fr["u"])])]


def trace_events(world, seat):
    """per tick from DSM's engine-hooked game (events in engine order): both seats' executed wheat trades with prices,
    the opponent's commit sequence, hand events (harvest / take / feed / drop with the unit index) and midnight dumps,
    our seat's unit flows. None when the trace is missing or was run for another seat."""
    f = TRACE / f"dsm3q-{world}.items.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    if int(j.get("our_seat", -1)) != int(seat):
        return None
    ev = defaultdict(lambda: defaultdict(list))  # kind -> tick -> [values]
    for e in j["events"]:
        if e[5] != ITEM:
            continue
        kind, s, t = e[0], int(e[1]), int(e[2])
        who = "us" if s == seat else "opp"
        if kind in ("sold", "bought"):
            ev[f"{who}_{kind}"][t].append(int(round(e[6])))
            if who == "opp":
                ev["opp_seq"][t].append("S" if kind == "sold" else "B")
        elif who == "us" and kind in ("produced", "taken", "used"):
            ev[kind][t].append(int(e[6]))
        elif who == "us" and kind == "arrived":
            ev["dump" if e[4] == "dump" else "drop"][t].append(int(e[6]))
        elif who == "opp" and (kind in ("produced", "taken", "used") or kind == "arrived" and e[4] != "dump"):
            # the opponent's hand events in engine order (unit index, units): its hands are simulated from these
            ev["opp_units"][t].append(({"produced": "harvest", "taken": "take", "used": "feed"}.get(kind, "drop"),
                                       int(e[3]), int(e[6])))
        elif who == "opp" and kind == "arrived":
            ev["opp_dump"][t].append(int(e[6]))
    return ev


# ------------------------------------------------------------------------------------------------------------ board
def board_pass(G):
    """per tick from the frames: land at the start of the hour, plantings, harvests (unit, units), digs / weeds of wheat
    tiles, successful feeds; plus self-checks of the engine emulation against the next frame"""
    F, T = G["frames"], G["tiles"]
    N = len(F)
    out = dict(wheat=[0] * N, empty=[0] * N, weed=[0] * N, planted=[0] * N, harv=[0] * N, harv_tiles=[0] * N,
               wasted=[0] * N, wasted_units=[0] * N, feeds=[[] for _ in range(N)], harvest_by=[{} for _ in range(N)])
    bad = Counter()
    examples = []
    cu = {}                                   # (tile, crop, planted_day) -> consecutive unwatered day ends
    for t in range(N):
        day = t // TPD
        prev = [T[i] for i in F[t - 1]["b"]] if t else INITIAL
        cur = [T[i] for i in F[t]["b"]]
        ops = defaultdict(list)               # tile -> [(unit, command)] in execution order
        for j, c in enumerate(unit_cmds(F[t])):
            if c is None or c[0] in MOVES:
                continue
            x, y = F[t]["u"][j]
            ops[y * 10 + x].append((j, c))
        for k in range(100):
            x0, x1 = prev[k], cur[k]
            # ---- the state step t's units see (frame t-1 + step t-1's decay + the day end if t % 24 == 0); every crop
            # ages the same way: _decay_plants(step t-1) after its market phase, then _daily_refresh_plants at a day end
            pre_wheat = False
            alive = True
            if isinstance(x0, dict) and x0.get("kind") == "PLANT":
                y = int(x0.get("yield_units", 0) or 0)
                mls = int(x0.get("max_lifespan_step", -1))
                s_ = t - 1
                if mls >= 0 and s_ >= mls and (s_ - mls) % 2 == 0:
                    y -= 1
                    alive = y > 0
                pd = int(x0.get("planted_day", 0))
                if alive and t % TPD == 0:     # two unwatered day ends in a row (the planting day counts as one)
                    key = (k, x0.get("crop"), pd)
                    c_ = cu.get(key, 1)
                    c_ = 0 if x0.get("watered_today") else c_ + 1
                    cu[key] = c_
                    alive = c_ < 2
                if not alive:                  # turned to weed between the frames
                    out["weed"][t] += 1
                    if not ops.get(k) and not (isinstance(x1, dict) and x1.get("kind") == "WEED"):
                        bad["weed_not_seen"] += 1
                        examples.append(("weed_not_seen", t, k, x0.get("crop")))
            if is_wheat(x0):
                if not alive:
                    out["wasted"][t] += 1
                    out["wasted_units"][t] += max(0, y)
                else:
                    pre_wheat = True
                    out["wheat"][t] += 1
                    watered = False if t % TPD == 0 else bool(x0.get("watered_today"))
                    fud = int(x0.get("fertilized_until_day", -1))
                    age = day - pd
                    here = True
                    for (j, c) in ops.get(k, []):
                        op = c[0]
                        if not here:
                            break
                        if op == "WATER" and not watered:
                            watered = True
                            if WINDOW[0] <= age <= WINDOW[1]:
                                y = min(CROP["max_yield"], y + (2 if fud >= day else 1))
                        elif op == "FERTILIZE":
                            # success needs fertilizer in the hand (not recorded): read it off the next frame
                            if is_wheat(x1) and int(x1.get("planted_day", -9)) == pd and \
                                    int(x1.get("fertilized_until_day", -1)) >= day + 2 > fud:
                                fud = day + 2
                        elif op == "HARVEST" and age >= CROP["first_yield_day"] and y > 0:
                            out["harv"][t] += y
                            out["harv_tiles"][t] += 1
                            out["harvest_by"][t][k] = (j, y)
                            here = False
                        elif op == "DIG":
                            out["wasted"][t] += 1
                            out["wasted_units"][t] += y
                            here = False
                    if here:                   # still the same plant: the next frame must agree
                        if not (is_wheat(x1) and int(x1.get("planted_day", -9)) == pd and
                                int(x1.get("yield_units", 0) or 0) == y and bool(x1.get("watered_today")) == watered):
                            bad["plant_state"] += 1
                            if len(examples) < 20:
                                examples.append(("plant_state", t, k, y, watered, x1))
                    elif is_wheat(x1) and int(x1.get("planted_day", -9)) == pd:
                        bad["harvest_not_seen"] += 1
                        examples.append(("harvest_not_seen", t, k))
            elif isinstance(x0, dict) and x0.get("kind") == "WEED":
                out["weed"][t] += 1
            elif x0 is None or (x0 == "LOCKED" and x1 != "LOCKED"):
                # bare (or unlocked by step t-1's BUY_LAND); a weed may have spawned at the day end
                spawned = t % TPD == 0 and ((isinstance(x1, dict) and x1.get("kind") == "WEED") or
                                            any(c[0] == "DIG" for _, c in ops.get(k, [])))
                if spawned:
                    out["weed"][t] += 1
                else:
                    out["empty"][t] += 1
            # ---- plantings: a wheat plant dated today that was not on the tile before the step
            if is_wheat(x1) and int(x1.get("planted_day", -9)) == day and not (
                    pre_wheat and is_wheat(x0) and int(x0.get("planted_day", -9)) == day):
                out["planted"][t] += 1
                if not any(c[0] == "PLANT" and len(c) > 1 and c[1] == ITEM for _, c in ops.get(k, [])):
                    bad["plant_without_command"] += 1
            # ---- feeds: fed_today switched on in this step (it is reset at every day end)
            if isinstance(x1, dict) and x1.get("animal") and x1.get("fed_today"):
                before = t % TPD != 0 and isinstance(x0, dict) and x0.get("animal") and x0.get("fed_today")
                if not before:
                    out["feeds"][t].append(k)
    out["bad"], out["examples"] = dict(bad), examples[:12]
    return out


# ----------------------------------------------------------------------------------------------------------- market
def lockstep(inv, orders, seat, have, buy_cap, ocap, oshed, obuy):
    """one step's wheat market phase (_process_market): for order index i = 0..9 both players' i-th orders run unit by
    unit, both quoting the same pre-commit inventory (SELL: price(inv), BUY_PRODUCT: price(inv - 1)), commits in seat
    order; a failed commit drops the rest of that order. Our side: a sell needs a unit in our shed (have), a buy one of
    buy_cap units. The opponent: ocap = its executed units per order index (decoded from the engine trace), or None =
    simulate: a sell needs a unit in its shed (oshed), a buy one of obuy units (its credited purchase count this step).
    Returns inventory after, per seat [sold, revenue, bought, spend], fills [(seat, op, index, price)], have, oshed,
    obuy, whether a decoded opponent sale exceeded its tracked shed, and 'dry': at each decoded opponent sell order
    that stopped short (its shed was empty right there) the units its tracked shed still held (then reset to 0)."""
    res = [[0, 0, 0, 0], [0, 0, 0, 0]]
    fills = []
    over = False
    dry = []
    ocap = list(ocap) if ocap is not None else None
    for i in range(max(len(orders[0]), len(orders[1]))):
        cur = [orders[p][i] if i < len(orders[p]) else None for p in (0, 1)]
        rem = [c[1] if c else 0 for c in cur]
        while rem[0] > 0 or rem[1] > 0:
            quote = [None, None]
            for p in (0, 1):
                if rem[p] > 0:
                    quote[p] = SM.price(ITEM, inv) if cur[p][0] == "S" else SM.price(ITEM, inv - 1)
            done = False
            for p in (0, 1):
                if quote[p] is None:
                    continue
                op = cur[p][0]
                if p == seat:
                    ok = have > 0 if op == "S" else buy_cap > 0
                elif ocap is not None:
                    ok = ocap[i] > 0
                    if not ok and op == "S":           # its real sale stopped here: its shed was empty
                        dry.append(oshed)
                        oshed = 0
                else:
                    ok = oshed > 0 if op == "S" else obuy > 0
                if not ok:
                    rem[p] = 0
                    continue
                rem[p] -= 1
                if p == seat:
                    if op == "S":
                        have -= 1
                    else:
                        have += 1
                        buy_cap -= 1
                else:
                    if ocap is not None:
                        ocap[i] -= 1
                        over |= op == "S" and oshed <= 0
                    if op == "S":
                        oshed -= 1
                    else:
                        oshed += 1
                        obuy -= 1
                r = res[p]
                if op == "S":
                    r[0] += 1
                    r[1] += quote[p]
                    if quote[p] > 1:
                        inv += 1
                else:
                    r[2] += 1
                    r[3] += quote[p]
                    inv -= 1
                fills.append((p, op, i, quote[p]))
                done = True
            if not done:
                break
    return inv, res, fills, have, oshed, obuy, over, dry


def decode_opp(orders, seq):
    """the opponent's executed units per order index from its commit sequence in the engine trace ('S' / 'B' in
    engine order): its index-i units all precede its index-(i+1) units, and an order that stops early (empty shed, no
    cash) leaves nothing for a later order of the same kind in that step, so a greedy walk is exact. Returns (caps, ok)."""
    caps, k = [], 0
    for o in orders:
        n = 0
        if o:
            while n < o[1] and k < len(seq) and seq[k] == o[0]:
                n += 1
                k += 1
        caps.append(n)
    return caps, k == len(seq)


SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}   # kaggriculture.py CROPS seed
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}                                  # ANIMALS cost
LAND_PRICES = [1000, 2000, 4000]
_INV_RANGE = {}


def inv_range(item, p):
    """the market inventories whose engine price rounds to p (price is non-increasing in inventory)"""
    key = (item, p)
    if key not in _INV_RANGE:
        lo, hi = 0, 2 * SM.MARKET_I0               # smallest inventory with price <= p
        while lo < hi:
            mid = (lo + hi) // 2
            if SM.price(item, mid) <= p:
                hi = mid
            else:
                lo = mid + 1
        a = lo
        lo, hi = 0, 2 * SM.MARKET_I0               # largest inventory with price >= p
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if SM.price(item, mid) >= p:
                lo = mid
            else:
                hi = mid - 1
        _INV_RANGE[key] = (a, max(a, lo))
    return _INV_RANGE[key]


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _units(orders, kind, item):
    """units ordered by these orders of one kind ('SELL' / 'BUY_PRODUCT') of one good"""
    return sum(_int(x[2]) for x in orders if isinstance(x, list) and len(x) >= 3 and x[0] == kind and x[1] == item)


def other_cash(fr, oact):
    """bounds [lo, hi] on the cash our NON-wheat orders of this step moved (engine: _process_market, _commit_unit,
    _do_hire, _do_buy_land): sells of goods we hold, at prices within the band the frame's price implies after every
    earlier unit of that good this step (ours, and at most all of the opponent's orders of it up to the same index);
    seeds / animals / hires / land at their fixed costs, each allowed to fail (cash, shed room) unless it cannot"""
    ords = SM._orders(fr.get("a"))
    oords = SM._orders(oact)
    shed = dict(fr.get("sh") or {})
    lo = hi = 0
    moved = defaultdict(int)                       # our units of a good already traded this step (+ sold, - bought)
    hires = len(fr["u"]) - 1                       # every hand on the farm was hired today
    for i, o in enumerate(ords):
        if not isinstance(o, list) or not o:
            continue
        op = o[0]
        if op == "HIRE":
            c = _fib(hires)
            lo, hires = lo - c, hires + 1          # may fail for cash: [-c, 0]
            continue
        if op == "BUY_LAND":
            lo -= LAND_PRICES[-1]                  # cost depends on quadrants owned: bound it
            continue
        if op not in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL") or len(o) < 3:
            continue
        n, item = _int(o[2]), o[1]
        if n <= 0 or item == ITEM and op in ("SELL", "BUY_PRODUCT"):
            continue
        if op == "BUY_SEED" and item in SEED_COST:
            lo -= n * SEED_COST[item]
        elif op == "BUY_ANIMAL" and item in ANIMAL_COST:
            lo -= n * ANIMAL_COST[item]
        elif op in ("SELL", "BUY_PRODUCT") and item in SM.GOODS:
            if op == "BUY_PRODUCT" and item != "FERTILIZER":
                continue                           # the engine only sells WHEAT / FERTILIZER
            if op == "SELL":
                u = min(n, max(0, int(shed.get(item, 0) or 0) - moved[item]))
            else:
                u = n
            if u <= 0:
                continue
            a, b = inv_range(item, int(fr["p"][SM.GOODS.index(item)]))
            # every unit of this good traded earlier this step by us, and at most all of the opponent's up to index i
            o_sell, o_buy = _units(oords[:i + 1], "SELL", item), _units(oords[:i + 1], "BUY_PRODUCT", item)
            s_lo = s_hi = 0
            for k in range(u):
                if op == "SELL":
                    v_lo, v_hi = a + moved[item] + k - o_buy, b + moved[item] + k + o_sell
                    s_lo += SM.price(item, v_hi)
                    s_hi += SM.price(item, max(0, v_lo))
                else:
                    v_lo, v_hi = a + moved[item] - k - o_buy - 1, b + moved[item] - k + o_sell - 1
                    s_lo -= SM.price(item, max(0, v_lo))
                    s_hi -= SM.price(item, v_hi)
            if op == "SELL":
                lo, hi = lo + s_lo, hi + s_hi
                moved[item] += u
            else:
                lo += s_lo                         # a purchase may fail (cash / shed room): [cost, 0]
                moved[item] -= u
    return lo, hi


def market_pass(G, A, our_cap, opp):
    """exact lockstep replay of the wheat market for one game (see the module doc). our_cap[t] = our executable buy
    units where the step's cash change does not decide them: m[t+1] - m[t] = wheat revenue - wheat spend + the cash of
    our other orders (bounded by other_cash), so a buy count is 'cash-solved' when exactly one count fits. opp =
    dict(caps=per tick per index executed units (DSM's game) or None (simulate), units / dumps=its hand events /
    midnight dumps per tick from the trace, buys=its credited purchase count per tick, phantom=units to drop from its
    simulated shed per tick)."""
    F = G["frames"]
    seat = G["seat"]
    N = len(F)
    R = {k: [0] * N for k in ("sold", "rev", "bought", "spend", "osold", "orev", "obought", "ospend", "inv", "draws",
                              "match", "req_s", "req_b", "oreq_s", "oreq_b", "oshed", "cash_solved", "cash_nofit",
                              "phantom")}
    fills = defaultdict(list)                  # (side, op) -> [(t, order index, price)]
    over = []
    inv = SM.MARKET_I0
    oshed = 0
    ohands = defaultdict(int)                  # the opponent's wheat per unit (hands leave at every day end)
    ochk = Counter()
    for t in range(N):
        R["inv"][t] = inv
        R["match"][t] = int(SM.price(ITEM, inv) == int(F[t]["p"][KP]))
        orders = [None, None]
        orders[seat] = wheat_orders(F[t].get("a"))
        oact = A[1 - seat][t] if t < len(A[1 - seat]) else None
        orders[1 - seat] = wheat_orders(oact)
        for p, key in ((seat, ""), (1 - seat, "o")):
            R[key + "req_s"][t] = sum(o[1] for o in orders[p] if o and o[0] == "S")
            R[key + "req_b"][t] = sum(o[1] for o in orders[p] if o and o[0] == "B")
        # the opponent's shed when the market opens: the midnight dump of what its hands held, then its units' hand
        # events of this step in engine order, each taking what this game's shed / hand allows
        if t % TPD == 0 and t:
            dump = sum(ohands.values())
            oshed += dump
            ochk["dump_diff"] += abs(dump - sum(opp["dumps"].get(t, [])))
            ohands.clear()
        ocmds = unit_cmds({"a": oact, "u": [0] * 64}) if isinstance(oact, dict) else []
        for kind, j, n in opp["units"].get(t, []):
            c = ocmds[j] if j < len(ocmds) else None
            if kind == "harvest":
                ohands[j] += n
            elif kind == "take":
                want = _int(c[2], 1) if c and c[0] == "PICKUP" and len(c) >= 3 else n
                got = min(want, max(0, oshed))
                ochk["take_diff"] += abs(got - n)
                oshed -= got
                ohands[j] += got
            elif kind == "feed":
                if ohands[j] >= 1:
                    ohands[j] -= 1
                else:
                    ochk["feed_failed"] += 1
            elif kind == "drop":
                m = ohands[j] if not (c and c[0] == "PLACE") else min(_int(c[2], 1) if len(c) >= 3 else 1, ohands[j])
                ochk["drop_diff"] += abs(m - n)
                oshed += m
                ohands[j] -= m
            if opp.get("log") is not None:     # debugging aid (off by default)
                opp["log"].append((t, kind, j, n, oshed, ohands[j]))
        if opp.get("phantom") and opp["phantom"][t]:
            oshed = max(0, oshed - opp["phantom"][t])
        have = int((F[t].get("sh") or {}).get(ITEM, 0))        # our shed when the market opens
        ocap = opp["caps"][t] if opp["caps"] is not None else None
        obuy = opp["buys"][t]
        cap = our_cap[t]
        if R["req_b"][t]:
            m1 = F[t + 1]["m"][0] if t + 1 < N else G["cash"]
            dm = int(m1) - int(F[t]["m"][0])
            lo, hi = other_cash(F[t], oact)
            fit = []
            for x in range(R["req_b"][t], -1, -1):
                r = lockstep(inv, orders, seat, have, x, ocap, oshed, obuy)[1][seat]
                if lo <= dm - (r[1] - r[3]) <= hi:
                    fit.append(x)
            if len(fit) == 1:
                cap = fit[0]
                R["cash_solved"][t] = 1
            elif fit:
                cap = min(cap, max(fit))
            else:
                R["cash_nofit"][t] = 1
        inv, res, f, _, oshed, _, ov, dry = lockstep(inv, orders, seat, have, cap, ocap, oshed, obuy)
        if ov:
            over.append(t)
        if dry:
            R["phantom"][t] = sum(dry)
        for p, pre in ((seat, ""), (1 - seat, "o")):
            R[pre + "sold"][t], R[pre + "rev"][t], R[pre + "bought"][t], R[pre + "spend"][t] = res[p]
        for (p, op, i, q) in f:
            fills[("us" if p == seat else "opp", op)].append((t, i, q))
        R["oshed"][t] = oshed
        R["draws"][t] = SM.draw(ITEM, t, F[t].get("s") or [])
        inv -= R["draws"][t]
    R["fills"] = fills
    R["opp_over"] = over
    R["opp_hand_check"] = dict(ochk)
    return R


# ------------------------------------------------------------------------------------------------------ units / shed
def unit_pass(G, B, M):
    """hand inventories and shed flows: every wheat unit a hand gains (HARVEST, PICKUP) or loses (FEED, DROP, PLACE,
    the midnight dump). Predicted shed vs the frame's shed gives a residual per tick."""
    F = G["frames"]
    N = len(F)
    S_ = {k: [0] * N for k in ("drop", "dump", "pick", "fed", "carried", "resid", "shed", "post")}
    bad = Counter()
    inv = [0]
    post = 0                                   # our shed after the previous step's market phase
    dump_carried = [0] * N                     # what the hands held at the day end (before the shed cap)
    for t in range(N):
        if t % TPD == 0:
            if t:
                dump_carried[t] = sum(inv)
            inv = [0]                          # hands leave at the day end; the farmer starts empty
        S = post + dump_carried[t]
        pending = set(B["feeds"][t])
        for j, c in enumerate(unit_cmds(F[t])):
            while len(inv) <= j:
                inv.append(0)
            if c is None:
                continue
            op = c[0]
            p = tuple(F[t]["u"][j])
            k = p[1] * 10 + p[0]
            if op == "HARVEST":
                hb = B["harvest_by"][t].get(k)
                if hb and hb[0] == j:
                    inv[j] += hb[1]
            elif op == "PICKUP" and len(c) >= 2 and c[1] == ITEM and p in SHED_TILES:
                n = _int(c[2]) if len(c) >= 3 else 1
                if n > 0:
                    take = min(n, S)
                    inv[j] += take
                    S -= take
                    S_["pick"][t] += take
            elif op == "FEED" and k in pending and inv[j] >= 1:
                inv[j] -= 1
                pending.discard(k)
                S_["fed"][t] += 1
            elif op == "DROP" and p in SHED_TILES:
                S += inv[j]
                S_["drop"][t] += inv[j]
                inv[j] = 0
            elif op == "PLACE" and len(c) >= 2 and c[1] == ITEM and p in SHED_TILES:
                n = _int(c[2]) if len(c) >= 3 else 1
                if n > 0:
                    take = min(n, inv[j])
                    inv[j] -= take
                    S += take
                    S_["drop"][t] += take
        if pending:                            # the frame shows a feed no hand of ours could pay for
            bad["feed_without_wheat"] += len(pending)
            S_["fed"][t] += len(pending)
        shed = int((F[t].get("sh") or {}).get(ITEM, 0))
        S_["resid"][t] = shed - S
        S_["shed"][t] = shed
        S_["carried"][t] = sum(inv)
        S_["dump"][t] = dump_carried[t]
        post = shed - M["sold"][t] + M["bought"][t]
        S_["post"][t] = post
    S_["end_carried"] = sum(inv)
    S_["bad"] = dict(bad)
    return S_


def shed_total(fr):
    return sum(int(v or 0) for v in (fr.get("sh") or {}).values())


def shed_full(fr):
    """the shed can have been at its cap (100 units, all goods) during this step's unit actions: the frame total plus
    everything the units may have picked up after a drop reaches 100"""
    picks = sum(_int(c[2], 1) if len(c) >= 3 else 1 for c in unit_cmds(fr) if c and c[0] == "PICKUP")
    return shed_total(fr) + picks >= 100


# ------------------------------------------------------------------------------------------------------------- game
def ledger_days(G):
    """per day d from the game's own cumulative ledger (entry d = before step 24d; entry 30 = the final state)"""
    D, s = G["daily"], G["seat"]
    out = {}
    for side, idx in (("us", s), ("opp", 1 - s)):
        rows = defaultdict(list)
        for d in range(DAYS):
            a, b = D[idx][d], D[idx][d + 1]

            def dif(sec, key):
                return (b[sec].get(key, 0) or 0) - (a[sec].get(key, 0) or 0)
            rows["prod"].append(int(dif("physical", "produced:WHEAT")))
            rows["sold"].append(int(dif("sold_units", ITEM)))
            rows["rev"].append(int(round(dif("revenue", ITEM))))
            rows["spend"].append(int(round(dif("spend", "BUY_PRODUCT:WHEAT"))))
            rows["fed"].append(int(dif("physical", "op:FEED") - dif("physical", "no_effect:FEED")))
            rows["wh"].append(int(dif("tile_hours", "crop:WHEAT")))
            rows["eh"].append(int(dif("tile_hours", "empty")))
            rows["weh"].append(int(dif("tile_hours", "weed")))
            rows["seed"].append(int(round(dif("spend", "BUY_SEED:WHEAT"))))
        out[side] = dict(rows)
    return out


def per_day(xs, N):
    return [sum(xs[d * TPD:min(N, (d + 1) * TPD)]) for d in range(DAYS)]


def opp_model(world, game, G, A):
    """the opponent's side of the wheat market. Its commands, weeds and purchase counts are frozen in every game of a
    world (leader_commits: exact credit, its BUY units succeed exactly as often per step as in its real game), so its
    unit flows are DSM's game's (engine trace); in DSM's own game (the real game replayed) its executed units per order
    are decoded from the trace's commit sequence, in our games its credited buys fill in order-index order and its
    sells are limited by its shed (tracked from those flows)."""
    seat = G["seat"]
    N = len(G["frames"])
    ev = trace_events(world, seat)
    if ev is None:
        raise FileNotFoundError(f"{world}: no engine trace of DSM's game for seat {seat}")
    commits = json.loads((H / "leader_commits" / f"dsm3q-{world}.json").read_text())
    assert int(commits["lead_seat"]) == 1 - seat
    buys = [int((commits["steps"].get(str(t)) or {}).get("BUY_PRODUCT:WHEAT", 0)) for t in range(N)]
    caps, bad = [], []
    for t in range(N):
        c, ok = decode_opp(wheat_orders(A[1 - seat][t] if t < len(A[1 - seat]) else None), ev["opp_seq"].get(t, []))
        caps.append(c)
        if not ok:
            bad.append(t)
    model = dict(caps=caps, units=dict(ev["opp_units"]), dumps=dict(ev["opp_dump"]), buys=buys, decode_failed=bad,
                 phantom=None)
    if game != "dsm":
        # units its tracked shed holds where its real sales prove the shed was empty (e.g. overflow it lost at a full
        # shed, which the trace books as delivered): removed from the simulated shed at the same tick
        if world not in _PHANTOM:
            Gd, Ad = SM.load_game(world, "dsm")
            Fd = Gd["frames"]
            reqd = [sum(o[1] for o in wheat_orders(Fd[t].get("a")) if o and o[0] == "B") for t in range(len(Fd))]
            _PHANTOM[world] = [max(0, v) for v in market_pass(Gd, Ad, reqd, dict(model, phantom=None))["phantom"]]
        model.update(caps=None, phantom=_PHANTOM[world])
    return model, ev


_PHANTOM = {}


def build_game(world, game, verbose=True):
    G, A = SM.load_game(world, game)
    F = G["frames"]
    N = len(F)
    assert all(F[i]["t"] == i for i in range(N)), "frames not indexed by step"
    seat = G["seat"]
    opp, ev = opp_model(world, game, G, A)
    B = board_pass(G)
    # our buys: solved from the step's cash change where wheat is our only cash-moving order; elsewhere as ordered, less
    # what the next frame's shed shows missing (cash ran out). A pickup that empties the shed hides the shortfall until
    # the hands' wheat is next observed (a drop or the midnight dump): cut the last such buy that day.
    req_b = [sum(o[1] for o in wheat_orders(F[t].get("a")) if o and o[0] == "B") for t in range(N)]
    cap = list(req_b)
    for _ in range(40):
        M = market_pass(G, A, cap, opp)
        U = unit_pass(G, B, M)
        direct = [t for t in range(1, N) if U["resid"][t] < 0 and M["bought"][t - 1] > 0 and not M["cash_solved"][t - 1]]
        for t in direct:
            cap[t - 1] = M["bought"][t - 1] - min(-U["resid"][t], M["bought"][t - 1])
        if direct:
            continue
        back = None
        for t in range(1, N):
            r = U["resid"][t]
            if r < 0 and U["drop"][t] + U["dump"][t] > 0 and not shed_full(F[t]):
                lo = (t // TPD - (1 if t % TPD == 0 else 0)) * TPD
                cand = [s for s in range(t - 2, lo - 1, -1) if M["bought"][s] > 0 and not M["cash_solved"][s]
                        and U["shed"][s + 1] == 0 and U["pick"][s + 1] > 0]
                if cand:
                    back = (cand[0], -r)
                    break
        if back is None:
            break
        s, r = back
        cap[s] = M["bought"][s] - min(r, M["bought"][s])
    partial = {t: (req_b[t], M["bought"][t]) for t in range(N) if M["bought"][t] < req_b[t]}
    # remaining residuals: wheat that did not fit into the shed (cap 100 across all goods) at a drop or the midnight
    # dump - only possible when the shed is full at that frame (allowing for any pickups after the drop) - is lost;
    # anything else is reported as unexplained
    lost = [0] * N
    unexplained = []
    for t in range(N):
        r = U["resid"][t]
        if r == 0:
            continue
        inflow = U["drop"][t] + U["dump"][t]
        if r < 0 and -r <= inflow and shed_full(F[t]):
            lost[t] = -r
        else:
            unexplained.append((t, r))
    # daily comparison against the ledger
    L = ledger_days(G)
    mod = dict(us=dict(prod=per_day(B["harv"], N), sold=per_day(M["sold"], N), rev=per_day(M["rev"], N),
                       spend=per_day(M["spend"], N), fed=per_day(U["fed"], N), wh=per_day(B["wheat"], N),
                       eh=per_day(B["empty"], N), weh=per_day(B["weed"], N)),
               opp=dict(sold=per_day(M["osold"], N), rev=per_day(M["orev"], N), spend=per_day(M["ospend"], N)))
    mism = []
    n_cmp = n_ok = 0
    for side, keys in (("us", ("prod", "sold", "rev", "spend", "fed", "wh", "eh", "weh")), ("opp", ("sold", "rev", "spend"))):
        for key in keys:
            for d in range(DAYS):
                n_cmp += 1
                a, b = mod[side][key][d], L[side][key][d]
                if a == b:
                    n_ok += 1
                else:
                    mism.append([side, key, d, a, b])
    # tick-level check of DSM's game against the engine trace
    tick = None
    if game == "dsm":
        tick = {}
        pairs = [("us sold", M["sold"], "us_sold", len), ("us revenue", M["rev"], "us_sold", sum),
                 ("us bought", M["bought"], "us_bought", len), ("us spend", M["spend"], "us_bought", sum),
                 ("opp sold", M["osold"], "opp_sold", len), ("opp revenue", M["orev"], "opp_sold", sum),
                 ("opp bought", M["obought"], "opp_bought", len), ("opp spend", M["ospend"], "opp_bought", sum),
                 ("harvested", B["harv"], "produced", sum), ("fed", U["fed"], "used", sum),
                 ("picked up", U["pick"], "taken", sum), ("dropped", U["drop"], "drop", sum),
                 ("dumped", U["dump"], "dump", sum)]
        for name, xs, key, f in pairs:
            bad_t = [t for t in range(N) if xs[t] != f(ev[key].get(t, []))]
            tick[name] = [N - len(bad_t), N, bad_t[:6]]
    # stock balance per side (start stock 0: the shed starts empty, no unit carries anything)
    end_stock = U["post"][N - 1] + U["end_carried"]
    bal = sum(B["harv"]) + sum(M["bought"]) - sum(M["sold"]) - sum(U["fed"]) - sum(lost) - end_stock
    oL = L["opp"]
    opp_implied = sum(oL["prod"]) + sum(M["obought"]) - sum(oL["sold"]) - sum(oL["fed"])
    checks = dict(price_match=[sum(M["match"]), N], ledger=[n_ok, n_cmp], mismatches=mism, balance=bal,
                  unexplained=unexplained[:20], n_unexplained=len(unexplained), partial_buys=len(partial),
                  lost=sum(lost), board=B["bad"], board_examples=[str(e) for e in B["examples"]], units=U["bad"],
                  tick=tick, opp_implied_end_stock=opp_implied, end_stock=end_stock,
                  opp_req_vs_exec=[sum(M["oreq_s"]), sum(M["osold"]), sum(M["oreq_b"]), sum(M["obought"])],
                  opp_decode_failed=opp["decode_failed"][:10], opp_shed_min=min(M["oshed"]), opp_over=M["opp_over"][:10],
                  cash_solved=sum(M["cash_solved"]), cash_nofit=[t for t in range(N) if M["cash_nofit"][t]][:10])
    if verbose:
        print(f"  {world} {game:12s} seat {seat}  price {sum(M['match'])}/{N}  ledger {n_ok}/{n_cmp}"
              f"  balance: 0 + harvested {sum(B['harv'])} + bought {sum(M['bought'])} - sold {sum(M['sold'])}"
              f" - fed {sum(U['fed'])} - lost {sum(lost)} - end stock {end_stock} = {bal}"
              f"  | partial buys {len(partial)} ({sum(M['cash_solved'])} of {sum(1 for x in req_b if x)} buy ticks"
              f" solved from cash{', no cash fit at ' + str(checks['cash_nofit']) if checks['cash_nofit'] else ''}),"
              f" unexplained shed residuals {len(unexplained)}"
              + (f"  board {B['bad']}" if B["bad"] else "") + (f"  units {U['bad']}" if U["bad"] else "")
              + (f"  opp decode failed at {opp['decode_failed'][:5]}" if opp["decode_failed"] else "")
              + (f"  opp shed min {min(M['oshed'])}" if min(M["oshed"]) < 0 else "")
              + (f"  opp sale beyond tracked shed at {M['opp_over'][:5]}" if M["opp_over"] else "")
              + (f"  opp hands vs DSM trace {M['opp_hand_check']}" if any(M["opp_hand_check"].values()) else "")
              + (f"  opp phantom units {sum(M['phantom'])}" if game == "dsm" and sum(M["phantom"]) else ""), flush=True)
        if mism:
            print("     ledger mismatches [side, field, day, model, ledger]:", mism[:12], "..." if len(mism) > 12 else "")
        if unexplained:
            print("     unexplained shed residuals (t, units):", unexplained[:10])
        if tick:
            off = {k: v for k, v in tick.items() if v[0] != v[1]}
            print("     vs engine trace, ticks equal:", "all 13 series 719/719" if not off else off)
        print(f"     opponent: harvested {sum(oL['prod'])} + bought {sum(M['obought'])} - sold {sum(oL['sold'])}"
              f" - fed {sum(oL['fed'])} = {opp_implied} (its end stock + losses; its shed is not recorded)"
              f"  | ordered sell {sum(M['oreq_s'])} / executed {sum(M['osold'])}, ordered buy {sum(M['oreq_b'])}"
              f" / executed {sum(M['obought'])}", flush=True)
    # per-tick price ranges and order indices (tooltips)
    def pxmap(side, op):
        d = {}
        for (t, i, p) in M["fills"][(side, op)]:
            v = d.setdefault(t, [p, p, set()])
            v[0], v[1] = min(v[0], p), max(v[1], p)
            v[2].add(i)
        return {str(t): [v[0], v[1], sorted(v[2])] for t, v in d.items()}
    reveals, prev = [], []
    for t in range(N):
        s = list(F[t].get("s") or [])
        if len(s) > len(prev):
            for name in s[len(prev):]:
                reveals.append([t, name])
        prev = s
    # opponent orders that did not fully execute (shed ran dry / cash) - shown in the tooltip
    oshort = {str(t): [M["oreq_s"][t], M["osold"][t], M["oreq_b"][t], M["obought"][t]] for t in range(N)
              if M["oreq_s"][t] != M["osold"][t] or M["oreq_b"][t] != M["obought"][t]}
    mm_days = sorted({m[2] for m in mism})
    # what entered the shed: the hands' drops / midnight dump less what did not fit (at hour 0 only the dump arrives;
    # the unit series above keep the hand side, which is what the engine trace books)
    drop_in = [U["drop"][t] - (lost[t] if t % TPD else 0) for t in range(N)]
    dump_in = [U["dump"][t] - (lost[t] if t % TPD == 0 else 0) for t in range(N)]
    res = dict(
        label=GV.ARM_LABEL.get(game, game), cash=G["cash"], opp_cash=G["opp_cash"], margin=G["margin"], seat=seat,
        reveals=reveals, price=[int(fr["p"][KP]) for fr in F], wheat=B["wheat"], empty=B["empty"], weed=B["weed"],
        shed=U["shed"], carried=U["carried"],
        planted=sparse(B["planted"]), harv=sparse(B["harv"]), harvT=sparse(B["harv_tiles"]),
        wasted=sparse(B["wasted"]), wastedU=sparse(B["wasted_units"]),
        drop=sparse(drop_in), dump=sparse(dump_in), pick=sparse(U["pick"]), lost=sparse(lost), fed=sparse(U["fed"]),
        sold=sparse(M["sold"]), rev=sparse(M["rev"]), bought=sparse(M["bought"]), spend=sparse(M["spend"]),
        osold=sparse(M["osold"]), orev=sparse(M["orev"]), obought=sparse(M["obought"]), ospend=sparse(M["ospend"]),
        px=pxmap("us", "S"), bpx=pxmap("us", "B"), opx=pxmap("opp", "S"), obpx=pxmap("opp", "B"),
        partial={str(t): v for t, v in partial.items()}, oshort=oshort, draws=sparse(M["draws"]),
        opp_model="decoded from the engine trace" if game == "dsm" else
        "simulated (credited buys, sells limited by its shed; hands from the engine trace)",
        ledger=L, mismatch_days=mm_days, mismatches=mism[:60],
        checks=dict(price=checks["price_match"], ledger=checks["ledger"], balance=bal, lost=sum(lost),
                    unexplained=len(unexplained), partial=len(partial), end_stock=end_stock,
                    opp_implied=opp_implied, tick=tick),
        totals=dict(harv=sum(B["harv"]), planted=sum(B["planted"]), fed=sum(U["fed"]), sold=sum(M["sold"]),
                    rev=sum(M["rev"]), bought=sum(M["bought"]), spend=sum(M["spend"]), osold=sum(M["osold"]),
                    orev=sum(M["orev"]), obought=sum(M["obought"]), ospend=sum(M["ospend"]), lost=sum(lost),
                    wasted=sum(B["wasted"]), wh=sum(B["wheat"]), eh=sum(B["empty"])))
    return res, checks


def main():
    data = dict(buyers=BUYERS, worlds={})
    summary = Counter()
    for w in GV.WORLDS:
        arms = GV.available(w)
        if not arms:
            continue
        print(w, "arms", arms, flush=True)
        games = {}
        for g in ["dsm"] + arms:
            res, chk = build_game(w, g)
            games[g] = res
            summary["games"] += 1
            summary["price_ok"] += chk["price_match"][0]
            summary["price_n"] += chk["price_match"][1]
            summary["ledger_ok"] += chk["ledger"][0]
            summary["ledger_n"] += chk["ledger"][1]
            summary["balance_zero"] += int(chk["balance"] == 0)
            summary["unexplained"] += chk["n_unexplained"]
            summary["partial"] += chk["partial_buys"]
            summary["lost"] += chk["lost"]
        G, _ = SM.load_game(w, "dsm")
        data["worlds"][w] = dict(shops=G["shops"], dsm_seat=G["seat"], arms=arms, games=games)
    print(f"SUMMARY {summary['games']} games: price {summary['price_ok']}/{summary['price_n']} ticks,"
          f" ledger {summary['ledger_ok']}/{summary['ledger_n']} day-fields"
          f" ({100 * summary['ledger_ok'] / max(1, summary['ledger_n']):.2f}%), balance 0 in"
          f" {summary['balance_zero']}/{summary['games']} games, partial (cash-limited) buy ticks {summary['partial']},"
          f" wheat lost at the shed cap {summary['lost']}, unexplained shed residuals {summary['unexplained']}", flush=True)
    if not TEMPLATE.exists():
        print("template missing:", TEMPLATE)
        return
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
