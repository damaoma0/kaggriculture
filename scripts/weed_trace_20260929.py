"""Where our weeds come from (exact day-11 benchmark, 2026-09-29): n18rc8x / n18rc70 carry 1.4-3.7 weed tiles a day from
day 18 where DSM's continuation carries < 1 - tiles that DSM uses for wheat / carrots. The engine makes a WEED three ways:
a plant past its lifespan decays to 0 (_decay_plants, every 2 steps after max_lifespan_step), a plant unwatered two days
running wilts at the midnight refresh (_daily_refresh_plants), or a random spawn on an empty tile (_spawn_weeds).

Hooks log every tile that turns into a WEED (seat, step, cause, the plant: crop, planted day, yield, lifespan) and every
DIG (seat, step, tile), plus the weed tiles on the board at each day end.

usage: weed_trace_20260929.py CAND CASE_ID [CASE_ID ...] [--cases dsmseat_cases.json] [--controls local_dsmseat/_controls]
       [--prefix 264] [--source-control] [--workers 2]   -> per-seat causes, crops and dig delays"""
import json
import sys
import types
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))


def instrument(E, ev):
    od, orf, osw, oa, oe, om = (E._decay_plants, E._daily_refresh_plants, E._spawn_weeds, E._apply_unit_action,
                                E._end_of_day, E._process_market)
    cur = {"farms": None, "step": 0, "day": 0}
    buf = []                                       # unit actions of this step: the seat is resolved at the market call

    def seat_of(farm):
        fs = cur["farms"]
        return 0 if fs and farm is fs[0] else (1 if fs and farm is fs[1] else None)

    def snap(farm):
        return {(y, x): dict(t) for y, row in enumerate(farm["tiles"]) for x, t in enumerate(row)
                if isinstance(t, dict) and t.get("kind") == "PLANT"}

    def diff(farm, before, cause, t):
        s = seat_of(farm)
        for (y, x), p in before.items():
            now = farm["tiles"][y][x]
            if isinstance(now, dict) and now.get("kind") == "WEED":
                ev.append(("weed", s, t, cause, [x, y], p.get("crop"), p.get("planted_day"), p.get("yield_units"),
                           p.get("max_lifespan_step"), p.get("consecutive_unwatered")))

    def dp(farm, step):
        b = snap(farm)
        r = od(farm, step)
        diff(farm, b, "decay", step)
        return r

    def rf(farm, current_day, turns_per_day):
        b = snap(farm)
        r = orf(farm, current_day, turns_per_day)
        diff(farm, b, "wilt", (current_day + 1) * 24)
        return r

    def sw(farm, board_size, weed_chance, rng):
        before = {(y, x) for y, row in enumerate(farm["tiles"]) for x, t in enumerate(row) if t is None}
        r = osw(farm, board_size, weed_chance, rng)
        s = seat_of(farm)
        for (y, x) in before:
            t = farm["tiles"][y][x]
            if isinstance(t, dict) and t.get("kind") == "WEED":
                ev.append(("weed", s, (cur["day"] + 1) * 24, "spawn", [x, y], None, None, None, None, None))
        return r

    def ap(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        op = action[0] if isinstance(action, (list, tuple)) and action else None
        pos = E._farmer_position(farm, idx) if op in ("DIG", "PLANT") else None
        was = None
        if pos is not None:
            t0 = farm["tiles"][pos[1]][pos[0]]
            was = (t0.get("kind") if t0.get("kind") != "PLANT" else "PLANT:" + str(t0.get("crop"))) if isinstance(t0, dict) else t0
        r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        if pos is not None:
            t1 = farm["tiles"][pos[1]][pos[0]]
            ok = (t1 is None) if op == "DIG" else (isinstance(t1, dict) and t1.get("kind") == "PLANT" and was is None)
            if ok:
                buf.append((farm, op.lower(), was if op == "DIG" else t1.get("crop"), list(pos)))
        return r

    def ee(state, env, day, *a, **k):
        cur["farms"] = state[0].observation.farms
        cur["day"] = day
        for i in range(2):
            n = sum(1 for row in state[0].observation.farms[i]["tiles"] for t in row
                    if isinstance(t, dict) and t.get("kind") == "WEED")
            ev.append(("weeds_on_board", i, day, None, None, None, None, n, None, None))
        return oe(state, env, day, *a, **k)

    def pm(state, env, *a, **k):
        cur["farms"] = state[0].observation.farms
        cur["step"] = int(state[0].observation.step)
        for (farm, kind, what, pos) in buf:
            ev.append((kind, seat_of(farm), cur["step"], what, pos, None, None, None, None, None))
        buf.clear()
        return om(state, env, *a, **k)
    E._decay_plants, E._daily_refresh_plants, E._spawn_weeds = dp, rf, sw
    E._apply_unit_action, E._end_of_day, E._process_market = ap, ee, pm

    def undo():
        E._decay_plants, E._daily_refresh_plants, E._spawn_weeds = od, orf, osw
        E._apply_unit_action, E._end_of_day, E._process_market = oa, oe, om
    return undo


def job(args):
    cand, case, extra = args
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    ev = []
    un = instrument(E, ev)
    me = Path(__file__).resolve()                  # the harness audit rejects unfrozen repo modules: drop this runner
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    out = H / "weed_trace" / (cand + ("_src" if extra.get("source_control") else ""))
    out.mkdir(parents=True, exist_ok=True)
    try:
        harness = H / "study/candidates" / cand / "harness"
        j = dict(study=str(H / "study"), case=case, kind="recorded", output=str(out / f"{case['id']}.json"), candidate=cand,
                 control=str(H / extra["controls"] / f"{case['id']}.json"), leader_credit="exact",
                 leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True)
        if extra.get("prefix"):
            j["prefix_steps"] = int(extra["prefix"])
        if extra.get("source_control"):
            j = dict(study=str(H / "study"), case=case, kind="source_control", output=str(out / f"{case['id']}.ctl.json"),
                     candidate=cand, leader_weeds=True)
        SH._worker((str(harness), j, True))
    finally:
        un()
    (out / f"{case['id']}.weeds.json").write_text(json.dumps(dict(seat=int(case["seat"]), events=ev)))
    return case["id"], int(case["seat"]), ev


def main():
    a = sys.argv
    cand = a[1]
    ids = [x for x in a[2:] if x.startswith("dsm") or x.startswith("lead")]
    cfile = Path(a[a.index("--cases") + 1]) if "--cases" in a else H / "dsmseat_cases.json"
    extra = dict(controls=a[a.index("--controls") + 1] if "--controls" in a else "local_dsmseat/_controls",
                 prefix=int(a[a.index("--prefix") + 1]) if "--prefix" in a else 0, source_control="--source-control" in a)
    cases = [c for c in json.loads(cfile.read_text())["cases"] if c["id"] in ids]
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 2
    agg, crops, digk = Counter(), Counter(), Counter()
    boards = defaultdict(float)
    delays = []
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        for cid, s, ev in pool.map(job, [(cand, c, extra) for c in cases]):
            born = {}
            for e in sorted(ev, key=lambda e: e[2]):
                if e[1] != s:
                    continue
                if e[0] == "weed" and e[2] >= 264:
                    agg[e[3]] += 1
                    crops[(e[3], e[5])] += 1
                    born[tuple(e[4])] = e[2]
                elif e[0] == "dig" and e[2] >= 264:
                    digk[e[3]] += 1
                    if tuple(e[4]) in born:
                        delays.append(e[2] - born.pop(tuple(e[4])))
                elif e[0] == "plant" and e[2] >= 264:
                    digk["plant:" + str(e[3])] += 1
                elif e[0] == "weeds_on_board" and e[2] >= 11:
                    boards[e[2] // 3] += e[7]
    n = max(1, len(cases))
    print(f"{cand}{' (source control)' if extra['source_control'] else ''}: weeds born after day 11 per game:",
          {k: round(v / n, 1) for k, v in agg.items()})
    print("   by cause:crop:", {f"{k[0]}:{k[1]}": round(v / n, 1) for k, v in sorted(crops.items(), key=lambda kv: -kv[1])})
    print("   weed tiles at day end, per 3-day block from day 12:", [round(boards[b] / n / 3, 1) for b in range(4, 10)])
    print("   DIGs after day 11 per game by what was dug:", {str(k): round(v / n, 1) for k, v in digk.items()})
    if delays:
        delays.sort()
        print(f"   weeds dug {len(delays) / n:.1f} per game, steps birth -> dig: median {delays[len(delays) // 2]},"
              f" p90 {delays[int(len(delays) * .9)]}")


if __name__ == "__main__":
    main()
