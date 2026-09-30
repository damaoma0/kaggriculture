"""How the leaders bring goods back to the shed during the day (user 2026-09-29: "focus on the bring-back hands, the
objective is to make these resemble DSM's choice closely, and then make a good layout of other hands"; "reserve
fertilizer at shed, have hands pick up at shed instead of trying to find an animal to collect").

Engine hooks log every unit command of both seats, per unit and day (days 6-29):
  shed stops       a unit on a shed-access tile that DROPs / PLACEs goods or PICKs UP; for a drop: hour, items dropped,
                   what the unit gathered since its previous shed stop, effective ops before it, farthest Manhattan
                   distance from the shed, field ops afterwards, and what it picked up at the same stop
  midnight dump    what every unit still carries after hour 23 (dumped into the shed at midnight, capped at 100)
  fertilizer       COLLECT_FERTILIZER / FERTILIZE / PICKUP FERTILIZER per day, shed fertilizer at hour 0
  sales            executed SELL units per hour and product (goods sell only from the shed)
Two drivers:
  recording  exact replay of a recorded leader game (scripts/upkeep_engine.World, both recorded streams)
  harness    a frozen-harness game of a candidate vs the recorded leader (exact credit + recorded weeds): BOTH seats
             in the same world, so our arm and the leader compare apples to apples

usage: bringback_profile_20260929.py recording [--cases leaders_cases.json] [--ids a,b] [--out FILE]
       bringback_profile_20260929.py harness CAND [--cases ...] [--ids a,b] [--out FILE]   (one process per game)"""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))
MOVES = ("NORTH", "SOUTH", "EAST", "WEST")
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
BOARD = 10
PX_ITEMS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def shed_tiles():
    h = BOARD // 2
    return {(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)}


SHED = shed_tiles()
SHED_CORE = set()                                  # the shed itself sits between the four access tiles (no tile)


def dist(pos):
    return min(abs(pos[0] - x) + abs(pos[1] - y) for x, y in SHED)


class Profiler:
    """one seat: event(...) per unit command (with its hour), end_of_day / start_of_day / sell"""

    def __init__(self):
        self.days = defaultdict(lambda: dict(units={}, sells=Counter(), ops=Counter()))
        self.u = {}
        self.cyc = {}                                  # tile -> running one-time-crop cycle
        self.cycles = []                               # finished cycles (harvested)

    def unit(self, day, idx):
        k = (day, idx)
        if k not in self.u:
            self.u[k] = dict(first=None, stops=[], gathered=Counter(), ops=0, far=0, ops_total=0, last=None, trace=[])
            self.days[day]["units"][idx] = self.u[k]
        return self.u[k]

    def event(self, day, hour, idx, action, pos, tile0, inv0, inv1, tile1):
        if day < 6:
            return
        op = action[0] if isinstance(action, list) and action else None
        s = self.unit(day, idx)
        if op is None or op == "PASS":
            s["trace"].append(".")
            return
        if s["first"] is None:
            s["first"] = hour
        if op in MOVES:
            s["trace"].append("-")
            return
        eff = tile0 != tile1 or inv0 != inv1
        if eff and pos is not None:
            self.crop_event(day, hour, op, pos, tile0, tile1, inv0, inv1)
        s["trace"].append(op[0] if eff else op[0].lower())
        if not eff:
            self.days[day]["ops"]["noeff:" + op] += 1
            return
        self.days[day]["ops"][op] += 1
        at_shed = pos is not None and tuple(pos) in SHED
        if op in ("DROP", "PLACE", "PICKUP") and at_shed:
            dropped = {k: inv0.get(k, 0) - inv1.get(k, 0) for k in inv0 if inv0.get(k, 0) > inv1.get(k, 0)}
            picked = {k: inv1.get(k, 0) - inv0.get(k, 0) for k in inv1 if inv1.get(k, 0) > inv0.get(k, 0)}
            if op == "PICKUP":
                self.days[day]["ops"]["pickup:" + str(action[1] if len(action) > 1 else "")] += sum(picked.values())
            st = s["stops"][-1] if s["stops"] and s["stops"][-1]["open"] else None
            if st is None:
                st = dict(hour=hour, dropped=Counter(), picked=Counter(), gathered=dict(s["gathered"]), ops=s["ops"],
                          far=s["far"], open=True, field_after=0)
                s["stops"].append(st)
                s["gathered"], s["ops"], s["far"] = Counter(), 0, 0
            st["dropped"].update(dropped)
            st["picked"].update(picked)
            return
        for st in s["stops"]:
            st["open"] = False
        if s["stops"]:
            s["stops"][-1]["field_after"] += 1
        s["ops"] += 1
        s["ops_total"] += 1
        s["last"] = hour
        if pos is not None:
            s["far"] = max(s["far"], dist(pos))
        for k in inv1:
            if inv1.get(k, 0) > inv0.get(k, 0):
                s["gathered"][k] += inv1[k] - inv0.get(k, 0)

    def crop_event(self, day, hour, op, pos, tile0, tile1, inv0, inv1):
        """one-time crops (WHEAT / CARROT / MELON): plant day, watering / fertilize ages, harvested units"""
        if op == "PLANT" and isinstance(tile1, dict) and tile1.get("crop") in ("WHEAT", "CARROT", "MELON"):
            self.cyc[pos] = dict(crop=tile1["crop"], planted=day, water=[], fert=[], harvest=None, units=0, tile=list(pos))
        c = self.cyc.get(pos)
        if c is None or not isinstance(tile0, dict) or tile0.get("crop") != c["crop"]:
            return
        age = day - c["planted"]
        if op == "WATER":
            c["water"].append(age)
        elif op == "FERTILIZE":
            c["fert"].append(age)
        elif op == "HARVEST":
            c["harvest"], c["units"] = age, sum(inv1.values()) - sum(inv0.values())
            c["day"] = day
            self.cycles.append(c)
            self.cyc.pop(pos, None)

    def board(self, day, farm):                    # hour-0 layout: what stands on every tile, by distance from the shed
        if day < 6:
            return
        lay = Counter()
        for y, row in enumerate(farm["tiles"]):
            for x, t in enumerate(row):
                if t == "LOCKED" or (isinstance(t, dict) and t.get("kind") == "LOCKED"):
                    continue
                if (x, y) in SHED_CORE:
                    continue
                kind = ("empty" if t is None else t.get("crop") if isinstance(t, dict) and t.get("crop") else
                        t.get("animal") if isinstance(t, dict) and t.get("animal") else
                        (t.get("kind") if isinstance(t, dict) else str(t)))
                lay[f"{kind}@{min(dist((x, y)), 6)}"] += 1
        self.days[day]["board"] = dict(lay)

    def end_of_day(self, day, private):          # after hour 23's commands and market, before the midnight dump
        if day >= 6:
            self.days[day]["dump"] = [dict(i) for i in private["inventories"]]
            self.days[day]["shed_2300"] = dict(private["shed"])

    def start_of_day(self, day, private):        # after the midnight dump
        if 6 <= day:
            self.days[day]["shed0"] = dict(private["shed"])

    def sell(self, day, hour, item, price=0.0):
        if day >= 6:
            self.days[day]["sells"][(hour, item)] += 1
            self.days[day].setdefault("rev", Counter())[(hour, item)] += float(price)

    def summary(self):
        out = {}
        for day, D in sorted(self.days.items()):
            units = {}
            for idx, s in D["units"].items():
                units[idx] = dict(first=s["first"], ops=s["ops_total"], last=s["last"], trace="".join(s["trace"]),
                                  stops=[dict(hour=st["hour"], dropped=dict(st["dropped"]), picked=dict(st["picked"]),
                                              gathered=st["gathered"], ops_before=st["ops"], far=st["far"],
                                              field_after=st["field_after"]) for st in s["stops"]],
                                  tail=dict(s["gathered"]))
            out[day] = dict(units=units, sells={f"{h}:{i}": n for (h, i), n in D["sells"].items()}, ops=dict(D["ops"]),
                            rev={f"{h}:{i}": round(v, 1) for (h, i), v in (D.get("rev") or {}).items()},
                            shed0=D.get("shed0"), dump=D.get("dump"), shed_2300=D.get("shed_2300"), board=D.get("board"))
        out["cycles"] = self.cycles
        return out


def instrument(E):
    """hooks on the engine module: returns (profilers[2], uninstall). Unit commands are buffered and assigned their seat
    (private-object identity) and hour when the step's market runs (after every unit command of the step)."""
    P = [Profiler(), Profiler()]
    P[0].px = PX = []                              # market prices / stock before each step's market (hour-of-day curve)
    buf = []
    cur = dict(step=0, privs=None)
    oa, om, oc, oe = E._apply_unit_action, E._process_market, E._commit_unit, E._end_of_day

    def ap(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        pos = E._farmer_position(farm, idx)
        pos = tuple(pos) if pos is not None else None
        tile0 = None
        if pos is not None:
            t = farm["tiles"][pos[1]][pos[0]]
            tile0 = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        t1 = farm["tiles"][pos[1]][pos[0]] if pos is not None else None
        inv1 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        buf.append((private, day, idx, action, pos, tile0, inv0, inv1, dict(t1) if isinstance(t1, dict) else t1))
        return r

    def pm(state, env, *a, **k):
        step = int(state[0].observation.step)
        privs = [state[i].observation.private for i in range(2)]
        cur["step"], cur["privs"] = step, privs
        for (priv, day, idx, action, pos, tile0, inv0, inv1, tile1) in buf:
            seat = 0 if priv is privs[0] else (1 if priv is privs[1] else None)
            if seat is not None:
                P[seat].event(day, step % 24, idx, action, pos, tile0, inv0, inv1, tile1)
        buf.clear()
        mk = state[0].observation.market
        PX.append([step] + [round(float(mk["prices"].get(q, 0)), 1) for q in PX_ITEMS] + [int(mk["inventory"].get(q, 0)) for q in PX_ITEMS])
        r = om(state, env, *a, **k)
        if step % 24 == 23:
            for i in range(2):
                P[i].end_of_day(step // 24, privs[i])
        return r

    def cu(op, item, price, farm, private, market, *a, **k):
        r = oc(op, item, price, farm, private, market, *a, **k)
        if r and op == "SELL" and cur["privs"] is not None:
            for i in range(2):
                if private is cur["privs"][i]:
                    P[i].sell(cur["step"] // 24, cur["step"] % 24, item, price)
        return r

    def ee(state, env, day, *a, **k):
        r = oe(state, env, day, *a, **k)
        for i in range(2):
            P[i].start_of_day(day + 1, state[i].observation.private)
            P[i].board(day + 1, state[0].observation.farms[i])
        return r
    E._apply_unit_action, E._process_market, E._commit_unit, E._end_of_day = ap, pm, cu, ee

    def uninstall():
        E._apply_unit_action, E._process_market, E._commit_unit, E._end_of_day = oa, om, oc, oe
    return P, uninstall


def replay_recording(case):
    import upkeep_engine as UE
    game = json.loads(gzip.decompress((H / "study" / case["file"]).read_bytes()))
    E = UE.engine()
    P, un = instrument(E)
    seat_of = {int(game["seat"]): "our_actions", 1 - int(game["seat"]): "opp_actions"}
    shops = game["shops"][-1] if game["shops"] and isinstance(game["shops"][0], list) else game["shops"]
    try:
        w = UE.World(game["seed"], shops)
        for t in range(719):
            w.step([UE.tape_action(game[seat_of[0]], t), UE.tape_action(game[seat_of[1]], t)])
    finally:
        un()
    s = int(case["seat"])
    return dict(ours=P[s].summary(), leader=P[1 - s].summary(), cash=[w.farms[0]["money"], w.farms[1]["money"]])


def plan_hook(plans):
    """wrap the candidate executor's _tier_pre (loaded by the semantic entry through importlib.util) to record every
    day's plan summary: per unit the planned end hour, start, ops, and the extras left unplanned"""
    import importlib.util as IU
    orig = IU.spec_from_file_location

    def sffl(name, *a, **k):
        spec = orig(name, *a, **k)
        if name != "_strategy_kb115lt" or spec is None:
            return spec
        ex0 = spec.loader.exec_module

        def exec_module(mod):
            ex0(mod)
            tp0 = mod._tier_pre

            def tier_pre(S, L, obs, step, day, hour, *aa, **kk):
                r = tp0(S, L, obs, step, day, hour, *aa, **kk)
                T = S.get("tier") or {}
                if T.get("day") == day and T.get("summary"):
                    sm = T["summary"]
                    plans[int(day)] = dict(
                        units={int(x["u"]): dict(t0=x["t0"], end=x["end"], late=x["late"], kind=x["kind"],
                                                 ops=sum(len(o) for _, o in x["stops"]), stops=len(x["stops"]))
                               for x in sm.get("units", [])},
                        unplanned=len(sm.get("unplanned") or []),
                        unplanned_v=round(sum(v for _, _, v in (sm.get("unplanned") or [])), 1),
                        unplanned_ops={} if not sm.get("unplanned") else dict(Counter(o for _, ops, _ in sm["unplanned"] for o in ops)))
                return r
            mod._tier_pre = tier_pre
        spec.loader.exec_module = exec_module
        return spec
    IU.spec_from_file_location = sffl
    return lambda: setattr(IU, "spec_from_file_location", orig)


def harness_job(args):
    cand, case, out = args[:3]
    extra = args[3] if len(args) > 3 else {}
    import types
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    P, un = instrument(E)
    plans = {}
    un_plan = plan_hook(plans)
    me = Path(__file__).resolve()                  # the harness audit rejects unfrozen repo modules: drop this runner
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    try:
        harness = H / "study/candidates" / cand / "harness"
        j = dict(study=str(H / "study"), case=case, kind="recorded", output=str(out / f"{case['id']}.json"), candidate=cand,
                 control=str(H / extra.get("controls", "leadersx_credit/_controls") / f"{case['id']}.json"), leader_credit="exact",
                 leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True)
        if extra.get("prefix"):
            j["prefix_steps"] = int(extra["prefix"])
        if extra.get("source_control"):           # both recorded streams (e.g. DSM continuing its own game)
            j = dict(study=str(H / "study"), case=case, kind="source_control", output=str(out / f"{case['id']}.ctl.json"),
                     candidate=cand, leader_weeds=True)
        row = SH._worker((str(harness), j, True))
    finally:
        un()
        un_plan()
    s = int(case["seat"])
    return case["id"], dict(ours=P[s].summary(), leader=P[1 - s].summary(), margin=row.get("margin"), plans=plans, px=P[0].px)


def aggregate(games):
    """games: list of per-seat summaries -> per-day means (days 6-29)"""
    A = Counter()
    hours, mix, picked_mid, ops = Counter(), Counter(), Counter(), Counter()
    n_days = 0
    for S in games:
        for day, D in S.items():
            if day == "cycles":
                continue
            day = int(day)
            if not 6 <= day <= 29:
                continue
            n_days += 1
            for k, v in (D.get("ops") or {}).items():
                ops[k] += v
            hands = {i: u for i, u in D["units"].items() if int(i) > 0 and u["ops"] > 0}
            A["hands"] += len(hands)
            A["idle_hand_hours"] += sum(u["trace"].count(".") for i, u in D["units"].items() if int(i) > 0)
            for i, u in D["units"].items():
                drops = [st for st in u["stops"] if any(k in GOODS or k == "FERTILIZER" for k in st["dropped"])]
                mid = [st for st in drops if st["hour"] < 23]
                if int(i) > 0 and mid:
                    A["hands_with_midday_drop"] += 1
                    A["midday_drops_hands"] += len(mid)
                    A["hands_drop_then_field"] += any(st["field_after"] > 0 for st in mid)
                if int(i) == 0:
                    A["farmer_midday_drops"] += len(mid)
                for st in mid:
                    hours[st["hour"]] += 1
                    for k, v in st["dropped"].items():
                        mix[k] += v
                    for k, v in st["picked"].items():
                        picked_mid[k] += v
                    A["drop_goods"] += sum(v for k, v in st["dropped"].items() if k in GOODS)
                    A["drop_fert"] += st["dropped"].get("FERTILIZER", 0)
                    A["_far"] += st["far"]
                    A["_ops"] += st["ops_before"]
                    A["_n"] += 1
                for st in u["stops"]:
                    A["pickup_fert"] += st["picked"].get("FERTILIZER", 0)
                    A["pickup_wheat"] += st["picked"].get("WHEAT", 0)
            dump = D.get("dump") or []
            A["dump_goods"] += sum(v for inv in dump for k, v in inv.items() if k in GOODS)
            A["dump_fert"] += sum(inv.get("FERTILIZER", 0) for inv in dump)
            shed = D.get("shed_2300") or {}
            A["shed_2300"] += sum(shed.values())
            load = sum(shed.values()) + sum(v for inv in dump for v in inv.values())
            A["midnight_overflow"] += max(0, load - 100)
            A["shed_fert_0"] += (D.get("shed0") or {}).get("FERTILIZER", 0)
            for key, n in D["sells"].items():
                h, _item = key.split(":")
                A["sold"] += n
                A["sold_before_16"] += n if int(h) < 16 else 0
    nd = max(1, n_days)
    res = {k: round(v / nd, 2) for k, v in A.items() if not k.startswith("_")}
    res["far_per_drop"] = round(A["_far"] / max(1, A["_n"]), 2)
    res["ops_before_drop"] = round(A["_ops"] / max(1, A["_n"]), 2)
    res["drop_hours"] = {h: round(n / nd, 2) for h, n in sorted(hours.items())}
    res["drop_mix"] = {k: round(v / nd, 2) for k, v in mix.most_common()}
    res["picked_at_midday_stop"] = {k: round(v / nd, 2) for k, v in picked_mid.most_common()}
    res["ops"] = {k: round(ops[k] / nd, 1) for k in ("COLLECT_FERTILIZER", "FERTILIZE", "noeff:FERTILIZE",
                                                     "noeff:COLLECT_FERTILIZER", "DROP", "PICKUP", "pickup:FERTILIZER")}
    return res


def report(res):
    for fam in ("dsm", "mmpq"):
        g = [v for k, v in res.items() if f"-{fam}-" in k]
        if not g:
            continue
        for side in ("ours", "leader"):
            print(f"{fam} {side:6s} {len(g)} games:", json.dumps(aggregate([x[side] for x in g])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("recording", "harness"))
    ap.add_argument("cand", nargs="?")
    ap.add_argument("--cases", default=str(H / "leaders_cases.json"))
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--controls", default="leadersx_credit/_controls", help="source-control dir (relative to the h2h dir)")
    ap.add_argument("--prefix", type=int, default=0, help="exact prefix steps (our seat replays its recording until then)")
    ap.add_argument("--source-control", action="store_true", help="profile the source control (both recordings) instead")
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text())["cases"]
    if a.ids:
        ids = Path(a.ids).read_text().split() if Path(a.ids).is_file() else a.ids.split(",")
        cases = [c for c in cases if c["id"] in ids]
    res = {}
    if a.mode == "recording":
        out = Path(a.out or H / "bringback/recordings.json")
        for c in cases:
            res[c["id"]] = replay_recording(c)
            print(c["id"], "cash", res[c["id"]]["cash"], flush=True)
    else:
        out_dir = H / "bringback" / a.cand
        out_dir.mkdir(parents=True, exist_ok=True)
        out = Path(a.out or out_dir / "profile.json")
        with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
            ex_ = dict(controls=a.controls, prefix=a.prefix, source_control=a.source_control)
            for cid, r in pool.map(harness_job, [(a.cand, c, out_dir, ex_) for c in cases]):
                res[cid] = r
                print(cid, "margin", r["margin"], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    report(res)


if __name__ == "__main__":
    main()
