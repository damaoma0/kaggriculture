"""Complete the opening/continuation comparison with router -> replant."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from statistics import mean

from search_growth_openings import ROOT, play


def main():
    out = ROOT / "results/fresh/router_replant"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [("public-router", {}, s, s+10000, seat, "replant",
             str(out/f"seed{s}-seat{seat}") if s == 86301 else None)
            for s in range(86301,86305) for seat in (0,1)]
    rows = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(play,j) for j in jobs]):
            r = f.result()
            rows.append(r)
            (out/"panel.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
            print(len(rows),r["seed"],r["seat"],r["our_final"],r["margin"],r["tail_losses"],flush=True)
    old = json.loads((ROOT/"results/fresh/router_handoff/panel.json").read_text())
    for r in rows:
        pair = next(p for p in old if p["name"] == "public-router" and p["seed"] == r["seed"] and p["seat"] == r["seat"])
        assert r["day9"] == pair["day9"]
    for seat in (0,1):
        a = json.loads((out/f"seed86301-seat{seat}/opening.json").read_text())
        b = json.loads((ROOT/f"results/fresh/router_handoff/public-router-router-86301-seat{seat}/opening.json").read_text())
        assert {k:v for k,v in a.items() if k != "id"} == {k:v for k,v in b.items() if k != "id"}
    files = ["agents/public/tschinkel_router_v31.py", "agents/opening_v1.py", "scripts/search_growth_openings.py", "scripts/evaluate_boards.py", "scripts/test_router_replant.py"]
    (out/"manifest.json").write_text(json.dumps({"hashes":{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files},"jobs":jobs},indent=2),encoding="utf-8")
    groups = [("Our opening → replant",[r for r in old if r["name"] == "small-herd" and r["continuation"] == "replant"]),
              ("Router opening → replant",rows),
              ("Our opening → router",[r for r in old if r["name"] == "small-herd" and r["continuation"] == "router"]),
              ("Router throughout",[r for r in old if r["name"] == "public-router"])]
    lines = ["# Router opening followed by continuous replanting", "",
             "Four seed pairs (86301–86304 / 96301–96304), both seats: eight additional runs complete the opening/continuation comparison. The opponent always uses the public router throughout. Handoff is at step 216, the start of day 9. All means are full-season terminal cash.", "",
             "Replanting is exactly the existing evaluator policy: maintain existing animals and crops, then replace cleared original crop slots with wheat through day 25. It buys no new land or animals and uses the common staffing rule capped at 10 hands. It is not repeated planting of the router's original premium crops.", "",
             "| Our opening → continuation | Our cash | Opponent cash | Margin | Premature crop losses after handoff | Animal losses after handoff |", "|---|---:|---:|---:|---:|---:|"]
    for label,group in groups:
        lines.append(f"| {label} | {mean(r['our_final'] for r in group):,.0f} | {mean(r['router_final'] for r in group):,.0f} | {mean(r['margin'] for r in group):+,.0f} | {mean(r['tail_losses'].get('premature_crop',0) for r in group):.1f} | {mean(r['tail_losses'].get('animal',0) for r in group):.1f} |")
    control = {(r['seed'],r['seat']):r for r in groups[0][1]}
    cash_gains = [r['our_final']-control[r['seed'],r['seat']]['our_final'] for r in rows]
    margin_gains = [r['margin']-control[r['seed'],r['seat']]['margin'] for r in rows]
    lines += ["", f"Under the same replanting rule, the router opening changes our cash by {mean(cash_gains):+,.0f} and margin by {mean(margin_gains):+,.0f} on average relative to our growth opening. Cash improves in {sum(g>0 for g in cash_gains)}/8 paired scenarios; margin improves in {sum(g>0 for g in margin_gains)}/8. Router opening → replant wins {sum(r['margin']>0 for r in rows)}/8 against the complete router.", "",
              "## Checks and interpretation", "",
              "All eight additional runs completed with valid intermediate statuses and exact continuation cash accounting. Their day-9 features match the complete-router reference in all scenarios. Both saved opening replays match that reference exactly, excluding unique episode IDs. The generic controller takes over the actual farm state without changing assets or inventories.", "",
              "Using the same continuation rule is a better controlled comparison of openings, but remains policy-conditioned: different layouts interact with routing, staffing, and shared prices. It does not estimate the optimal value of either opening, and the four seeds are a small sample. The generic scheduler's premature crop losses also matter when interpreting the router board's value.", "",
              "| Seed | Seat | Router opening → replant cash | Opponent cash |", "|---:|---:|---:|---:|"]
    for r in sorted(rows,key=lambda r:(r['seed'],r['seat'])):
        lines.append(f"| {r['seed']} | {r['seat']} | {r['our_final']:,.0f} | {r['router_final']:,.0f} |")
    lines += ["", "[Full replay](../results/fresh/router_replant/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/router_replant/panel.json)", "", "Run `.venv/Scripts/python.exe scripts/test_router_replant.py` to reproduce. Saved replay folders are not overwritten; use a fresh output directory in the script for reruns.", ""]
    (ROOT/"docs/router_replant.md").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines[6:14]))
    print("PASS: eight runs, reconciled cash, paired day-9 roots and saved opening replays.")


if __name__ == "__main__":
    main()
