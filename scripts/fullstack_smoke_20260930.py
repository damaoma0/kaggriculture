"""Full-stack smoke (user 2026-09-30: "integrate this, the semantic planner and tiler, with our new search algorithm,
into a full stack"):
  days 0-10   DSM's recorded actions (exact handover at the day-11 dawn, as tpp_smoke_20260930.py);
  planning    the semantic strategy's own planning layer, loaded from a candidate project (default d9c4o): every step
              policy.observe + observe_own (also during the prefix, so its memory is a real game's), every hour 0
              from day 6 the proposal, plant extras / gates, the cassette (optionally a season cassette with the other
              leaders' figures: scripts/merge_cassette_20260930.py), free-fill and build_plan (the tiler) -> the day's
              tile plan;
  execution   from day 11 the tile plan's day (plantings, one-time harvests, new structures and animals vs our board,
              digs, crew) goes to the time-based path-partition executor (TPPAgent of tpp_smoke_20260930.py: mandatory /
              non-mandatory / slack, priority bring-backs, strawberry / wool / milk sold first, arm-i settings).
The opponent replays its recorded game (logged weeds, exact purchase credit). Compared with DSM's own continuation.

usage: fullstack_smoke_20260930.py EP [--tag A] [--project d9c4o] [--cassette FILE] [--until-day 12]
       [--opening agents/router4q_dsm_lr.py]   (days 0-10 from the 4Q tape router instead of DSM's recording)"""
import argparse
import gzip
import importlib.util
import json
import os
import sys
import time
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import tpp_smoke_20260930 as TS  # noqa: E402

PP = TS.PP
STUDY = TS.STUDY
PREFIX = 264
PASS = {"farmer": ["PASS"], "hands": [], "market": []}


class Semantic:
    """the candidate's planning layer without its executor"""

    def __init__(self, project, cassette=None, until_day=None):
        self.project = Path(project).resolve()
        cwd = os.getcwd()
        os.chdir(self.project)
        spec = importlib.util.spec_from_file_location("semantic_entry_fs", self.project / "agents/semantic_strategy_20260928.py")
        self.M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.M)
        self.state = self.M._initialize()
        os.chdir(cwd)
        if cassette:
            self.state["config"]["cassette"] = dict(self.state["config"].get("cassette") or {}, file=str(Path(cassette).resolve()))
        if until_day is not None:
            self.state["config"].setdefault("cassette", {})["until_day"] = int(until_day)
        self.plans, self.diag = {}, {}

    def observe(self, observation, t):
        obs = dict(observation)
        day, hour = divmod(t, 24)
        obs.update(day=day, hour=hour)
        st_ = self.state
        st_["policy_memory"] = st_["policy"].observe(obs, st_["policy_memory"], st_["last_action"])
        self.M._observe_own(obs, st_["tile_memory"])
        if t >= 144 and hour == 0 and day != st_["day"]:
            self.plan_day(obs, day)
        return obs

    def plan_day(self, obs, day):
        st_ = self.state
        me = int(obs["player"])
        st_["morning_land"] = len(obs["farms"][me]["unlocked_quadrants"])
        st_["policy_memory"]["committed_retirement_counts"] = self.M._committed_retirements(st_, obs)
        proposal = st_["policy"].propose(obs, st_["policy_memory"])
        st_["policy_memory"] = proposal["memory"]
        open_ = {s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])}
        for crop_, n_ in ((st_["config"].get("plant_extra") or {}).get(str(day)) or {}).items():   # as agent()
            pc_ = proposal["today"].setdefault("plant_counts", {})
            gate_ = (st_["config"].get("plant_extra_gate") or {}).get(crop_)
            if gate_ and not open_ & set(gate_):
                continue
            if st_["config"].get("plant_extra_topup"):
                have_ = sum(1 for r_ in obs["farms"][me]["tiles"] for t_ in r_ if isinstance(t_, dict) and t_.get("crop") == crop_)
                pc_[crop_] = max(int(pc_.get(crop_, 0)), int(n_) - have_)
            else:
                pc_[crop_] = int(pc_.get(crop_, 0)) + int(n_)
        for crop_, gate_ in (st_["config"].get("plant_gate") or {}).items():
            if not open_ & set(gate_):
                proposal["today"].setdefault("plant_counts", {}).pop(crop_, None)
        self.M._cassette_apply(st_, obs, proposal, day)
        self.M._fill_free_apply(st_, obs, proposal, day)
        plan, st_["tile_memory"], audit = self.M._build_plan(obs, proposal, st_["tile_memory"], st_["config"].get("tiles"))
        st_["day"] = day
        self.plans[day] = self.to_tpp(plan, day, obs)
        self.diag[day] = dict(proposal=deepcopy(proposal["today"]), cassette=deepcopy(st_.get("cassette_last")),
                              warnings=(plan.get("planner_metadata") or {}).get("warnings"))

    @staticmethod
    def to_tpp(plan, day, obs):
        """the tile plan's day in the executor's terms; structures / animals = the plan's end-of-day targets not yet on
        our board (robust to the daily re-plan)"""
        me = int(obs["player"])
        tiles = obs["farms"][me]["tiles"]
        xy = lambda i: (int(i) % 10, int(i) // 10)  # noqa: E731
        plant = {xy(i): c for i, c in ((plan.get("plant") or [])[day] or {}).items()} if day < len(plan.get("plant") or []) else {}
        harvest = {xy(i) for i in ((plan.get("harv_tiles") or [])[day] or [])} if day < len(plan.get("harv_tiles") or []) else set()
        build, place = {}, {}
        for i, k in (((plan.get("struct_by_day") or [])[day] or {}) if day < len(plan.get("struct_by_day") or []) else {}).items():
            x, y = xy(i)
            t = tiles[y][x]
            if not (isinstance(t, dict) and t.get("kind") == k):
                build[(x, y)] = k
        for i, sp in (((plan.get("animals_by_day") or [])[day] or {}) if day < len(plan.get("animals_by_day") or []) else {}).items():
            x, y = xy(i)
            t = tiles[y][x]
            if not (isinstance(t, dict) and t.get("animal") == sp):
                place[(x, y)] = sp
        rem = (plan.get("removals") or [])[day] if day < len(plan.get("removals") or []) else []
        dig = set()
        for r in rem or []:
            # tiler removals are [tile, crop, planted_day] (semantic_tile_planner_20260928)
            i = r.get("tile", r.get("idx")) if isinstance(r, dict) else (r[0] if isinstance(r, (list, tuple)) else r)
            if i is not None:
                dig.add(xy(i))
        hands = (plan.get("hands") or [])
        units = int(hands[day]) + 1 if day < len(hands) and hands[day] is not None else 13
        land_day = plan.get("land_day") or {}
        land_target = 1 + sum(1 for q_, d_ in land_day.items() if d_ is not None and int(d_) <= day)
        return dict(plant=plant, harvest=harvest, build=build, place=place, dig=dig, units=units, land_target=land_target)


def run(a):
    import semantic_h2h_20260929 as SH
    sys.path.insert(0, str(TS.HARNESS))
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    CR, AN = PP._engine_tables()
    ep = a.ep
    rec = json.loads(gzip.decompress((STUDY / f"recordings_d4q9/{ep}.json.gz").read_bytes()))
    seat, lead = int(rec["seat"]), 1 - int(rec["seat"])
    SH._leader_credit_exact(lead, json.loads((ROOT / f"results/fresh/semantic_h2h_20260929/leader_commits/d4q9-{ep}.json")
                                             .read_text())["steps"])
    spawns = json.loads((TS.GAMES / f"d4q9-{ep}.dsm.result.spawns.json").read_text())[lead]
    sem = Semantic(STUDY / "candidates" / a.project / "project", a.cassette, a.until_day)
    cfg = dict(crew="dsm", bring=2, bring_cap=8, fix=1, fert_keep=20, care_n=1, precheck=1, room=1, bb_mode=1, max_bring=6,
               front_deadline=10, sb_fert=1, animal_slack=1, sb_bring=0, sb_deadline=20, fert_use=1, sb_morning=0, eve_drop=1,
               buy_land=a.fixes, cash_first=a.fixes)
    agent = TS.TPPAgent({}, cfg, CR, AN)
    agent.plans = sem.plans                              # filled at each hour 0 by the planner
    tiles, lookup, frames = [], {}, []

    def tid(t):
        v = {k: t[k] for k in TS.PP_TILE_KEYS if k in t} if isinstance(t, dict) else t
        key = json.dumps(v, sort_keys=True, separators=(",", ":"))
        if key not in lookup:
            lookup[key] = len(tiles)
            tiles.append(v)
        return lookup[key]
    om = E._process_market

    def pm(state, env, *x, **k):
        obs = state[0].observation
        farm = obs.farms[seat]
        act = state[seat].action
        frames.append(dict(t=int(obs.step), m=[int(obs.farms[seat]["money"]), int(obs.farms[lead]["money"])],
                           u=[list(farm["farmer"])] + [list(h) for h in farm["hands"]],
                           b=[tid(t) for row in farm["tiles"] for t in row],
                           sh={g: int(v) for g, v in dict(state[seat].observation.private["shed"]).items() if int(v or 0)},
                           a=deepcopy(act) if isinstance(act, dict) else None,
                           p=[int(obs.market["prices"].get(g, 0)) for g in PP.GOODS],
                           s=list(obs.town["unlocked_shops"]), q=len(farm.get("unlocked_quadrants") or [])))
        return om(state, env, *x, **k)
    E._process_market = pm
    errors, plan_s = [], []

    def ours(obs, t):
        try:
            t0 = time.perf_counter()
            sem.observe(obs, t)
            plan_s.append(time.perf_counter() - t0)
        except Exception:
            errors.append((t, "planner " + traceback.format_exc()))
        if t < PREFIX:
            act = deepcopy(rec["our_actions"][t]) if rec["our_actions"][t] else PASS
        else:
            try:
                act = agent.act(obs, t)
            except Exception:
                errors.append((t, traceback.format_exc()))
                act = PASS
        sem.state["last_action"] = act
        return act

    def opp(obs, t):
        x = rec["opp_actions"][t] if t < len(rec["opp_actions"]) else None
        return deepcopy(x) if x else PASS
    env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 100000}, info={"seed": rec["seed"]})
    players = [ours, opp] if seat == 0 else [opp, ours]
    if a.opening == "candidate":
        # 2026-09-30 (user: "didn't we already build day 6-8 and 9-11 routers?"): days 0-10 by the candidate itself -
        # its tape-router opening (days 0-5), then its planner + cassette + its own executor (days 6-10, land included);
        # its live planner state is handed to the path-partition executor at the day-11 dawn
        orig_ours_c = ours

        def ours(obs, t):                               # noqa: F811
            if t < PREFIX:
                try:
                    act = sem.M.agent(obs, env.configuration)
                    sem.state = sem.M._STATE
                except Exception:
                    errors.append((t, "candidate " + traceback.format_exc()))
                    act = PASS
                return act
            return orig_ours_c(obs, t)
        players = [ours, opp] if seat == 0 else [opp, ours]
    elif a.opening:
        # 2026-09-30 (user: "assemble with the opening predictor"): days 0-10 from the 4Q tape router (it picks a leader
        # tape by the revealed shops, land guard on days 6-10), handover to the planner + executor at the day-11 dawn
        from kaggle_environments.agent import get_last_callable
        src = (ROOT / a.opening).read_text(encoding="utf-8")
        router = get_last_callable(src, path=str(ROOT / a.opening))
        orig_ours = ours

        def ours(obs, t):                               # noqa: F811
            if t < PREFIX:
                try:
                    sem.observe(obs, t)
                except Exception:
                    errors.append((t, "planner " + traceback.format_exc()))
                try:
                    act = router(obs, env.configuration)
                except Exception:
                    errors.append((t, "router " + traceback.format_exc()))
                    act = PASS
                sem.state["last_action"] = act
                return act
            return orig_ours(obs, t)
        players = [ours, opp] if seat == 0 else [opp, ours]
    t0 = time.time()
    try:
        res = TV._play(E, env, players, seat, rec["shops"], spawns, lead, lead)
    finally:
        E._process_market = om
    final = res["final"]
    key = f"fs{a.tag}.p{PREFIX}"
    g = dict(tiles=tiles, frames=frames, cash=final[seat], opp_cash=final[lead], margin=final[seat] - final[lead],
             daily=res["daily"], shops=rec["shops"][30], seat=seat, errors=[e[1][-800:] for e in errors[:5]],
             diag={str(d): {k: (dict(v) if isinstance(v, Counter) else v) for k, v in x.items()} for d, x in agent.diag.items()},
             plan_diag={str(d): x for d, x in sem.diag.items()})
    with gzip.open(TS.GAMES / f"d4q9-{ep}.{key}.game.json.gz", "wt", encoding="utf-8") as f:
        json.dump(g, f, separators=(",", ":"), default=list)
    dsm = json.loads(gzip.open(TS.GAMES / f"d4q9-{ep}.dsm.game.json.gz", "rt", encoding="utf-8").read())
    dsm_frame11 = dsm["frames"][PREFIX]
    d11 = next((f for f in frames if f["t"] == PREFIX), None)
    if d11:
        print(f"day-11 dawn: quadrants {d11['q']}, cash {d11['m'][0]} (DSM {dsm_frame11['m'][0]}, quadrants {dsm_frame11['q']})")
    print(f"world {ep} full stack {a.tag} ({a.project}, opening {a.opening or 'DSM prefix'}, cassette {Path(a.cassette).name if a.cassette else 'as configured'}, "
          f"until {a.until_day}): ours {final[seat]:.0f} vs DSM {dsm['cash']:.0f} ({final[seat] - dsm['cash']:+.0f}); opponent "
          f"{final[lead]:.0f} (DSM game {dsm['opp_cash']:.0f}); margin {final[seat] - final[lead]:+.0f} (DSM {dsm['margin']:+.0f}); "
          f"errors {len(errors)}; planner {sum(plan_s):.1f}s; {time.time() - t0:.0f}s")
    for e in errors[:2]:
        print("ERROR at", e[0], e[1][-1200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--tag", default="A")
    ap.add_argument("--project", default="d9c4o")
    ap.add_argument("--cassette", default=None)
    ap.add_argument("--until-day", dest="until_day", type=int, default=None)
    ap.add_argument("--opening", default=None)
    ap.add_argument("--fixes", type=int, default=1, help="executor buys the plan's land and buys cash-first (0 = as before)")
    a = ap.parse_args()
    run(a)


if __name__ == "__main__":
    main()
