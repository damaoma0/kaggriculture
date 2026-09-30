"""Exact offline model of one product's market (STRAWBERRY; also MILK / WOOL and the other sell-only goods) for the
recorded back-to-back games in results/fresh/semantic_h2h_20260929/b2b/ (2026-09-30, market-model task).

Engine (kaggle_environments 1.32.7, envs/kaggriculture/kaggriculture.py), per interpreter step t:
  1. unit actions of both players (DROP / PLACE into the shed, PICKUP out of it; no unit action costs money)
  2. _process_market: both order queues cut to 10; for order index i = 0..9, HIRE / BUY_LAND first, then a per-unit
     lockstep over the two players' i-th orders: both players quote at the SAME pre-commit inventory, then commit
     (seat 0 first). A SELL unit pays market_price(inventory) and adds +1 to the market inventory (only when price > 1);
     it fails once the seller's shed holds none, which also drops the rest of that order. Prices refreshed after.
  3. _town_consume(step t): if t % 4 == 0 every unlocked shop instance takes 1 of each listed product (2 if the shop
     lists one product); if t % 24 == 0 the town center takes 1 of every product except FERTILIZER. Prices refreshed.
  4. end of day (t % 24 == 23): hand / farmer inventories drop into the shed (cap 100, overflow lost), next shop drawn.
STRAWBERRY / MILK / WOOL (and CARROT / TOMATO / MELON / EGG) cannot be bought, so their inventory moves only by the two
players' sales and the draws:   inventory[t+1] = inventory[t] + our_sales[t] + opp_sales[t] - draws[t],  inventory[0] = 10000.

Recorded game json (scripts/b2b_replay_20260929.py): frame t is captured when _process_market of step t is entered,
i.e. AFTER step t's unit actions and BEFORE its orders. So frame p[t] = price of the inventory entering step t (after
step t-1's town consumption), sh[t] = our shed after step t's unit actions (exactly what the market phase can sell),
a[t] = our commands of step t, s[t] = unlocked shops (the list step t's town consumption uses). Our sales are exact:
min(ordered, sh[t]) filled order by order.

Opponent (a frozen replay): its commands for step t are <case>.<game>.result.actions.json[1 - seat][t] (the harness
writes both seats' processed actions; our seat's list equals the frames' a[t] at every step). Its SELL orders are NOT
forced by the harness (leader_commits force only BUY_* / HIRE / BUY_LAND counts) and execute against its own shed,
which is not recorded. Several recorded opponents over-request (e.g. SELL WOOL 999, or the same SELL every tick), so
opp_source:
  'orders'  its SELL orders in full (exact whenever its daily ledger shows no shortfall)
  'infer'   exact set-valued reconstruction: at each tick the opponent sold x in 0..ordered (x < ordered means its shed ran
            dry, so its orders fill in index order until x units); every candidate path must reproduce the recorded
            frame price at every tick and, at each day end, the game's own daily ledger (both seats' units AND revenue
            of the item; revenue pins down the unit interleaving) and each tick's recorded cash flow (money moves only
            in the market phase: a side with no BUY_* / HIRE / BUY_LAND order earns at least the item's revenue, a side
            whose only orders are SELL <item> earns exactly it). Paths that reach the same (inventory, units,
            revenues) are merged; a day is 'ambiguous' when more than one timing survives all of these checks.
  'auto'    (default) 'orders' for an item whose opponent ledger has no shortfall on any day, else 'infer'.
  'trace'   the engine-hooked source-control run (item_trace x_n18rc8x_src; exact for DSM's own game only).
Validation (__main__ --all, 90 cached games x 7 sell-only goods, 2026-09-30): recomputed price == frame price at
64,710/64,710 ticks per good; both seats' daily units and revenue exact on every day; per-tick cash consistent.
counterfactual(m, our_sales) re-prices another schedule of our sales against the same frozen opponent (margin delta).

usage: strawberry_market_20260930.py [CASE ...] [--game dsm|n18rc127.p0|...] [--item STRAWBERRY] [--all-items] [--all]
       default: worlds 114393058 and 114433787, games dsm and n18rc127.p0, items STRAWBERRY, MILK, WOOL.
       --all: every cached b2b game (all dsm3q worlds and arms), summary per item.
"""
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B2B = ROOT / "results/fresh/semantic_h2h_20260929/b2b"
TRACE = ROOT / "results/fresh/semantic_h2h_20260929/item_trace/x_n18rc8x_src"   # engine-hooked source controls
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SELL_ONLY = ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")   # no BUY_PRODUCT path in the engine
CASES = ("114393058", "114432897", "114433787", "114448465", "114479550", "114514221", "114523301", "114537918",
         "114600746")

# engine constants (kaggriculture.py 1.32.7; engine_price_check() asserts MARKET_PARAMS / SHOPS are identical)
MARKET_I0 = 10000
PRICE_FLOOR = 1
HINGE_GAIN = 8.0
MAX_ORDERS = 10
SHOP_INTERVAL = 4          # townShopSellInterval
CENTER_INTERVAL = 24       # townCenterSellInterval
TURNS_PER_DAY = 24
MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}
SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


# ----------------------------------------------------------------------------------------------------------- engine
def _shape(func, x, T=None):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "log10":
        return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0:
            return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x


def price(item, inventory, params=None):
    """engine market_price(): the price paid for ONE unit sold at this market inventory (floored at 1)"""
    p = (params or MARKET_PARAMS)[item]
    base, I0, T = p["base"], p["I0"], p["T"]
    if inventory < I0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T, T)
        v = base + amp * _shape(f, I0 - inventory, T)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T, T)
        v = base - amp * _shape(f, inventory - I0, T)
    return max(PRICE_FLOOR, int(round(v)))


def draw(item, step, shops):
    """town consumption of `item` in interpreter step `step` with this unlocked-shop list (subtracts unconditionally)"""
    n = 0
    if step % SHOP_INTERVAL == 0:
        for s in shops:
            prods = SHOPS[s]
            if item in prods:
                n += 2 if len(prods) == 1 else 1
    if step % CENTER_INTERVAL == 0 and item != "FERTILIZER":
        n += 1
    return n


def sell_proceeds(item, inventory, n, params=None):
    """n units sold alone, one by one, from `inventory`: (revenue, inventory after)"""
    rev = 0
    for _ in range(int(n)):
        p = price(item, inventory, params)
        rev += p
        if p > 1:
            inventory += 1
    return rev, inventory


def market_step(item, inv, sells, have):
    """one step's market phase for one item. sells[pid] = per order index the SELL-<item> units requested (0 = another
    order); have[pid] = sellable shed units. Lockstep: at each index both players quote the same pre-commit inventory,
    a failed commit (empty shed) drops that player's order. Returns (inventory after, sold[2], revenue[2], fills) with
    fills = [(order index, pid, inventory quoted, price)]."""
    have = list(have)
    sold, rev, fills = [0, 0], [0, 0], []
    for i in range(max(len(sells[0]), len(sells[1]))):
        rem = [sells[0][i] if i < len(sells[0]) else 0, sells[1][i] if i < len(sells[1]) else 0]
        while rem[0] > 0 or rem[1] > 0:
            quote = price(item, inv)
            for pid in (0, 1):
                if rem[pid] <= 0:
                    continue
                if have[pid] <= 0:
                    rem[pid] = 0
                    continue
                have[pid] -= 1
                rem[pid] -= 1
                sold[pid] += 1
                rev[pid] += quote
                fills.append((i, pid, inv, quote))
                if quote > 1:
                    inv += 1
    return inv, sold, rev, fills


# ------------------------------------------------------------------------------------------------------------ data
def _game_paths(case, game):
    case = str(case).replace("dsm3q-", "")
    g = game if (game == "dsm" or ".p" in game) else game + ".p0"
    stem = B2B / f"dsm3q-{case}.{g}"
    return case, g, Path(str(stem) + ".game.json.gz"), Path(str(stem) + ".result.actions.json")


def load_game(case, game):
    case, g, gp, ap = _game_paths(case, game)
    G = json.loads(gzip.open(gp, "rt", encoding="utf-8").read())
    A = json.loads(ap.read_text()) if ap.exists() else None
    return G, A


def _orders(action):
    m = action.get("market", []) if isinstance(action, dict) else []
    return list(m)[:MAX_ORDERS] if isinstance(m, list) else []


def _sell_n(order, item):
    """units of a SELL <item> order as the engine's _parse_order reads it (0 = not a sell of this item)"""
    if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL" or order[1] != item:
        return 0
    try:
        n = int(order[2])
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def _n_pos(order):
    try:
        return int(order[2]) > 0
    except (TypeError, ValueError, IndexError):
        return False


def _cash_ok(P, t, rev_us, rev_opp):
    """step t's item revenue is consistent with both sides' recorded cash flow (see _prep)"""
    for side, r in ((0, rev_us), (1, rev_opp)):
        dm = P["dm"][side][t]
        if dm is None:
            continue
        if P["only_item"][side][t] and r != dm:
            return False
        if P["no_buy"][side][t] and r > dm:
            return False
    return True


def _prep(G, A, item):
    """per-tick inputs shared by every opp_source"""
    if A is None:
        raise FileNotFoundError("result.actions.json missing: opponent commands unavailable")
    seat = int(G["seat"])
    k = GOODS.index(item)
    frames = G["frames"]
    N = len(frames)
    P = dict(seat=seat, N=N, p_rec=[], have_us=[], sells_us=[], sells_opp=[], draws=[])
    for t, fr in enumerate(frames):
        assert int(fr["t"]) == t, (t, fr["t"])
        P["p_rec"].append(int(fr["p"][k]))
        P["have_us"].append(int((fr.get("sh") or {}).get(item, 0)))
        P["sells_us"].append([_sell_n(o, item) for o in _orders(fr.get("a"))])
        P["sells_opp"].append([_sell_n(o, item) for o in _orders(A[1 - seat][t] if t < len(A[1 - seat]) else None)])
        P["draws"].append(draw(item, t, fr.get("s") or []))
    # per-tick cash: money moves only in the market phase (no unit action costs money), so m[t+1] - m[t] is step t's
    # market cash flow; frame m = [our seat, the other seat]. A side with no BUY_* / HIRE / BUY_LAND order in step t
    # earns at least this item's revenue; a side whose only valid orders are SELL <item> earns exactly it.
    P["dm"], P["no_buy"], P["only_item"] = ([[None] * N, [None] * N] for _ in range(3))
    for t in range(N):
        for side, acts in ((0, frames[t].get("a")), (1, A[1 - seat][t] if t < len(A[1 - seat]) else None)):
            if t + 1 < N:
                P["dm"][side][t] = int(frames[t + 1]["m"][side]) - int(frames[t]["m"][side])
            # orders that can move money: HIRE / BUY_LAND, and BUY_* / SELL with a positive count
            movers = [o for o in _orders(acts) if isinstance(o, list) and o and
                      (o[0] in ("HIRE", "BUY_LAND") or (o[0] in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL")
                                                         and _n_pos(o)))]
            P["no_buy"][side][t] = all(o[0] == "SELL" for o in movers)
            P["only_item"][side][t] = all(o[0] == "SELL" and o[1] == item for o in movers)
    D = G.get("daily")
    P["ledger"] = None
    if D:
        L = []
        for d in range((N + TURNS_PER_DAY - 1) // TURNS_PER_DAY):
            row = {}
            for side, s in (("us", seat), ("opp", 1 - seat)):
                cur, prev = D[s][d + 1], D[s][d]
                row[side] = (int(cur["sold_units"].get(item, 0)) - int(prev["sold_units"].get(item, 0)),
                             int(round(cur["revenue"].get(item, 0) - prev["revenue"].get(item, 0))))
            L.append(row)
        P["ledger"] = L
    return P


def _sells_pair(P, t, seat):
    s = [None, None]
    s[seat], s[1 - seat] = P["sells_us"][t], P["sells_opp"][t]
    return s


# ------------------------------------------------------------------------------------------------ opponent inference
def infer_opp_sales(G, A, item, P=None, max_states=50000, use_cash=True):
    """Exact reconstruction of the opponent's executed SELL units of `item` per tick (see module doc, 'infer').
    Returns dict(x=[units per tick], ok, fail_tick, ambiguous_days=[(day, n_timings)], max_states, truncated)."""
    P = P or _prep(G, A, item)
    seat, N, L = P["seat"], P["N"], P["ledger"]
    n_opp = [sum(s) for s in P["sells_opp"]]
    day_end = lambda t: t % TURNS_PER_DAY == TURNS_PER_DAY - 1 or t == N - 1
    rem_after = [0] * N                      # opponent units still ordered later the same day
    for t in range(N - 2, -1, -1):
        rem_after[t] = 0 if day_end(t) else rem_after[t + 1] + n_opp[t + 1]
    x_out = [0] * N
    states = {(MARKET_I0, 0, 0, 0): ((), 1)}  # (inventory, opp units today, opp revenue today, our revenue today)
    amb, peak, truncated = [], 1, False
    for t in range(N):
        d = t // TURNS_PER_DAY
        states = {k: v for k, v in states.items() if price(item, k[0]) == P["p_rec"][t]}
        if not states:
            return dict(x=x_out, ok=False, fail_tick=t, ambiguous_days=amb, max_states=peak, truncated=truncated)
        U, R = (L[d]["opp"] if L else (None, None))
        RU = L[d]["us"][1] if L else None
        sells = _sells_pair(P, t, seat)
        new = {}
        for (inv, uo, ro, ru), (path, cnt) in states.items():
            n = n_opp[t]
            for x in range(n, -1, -1):
                if U is not None:
                    if uo + x > U:
                        continue
                    if uo + x + rem_after[t] < U:
                        break
                have = [0, 0]
                have[seat], have[1 - seat] = P["have_us"][t], x
                inv2, sold, rev, _ = market_step(item, inv, sells, have)
                if sold[1 - seat] != x:          # x beyond what the orders can take: not a distinct outcome
                    continue
                ro2, ru2 = ro + rev[1 - seat], ru + rev[seat]
                if R is not None and (ro2 > R or ru2 > RU):
                    continue
                if use_cash and not _cash_ok(P, t, rev[seat], rev[1 - seat]):
                    continue
                key = (inv2 - P["draws"][t], uo + x, ro2, ru2)
                npath = path + (x,) if n else path
                if key in new:
                    new[key] = (new[key][0], new[key][1] + cnt)
                else:
                    new[key] = (npath, cnt)
                if len(new) > max_states:
                    truncated = True
                    break
        states = new
        peak = max(peak, len(states))
        if day_end(t):
            if L:
                states = {k: v for k, v in states.items() if k[1] == U and k[2] == R and k[3] == RU}
            if not states:
                return dict(x=x_out, ok=False, fail_tick=t, ambiguous_days=amb, max_states=peak, truncated=truncated)
            # keep one path (the first found: fullest executions earliest); report how many timings fit
            (key, (path, cnt)), = [next(iter(states.items()))]
            nkeys = len(states)
            if cnt > 1 or nkeys > 1:
                amb.append((d, cnt if nkeys == 1 else sum(v[1] for v in states.values())))
            ticks = [tt for tt in range(d * TURNS_PER_DAY, t + 1) if n_opp[tt]]
            for tt, x in zip(ticks, path):
                x_out[tt] = x
            states = {(key[0], 0, 0, 0): ((), 1)}
    return dict(x=x_out, ok=True, fail_tick=None, ambiguous_days=amb, max_states=peak, truncated=truncated)


def trace_opp_sales(case, item, seat):
    """opponent SELL units per tick from the engine-hooked source-control trace (item_trace_20260929.py
    --source-control, x_n18rc8x_src): exact for DSM's own game; for our games only when the opponent's farm is
    unchanged (it can differ slightly: frozen commands that fail differently, e.g. wheat / feed knock-ons)"""
    f = TRACE / f"dsm3q-{str(case).replace('dsm3q-', '')}.items.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text())
    if int(j.get("our_seat", seat)) != seat:
        return None
    x = defaultdict(int)
    for e in j["events"]:
        if e[0] == "sold" and e[1] == 1 - seat and e[5] == item:
            x[int(e[2])] += 1
    inv = {int(r[0]): int(r[10 + GOODS.index(item)]) + MARKET_I0 for r in j.get("market", [])}
    return dict(x=x, inventory=inv)


# ------------------------------------------------------------------------------------------------------ the model
def load_market(case, game, item="STRAWBERRY", opp_source="auto", G=None, A=None):
    """Replay one product's market for a recorded b2b game.

    case: world id ('114393058' or 'dsm3q-114393058'); game: 'dsm' | 'n18rc127.p0' | 'n18rc206d' (.p0 implied) ...
    opp_source: 'auto' | 'orders' | 'infer' | 'trace' | a list of the opponent's executed units per tick.
    Returns a dict of per-tick lists, index t = interpreter step 0..718 (N = 719):
      inventory      market inventory entering step t (its price is the recorded frame price p[t])
      inv_after_mkt  inventory after step t's market phase, before its town consumption
      price          model price(item, inventory[t]);  price_rec  recorded frame price;  match  price == price_rec
      our_sales / opp_sales       executed units in step t  (our_ordered / opp_ordered: requested units)
      our_revenue / opp_revenue   money received for them (every unit at its own lockstep quote)
      draws          town consumption in step t (after the market phase)
      our_shed       our shed units when step t's market opens (frame sh[t], i.e. after step t's unit actions)
      our_in         units entering our shed in step t, net of pickups: our_shed[t] - (our_shed[t-1] - our_sales[t-1]);
                     at t % 24 == 0 this includes the previous midnight's inventory dump (hour-0 units carry nothing)
      our_dump       our_in at the day-start ticks (t % 24 == 0), else 0: the midnight dump of the previous day
      fills          per unit: (t, order index, 'us'|'opp', inventory quoted, price)
    plus: item, case, game, seat, n, opp_source (the one used), inference (diagnostics or None), match_rate,
    mismatch_ticks, daily (per day: side -> (model units, ledger units, model revenue, ledger revenue)), inventory_end.
    """
    if item not in SELL_ONLY:
        raise ValueError(f"{item}: only sell-only goods are modelled (WHEAT / FERTILIZER also have BUY_PRODUCT)")
    if G is None:
        G, A = load_game(case, game)
    P = _prep(G, A, item)
    seat, N = P["seat"], P["N"]
    inference = None
    src = opp_source
    if src == "auto":
        L = P["ledger"]
        full = True
        if L:
            for d, row in enumerate(L):
                ordered = sum(sum(P["sells_opp"][t]) for t in range(d * TURNS_PER_DAY, min(N, (d + 1) * TURNS_PER_DAY)))
                full &= ordered == row["opp"][0]
        src = "orders" if full else "infer"
    if src == "orders":
        cap = [10 ** 9] * N
    elif src == "infer":
        inference = infer_opp_sales(G, A, item, P)
        cap = inference["x"]
    elif src == "trace":
        tr = trace_opp_sales(case, item, seat)
        if tr is None:
            raise FileNotFoundError("no source-control trace for this world / seat")
        cap = [tr["x"].get(t, 0) for t in range(N)]
    else:
        cap = [int(v) for v in opp_source]
        src = "given"
    out = {key: [0] * N for key in ("inventory", "inv_after_mkt", "price", "price_rec", "match", "our_sales",
                                    "opp_sales", "our_ordered", "opp_ordered", "our_revenue", "opp_revenue",
                                    "draws", "our_shed", "our_in", "our_dump")}
    fills = []
    inv = MARKET_I0
    prev_left = 0                                   # our shed after the previous step's market phase
    for t in range(N):
        out["inventory"][t] = inv
        out["price"][t] = price(item, inv)
        out["price_rec"][t] = P["p_rec"][t]
        out["match"][t] = int(out["price"][t] == P["p_rec"][t])
        shed_us = P["have_us"][t]
        out["our_shed"][t] = shed_us
        out["our_in"][t] = shed_us - prev_left
        if t % TURNS_PER_DAY == 0:
            out["our_dump"][t] = out["our_in"][t]
        out["our_ordered"][t], out["opp_ordered"][t] = sum(P["sells_us"][t]), sum(P["sells_opp"][t])
        have = [0, 0]
        have[seat], have[1 - seat] = shed_us, cap[t]
        inv, sold, rev, f = market_step(item, inv, _sells_pair(P, t, seat), have)
        fills.extend((t, i, "us" if pid == seat else "opp", q_inv, q_p) for i, pid, q_inv, q_p in f)
        out["our_sales"][t], out["opp_sales"][t] = sold[seat], sold[1 - seat]
        out["our_revenue"][t], out["opp_revenue"][t] = rev[seat], rev[1 - seat]
        out["inv_after_mkt"][t] = inv
        prev_left = shed_us - sold[seat]
        out["draws"][t] = P["draws"][t]
        inv -= P["draws"][t]
    cash = {}
    for side, key in ((0, "our"), (1, "opp")):
        eq = [out[key + "_revenue"][t] == P["dm"][side][t] for t in range(N - 1) if P["only_item"][side][t]]
        le = [out[key + "_revenue"][t] <= P["dm"][side][t] for t in range(N - 1) if P["no_buy"][side][t]]
        cash[key] = dict(exact_ok=sum(eq), exact_n=len(eq), bound_ok=sum(le), bound_n=len(le))
    out["cash_check"] = cash
    mism = [t for t in range(N) if not out["match"][t]]
    out.update(fills=fills, inventory_end=inv, item=item, case=str(case).replace("dsm3q-", ""), game=game, seat=seat,
               n=N, opp_source=src, inference=inference, match_rate=(N - len(mism)) / N, mismatch_ticks=mism)
    out["daily"] = [dict(day=d, our=(sum(out["our_sales"][d * 24:(d + 1) * 24]), row["us"][0],
                                     sum(out["our_revenue"][d * 24:(d + 1) * 24]), row["us"][1]),
                         opp=(sum(out["opp_sales"][d * 24:(d + 1) * 24]), row["opp"][0],
                              sum(out["opp_revenue"][d * 24:(d + 1) * 24]), row["opp"][1]))
                    for d, row in enumerate(P["ledger"] or [])]
    out["_orders"] = dict(us=P["sells_us"], opp=P["sells_opp"])   # per tick, SELL-<item> units per order index
    return out


def counterfactual(m, our_sales, our_index=None):
    """Re-price an alternative schedule of OUR sales of m's item against the same frozen opponent: the opponent's
    executed units per tick and their order positions stay as in m (its sales follow its shed, not the price), the
    draws stay (fixed schedule). our_sales[t] = units we sell in step t, placed at order index our_index (default:
    the index of our first SELL-<item> order in the recorded step, else 0; a tick whose count equals the recorded one
    keeps its recorded order structure, so counterfactual(m, m['our_sales']) reproduces m exactly).
    Returns per-tick inventory / our_revenue / opp_revenue, totals, margin_delta (our revenue gain minus the
    opponent's revenue gain on this item) and stock_short: ticks where the schedule sells units not yet in our shed
    by m's inflows (our_in); holding units longer can also overflow the 100-unit shed at midnight, not modelled here."""
    N, seat = m["n"], m["seat"]
    inv = MARKET_I0
    res = dict(inventory=[0] * N, our_revenue=[0] * N, opp_revenue=[0] * N, our_sales=[0] * N, opp_sales=[0] * N)
    stock, short = 0, []
    for t in range(N):
        res["inventory"][t] = inv
        stock += m["our_in"][t]
        want = int(our_sales[t])
        rec = m["_orders"]["us"][t]
        if want == m["our_sales"][t]:
            ours = list(rec)
        else:
            idx = our_index if our_index is not None else next((i for i, n in enumerate(rec) if n > 0), 0)
            ours = [0] * (idx + 1)
            ours[idx] = want
        if want > stock:
            short.append(t)
        sells = [None, None]
        sells[seat], sells[1 - seat] = ours, m["_orders"]["opp"][t]
        have = [0, 0]
        have[seat], have[1 - seat] = want, m["opp_sales"][t]
        inv, sold, rev, _ = market_step(m["item"], inv, sells, have)
        stock -= sold[seat]
        res["our_sales"][t], res["opp_sales"][t] = sold[seat], sold[1 - seat]
        res["our_revenue"][t], res["opp_revenue"][t] = rev[seat], rev[1 - seat]
        inv -= m["draws"][t]
    res["our_total"], res["opp_total"] = sum(res["our_revenue"]), sum(res["opp_revenue"])
    res["margin_delta"] = (res["our_total"] - sum(m["our_revenue"])) - (res["opp_total"] - sum(m["opp_revenue"]))
    res["stock_short"] = short
    return res


def summary(m):
    """compact validation numbers for one load_market() result"""
    bad_u = {side: [r["day"] for r in m["daily"] if r[side][0] != r[side][1]] for side in ("our", "opp")}
    bad_r = {side: [r["day"] for r in m["daily"] if r[side][2] != r[side][3]] for side in ("our", "opp")}
    tot = {side: (sum(m[side + "_sales"]), sum(m[side + "_revenue"])) for side in ("our", "opp")}
    rec = {side: (sum(r[side][1] for r in m["daily"]), sum(r[side][3] for r in m["daily"])) for side in ("our", "opp")}
    inf = m.get("inference") or {}
    return dict(item=m["item"], case=m["case"], game=m["game"], seat=m["seat"], opp_source=m["opp_source"],
                price_match=f"{m['n'] - len(m['mismatch_ticks'])}/{m['n']}", mismatch_ticks=m["mismatch_ticks"][:10],
                units_model=tot, units_revenue_recorded=rec, days_units_off=bad_u, days_revenue_off=bad_r,
                ledger_exact=not any(bad_u.values()) and not any(bad_r.values()),
                opp_shortfall=sum(m["opp_ordered"]) - sum(m["opp_sales"]),
                inference_ok=inf.get("ok"), ambiguous_days=inf.get("ambiguous_days"), fail_tick=inf.get("fail_tick"),
                cash_check=m["cash_check"],
                cash_ok=all(c["exact_ok"] == c["exact_n"] and c["bound_ok"] == c["bound_n"] for c in m["cash_check"].values()))


def engine_price_check(items=GOODS, lo=8000, hi=12000):
    """price() == the installed engine's market_price over an inventory range (engine module loaded by path with a
    stub for its one package import, so the kaggle_environments package itself is not imported)"""
    import importlib.util
    import types
    f = ROOT / ".venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py"
    names = ("kaggle_environments", "kaggle_environments.utils")
    saved = {k: sys.modules.get(k) for k in names}
    try:
        if saved[names[0]] is None:
            pkg, utils = types.ModuleType(names[0]), types.ModuleType(names[1])
            utils.resolve_episode_seed = lambda *a, **k: 0
            pkg.utils = utils
            sys.modules[names[0]], sys.modules[names[1]] = pkg, utils
        spec = importlib.util.spec_from_file_location("kg_engine_copy", f)
        E = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(E)
        assert E.MARKET_PARAMS == MARKET_PARAMS and E.SHOPS == SHOPS, "engine constants differ from this copy"
        bad = [(it, v) for it in items for v in range(lo, hi + 1) if E.market_price(it, v) != price(it, v)]
    finally:
        for k_, v_ in saved.items():
            if v_ is None:
                sys.modules.pop(k_, None)
    return len(bad) == 0, bad[:5]


# ------------------------------------------------------------------------------------------------------- __main__
def _line(case, game, item, m, s):
    tr = trace_opp_sales(case, item, s["seat"])
    extra = ""
    if tr is not None and game == "dsm":        # the trace is DSM's own game re-run with engine hooks
        tx = [tr["x"].get(t, 0) for t in range(m["n"])]
        inv_ok = sum(1 for t in range(m["n"]) if tr["inventory"].get(t) == m["inventory"][t])
        extra = (f"  | vs engine trace: opp units/tick {sum(a == b for a, b in zip(tx, m['opp_sales']))}/{m['n']},"
                 f" inventory/tick {inv_ok}/{m['n']}")
    amb = s["ambiguous_days"]
    return (f"{case} {game:12s} {item:10s} seat {s['seat']} opp={s['opp_source']:6s} price {s['price_match']}"
            f"  ledger(2 seats x units+revenue x 30 days) {'exact' if s['ledger_exact'] else 'OFF'}"
            f"  us {s['units_model']['our']} opp {s['units_model']['opp']}"
            + "  cash/tick " + " ".join(f"{k} ={c['exact_ok']}/{c['exact_n']} <={c['bound_ok']}/{c['bound_n']}"
                                         for k, c in s["cash_check"].items())
            + (f"  opp shortfall {s['opp_shortfall']} units" if s["opp_shortfall"] else "")
            + (f"  ambiguous days {amb}" if amb else "")
            + (f"  INFERENCE FAILED at t={s['fail_tick']}" if s["inference_ok"] is False else "")
            + (f"  mismatch ticks {s['mismatch_ticks']}" if s["mismatch_ticks"] else "") + extra)


def _main(argv):
    items = [argv[i + 1] for i, a in enumerate(argv) if a == "--item"] or ["STRAWBERRY", "MILK", "WOOL"]
    if "--all-items" in argv:
        items = list(SELL_ONLY)
    ok, bad = engine_price_check()
    print("price() vs engine market_price, all 9 goods, inventory 8000..12000:", "identical" if ok else f"DIFF {bad}")
    if "--all" in argv:
        tot = defaultdict(lambda: [0] * 7)   # item -> games, ticks matched, ticks, ledger exact, inferred, amb, cash ok
        for f in sorted(B2B.glob("dsm3q-*.game.json.gz")):
            case, game = f.name[len("dsm3q-"):-len(".game.json.gz")].split(".", 1)
            G, A = load_game(case, game)
            if A is None or len(G["frames"]) < 719:
                print("skip", f.name, "(no actions file)" if A is None else "(short)")
                continue
            for item in items:
                m = load_market(case, game, item, G=G, A=A)
                s = summary(m)
                r = tot[item]
                r[0] += 1
                r[1] += m["n"] - len(m["mismatch_ticks"])
                r[2] += m["n"]
                r[3] += int(s["ledger_exact"])
                r[4] += int(s["opp_source"] == "infer")
                r[5] += len(s["ambiguous_days"] or [])
                r[6] += int(s["cash_ok"])
                if not s["ledger_exact"] or m["mismatch_ticks"] or not s["cash_ok"]:
                    print(_line(case, game, item, m, s))
        for item, r in tot.items():
            print(f"{item:10s} games {r[0]}  price ticks {r[1]}/{r[2]}  ledger exact {r[3]}/{r[0]}  opp inferred in"
                  f" {r[4]} games  ambiguous days {r[5]}  per-tick cash consistent {r[6]}/{r[0]}")
        return
    cases = [a for a in argv if a.isdigit()] or ["114393058", "114433787"]
    games = [argv[i + 1] for i, a in enumerate(argv) if a == "--game"] or ["dsm", "n18rc127.p0"]
    for case in cases:
        for game in games:
            try:
                G, A = load_game(case, game)
            except FileNotFoundError as e:
                print(case, game, "missing:", e)
                continue
            for item in items:
                for src in ("orders", "auto"):
                    m = load_market(case, game, item, opp_source=src, G=G, A=A)
                    if src == "auto" and m["opp_source"] == "orders":
                        continue                    # identical to the line above
                    print(_line(case, game, item, m, summary(m)))


if __name__ == "__main__":
    _main(sys.argv[1:])
