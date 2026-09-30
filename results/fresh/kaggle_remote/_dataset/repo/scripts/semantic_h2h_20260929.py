"""Head-to-head of a frozen semantic-strategy candidate (full stack: semantic policy + tile compiler + executor) against the
study's packaged live opponent (mgt_v9lite) on NEW random seeds, through the candidate's own frozen harness
(`play_job`: official 1 s allowance + 60 s overage, both ledgers reconciled, frozen-file checks). The study's development
and qualification panels are not touched: seeds are drawn fresh and must not appear in its protocol.

usage: semantic_h2h_20260929.py seeds --n N --out SEEDS.json [--exclude protocol.json]
       semantic_h2h_20260929.py run --study DIR --candidate ID --seeds SEEDS.json --out DIR [--workers 4]
out: DIR/<case>.json (+ .actions.json, .log) as the harness writes them, DIR/summary.json."""
import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def all_seeds(x, out):
    if isinstance(x, dict):
        if isinstance(x.get("seed"), int):
            out.add(x["seed"])
        for v in x.values():
            all_seeds(v, out)
    elif isinstance(x, list):
        for v in x:
            all_seeds(v, out)
    return out


def make_seeds(n, out, exclude):
    used = all_seeds(json.loads(Path(exclude).read_text()), set()) if exclude else set()
    seeds = []
    while len(seeds) < n:
        s = secrets.randbits(32)
        if s not in used and s not in seeds:
            seeds.append(s)
    cases = [dict(id=f"h2h-{i:02d}-s{seat}", seed=s, seat=seat) for i, s in enumerate(seeds) for seat in (0, 1)]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(dict(excluded=len(used), cases=cases), indent=1))
    print(len(cases), "cases ->", out)


def _load_gate(harness):
    import importlib.util
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    spec = importlib.util.spec_from_file_location("frozen_gate", Path(harness) / "semantic_strategy_gate_20260928.py")
    G = importlib.util.module_from_spec(spec)
    sys.modules["frozen_gate"] = G
    spec.loader.exec_module(G)
    return G


def _worker(args):
    """one game in a fresh process (spawned workers cannot unpickle a function of a module loaded by path)"""
    harness, job, no_timeout = args
    if job.get("leader_credit") and job.get("kind") == "recorded":
        if job.get("leader_commits"):              # exact credit: only the real game's outcomes, whatever the cash
            _leader_credit_exact(1 - int(job["case"]["seat"]), json.loads(Path(job["leader_commits"]).read_text())["steps"])
        else:
            _leader_credit(1 - int(job["case"]["seat"]))
    if job.get("leader_weeds") and job.get("kind") in ("source_control", "recorded"):
        _leader_weeds(harness, job)
    if no_timeout:                                 # research mode: no agent time limit (the harness still measures and
        import kaggle_environments as KE           # flags overage); the packaged V9-lite's search is capped per reveal
        orig = KE.make

        def make(*a, **k):
            cfg = dict(k.get("configuration") or {})
            cfg["actTimeout"] = 100000
            k["configuration"] = cfg
            return orig(*a, **k)
        KE.make = make
    # this runner is the worker's __mp_main__; on the laptop it sits under the repository path, and the harness's
    # source-module audit (candidate code must be frozen files only) would reject the finished game for it
    _drop_runner_modules()
    return _load_gate(harness).play_job(job)


def _leader_weeds(harness, job):
    """the leader's weeds as recorded (2026-09-29: weeds share one RNG stream across both farms, so our different empty
    tiles moved the leader's weeds - its weed tile-hours rose e.g. 119 -> 1,127 - and its recorded plantings failed on
    them). The source control saves the leader's logged spawns; the candidate game forces them on the leader's farm
    through the harness's own spawns / spawn_seat arguments (tape_vs_bench._play)."""
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    import tape_vs_bench as TV
    orig = TV._play
    side = Path(str(job["output"])[:-5] + ".spawns.json")
    lead = 1 - int(job["case"]["seat"])
    if job["kind"] == "source_control":
        def play(*a, **k):
            r = orig(*a, **k)
            side.write_text(json.dumps(r["logged_spawns"]))
            return r
    else:
        sp = json.loads(Path(str(job["control"])[:-5] + ".spawns.json").read_text())[lead]

        def play(E, env, players, seat, shops_by_day, spawns, spawn_seat, record_seat, cushion=0):
            return orig(E, env, players, seat, shops_by_day, sp, lead, record_seat, cushion)
    TV._play = play


def _leader_credit(lead):
    """user 2026-09-29 (knockout bounds): the recorded leader's frozen purchases, hires and land never fail for cash; its
    money may go negative. Normal engine = our upper bound (a failed purchase can knock out the frozen plan), leader
    credit = our lower bound (the leader even spends money it would not have). Only the leader's farm is affected."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as K
    cur, big = {}, 10 ** 7
    o_pm, o_cu, o_hi, o_la = K._process_market, K._commit_unit, K._do_hire, K._do_buy_land

    def credited(farm, call):
        if farm is not cur.get("farm"):
            return call()
        farm["money"] += big                       # the check passes; the true cost is still deducted
        try:
            return call()
        finally:
            farm["money"] -= big

    def pm(state, env):
        cur["farm"] = state[0].observation.farms[lead]
        return o_pm(state, env)

    def cu(op, item, price, farm, private, market, *a, **k):
        if op.startswith("BUY"):
            return credited(farm, lambda: o_cu(op, item, price, farm, private, market, *a, **k))
        return o_cu(op, item, price, farm, private, market, *a, **k)
    K._process_market = pm
    K._commit_unit = cu
    K._do_hire = lambda farm, *a, **k: credited(farm, lambda: o_hi(farm, *a, **k))
    K._do_buy_land = lambda farm, *a, **k: credited(farm, lambda: o_la(farm, *a, **k))


def _leader_credit_exact(lead, steps):
    """exact credit (2026-09-29): the leader's BUY_* units, hires and land succeed exactly as many times per step as in
    its REAL game (scripts/leader_commits_20260929.py), whatever its cash; beyond that they fail as they did for real.
    Plain credit also let the over-requested orders that failed for cash in the real game succeed: an extra hire shifts
    every later hand command, and 11 of 32 recordings broke from day 2 for every arm. Only the leader's farm."""
    from collections import defaultdict
    from kaggle_environments.envs.kaggriculture import kaggriculture as K
    cur, big, used = {}, 10 ** 7, defaultdict(int)
    o_pm, o_cu, o_hi, o_la = K._process_market, K._commit_unit, K._do_hire, K._do_buy_land

    def allowed(key):
        return used[(cur["step"], key)] < int((steps.get(str(cur["step"])) or {}).get(key, 0))

    def credited(farm, call):
        farm["money"] += big
        try:
            return call()
        finally:
            farm["money"] -= big

    def pm(state, env, *a, **k):
        cur["farm"] = state[0].observation.farms[lead]
        cur["step"] = int(state[0].observation.step)
        return o_pm(state, env, *a, **k)

    def cu(op, item, price, farm, private, market, *a, **k):
        if farm is cur.get("farm") and op.startswith("BUY"):
            key = f"{op}:{item}"
            if not allowed(key):
                return False
            r = credited(farm, lambda: o_cu(op, item, price, farm, private, market, *a, **k))
            if r:
                used[(cur["step"], key)] += 1
            return r
        return o_cu(op, item, price, farm, private, market, *a, **k)

    def hi(farm, *a, **k):
        if farm is not cur.get("farm"):
            return o_hi(farm, *a, **k)
        if not allowed("HIRE"):
            return None
        n0 = len(farm["hands"])
        r = credited(farm, lambda: o_hi(farm, *a, **k))
        used[(cur["step"], "HIRE")] += int(len(farm["hands"]) > n0)
        return r

    def la(farm, *a, **k):
        if farm is not cur.get("farm"):
            return o_la(farm, *a, **k)
        if not allowed("BUY_LAND"):
            return None
        n0 = len(farm.get("unlocked_quadrants") or [])
        r = credited(farm, lambda: o_la(farm, *a, **k))
        used[(cur["step"], "BUY_LAND")] += int(len(farm.get("unlocked_quadrants") or []) > n0)
        return r
    K._process_market, K._commit_unit, K._do_hire, K._do_buy_land = pm, cu, hi, la


def _drop_runner_modules():
    """spawn registers this runner as both __mp_main__ and __main__; stand-ins without a __file__ take their place"""
    import types
    me = Path(__file__).resolve()
    for k, m in list(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if f and Path(f).resolve() == me:
            sys.modules[k] = types.ModuleType(k)


def shops_by_day(final):
    """the engine appends one shop at the end of every third day (next_day % 3 == 0, at most 8): day d has d // 3"""
    return [list(final[:min(len(final), d // 3)]) for d in range(31)]


def run(study, candidate, seeds, out, workers, no_timeout=False, only=None, force_from=None, leader_credit=False,
        leader_weeds=False):
    study = (ROOT / study).resolve() if not Path(study).is_absolute() else Path(study)
    for f in list(study.rglob("*.gz.raw")):        # bundle KGR_GZ_RAW: restore the byte-identical .gz payloads
        f.rename(str(f)[:-4])
    harness = study / "candidates" / candidate / "harness"
    protocol_seeds = all_seeds(json.loads((study / "protocol.json").read_text()), set())
    if seeds == "dev":                             # the study's own development live cases (already played by the study)
        cases = json.loads((study / "protocol.json").read_text())["development"]["live"]
    else:
        cases = json.loads((ROOT / seeds).read_text())["cases"]
        assert not any(c["seed"] in protocol_seeds for c in cases), "a seed belongs to the study's protocol"
    if only:                                       # a subset of the panel's case ids
        cases = [c for c in cases if c["id"] in only.split(",")]
    out = (ROOT / out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    jobs = [dict(study=str(study), case=c, kind="live", output=str(out / f"{c['id']}.json"), candidate=candidate)
            for c in cases if not (out / f"{c['id']}.json").exists()]
    if force_from:                                 # fixed-shop paired panel: every arm sees the reference game's shops
        for j in jobs:
            ref = json.loads((ROOT / force_from / f"{j['case']['id']}.json").read_text())
            j["force_shops"] = shops_by_day(ref["shops"])
    from concurrent.futures import ProcessPoolExecutor, as_completed

    def pool_run(js):
        with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
            futs = [pool.submit(_worker, (str(harness), j, no_timeout)) for j in js]
            for fu in as_completed(futs):
                try:
                    r_ = fu.result()
                    print(json.dumps({k: r_.get(k) for k in ("case", "kind", "completed", "eligible", "margin",
                                                              "recorded_cash_match")} if isinstance(r_, dict) else r_,
                                     default=str), flush=True)
                except Exception as exc:           # one broken worker must not stop the panel
                    print("worker failed:", repr(exc), flush=True)
    if cases and "file" in cases[0]:               # recorded opponents: source controls first (both tapes, recorded cash)
        ctl = out.parent / "_controls"
        ctl.mkdir(parents=True, exist_ok=True)
        cjobs = [dict(study=str(study), case=c, kind="source_control", output=str(ctl / f"{c['id']}.json"),
                      candidate=candidate, leader_weeds=bool(leader_weeds))
                 for c in cases if not (ctl / f"{c['id']}.json").exists()]
        print(len(cjobs), "source controls to play", flush=True)
        pool_run(cjobs)
        for j in jobs:
            j["kind"] = "recorded"
            j["control"] = str(ctl / f"{j['case']['id']}.json")
            j["leader_credit"] = bool(leader_credit)
            if leader_credit == "exact":           # the real game's market outcomes (leader_commits_20260929.py)
                j["leader_commits"] = str(ROOT / "results/fresh/semantic_h2h_20260929/leader_commits" / f"{j['case']['id']}.json")
            j["leader_weeds"] = bool(leader_weeds)
        ok = {c["id"] for c in cases if (ctl / f"{c['id']}.json").exists()
              and json.loads((ctl / f"{c['id']}.json").read_text()).get("recorded_cash_match")}
        jobs = [j for j in jobs if j["case"]["id"] in ok]
        print(len(ok), "of", len(cases), "controls reproduce the recorded cash", flush=True)
    print(len(jobs), "games to play", flush=True)
    pool_run(jobs)
    rows = []
    for c in cases:
        p = out / f"{c['id']}.json"
        if p.exists():
            r = json.loads(p.read_text())
            rows.append({k: r.get(k) for k in ("case", "completed", "eligible", "cash", "opponent_cash", "margin",
                                               "measured_overage_used", "wall_seconds", "error", "opponent_health_failure",
                                               "recorded_rival_audit")})
    (out / "summary.json").write_text(json.dumps(rows, indent=1, default=str))
    ok = [r for r in rows if r["eligible"]]
    print(f"{len(ok)}/{len(rows)} valid; wins {sum(r['margin'] > 0 for r in ok)}; mean margin "
          f"{sum(r['margin'] for r in ok) / max(1, len(ok)):+.0f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("seeds", "run"))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out")
    ap.add_argument("--exclude")
    ap.add_argument("--study", default="results/fresh/semantic_strategy_20260928")
    ap.add_argument("--candidate")
    ap.add_argument("--seeds")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-timeout", action="store_true")
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--force-shops-from", help="dir of reference results (one per case id) whose shops every game uses")
    ap.add_argument("--leader-credit", action="store_true", help="recorded leader's purchases never fail for cash")
    ap.add_argument("--leader-credit-exact", action="store_true",
                    help="lower bound: the leader's purchases / hires / land succeed exactly as in its real game")
    ap.add_argument("--leader-weeds", action="store_true", help="recorded leader's weeds forced as recorded")
    a = ap.parse_args()
    if a.command == "seeds":
        make_seeds(a.n, a.out, a.exclude)
    else:
        for cand in a.candidate.split(","):
            run(a.study, cand, a.seeds, str(Path(a.out) / cand), a.workers, a.no_timeout, a.only, a.force_shops_from,
                "exact" if a.leader_credit_exact else a.leader_credit, a.leader_weeds)


if __name__ == "__main__":
    main()
