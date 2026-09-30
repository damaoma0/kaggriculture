"""xopen: opening facts for the exact-following design (stored data only, no games). Thread xopen, 2026-09-25.

(a) the day-0 exemplar's plan (DSM seat of 112655730) days 0-12: cash, reinvestment by kind, hands, plantings,
    animals, builds, digs, failed orders in its own world (G1 ledger results/fresh/lead_ledger/leader_112655730.json,
    correctly dated; semantics for tiles), its SE-quadrant work
(b) how shop-dependent the leaders' openings are: board Hamming to the team medoid by day; animal / strawberry
    counts at day 11 by the shops revealed by day 9
(c) the compatible re-retrieval pool: corpus games within Hamming <= 0/2/4/8 of the exemplar's board on days 3/6/9
(d) what the deploy's day-3/6/9 retrieval does in the 185 p2750 worlds (mgt_lpv_tievalff 'switches'): Hamming of
    the retrieved game to the exemplar on the switch day and 3 days later
(e) weeds: expected weed spawns on the exemplar's empty unlocked tiles days 0-10 (p = 0.005 / tile / day) and how
    many of those tiles the plan uses by day 12; the exemplar's own DIGs
(f) the exemplar's plan carried with lower revenue: uniform haircuts and the 185 worlds' own revenue ratios
    (proxy: the deploy's revenue, which follows the exemplar only on days 0-2): deferred coins by day

usage: .venv/Scripts/python.exe scripts/xopen_open_stats.py   -> results/fresh/xopen_20260925/open_stats.txt/.json
"""
import gzip
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import leader_plan_retrieval as lpr  # noqa: E402
import xopen_cash_safe as xcs  # noqa: E402

OUT = ROOT / "results/fresh/xopen_20260925"
EX_TEAM, EX_EP = "16732748", 112655730
LINES = []
SHOP_PROD = {"YARN_STORE": "WOOL", "BAKERY": "EGG", "BRUNCH_SPOT": "EGG", "PIZZA_SHOP": "MILK",
             "ICE_CREAM_SHOP": "MILK", "SMOOTHIE_SHOP": "MILK"}


def say(s=""):
    LINES.append(s)
    print(s)


def quad(i):
    x, y = i % 10, i // 10
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def pct(xs, q):
    return xcs.pct(xs, q)


def exemplar():
    say("== (a) EXEMPLAR PLAN, DSM seat of 112655730, days 0-12 (its own world; ledger = correctly dated)")
    L = json.loads((ROOT / ("results/fresh/lead_ledger/leader_%d.json" % EX_EP)).read_text(encoding="utf-8"))
    s = json.load(gzip.open(ROOT / "data/leader_semantics" / EX_TEAM / ("%d.json.gz" % EX_EP), "rt", encoding="utf-8"))
    say("day   cash    rev  seeds anim  land wheat fert wages hands | planted | animals placed | built | dug | failed orders (own world)")
    for t in range(13):
        x = L["days"][t]
        sp = Counter()
        for k, v in x["spend"].items():
            kind, item = k.split(":")
            sp["seeds" if kind == "BUY_SEED" else "anim" if kind == "BUY_ANIMAL" else item.lower()] += v
        sd = s["days"][t]
        planted = {c[:2]: len(v) for c, v in sd["planted"].items() if v}
        placed = Counter(s["days"][t + 1]["board"][i] for i in sd["animals"]["placed"]) if t < 29 else {}
        built = {k[6:9]: len(v) for k, v in sd["built"].items() if v}
        say("%3d %6.0f %6.0f %5.0f %5.0f %5.0f %5.0f %4.0f %5.0f %5d | %s | %s | %s | %d | %s" % (
            t, x["cash"], sum(x["rev"].values()), sp["seeds"], sp["anim"], x["land"], sp["wheat"], sp["fertilizer"],
            x["wages"], sd["labour"]["hands_present"], planted, dict(placed), built, len(sd["dug"]),
            {k.split(":")[1][:5]: v for k, v in x["failed"].items()}))
    se = defaultdict(list)
    for t in range(9, 16):
        sd = s["days"][t]
        for c, v in sd["planted"].items():
            n = sum(1 for i in v if quad(i) == "SE")
            if n:
                se[t].append("%s x%d" % (c[:2], n))
        for k, v in sd["built"].items():
            n = sum(1 for i in v if quad(i) == "SE")
            if n:
                se[t].append("%s x%d" % (k, n))
    say("SE-quadrant work (bought day 10 for 4000): " + "; ".join("d%d %s" % (t, ", ".join(v)) for t, v in sorted(se.items())))
    # total unit-days ops the plan puts on SE by day 15
    tot_fail = sum(sum(L["days"][t]["failed"].values()) for t in range(11))
    say("failed buy orders in its own world days 0-10: %d (the leader over-asks; the engine drops what cash cannot pay)" % tot_fail)
    return L, s


def variability():
    say("\n== (b) HOW SHOP-DEPENDENT ARE THE OPENINGS (corpus boards, day-start labels)")
    G = lpr.load_corpus()
    teams = sorted({g["team_id"] for g in G})
    say("median Hamming of a game's board to its team medoid (min total Hamming) on day d; p90 in brackets")
    say("team        " + " ".join("   d%-2d    " % d for d in (3, 6, 9, 11, 12)))
    for tm in teams:
        gs = [g for g in G if g["team_id"] == tm]
        row = []
        for d in (3, 6, 9, 11, 12):
            bs = [g["boards"][d] for g in gs]
            med = min(bs, key=lambda b: sum(lpr.hamming(b, c) for c in bs))
            hs = [lpr.hamming(b, med) for b in bs]
            row.append("%4.1f (%2d)" % (st.median(hs), pct(hs, 0.9)))
        say("%-10s  %s" % (tm, "  ".join(row)))
    # exemplar distance to DSM games
    ex = [g for g in G if g["team_id"] == EX_TEAM and g["episode"] == EX_EP][0]
    dsm = [g for g in G if g["team_id"] == EX_TEAM and g["episode"] != EX_EP]
    say("DSM games vs the exemplar board: " + ", ".join(
        "d%d median %d (p10 %d, p90 %d)" % (d, st.median([lpr.hamming(g["boards"][d], ex["boards"][d]) for g in dsm]),
                                           pct([lpr.hamming(g["boards"][d], ex["boards"][d]) for g in dsm], 0.1),
                                           pct([lpr.hamming(g["boards"][d], ex["boards"][d]) for g in dsm], 0.9))
        for d in (3, 6, 9, 11)))
    # shop conditioning: counts at day 11 by the shops revealed by day 9 (shops[0..2] revealed days 3/6/9)
    say("counts on the day-11 board by whether a demand shop was revealed by day 9 (all 540 games; mean with / without, n with):")
    for lab, prod in (("sh", "WOOL"), ("go", "EGG"), ("co", "MILK"), ("ST", "STRAWBERRY"), ("TO", "TOMATO"), ("CA", "CARROT")):
        wth, wo = [], []
        for g in G:
            seen = g["shops"][:3] if "shops" in g else []
            dem = any(prod in lpr_dem(sh) for sh in seen)
            n = sum(1 for x in g["boards"][11] if x == lab)
            (wth if dem else wo).append(n)
        say("  %-2s (%-10s): %5.2f / %5.2f  (n %d / %d)" % (lab, prod, st.mean(wth) if wth else float("nan"),
                                                         st.mean(wo) if wo else float("nan"), len(wth), len(wo)))
    return G, ex


_DEM = {'BAKERY': ('EGG', 'WHEAT'), 'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'), 'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'),
        'YARN_STORE': ('WOOL',), 'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'), 'PET_CAFE': ('CARROT',),
        'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'), 'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY')}


def lpr_dem(shop):
    return _DEM.get(shop, ())


def pool(G, ex):
    say("\n== (c) COMPATIBLE RE-RETRIEVAL POOL: corpus games (other than the exemplar, any team) whose board on day d is")
    say("   within Hamming k of the exemplar's board on day d (an exact follower's board ~ the exemplar's)")
    out = {}
    for d in (3, 6, 9):
        hs = [(lpr.hamming(g["boards"][d], ex["boards"][d]), g) for g in G if not (g["team_id"] == EX_TEAM and g["episode"] == EX_EP)]
        row = []
        for k in (0, 2, 4, 8):
            sel = [g for h, g in hs if h <= k]
            row.append("k<=%d: %3d games (%s)" % (k, len(sel), ", ".join("%s %d" % (t, n) for t, n in sorted(Counter(g["team_id"] for g in sel).items()))))
        say("  day %d: " % d + " | ".join(row))
        out[d] = {k: sum(1 for h, _ in hs if h <= k) for k in (0, 2, 4, 8)}
    return out


def deploy_switches(G, ex):
    say("\n== (d) THE DEPLOY'S RETRIEVAL IN THE 185 p2750 WORLDS (mgt_lpv_tievalff 'switches')")
    idx = {(g["team_id"], g["episode"]): g for g in G}
    byep = defaultdict(list)
    for g in G:
        byep[g["episode"]].append(g)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "results/fresh/ladder_panel/mgt_lpv_tievalff").glob("*.json")]
    stats = defaultdict(list)
    same = Counter()
    for r in rows:
        for d, ep in r.get("switches") or []:
            if d == 0:
                continue
            gs = byep.get(ep) or []
            if not gs:
                continue
            g = gs[0]
            stats[d].append((lpr.hamming(g["boards"][d], ex["boards"][d]), lpr.hamming(g["boards"][min(29, d + 3)], ex["boards"][min(29, d + 3)])))
            same[(d, g["team_id"] == EX_TEAM)] += 1
    for d in sorted(stats):
        a = [x for x, _ in stats[d]]
        b = [y for _, y in stats[d]]
        say("  day %d: %3d switches; Hamming retrieved vs exemplar on day %d median %d (p10 %d, p90 %d), on day %d median %d (p90 %d); "
            "same team as exemplar %d; within 2 tiles on the switch day %d" % (
                d, len(a), d, st.median(a), pct(a, 0.1), pct(a, 0.9), d + 3, st.median(b), pct(b, 0.9), same[(d, True)],
                sum(1 for x in a if x <= 2)))
    return {d: dict(n=len(v), med=st.median([x for x, _ in v])) for d, v in stats.items()}


def weeds(s):
    say("\n== (e) WEEDS on the exemplar's plan (p = 0.005 per empty unlocked tile per day; engine rule)")
    days = s["days"]
    exp = 0.0
    used_exp = 0.0
    later_used = defaultdict(set)
    for t in range(0, 13):
        for c, v in days[t]["planted"].items():
            for i in v:
                later_used[t].add(i)
        for k, v in days[t]["built"].items():
            for i in v:
                later_used[t].add(i)
    for t in range(0, 11):
        b = days[t + 1]["board"]           # a weed spawns at the night of day t on tiles empty then
        empty = [i for i in range(100) if b[i] == " ."]
        exp += 0.005 * len(empty)
        used = [i for i in empty if any(i in later_used[u] for u in range(t + 1, 13))]
        used_exp += 0.005 * len(used)
    dug = sum(len(days[t]["dug"]) for t in range(11))
    say("  expected weed spawns on its empty tiles, nights 0-10: %.2f a game; on tiles it plants / builds on by day 12: %.2f" % (exp, used_exp))
    say("  the exemplar's own DIGs days 0-10: %d (in a new world they meet no weed; DIG on an empty tile is a no-op)" % dug)
    return dict(expected=exp, on_used=used_exp, dug=dug)


def shortfall(L):
    say("\n== (f) THE EXEMPLAR'S PLAN CARRIED WITH LOWER REVENUE (effective reinvestment R fixed, days 0-10; deferred")
    say("   purchases retried the next day; wages / feed are part of R, so this is the load the failsafe must cut)")
    days = L["days"]
    V = [float(sum(d["rev"].values())) for d in days]
    R = [float(sum(d["spend"].values())) + d["wages"] + d["land"] for d in days]

    def carry(rho, last=10):
        C, carry_, out = 3000.0, 0.0, []
        for t in range(0, last + 1):
            need = R[t] + carry_
            avail = C + rho[t] * V[t]
            cut = max(0.0, need - avail)
            spent = need - cut
            C = avail - spent
            carry_ = cut
            out.append(cut)
        return out, C
    say("  uniform haircut h on every day's revenue: deferred coins at the end of day t (days 0-10), cash day 11")
    say("  h     " + " ".join("%6d" % t for t in range(11)) + "   C11")
    res = {}
    for h in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3):
        cuts, C = carry([1 - h] * 30)
        res[h] = cuts
        say("  %.2f  " % h + " ".join("%6.0f" % c for c in cuts) + "  %5.0f" % C)
    say("  same without the day-10 SE quadrant (land_max 2: R[10] - 4000):")
    R10 = R[10]
    R[10] = R10 - 4000.0
    for h in (0.05, 0.1, 0.15, 0.2, 0.3):
        cuts, C = carry([1 - h] * 30)
        res["noSE_%g" % h] = cuts
        say("  %.2f  " % h + " ".join("%6.0f" % c for c in cuts) + "  %5.0f" % C)
    R[10] = R10
    # per-world revenue ratio proxy from the 185 panel (the deploy's own revenue; days 0-2 = exemplar opening)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "results/fresh/ladder_panel/mgt_lpv_tievalff").glob("*.json")]
    worst = []
    anycut = Counter()
    maxcut = []
    for r in rows:
        cum = r["revenue_daily"]
        ours = [sum(cum[min(t + 1, len(cum) - 1)].values()) - sum(cum[min(t, len(cum) - 1)].values()) for t in range(12)]
        # pool days 0-1 (the deploy sells nothing on day 0), ratio capped to [0.5, 1.5]
        rho = [1.0] * 30
        r01 = (ours[0] + ours[1]) / max(1.0, V[0] + V[1])
        rho[0] = rho[1] = max(0.5, min(1.5, r01))
        for t in range(2, 11):
            rho[t] = max(0.5, min(1.5, ours[t] / max(1.0, V[t])))
        cuts, C = carry(rho)
        for t, c in enumerate(cuts):
            if c > 1:
                anycut[t] += 1
        maxcut.append(max(cuts))
        worst.append(C)
    say("  185 worlds, per-world revenue ratio (proxy): share of worlds with deferred purchases at the end of day t:")
    say("        " + " ".join("%5.0f%%" % (100.0 * anycut[t] / len(rows)) for t in range(11)))
    say("  largest deferred amount in a world: median %.0f, p90 %.0f, max %.0f; cash at day 11 median %.0f, p10 %.0f" % (
        st.median(maxcut), pct(maxcut, 0.9), max(maxcut), st.median(worst), pct(worst, 0.1)))
    return dict(uniform={str(k): v for k, v in res.items()}, panel_anycut={str(k): v for k, v in anycut.items()},
                panel_maxcut=maxcut, panel_c11=worst)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L, s = exemplar()
    G, ex = variability()
    pl = pool(G, ex)
    sw = deploy_switches(G, ex)
    wd = weeds(s)
    sf = shortfall(L)
    (OUT / "open_stats.json").write_text(json.dumps(dict(pool=pl, switches=sw, weeds=wd, shortfall=sf)), encoding="utf-8")
    (OUT / "open_stats.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------------------------------------ strict pool
def _state(sem, d):
    """day-start state key of day d: per tile (label, day the crop was planted / the animal placed on it)."""
    last = {}
    for t in range(d):
        day = sem["days"][t]
        for c, v in day["planted"].items():
            for i in v:
                last[i] = t
        for i in day["animals"]["placed"]:
            last[i] = t
    b = sem["days"][d]["board"]
    key = []
    for i in range(100):
        lab = b[i]
        if lab in (" .", " L") or lab in ("pa", "co") and i not in last:
            key.append((lab, None))
        else:
            key.append((lab, last.get(i)))
    return key


def strict_pool():
    say("\n== (g) STRICT COMPATIBILITY at day start (label AND planting / placement day on every tile) with the exemplar;")
    say("   only such a game can take over the exact replay at that day's hour 0 (all units respawn at the shed)")
    import glob
    ex = json.load(gzip.open(ROOT / "data/leader_semantics" / EX_TEAM / ("%d.json.gz" % EX_EP), "rt", encoding="utf-8"))
    exk = {d: _state(ex, d) for d in range(3, 12)}
    rows = defaultdict(list)
    cash = defaultdict(list)
    for f in sorted(glob.glob(str(ROOT / "data/leader_semantics" / "*" / "*.json.gz"))):
        g = json.load(gzip.open(f, "rt", encoding="utf-8"))
        tm = Path(f).parent.name
        if tm == EX_TEAM and g["meta"]["episode"] == EX_EP:
            continue
        for d in range(3, 12):
            k = _state(g, d)
            diff = sum(1 for a, b in zip(k, exk[d]) if a != b)
            rows[d].append((diff, tm))
            if diff == 0:
                cash[d].append(g["days"][d]["cash_start"])
    say("   day: games with 0 / <= 2 differing tiles (by team for 0)")
    out = {}
    for d in range(3, 12):
        z = [tm for x, tm in rows[d] if x == 0]
        two = sum(1 for x, _ in rows[d] if x <= 2)
        say("   d%-2d  %3d / %3d   %s   cash of the exact matches: median %s (exemplar %.0f)" % (
            d, len(z), two, dict(Counter(z)), ("%.0f" % st.median(cash[d])) if cash[d] else "-", ex["days"][d]["cash_start"]))
        out[d] = dict(exact=len(z), le2=two, teams=dict(Counter(z)))
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    LINES.clear()
    sp = strict_pool()
    (OUT / "open_stats_strict.json").write_text(json.dumps(sp), encoding="utf-8")
    (OUT / "open_stats_strict.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ tape stats
def tape_stats(last_day=12):
    """the exemplar's recorded per-step stream, days 0..last_day: hires asked / arrived (hands list growth), unit-steps,
    PASS (slack available for repairs), tile ops, moves, market orders."""
    say("\n== (h) THE EXEMPLAR'S RECORDED STREAM (data/leader_tapes/16732748_56498734/112655730.json.gz), per day")
    import lead_route_order as lro
    tp = json.load(gzip.open(ROOT / "data/leader_tapes/16732748_56498734/112655730.json.gz", "rt", encoding="utf-8"))
    A = tp["actions"]
    say("day  HIRE asked (hours)            arrived  hands  unit-steps  PASS  tile-ops  moves  shed-ops | market: SELL BUY_SEED BUY_ANIMAL BUY_PRODUCT LAND")
    out = []
    for d in range(last_day + 1):
        asked, hours, us, pas, ops, mv, shed = 0, Counter(), 0, 0, 0, 0, 0
        mk = Counter()
        prev = 0
        arrived = 0
        for h in range(24):
            t = d * 24 + h
            a = A[t] if t < len(A) and isinstance(A[t], dict) else {}
            hands = a.get("hands") or []
            if h > 0 and len(hands) > prev:
                arrived += len(hands) - prev
            prev = len(hands)
            units = [a.get("farmer") or ["PASS"]] + list(hands)
            us += len(units)
            for u in units:
                op = u[0] if isinstance(u, list) and u else "PASS"
                if op == "PASS":
                    pas += 1
                elif op in lro.MOVES:
                    mv += 1
                elif op in ("PICKUP", "DROP") or (op == "PLACE" and len(u) > 1 and u[1] in ("WHEAT", "FERTILIZER", "EGG", "MILK", "WOOL")):
                    shed += 1
                else:
                    ops += 1
            for o in (a.get("market") or [])[:10]:
                if not o:
                    continue
                if o[0] == "HIRE":
                    asked += 1
                    hours[h] += 1
                else:
                    mk[o[0]] += 1
        say("%3d  %3d %-26s %5d  %5d  %9d  %4d  %8d  %5d  %8d | %4d %8d %10d %11d %4d" % (
            d, asked, dict(sorted(hours.items())), arrived, prev, us, pas, ops, mv, shed, mk["SELL"], mk["BUY_SEED"],
            mk["BUY_ANIMAL"], mk["BUY_PRODUCT"], mk["BUY_LAND"]))
        out.append(dict(day=d, asked=asked, arrived=arrived, unit_steps=us, passes=pas, ops=ops, moves=mv))
    return out


if __name__ == "__main__":
    LINES.clear()
    ts = tape_stats()
    (OUT / "open_stats_tape.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ pool diversity
def pool_diversity():
    """among the games strictly compatible with the exemplar at day 6 (the day-6 re-retrieval pool): what they do on
    days 6-10 depending on the first two shops (revealed days 3 and 6), read off the day-11 board."""
    say("\n== (i) THE DAY-6 POOL (strictly compatible with the exemplar at day-6 start): day-11 board by the first two shops")
    import glob
    ex = json.load(gzip.open(ROOT / "data/leader_semantics" / EX_TEAM / ("%d.json.gz" % EX_EP), "rt", encoding="utf-8"))
    k6 = _state(ex, 6)
    pool_ = []
    for f in sorted(glob.glob(str(ROOT / "data/leader_semantics" / "*" / "*.json.gz"))):
        g = json.load(gzip.open(f, "rt", encoding="utf-8"))
        if _state(g, 6) == k6:
            pool_.append(g)
    say("  pool size incl. the exemplar: %d" % len(pool_))
    for lab, prod in (("sh", "WOOL"), ("go", "EGG"), ("co", "MILK"), ("ST", "STRAWBERRY"), ("TO", "TOMATO"), ("CA", "CARROT"), ("WH", "WHEAT")):
        wth, wo = [], []
        for g in pool_:
            seen = [s["shop"] for s in g["shops"][:2]]
            dem = any(prod in lpr_dem(sh) for sh in seen)
            n = sum(1 for x in g["days"][11]["board"] if x == lab)
            (wth if dem else wo).append(n)
        say("  %-2s (%-10s): %5.2f with a demand shop among the first two / %5.2f without  (n %d / %d)" % (
            lab, prod, st.mean(wth) if wth else float("nan"), st.mean(wo) if wo else float("nan"), len(wth), len(wo)))
    spend = [sum(xcs.sem_flows(g)["R"][6:11]) for g in pool_]
    say("  reinvestment days 6-10 in the pool: median %.0f (p10 %.0f, p90 %.0f); exemplar %.0f" % (
        st.median(spend), pct(spend, 0.1), pct(spend, 0.9), sum(xcs.sem_flows(ex)["R"][6:11])))
    return len(pool_)


if __name__ == "__main__":
    LINES.clear()
    pool_diversity()
    (OUT / "open_stats_pool.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
