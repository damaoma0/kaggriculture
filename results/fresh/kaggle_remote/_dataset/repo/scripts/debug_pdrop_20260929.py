"""Debug the mid-day drop (sd_tier_pdrop) in one local game vs MGT: wraps the executor's _tier_pdrop and prints, per day and
planning pass, the drops made and the planner's reasons (why-counters). usage: debug_pdrop_20260929.py CAND [CASE]"""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_h2h_20260929 as SH  # noqa: E402

H = ROOT / "results/fresh/semantic_h2h_20260929"


def main():
    cand, cid = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "h2h-00-s0")
    case = next(c for c in json.loads((H / "seeds_fresh8.json").read_text())["cases"] if c["id"] == cid)
    job = dict(study=str(H / "study"), case=case, kind="live", output=str(ROOT / "results/fresh/tmp_debug_pdrop.json"), candidate=cand)
    job["force_shops"] = SH.shops_by_day(json.loads((H / "shops_ref/fresh8" / f"{cid}.json").read_text())["shops"])
    import kaggle_environments as KE
    om = KE.make
    KE.make = lambda *a, **k: om(*a, **dict(k, configuration=dict(k.get("configuration") or {}, actTimeout=100000)))
    G = SH._load_gate(H / "study/candidates" / cand / "harness")
    log = []
    ole = G.load_entry

    def le(path, project, *a, **k):
        fn, cfg, lo = ole(path, project, *a, **k)
        if "semantic_strategy" not in str(path):
            return fn, cfg, lo

        def w(obs, *x, **kw):
            r = fn(obs, *x, **kw)
            st = fn.__globals__.get("_STATE")
            kb = st and st.get("kb")
            if kb is not None and not getattr(kb, "_pdrop_wrapped", False):
                orig = kb._tier_pdrop

                def pd(S, segs, tiles, day, st_):
                    n = orig(S, segs, tiles, day, st_)
                    rec = (st_.get("_pdrop_day") or [{}])[-1]
                    log.append(dict(day=day, drops=n, why=dict(rec.get("why") or {}), units=dict(rec.get("units") or {}),
                                    need=rec.get("need"), routes=len(segs), days=kb.CFG.get("sd_tier_pdrop_days")))
                    return n
                kb._tier_pdrop = pd
                kb._pdrop_wrapped = True
            return r
        return w, cfg, lo
    G.load_entry = le
    SH._drop_runner_modules()
    me = Path(__file__).resolve()
    for k, m in list(sys.modules.items()):
        if getattr(m, "__file__", None) and Path(m.__file__).resolve() == me:
            sys.modules[k] = types.ModuleType(k)
    row = G.play_job(job)
    print("margin", row.get("margin"), (row.get("error") or "")[-200:])
    for x in log:
        if 6 <= x["day"] <= 11:
            print(x)


if __name__ == "__main__":
    main()
