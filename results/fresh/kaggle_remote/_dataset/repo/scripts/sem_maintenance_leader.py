"""Leader maintenance vs sem_maintenance jobs on the leader's own boards (one recorded game).

Replays a leader tape through the official engine exactly like scripts/extract_leader_semantics.py
(recorded seed, forced shop schedule, both seats' recorded actions; final cash checked), and
  * at hour 0 of every day calls maintenance_jobs(obs, leader_seat, ...) on the leader's REAL
    observation (full tile dicts), fertilize='auto' and fertilize=True, include_optional=True;
  * hooks E._apply_unit_action to record the leader's effective WATER / FEED / CARE / FERTILIZE /
    HARVEST / COLLECT_FERTILIZER per tile and day (flag flipped / units gained);
  * counts plants that turned into weeds (died) and animals that escaped.
Then compares day by day: jobs done by the leader, jobs the leader skipped (with their value), leader
actions outside the job list (over-maintenance, by reason), harvest timing.

usage: sem_maintenance_leader.py [team_dir episode]   (default 16732748_56498734 112655730)
Writes results/fresh/sem_maintenance/leader_<episode>.json
"""
import gzip
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "fragments"))
import sem_maintenance as SM  # noqa: E402

OUT = os.path.join(ROOT, "results", "fresh", "sem_maintenance")
OPS = ("WATER", "FEED", "CARE", "FERTILIZE", "HARVEST", "COLLECT_FERTILIZER")


def replay(team_dir, episode):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    path = os.path.join(ROOT, "data", "leader_tapes", team_dir, "%s.json.gz" % episode)
    g = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
    seat, seed = g["seat"], g["seed"]
    shops_by_day = [list(g["shops"][:min(8, d // 3)]) for d in range(31)]
    actions = [None, None]
    actions[seat] = g["actions"]
    actions[1 - seat] = g["opp_actions"]
    done = defaultdict(list)            # day -> [(x, y, op, hour, units)]
    jobs_auto, jobs_fert, tiles_start, timing = {}, {}, {}, []
    log = []
    farms_box = []
    old_apply, old_end = E._apply_unit_action, E._end_of_day

    def apply_hook(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        op = action[0] if isinstance(action, list) and action else None
        mine = farms_box and farm is farms_box[0][seat]
        if not mine or op not in OPS:
            return old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        pos = E._farmer_position(farm, idx)
        if pos is None:
            return old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        x, y = pos
        t0 = farm["tiles"][y][x]
        t0 = dict(t0) if isinstance(t0, dict) else t0
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        res = old_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        t1 = farm["tiles"][y][x]
        inv1 = private["inventories"][idx] if idx < len(private["inventories"]) else {}
        eff, units = False, 0
        if isinstance(t0, dict):
            if op == "WATER":
                eff = not t0.get("watered_today") and isinstance(t1, dict) and t1.get("watered_today")
            elif op == "FEED":
                eff = not t0.get("fed_today") and isinstance(t1, dict) and t1.get("fed_today")
            elif op == "CARE":
                eff = not t0.get("cared_today") and isinstance(t1, dict) and t1.get("cared_today")
            elif op == "FERTILIZE":
                eff = isinstance(t1, dict) and t0.get("fertilized_until_day") != t1.get("fertilized_until_day")
            elif op in ("HARVEST", "COLLECT_FERTILIZER"):
                units = sum(max(0, inv1.get(k, 0) - inv0.get(k, 0)) for k in inv1)
                eff = units > 0
        if eff:
            hour = E_step[0] % 24
            done[day].append((x, y, op, hour, units))
        return res

    E_step = [0]

    def end_hook(state, environment, day):
        old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    E._apply_unit_action, E._end_of_day = apply_hook, end_hook
    try:
        env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": seed})
        orig = env.interpreter

        def interp(state, environment):
            farms = getattr(state[0].observation, "farms", None)
            if farms:
                farms_box[:] = [farms]
            E_step[0] = int(getattr(state[0].observation, "step", 0) or 0)
            return orig(state, environment)
        env.interpreter = interp

        def player(i):
            def act(obs):
                t = int(obs["step"])
                d, h = divmod(t, 24)
                if i == seat and h == 0:
                    t0 = time.perf_counter()
                    ja = SM.maintenance_jobs(obs, seat, fertilize="auto", include_optional=True, log=log)
                    timing.append(time.perf_counter() - t0)
                    jobs_auto[d] = ja
                    jobs_fert[d] = SM.maintenance_jobs(obs, seat, fertilize=True, include_optional=True)
                    tiles_start[d] = deepcopy(obs["farms"][seat]["tiles"])
                a = actions[i][t] if t < len(actions[i]) else {}
                return deepcopy(a) if a else {"farmer": ["PASS"], "hands": [], "market": []}
            return act
        env.run([player(0), player(1)])
        final = [float(s.reward) for s in env.state]
    finally:
        E._apply_unit_action, E._end_of_day = old_apply, old_end
    return g, seat, final, done, jobs_auto, jobs_fert, tiles_start, timing, log


def asset_of(t):
    if not isinstance(t, dict):
        return None
    if t.get("kind") == "PLANT":
        return t.get("crop")
    return t.get("animal")


def main():
    team_dir, episode = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("16732748_56498734", "112655730")
    t = time.time()
    g, seat, final, done, jobs_auto, jobs_fert, tiles_start, timing, log = replay(team_dir, episode)
    cash_match = round(final[0]) == round(g["rewards"][0]) and round(final[1]) == round(g["rewards"][1])
    days = []
    tot = Counter()
    extra_by = Counter()
    miss_by = Counter()
    miss_value = Counter()
    deaths = Counter()
    for d in range(30):
        jobs = jobs_auto.get(d, [])
        req = {(j["tile"], j["cmd"]): j for j in jobs if not j.get("optional")}
        opt = {(j["tile"], j["cmd"]) for j in jobs if j.get("optional")}
        fjobs = {(j["tile"], j["cmd"]) for j in jobs_fert.get(d, []) if not j.get("optional")}
        lead = {}
        for x, y, op, hour, units in done.get(d, []):
            lead.setdefault(((x, y), op), (hour, units))
        tiles = tiles_start.get(d)
        row = {"day": d, "jobs": Counter(), "leader": Counter(), "matched": Counter(), "missed": Counter(),
               "extra": Counter(), "missed_value": 0.0, "early_harvest": 0}
        for (tile, cmd), j in req.items():
            row["jobs"][cmd] += 1
            if (tile, cmd) in lead:
                row["matched"][cmd] += 1
            else:
                row["missed"][cmd] += 1
                row["missed_value"] += j["value"]
                miss_by[(cmd, j["asset"], j["kind"])] += 1
                miss_value[(cmd, j["asset"], j["kind"])] += j["value"]
        for (tile, cmd), (hour, units) in lead.items():
            row["leader"][cmd] += 1
            if (tile, cmd) in req:
                continue
            a = asset_of(tiles[tile[1]][tile[0]]) if tiles else None
            if cmd == "HARVEST" and (tile, cmd) in opt:
                row["early_harvest"] += 1
                extra_by[(cmd, a, "optional harvest (could wait)")] += 1
                continue
            if cmd == "FERTILIZE" and (tile, cmd) in fjobs:
                why = "fertilise: +units but not paying at market fert price"
            elif a is None:
                why = "tile planted/placed during the day"
            else:
                why = "not needed today (0 value)"
            row["extra"][cmd] += 1
            extra_by[(cmd, a, why)] += 1
        # deaths during day d: plant at start of d -> WEED at start of d+1 without a harvest on d
        if tiles and d + 1 in tiles_start:
            nxt = tiles_start[d + 1]
            harvested = {(x, y) for x, y, op, h, u in done.get(d, []) if op == "HARVEST"}
            for y in range(10):
                for x in range(10):
                    a0, t1 = tiles[y][x], nxt[y][x]
                    if isinstance(a0, dict) and a0.get("kind") == "PLANT" and (x, y) not in harvested:
                        if isinstance(t1, dict) and t1.get("kind") == "WEED":
                            deaths["plant:" + a0["crop"]] += 1
                    if isinstance(a0, dict) and a0.get("animal") and isinstance(t1, dict) and not t1.get("animal") \
                            and t1.get("kind") in ("COOP", "PASTURE"):
                        deaths["escaped:" + a0["animal"]] += 1
        for k in ("jobs", "leader", "matched", "missed", "extra"):
            tot[k] += sum(row[k].values())
        row = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in row.items()}
        row["missed_value"] = round(row["missed_value"], 1)
        days.append(row)
    by_cmd = defaultdict(Counter)
    for r in days:
        for k in ("jobs", "leader", "matched", "missed", "extra"):
            for c, n in r[k].items():
                by_cmd[c][k] += n
    res = {
        "team_dir": team_dir, "episode": episode, "seat": seat, "cash_match": cash_match, "final": final,
        "timing_ms": {"n": len(timing), "median": round(1000 * statistics.median(timing), 2),
                      "max": round(1000 * max(timing), 2), "first": round(1000 * timing[0], 2),
                      "p90": round(1000 * sorted(timing)[int(0.9 * len(timing))], 2)},
        "totals": dict(tot), "by_cmd": {c: dict(v) for c, v in by_cmd.items()},
        "missed_by": sorted([[list(k), n, round(miss_value[k], 1)] for k, n in miss_by.items()], key=lambda r: -r[2]),
        "extra_by": sorted([[list(k), n] for k, n in extra_by.items()], key=lambda r: -r[1]),
        "deaths": dict(deaths), "abandonment_log": log, "days": days,
        "runtime_s": round(time.time() - t, 1),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "leader_%s.json" % episode), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print("cash_match", cash_match, "timing", res["timing_ms"])
    print("totals", res["totals"])
    for c, v in res["by_cmd"].items():
        print("  ", c, dict(v))
    print("deaths", res["deaths"])
    print("missed (top):")
    for r in res["missed_by"][:12]:
        print("  ", r)
    print("extra (top):")
    for r in res["extra_by"][:12]:
        print("  ", r)
    print("day | jobs | leader | matched | missed(value) | extra | early harvests")
    for r in days:
        print(r["day"], sum(r["jobs"].values()), sum(r["leader"].values()), sum(r["matched"].values()),
              "%d(%.0f)" % (sum(r["missed"].values()), r["missed_value"]), sum(r["extra"].values()), r["early_harvest"])
    print("abandonment log:", len(log), Counter(e["verdict"] for e in log))


if __name__ == "__main__":
    main()
