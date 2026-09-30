"""Which optional jobs the new DSM (56692773) leaves undone, day by day after day 11 (user 2026-09-30: "Let's talk about
solver post day11 ... I would like to know what are the optional jobs DSM is dropping in each turn").

Replays DSM's 43 recorded 4-quadrant games (results/fresh/semantic_h2h_20260929/study/recordings_d4q9, both seats'
recorded actions, engine 1.32.7 via scripts/upkeep_engine.World) and compares, for DSM's farm, each day's state at dawn
(after the midnight refresh) with its state after the day's last unit actions (before the refresh). Job classes (engine
rules, kaggriculture.py):
  plants  water_req     not watered yesterday (consecutive_unwatered >= 1): unwatered today -> weed tonight
          water_seed    planted today (starts at consecutive_unwatered 1): same
          water_window  one-time crop inside its yield window below max: watering adds +1 unit (+2 fertilized) at once
          water_fprod   ongoing crop, fertilized, producing tonight: watering today = +1 extra unit
          water_other   everything else (watered yesterday, no bonus): only resets the dry counter
          harvest_ripe  one-time crop ripe (age >= first yield day), harvested today or left standing
          harvest_ongo  ongoing crop holding units, collected today or left on the plant
          fertilize     FERTILIZE commands (not a dawn job; counted per day)
  animals feed_req      not fed yesterday (consecutive_unfed >= 1): unfed today -> escapes tonight
          feed_bank     produces tonight with a banked care bonus: unfed -> the bank is wiped
          feed_other    the rest: a fed + cared day banks +1 for the next production
          care          cared today (banks only when fed too)
          fert_collect  fertilizer_available at dawn (every animal, every night; not cumulative)
          product       animal holding products at dawn: collected today or left (held cap 6)
  land    empty         owned empty tiles at dawn: planted / built by the day's end or left empty
          weed          weeds at dawn: cleared or left
Output: per day 11..29 mean per game of available / done; JSON with every day and game.

usage: dsm4q_dropped_jobs_20260930.py [--workers 2] [--json out.json]"""
import argparse
import copy
import gzip
import json
import statistics as st
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
CASES = ROOT / "results/fresh/dsm4q_d9_20260930/cases.json"
CROPS = {"WHEAT": dict(first=2, maxd=4, mx=6, ongoing=False, interval=0),
         "CARROT": dict(first=2, maxd=3, mx=4, ongoing=False, interval=0),
         "MELON": dict(first=10, maxd=12, mx=6, ongoing=False, interval=0),
         "TOMATO": dict(first=8, maxd=8, mx=4, ongoing=True, interval=2),
         "STRAWBERRY": dict(first=10, maxd=10, mx=4, ongoing=True, interval=2)}
ANIMALS = {"GOOSE": dict(first=4, interval=1), "COW": dict(first=8, interval=2), "SHEEP": dict(first=6, interval=3)}
DAYS = range(11, 30)


def crop_table():
    """the engine's own crop table (first yield day / max yield day / interval) overrides the constants above"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    E = UE.engine()
    for c, d in E.CROPS.items():
        if c in CROPS:
            CROPS[c].update(first=d["first_yield_day"], maxd=d["max_yield_day"], mx=d["max_yield"],
                            ongoing=bool(d["ongoing"]), interval=int(d.get("interval") or 0))
    for a, d in E.ANIMALS.items():
        if a in ANIMALS:
            ANIMALS[a].update(first=d["first_yield_day"], interval=d["interval"], held=d["max_held"])


def produces_tonight_plant(t, day):
    cd = CROPS[t["crop"]]
    dsf = day + 1 - int(t["planted_day"]) - cd["first"]
    return cd["ongoing"] and dsf >= 0 and dsf % cd["interval"] == 0 and dsf // cd["interval"] + 1 <= cd["mx"]


def produces_tonight_animal(t, day):
    a = ANIMALS[t["animal"]]
    dsf = day + 1 - int(t["placed_day"]) - a["first"]
    return dsf >= 0 and dsf % a["interval"] == 0


def same_plant(a, b):
    return isinstance(b, dict) and b.get("kind") == "PLANT" and b.get("crop") == a.get("crop") \
        and b.get("planted_day") == a.get("planted_day")


def classify(dawn, dusk, day, cmds):
    """job counts (available, done) for one day of one farm"""
    out = Counter()
    for i in range(100):
        a, b = dawn[i], dusk[i]
        if a == "LOCKED":
            continue
        if a is None:
            out["empty:avail"] += 1
            out["empty:done"] += b is not None
            continue
        if a.get("kind") == "WEED":
            out["weed:avail"] += 1
            out["weed:done"] += not (isinstance(b, dict) and b.get("kind") == "WEED")
            continue
        if a.get("kind") == "PLANT":
            cd = CROPS[a["crop"]]
            age = day - int(a["planted_day"])
            gone = not same_plant(a, b)
            if not cd["ongoing"] and age >= cd["first"] and int(a.get("yield_units", 0)) > 0:
                out["harvest_ripe:avail"] += 1
                out["harvest_ripe:done"] += gone
                # maxed = no more growth (at max yield or past the last window day: it decays after its lifespan)
                k_ = "harvest_maxed" if int(a.get("yield_units", 0)) >= cd["mx"] or age >= cd["maxd"] else "harvest_growing"
                out[k_ + ":avail"] += 1
                out[k_ + ":done"] += gone
                if gone:
                    continue                      # harvested: its water / window counts no longer apply
            if cd["ongoing"] and int(a.get("yield_units", 0)) > 0:
                out["harvest_ongo:avail"] += 1
                out["harvest_ongo:done"] += (not gone) and int(b.get("yield_units", 0)) < int(a.get("yield_units", 0))
            if gone:
                continue
            watered = bool(b.get("watered_today"))
            if int(a.get("consecutive_unwatered", 0)) >= 1:
                k = "water_req"
            elif not cd["ongoing"] and (cd["maxd"] + 1) // 2 <= age <= cd["maxd"] and int(a.get("yield_units", 0)) < cd["mx"]:
                k = "water_window"
            elif cd["ongoing"] and int(a.get("fertilized_until_day", -1)) >= day and produces_tonight_plant(a, day):
                k = "water_fprod"
            else:
                k = "water_other"
            out[k + ":avail"] += 1
            out[k + ":done"] += watered
            continue
        if a.get("animal"):
            if not (isinstance(b, dict) and b.get("animal") == a["animal"]):
                continue                              # moved / gone during the day (rare)
            if int(a.get("consecutive_unfed", 0)) >= 1:
                k = "feed_req"
            elif produces_tonight_animal(a, day) and int(a.get("pending_care_bonus", 0) or 0) > 0:
                k = "feed_bank"
            else:
                k = "feed_other"
            out[k + ":avail"] += 1
            out[k + ":done"] += bool(b.get("fed_today"))
            out["care:avail"] += 1
            out["care:done"] += bool(b.get("cared_today"))
            out["care_banked:done"] += bool(b.get("cared_today")) and bool(b.get("fed_today"))
            if a.get("fertilizer_available"):
                out["fert_collect:avail"] += 1
                out["fert_collect:done"] += not b.get("fertilizer_available")
            if int(a.get("yield_units", 0)) > 0:
                out["product:avail"] += 1
                out["product:done"] += int(b.get("yield_units", 0)) < int(a.get("yield_units", 0))
                out["product_held_units"] += int(a.get("yield_units", 0))
                if produces_tonight_animal(a, day) and int(a.get("yield_units", 0)) + 1 > ANIMALS[a["animal"]]["held"]:
                    out["product_overflow:avail"] += 1    # full and producing tonight: uncollected -> tonight's unit lost
                    out["product_overflow:done"] += int(b.get("yield_units", 0)) < int(a.get("yield_units", 0))
    for i in range(100):                              # seedlings planted today (dusk plants with planted_day == day)
        b = dusk[i]
        if isinstance(b, dict) and b.get("kind") == "PLANT" and int(b.get("planted_day", -1)) == day:
            out["water_seed:avail"] += 1
            out["water_seed:done"] += bool(b.get("watered_today"))
    for c in cmds:
        out["unit_hours"] += 1
        if c and c[0] in ("FERTILIZE", "PLANT", "WATER", "FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER", "DIG"):
            out["op:" + c[0]] += 1
        elif c and c[0] in ("NORTH", "SOUTH", "EAST", "WEST"):
            out["moves"] += 1
        elif not c or c[0] == "PASS":
            out["idle"] += 1
        else:
            out["op:" + c[0]] += 1                        # PICKUP / DROP / PLACE / BUILD_* ...
    return out


def flat(tiles):
    return [copy.deepcopy(t) for row in tiles for t in row]


def replay(case):
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    crop_table()
    rec = json.loads(gzip.decompress((STUDY / case["file"]).read_bytes()))
    seat = int(rec["seat"])
    w = UE.World(rec["seed"], rec["shops"][30])
    E = w.E
    dusk = {}
    om = E._process_market

    def pm(state, env, *a, **k):
        t = int(state[0].observation.step)
        if t % 24 == 23:
            dusk[t // 24] = flat(state[0].observation.farms[seat]["tiles"])
        return om(state, env, *a, **k)
    E._process_market = pm
    days = {}
    cmds = {}
    try:
        while w.t < 720:
            t = w.t
            if t % 24 == 0:
                days[t // 24] = flat(w.farms[seat]["tiles"])
            acts = [None, None]
            acts[seat] = UE.tape_action(rec["our_actions"], t)
            acts[1 - seat] = UE.tape_action(rec["opp_actions"], t)
            a = acts[seat] or {}
            cmds.setdefault(t // 24, []).extend([a.get("farmer")] + list(a.get("hands") or []))
            w.step(acts)
    finally:
        E._process_market = om
    money = float(w.farms[seat]["money"])
    res = {d: dict(classify(days[d], dusk[d], d, cmds.get(d, []))) for d in DAYS if d in days and d in dusk}
    return case["episode"], money, float(rec["rewards"][seat]), res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--json", default=str(ROOT / "results/fresh/dsm4q_d9_20260930/dsm_dropped_jobs.json"))
    a = ap.parse_args()
    cases = json.loads(CASES.read_text("utf-8"))["cases"]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(replay, cases))
    ok = [r for r in rows if abs(r[1] - r[2]) < 1.0]
    print(f"{len(rows)} DSM games replayed; final cash reproduces the recorded reward in {len(ok)}")
    if len(ok) < len(rows):
        print("   mismatches:", [(r[0], r[1], r[2]) for r in rows if abs(r[1] - r[2]) >= 1.0][:10])
    Path(a.json).write_text(json.dumps({r[0]: r[3] for r in ok}), "utf-8")
    keys = ["water_req", "water_seed", "water_window", "water_fprod", "water_other", "harvest_ripe", "harvest_growing",
            "harvest_maxed", "harvest_ongo", "feed_req", "feed_bank", "feed_other", "care", "fert_collect", "product",
            "product_overflow", "empty", "weed"]
    n = len(ok)
    blocks = [(11, 14), (15, 19), (20, 24), (25, 29)]
    print("\nper game per day, mean over days in the block: available / done / DROPPED (share dropped)")
    print(f"{'job':14s}" + "".join(f"{f'days {b0}-{b1}':>26s}" for b0, b1 in blocks))
    for k in keys:
        line = f"{k:14s}"
        for b0, b1 in blocks:
            ds = [d for d in range(b0, b1 + 1)]
            av = st.mean(r[3].get(d, {}).get(k + ":avail", 0) for r in ok for d in ds)
            dn = st.mean(r[3].get(d, {}).get(k + ":done", 0) for r in ok for d in ds)
            line += f"{av:8.1f}{dn:7.1f}{av - dn:6.1f} ({(av - dn) / av * 100 if av else 0:3.0f}%)"
        print(line)
    extra = ["care_banked:done", "product_held_units", "op:FERTILIZE", "op:WATER", "op:FEED", "op:CARE", "op:HARVEST",
             "op:COLLECT_FERTILIZER", "op:PLANT", "op:DIG"]
    for k in extra:
        print(f"{k:22s}" + "".join(f"{st.mean(r[3].get(d, {}).get(k, 0) for r in ok for d in range(b0, b1 + 1)):20.1f}"
                                    for b0, b1 in blocks))
    print("\nper day (mean per game): dropped water_req / water_window / water_other | feed_req / feed_bank / feed_other | "
          "care | fert_collect | product | empty")
    for d in DAYS:
        g = lambda k: st.mean(r[3].get(d, {}).get(k + ":avail", 0) - r[3].get(d, {}).get(k + ":done", 0) for r in ok)  # noqa: E731
        print(f"  day {d:2d}: {g('water_req'):4.1f} / {g('water_window'):4.1f} / {g('water_other'):5.1f} | {g('feed_req'):4.1f} / "
              f"{g('feed_bank'):4.1f} / {g('feed_other'):4.1f} | {g('care'):4.1f} | {g('fert_collect'):4.1f} | {g('product'):4.1f} | "
              f"{g('empty'):4.1f}")


if __name__ == "__main__":
    main()
