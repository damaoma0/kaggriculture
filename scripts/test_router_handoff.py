"""Compare a literal day-9 router splice with complete-router and service controls."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from statistics import mean

from search_growth_openings import ROOT, play


def main():
    out = ROOT / "results/fresh/router_handoff"
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for seed, future in ((86301, 96301), (86302, 96302), (86303, 96303), (86304, 96304)):
        for seat in (0, 1):
            for name, cfg, mode in (("small-herd", {"cows": 4, "sheep": 4}, "replant"),
                                    ("small-herd", {"cows": 4, "sheep": 4}, "router"),
                                    ("public-router", {}, "router")):
                save = str(out / f"{name}-{mode}-{seed}-seat{seat}") if seed == 86301 else None
                jobs.append((name, cfg, seed, future, seat, mode, save))
    rows = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(play, j) for j in jobs]):
            r = f.result()
            rows.append(r)
            (out / "panel.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(len(rows), r["name"], r["continuation"], r["seed"], r["seat"], r["our_final"], r["margin"], r["tail_losses"], flush=True)
    for name, mode in (("small-herd", "replant"), ("small-herd", "router"), ("public-router", "router")):
        group = [r for r in rows if (r["name"], r["continuation"]) == (name, mode)]
        print(name, mode, "cash", mean(r["our_final"] for r in group), "opponent", mean(r["router_final"] for r in group), "margin", mean(r["margin"] for r in group))
    files = ["agents/opening_v2.py", "agents/public/tschinkel_router_v31.py", "scripts/search_growth_openings.py", "scripts/test_router_handoff.py", "scripts/evaluate_boards.py"]
    (out / "manifest.json").write_text(json.dumps({"hashes": {p: sha256((ROOT/p).read_bytes()).hexdigest() for p in files}, "handoff_step": 216, "jobs": jobs}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
