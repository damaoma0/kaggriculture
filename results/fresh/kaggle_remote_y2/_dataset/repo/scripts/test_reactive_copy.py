"""Evaluate public-board copying on the same scenarios as the router handoff."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from statistics import mean
from search_growth_openings import ROOT, play


def main():
    out = ROOT / "results/fresh/reactive_copy"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [("reactive-copy", {}, s, s+10000, seat, "copy", str(out/f"seed{s}-seat{seat}") if s == 86301 else None)
            for s in range(86301,86305) for seat in (0,1)]
    rows = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(play,j) for j in jobs]):
            r = f.result()
            rows.append(r)
            (out/"panel.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
            print(len(rows), r["seed"], r["seat"], r["our_final"], r["margin"], r["opening_losses"], r["tail_losses"],flush=True)
    files = ["agents/reactive_copy.py", "agents/opening_v2.py", "agents/public/tschinkel_router_v31.py", "scripts/search_growth_openings.py", "scripts/test_reactive_copy.py"]
    (out/"manifest.json").write_text(json.dumps({"hashes":{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files},"jobs":jobs},indent=2),encoding="utf-8")
    print("Mean cash",mean(r["our_final"] for r in rows),"opponent",mean(r["router_final"] for r in rows),"margin",mean(r["margin"] for r in rows))


if __name__ == "__main__":
    main()
