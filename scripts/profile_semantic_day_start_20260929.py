"""Profile a semantic-stack candidate's day-start (hour 0) calls on days >= 6 in one full game vs MGT through the
frozen harness (research mode, no time limit). Shipping needs the whole game inside the 60 s overage bank; n17 uses
~100 s, all of it at hour 0 on days 6-28 (the executor's day plan; the semantic planner is ~0.3 s).

usage: profile_semantic_day_start_20260929.py --candidate n17 [--case h2h-00-s0] [--seeds ...] [--shops-ref DIR]
       [--days 6-29] [--out stats.prof] [--result game.json]
prints each profiled call's wall time and the top functions by cumulative / own time inside the profiled calls"""
import argparse
import cProfile
import json
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_h2h_20260929 as SH  # noqa: E402

H = ROOT / "results/fresh/semantic_h2h_20260929"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="n17")
    ap.add_argument("--case", default="h2h-00-s0")
    ap.add_argument("--seeds", default=str(H / "seeds_fresh8.json"))
    ap.add_argument("--shops-ref", default=str(H / "shops_ref/fresh8"))
    ap.add_argument("--days", default="6-29")
    ap.add_argument("--out", default=None)
    ap.add_argument("--result", required=True, help="write the game's result json here")
    ap.add_argument("--no-profile", action="store_true", help="time the calls only")
    a = ap.parse_args()
    d0, d1 = (int(x) for x in a.days.split("-"))
    study = H / "study"
    case = next(c for c in json.loads(Path(a.seeds).read_text())["cases"] if c["id"] == a.case)
    job = dict(study=str(study), case=case, kind="live", output=a.result, candidate=a.candidate)
    ref = json.loads((Path(a.shops_ref) / f"{case['id']}.json").read_text())
    job["force_shops"] = SH.shops_by_day(ref["shops"])
    import kaggle_environments as KE
    orig_make = KE.make

    def make(*x, **k):
        cfg = dict(k.get("configuration") or {})
        cfg["actTimeout"] = 100000
        k["configuration"] = cfg
        return orig_make(*x, **k)
    KE.make = make
    harness = study / "candidates" / a.candidate / "harness"
    G = SH._load_gate(harness)
    prof = cProfile.Profile()
    calls = []
    orig_le = G.load_entry

    def load_entry(path, project, *x, **k):
        fn, config, loading = orig_le(path, project, *x, **k)
        if "semantic_strategy" not in str(path):
            return fn, config, loading

        def wrapped(obs, *args, **kw):
            step = int(obs["step"])
            if step % 24 == 0 and d0 <= step // 24 <= d1:
                t = time.perf_counter()
                if not a.no_profile:
                    prof.enable()
                try:
                    return fn(obs, *args, **kw)
                finally:
                    if not a.no_profile:
                        prof.disable()
                    calls.append((step // 24, round(time.perf_counter() - t, 2)))
            return fn(obs, *args, **kw)
        return wrapped, config, loading
    G.load_entry = load_entry
    SH._drop_runner_modules()
    import types
    me = Path(__file__).resolve()                  # this runner too (the harness audit rejects unfrozen repo modules)
    for k, m in list(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if f and Path(f).resolve() == me:
            sys.modules[k] = types.ModuleType(k)
    t0 = time.time()
    row = G.play_job(job)
    print("game done in %.0f s, margin %s, cash %s, error %s" % (time.time() - t0, row.get("margin"), row.get("cash"),
                                                                 (row.get("error") or "")[-300:]))
    print("profiled hour-0 calls (day, s):", calls, "total %.1f" % sum(c[1] for c in calls))
    if a.no_profile:
        return
    if a.out:
        prof.dump_stats(a.out)
    st = pstats.Stats(prof)
    st.sort_stats("cumulative").print_stats(45)
    st.sort_stats("tottime").print_stats(30)


if __name__ == "__main__":
    main()
