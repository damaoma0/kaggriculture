"""Wool / milk timeline viewer data (2026-09-30, user: "a visualizer on one single game of us and DSM vs a strong opponent
with us and their wool ready time and delivered time, sale time, amount and prices ... zoom in ... same for milk").

Source: the back-to-back games in results/fresh/semantic_h2h_20260929/b2b/ - DSM's recorded game against a strong recorded
opponent ('dsm') and our arm playing DSM's seat against the SAME frozen opponent ('<arm>.p0', prefix 0 = our arm from
step 0). Per tick t (interpreter step 0..718; frame t = after step t's unit actions, before its market phase):
  ready      units produced on our animals (yield increase on an animal tile; shows at hour 0 = the night's production)
  collected  units harvested off the animals (yield decrease) into a hand / the farmer
  delivered  units entering the shed (strawberry_market_20260930.load_market our_in; hour 0 = the midnight dump)
  sold       executed units, revenue, per-unit prices and order indices (exact lockstep market replay, load_market fills)
  lost       units collected but not in the shed after the midnight dump (shed cap 100: the engine drops the overflow)
  held       units on the animals / carried / in the shed
plus the opponent's sales in each game, the market price in each game, town draws, shop reveals, and per day the herd
(animals, fed, cared, banked care bonus at the day's last frame). FIFO ages: hours from production to sale / delivery.

usage: .venv/Scripts/python.exe scripts/goods_timeline_viz_20260930.py  [writes viz/goods_timeline.html]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import strawberry_market_20260930 as SM  # noqa: E402

B2B = ROOT / "results/fresh/semantic_h2h_20260929/b2b"
TEMPLATE = ROOT / "viz/goods_timeline_template.html"
OUT = ROOT / "viz/goods_timeline.html"
ANIMAL = {"WOOL": "SHEEP", "MILK": "COW"}
ANIMAL_SPEC = {"COW": dict(first_yield_day=8, interval=2, max_held=6),        # kaggriculture.py 1.32.7 ANIMALS
               "SHEEP": dict(first_yield_day=6, interval=3, max_held=6)}
BUYERS = {p: sorted(s for s, prods in SM.SHOPS.items() if p in prods) for p in ("WOOL", "MILK", "STRAWBERRY")}
ARM_LABEL = {
    "dsm": "DSM (recorded)",
    "n18rc216d": "rc216 = rc163 + strawberry sale rule (current best)",
    "n18rc222d": "rc222 = rc216 + milk sale rule",
    "n18rc223d": "rc223 = rc216 + milk & wool sale rules",
    "n18rc224d": "rc224 = rc216 + wool sale rule",
    "n18rc228d": "rc228 = rc216 + DSM reveal-day sheep rule x1",
    "n18rc229d": "rc229 = rc216 + DSM reveal-day sheep rule x1.5",
    "n18rc230d": "rc230 = rc216 + DSM reveal-day sheep rule x2",
    "n18rc163d": "rc163 (day-8 quadrant + wheat)",
    "n18rc219d": "rc219 = rc163 + strawberry-buyer cassette",
    "n18rc215d": "rc215 = rc163 + pickup + sheep + strawberry rule",
    "n18rc127.p0": "rc127 (packaged n18rc127s)",
}
WORLDS = ["114393058", "114514221", "114433787", "114432897", "114479550", "114537918", "114448465", "114523301",
          "114600746"]
ARM_ORDER = ["n18rc216d", "n18rc223d", "n18rc222d", "n18rc224d", "n18rc228d", "n18rc229d", "n18rc230d", "n18rc163d", "n18rc219d", "n18rc215d", "n18rc127.p0"]


def available(world):
    out = []
    for a in ARM_ORDER:
        g = a if ".p" in a else a + ".p0"
        if (B2B / f"dsm3q-{world}.{g}.game.json.gz").exists():
            out.append(a)
    return out


def sparse(xs):
    return {str(t): v for t, v in enumerate(xs) if v}


PRODUCTS = {"WOOL": ("animal", "SHEEP"), "MILK": ("animal", "COW"), "STRAWBERRY": ("crop", "STRAWBERRY")}
CROP_SPEC = {"STRAWBERRY": dict(first_yield_day=10, interval=2, max_yield=4)}      # kaggriculture.py 1.32.7 CROPS


def animal_flows(F, T, N, animal):
    """per tick: production (engine _daily_refresh_animals on the day's last frame; shows at hour 0), tile-cap loss,
    harvest; units on the animals; per day at the day's last frame [animals, fed, cared, banked bonus]"""
    prod, harv, capped, held = [0] * N, [0] * N, [0] * N, [0] * N
    spec = ANIMAL_SPEC[animal]
    for t in range(N):
        b = F[t]["b"]
        tot = 0
        for k in range(len(b)):
            x1 = T[b[k]]
            if isinstance(x1, dict) and x1.get("animal") == animal:
                y1 = int(x1.get("yield_units", 0) or 0)
                tot += y1
                if t > 0:
                    x0 = T[F[t - 1]["b"][k]]
                    if isinstance(x0, dict) and x0.get("animal") == animal:
                        y0 = int(x0.get("yield_units", 0) or 0)
                        if t % 24 == 0:
                            # production first (1 + banked bonus if fed), capped at max_held; a harvest in step t (hour 0)
                            # is what is missing from the refreshed yield
                            day = t // 24 - 1
                            since = day + 1 - int(x0.get("placed_day", 0) or 0) - spec["first_yield_day"]
                            y_ref = y0
                            if since >= 0 and since % spec["interval"] == 0:
                                bonus = int(x0.get("pending_care_bonus", 0) or 0) if x0.get("fed_today") else 0
                                y_ref = min(spec["max_held"], y0 + 1 + bonus)
                                prod[t] += y_ref - y0
                                capped[t] += y0 + 1 + bonus - y_ref
                            harv[t] += max(0, y_ref - y1)
                        elif y1 < y0:
                            harv[t] += y0 - y1
        held[t] = tot
    herd = []
    for d in range(N // 24 + 1):
        t = min(N - 1, d * 24 + 23)
        n_a = fed = cared = bank = 0
        for k in F[t]["b"]:
            x = T[k]
            if isinstance(x, dict) and x.get("animal") == animal:
                n_a += 1
                fed += bool(x.get("fed_today"))
                cared += bool(x.get("cared_today"))
                bank += int(x.get("pending_care_bonus", 0) or 0)
        herd.append([n_a, fed, cared, bank])
    return dict(prod=prod, harv=harv, capped=capped, held=held, herd=herd)


def crop_flows(F, T, N, crop):
    """per tick for an ongoing crop, replaying the engine between frame t-1 and frame t (step t-1's _decay_plants after
    its market, the day-end _daily_refresh_plants when t is hour 0, then step t's unit actions): planted tiles,
    production (1, or 2 when watered and fertilized that day; at most max_yield productions; held yield capped at
    max_yield), cap loss, rot (a unit lost every 2 steps from the lifespan end after the last production) and units lost
    with a plant that turned to weed (two days unwatered / rotted to 0) or was removed, harvest (every other drop).
    Per day at the day's last frame [plants, watered, fertilized, producing]; per tick plants and weed tiles."""
    sp = CROP_SPEC[crop]
    prod, harv, capped, held, planted, rot = ([0] * N for _ in range(6))
    plants, weeds = [0] * N, [0] * N

    def is_p(x):
        return isinstance(x, dict) and x.get("kind") == "PLANT" and x.get("crop") == crop

    for t in range(N):
        b = F[t]["b"]
        for k in range(len(b)):
            x1 = T[b[k]]
            if isinstance(x1, dict) and x1.get("kind") == "WEED":
                weeds[t] += 1
            if is_p(x1):
                plants[t] += 1
                held[t] += int(x1.get("yield_units", 0) or 0)
            if t == 0:
                continue
            x0 = T[F[t - 1]["b"][k]]
            same = is_p(x0) and is_p(x1) and x0.get("planted_day") == x1.get("planted_day")
            if is_p(x1) and not same:
                planted[t] += 1
            if not is_p(x0):
                continue
            y = int(x0.get("yield_units", 0) or 0)
            alive = True
            mls = int(x0.get("max_lifespan_step", -1))
            if mls >= 0 and t - 1 >= mls and (t - 1 - mls) % 2 == 0:
                if y > 0:
                    rot[t] += 1
                y -= 1
                if y <= 0:
                    alive, y = False, 0
            if alive and t % 24 == 0:
                day = t // 24 - 1
                watered = bool(x0.get("watered_today"))
                cu = 0 if watered else int(x0.get("consecutive_unwatered", 0) or 0) + 1
                if cu >= 2:
                    alive = False                           # turns to weed at the day end: its units are lost below
                else:
                    since = day + 1 - int(x0.get("planted_day", 0) or 0) - sp["first_yield_day"]
                    if since >= 0 and since % sp["interval"] == 0 and since // sp["interval"] + 1 <= sp["max_yield"]:
                        add = 2 if (watered and int(x0.get("fertilized_until_day", -1)) >= day) else 1
                        y2 = min(sp["max_yield"], y + add)
                        prod[t] += y2 - y
                        capped[t] += y + add - y2
                        y = y2
            if same:
                y1 = int(x1.get("yield_units", 0) or 0)
                if y1 < y:
                    harv[t] += y - y1
            else:
                rot[t] += y                                 # the plant is gone (weed / dug / replaced): its units lost
    herd = []
    for d in range(N // 24 + 1):
        t = min(N - 1, d * 24 + 23)
        n = w = f = pr = 0
        for k in F[t]["b"]:
            x = T[k]
            if is_p(x):
                n += 1
                w += bool(x.get("watered_today"))
                f += int(x.get("fertilized_until_day", -1)) >= d
                since = d + 1 - int(x.get("planted_day", 0) or 0) - sp["first_yield_day"]
                pr += since >= 0 and since // sp["interval"] + 1 <= sp["max_yield"]
        herd.append([n, w, f, pr])
    return dict(prod=prod, harv=harv, capped=capped, held=held, herd=herd, planted=planted, rot=rot, plants=plants,
                weeds=weeds)


def build_game(world, game):
    G, A = SM.load_game(world, game)
    F, T = G["frames"], G["tiles"]
    N = len(F)
    assert all(F[i]["t"] == i for i in range(N)), "frames not indexed by step"
    seat = G["seat"]
    res = dict(label=ARM_LABEL.get(game, game), cash=G["cash"], opp_cash=G["opp_cash"], margin=G["margin"], products={})
    # shop reveals (the list step t's town consumption uses)
    reveals, prev = [], []
    for t in range(N):
        s = list(F[t]["s"])
        if len(s) > len(prev):
            for name in s[len(prev):]:
                reveals.append([t, name])
        prev = s
    res["reveals"] = reveals
    for item, (kind, src) in PRODUCTS.items():
        m = SM.load_market(world, game, item, G=G, A=A)
        fl = animal_flows(F, T, N, src) if kind == "animal" else crop_flows(F, T, N, src)
        prod, harv, capped, onani, herd = fl["prod"], fl["harv"], fl["capped"], fl["held"], fl["herd"]
        rot = fl.get("rot", [0] * N)
        arr = list(m["our_in"])
        sold, rev = list(m["our_sales"]), list(m["our_revenue"])
        # carried = collected but not yet in the shed; after the midnight dump anything still "carried" was lost
        carried, lost = [0] * N, [0] * N
        c = 0
        for t in range(N):
            if t > 0 and t % 24 == 0:
                # the midnight dump (arr[t] at hour 0) empties every hand: what it did not bring in was dropped (shed full)
                lost[t] = max(0, c - max(0, arr[t]))
                c = harv[t]
            else:
                c += harv[t] - max(0, arr[t])
            carried[t] = max(0, c)
        # per-unit fills -> per tick price range and order indices, per side
        px = {"us": {}, "opp": {}}
        for (t, idx, side, _inv, p) in m["fills"]:
            d = px[side].setdefault(t, [p, p, set()])
            d[0], d[1] = min(d[0], p), max(d[1], p)
            d[2].add(idx)
        pxo = {s: {str(t): [v[0], v[1], sorted(v[2])] for t, v in px[s].items()} for s in px}
        # FIFO ages: production tick -> sale / delivery tick (units present before the first frame count from 0)
        def fifo(outflow, extra_out=None):
            q, ages = [], [0] * N
            first = onani[0]
            if first:
                q.append([0, first])
            for t in range(N):
                if prod[t]:
                    q.append([t, prod[t]])
                for series in ([outflow] + ([extra_out] if extra_out else [])):
                    n = series[t]
                    agesum = 0
                    while n > 0 and q:
                        take = min(n, q[0][1])
                        agesum += take * (t - q[0][0])
                        q[0][1] -= take
                        n -= take
                        if q[0][1] == 0:
                            q.pop(0)
                    if series is outflow:
                        ages[t] = agesum
            return ages
        age_sold = fifo(sold, [a + b for a, b in zip(lost, rot)])
        age_del = fifo([max(0, a) for a in arr])
        daily = [[r["our"][0], r["our"][2], r["opp"][0], r["opp"][2]] for r in m["daily"]]
        res["products"][item] = dict(
            price=list(m["price_rec"]), shed=list(m["our_shed"]), onani=onani, carried=carried,
            prod=sparse(prod), harv=sparse(harv), arr=sparse([max(0, a) for a in arr]), lost=sparse(lost), capped=sparse(capped),
            sold=sparse(sold), rev=sparse(rev), osold=sparse(m["opp_sales"]), orev=sparse(m["opp_revenue"]),
            px=pxo["us"], opx=pxo["opp"], draws=sparse(m["draws"]), age_sold=sparse(age_sold), age_del=sparse(age_del),
            herd=herd, daily=daily, seat=seat, kind=kind,
            planted=sparse(fl.get("planted", [0] * N)), rot=sparse(rot), plants=fl.get("plants"), weeds=fl.get("weeds"),
            totals=dict(prod=sum(prod) + onani[0], sold=sum(sold), rev=sum(rev), osold=sum(m["opp_sales"]),
                        orev=sum(m["opp_revenue"]), lost=sum(lost), capped=sum(capped), rot=sum(rot),
                        planted=sum(fl.get("planted", [0] * N)), match=m["match_rate"]))
    return res


def main():
    data = dict(buyers=BUYERS, worlds={})
    for w in WORLDS:
        arms = available(w)
        if not arms:
            continue
        games = {"dsm": build_game(w, "dsm")}
        for a in arms:
            games[a] = build_game(w, a)
        G, _ = SM.load_game(w, "dsm")
        data["worlds"][w] = dict(shops=G["shops"], dsm_seat=G["seat"], arms=arms, games=games)
        print(w, "arms", arms, flush=True)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
