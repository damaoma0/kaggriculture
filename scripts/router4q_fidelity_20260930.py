"""Fidelity of a 4Q tape-router opening library (2026-09-30): replay the library in the leaders' OWN recorded worlds and
measure how close our day-start boards, land and cash come to the leader's recorded state.

For each recorded world (data/leader_semantics_router4q/<team_id>_<sub>/<episode>.json.gz, exact replays): official engine
(scripts/upkeep_engine.World: recorded seed, forced shops), our library in the leader's seat with the world's own tape left
out (MGT_EXCLUDE=<episode>, the library module is loaded fresh per world), the opponent's recorded commands. Steps
0 .. until-1 (default 288: the router also plays day 11, so the day-12 dawn board is the library's own). A control game (the
leader's own recorded commands in the same harness) gives the opponent's failed-command baseline: our different farm moves
the weeds of both farms (one RNG stream) and the frozen opponent cannot react.

Per world, at the day starts 3, 6, 9, 11, 12: tile Hamming distance to the leader's recorded board (weeds = empty, the
router's labels) and to the board of the tape we were following, label counts, cash, quadrants; per day: our failed market
orders (BUY_* for cash / shed, HIRE, BUY_LAND), our and the opponent's no-effect unit commands, router picks.

usage: router4q_fidelity_20260930.py --lib agents/router4q_dsm.py --worlds 16732748_56692773[,..] [--until 288]
       [--limit N] [--workers 2] [--out results/fresh/router4q_20260930/fidelity_<tag>.json]"""
import argparse
import gzip
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA = ROOT / "data/leader_semantics_router4q"
DAYS = (3, 6, 9, 11, 12)


def label(tile):
    if tile == "LOCKED":
        return " L"
    if tile is None:
        return " ."
    kind = tile.get("kind")
    if kind == "PLANT":
        return str(tile.get("crop"))[:2]
    if kind == "WEED":
        return " ."
    if tile.get("animal"):
        return str(tile["animal"])[:2].lower()
    return str(kind)[:2].lower()


def rec_labels(rows):
    b = "".join(rows)
    return [" ." if b[i:i + 2] == " w" else b[i:i + 2] for i in range(0, 200, 2)]


def load_lib(path, exclude, tag):
    os.environ["MGT_EXCLUDE"] = str(exclude)
    name = f"_r4q_lib_{tag}"
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return name, mod


def play(tape, lib_entry=None, until=288):
    """one game: our seat = the tape's seat, played by lib_entry (None = the leader's own recorded commands)"""
    import upkeep_engine as UE
    seat = int(tape["seat"])
    w = UE.World(tape["seed"], tape["shops"][30])
    E = w.E
    day_box = [0]
    fails = [[Counter() for _ in range(30)] for _ in range(2)]
    o_commit, o_hire, o_land, o_apply = E._commit_unit, E._do_hire, E._do_buy_land, E._apply_unit_action

    def pid(farm):
        fs = w.state[0].observation["farms"]
        return 0 if farm is fs[0] else (1 if farm is fs[1] else None)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        ok = o_commit(op, item, price, farm, private, market, shed_capacity)
        p = pid(farm)
        if not ok and p is not None:
            if op == "SELL":
                fails[p][day_box[0]]["sell_empty"] += 1
            elif farm["money"] < price:
                fails[p][day_box[0]]["buy_cash:" + str(item)] += 1
            else:
                fails[p][day_box[0]]["buy_shed:" + str(item)] += 1
        return ok

    def hire(farm, private, board_size, mult=1):
        n = len(farm["hands"])
        o_hire(farm, private, board_size, mult)
        p = pid(farm)
        if p is not None:
            fails[p][day_box[0]]["hire_ok" if len(farm["hands"]) > n else "hire_fail"] += 1

    def land(farm, board_size):
        n = len(farm["unlocked_quadrants"])
        o_land(farm, board_size)
        p = pid(farm)
        if p is not None:
            if len(farm["unlocked_quadrants"]) > n:
                fails[p][day_box[0]]["land_ok"] += 1
            elif n < 4:
                fails[p][day_box[0]]["land_fail"] += 1

    def apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        p = pid(farm)
        op = action[0] if isinstance(action, list) and action else None
        pos0 = E._farmer_position(farm, idx)
        t0 = None
        if pos0 is not None:
            t0 = farm["tiles"][pos0[1]][pos0[0]]
            t0 = dict(t0) if isinstance(t0, dict) else t0
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        r = o_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        if p is not None and op not in (None, "PASS"):
            pos1 = E._farmer_position(farm, idx)
            t1 = None
            if pos1 is not None:
                t1 = farm["tiles"][pos1[1]][pos1[0]]
                t1 = dict(t1) if isinstance(t1, dict) else t1
            inv1 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
            if pos0 == pos1 and t0 == t1 and inv0 == inv1:
                fails[p][day_box[0]]["no_effect"] += 1
                fails[p][day_box[0]]["no_effect:" + str(op)] += 1
        return r

    E._commit_unit, E._do_hire, E._do_buy_land, E._apply_unit_action = commit, hire, land, apply
    snaps = {}
    try:
        for t in range(until):
            day_box[0] = min(29, t // 24)
            if t % 24 == 0:
                f = w.farms[seat]
                snaps[t // 24] = dict(board=[label(c) for row in f["tiles"] for c in row], cash=float(f["money"]),
                                      quadrants=len(f["unlocked_quadrants"]),
                                      shed={k: v for k, v in w.private(seat)["shed"].items() if v},
                                      seeds={k: v for k, v in w.private(seat)["seeds"].items() if v})
            if lib_entry is None:
                ours = UE.tape_action(tape["actions"], t)
            else:
                ours = lib_entry(w.obs(seat), None)
            opp = UE.tape_action(tape["opp_actions"], t)
            w.step([ours, opp] if seat == 0 else [opp, ours])
        f = w.farms[seat]
        snaps[until // 24] = dict(board=[label(c) for row in f["tiles"] for c in row], cash=float(f["money"]),
                                  quadrants=len(f["unlocked_quadrants"]),
                                  shed={k: v for k, v in w.private(seat)["shed"].items() if v},
                                  seeds={k: v for k, v in w.private(seat)["seeds"].items() if v})
    finally:
        E._commit_unit, E._do_hire, E._do_buy_land, E._apply_unit_action = o_commit, o_hire, o_land, o_apply
    return snaps, [[dict(c) for c in fails[s]] for s in range(2)]


def job(args):
    lib, path, until, tag = args
    tape = json.load(gzip.open(path, "rt", encoding="utf-8"))
    seat = int(tape["seat"])
    t0 = time.time()
    ctl, ctl_fails = play(tape, None, until)
    name, mod = load_lib(lib, tape["episode"], tag)
    t1 = time.time()
    snaps, fails = play(tape, mod.mgt_kaggle_entry, until)
    lib_tapes = {str(t["ep"]): t for t in mod._MGT_TAPES}
    hist = [list(h) for h in mod._MGT_HISTORY]
    report = dict(mod._MGT_REPORT)
    chassis_diag = dict(mod._MGT_IMPL.chassis.diagnostics)
    del sys.modules[name]
    del mod
    import gc
    gc.collect()
    row = dict(episode=tape["episode"], team=tape.get("team"), seat=seat, seed=tape["seed"], shops=tape["shops"][30],
               opponent=(tape.get("names") or [None, None])[1 - seat], load_s=round(t1 - t0, 2),
               play_s=round(time.time() - t1, 2), history=hist, report=report, chassis=chassis_diag, days={})
    for d in DAYS:
        if d not in snaps:
            continue
        ours, lead = snaps[d], rec_labels(tape["boards"][d])
        # the tape we were following on this day (the router's pick at this day start, else the last pick before it)
        ep = next((h[1] for h in reversed(hist) if h[0] <= d), None)
        followed = lib_tapes.get(str(ep)) if ep is not None else None
        fl = None
        if followed is not None:
            b = followed["boards"][d]
            fl = [" ." if b[i:i + 2] == " w" else b[i:i + 2] for i in range(0, 200, 2)]
        cnt_o, cnt_l = Counter(ours["board"]), Counter(lead)
        row["days"][d] = dict(
            ham_leader=sum(x != y for x, y in zip(ours["board"], lead)),
            ham_followed=(sum(x != y for x, y in zip(ours["board"], fl)) if fl else None),
            followed_ep=ep, cash=ours["cash"], cash_leader=tape["cash"][d], quadrants=ours["quadrants"],
            quadrants_leader=tape["quadrants"][d], control_ok=(ctl[d]["board"] == lead and ctl[d]["cash"] == tape["cash"][d]),
            counts={k: cnt_o.get(k, 0) for k in set(cnt_o) | set(cnt_l) if k not in (" L",)},
            counts_leader={k: cnt_l.get(k, 0) for k in set(cnt_o) | set(cnt_l) if k not in (" L",)},
            shed=ours["shed"], seeds=ours["seeds"])
    row["fails"] = fails[seat][:until // 24 + 1]
    row["opp_no_effect"] = sum(c.get("no_effect", 0) for c in fails[1 - seat])
    row["opp_no_effect_control"] = sum(c.get("no_effect", 0) for c in ctl_fails[1 - seat])
    row["lead_fails_control"] = ctl_fails[seat][:until // 24 + 1]
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True)
    ap.add_argument("--worlds", required=True)
    ap.add_argument("--until", type=int, default=288)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    paths = []
    for d in a.worlds.split(","):
        ps = sorted((DATA / d).glob("*.json.gz"))
        paths += ps[:a.limit] if a.limit else ps
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if out.exists():
        done = {str(r["episode"]): r for r in json.loads(out.read_text())["rows"]}
    todo = [(a.lib, str(p), a.until, Path(p).name.split(".")[0]) for p in paths if p.name.split(".")[0] not in done]
    print(len(paths), "worlds,", len(todo), "to play", flush=True)
    rows = list(done.values())
    from concurrent.futures import ProcessPoolExecutor, as_completed
    t0 = time.time()
    # persistent workers (max_tasks_per_child hung on this laptop after worker replacement); job() reloads the library
    # module per world (MGT_EXCLUDE is read at import) and drops it afterwards
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(job, j): j for j in todo}
        for i, fu in enumerate(as_completed(futs)):
            try:
                r = fu.result()
            except Exception as exc:
                print("FAILED", futs[fu][1], repr(exc), flush=True)
                continue
            rows.append(r)
            d6, d12 = r["days"].get(6, {}), r["days"].get(12, {})
            print(i + 1, r["episode"], r["team"], "d6 ham", d6.get("ham_leader"), "d12 ham", d12.get("ham_leader"),
                  "q12", d12.get("quadrants"), "/", d12.get("quadrants_leader"), "cash12", d12.get("cash"), "/",
                  d12.get("cash_leader"), "switches", r["report"].get("switches"), f"{time.time() - t0:.0f}s", flush=True)
            if (i + 1) % 10 == 0:
                out.write_text(json.dumps(dict(lib=a.lib, until=a.until, rows=rows)))
    out.write_text(json.dumps(dict(lib=a.lib, until=a.until, rows=rows)))
    print("wrote", out, len(rows), "rows", flush=True)


if __name__ == "__main__":
    main()
