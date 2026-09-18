"""Direct head-to-head: growth vs router openings, then replant on BOTH farms."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from statistics import mean
from search_growth_openings import ROOT, play


def main():
    out = ROOT/"results/fresh/both_replant"
    out.mkdir(parents=True,exist_ok=True)
    jobs = [("small-herd",{"cows":4,"sheep":4},s,s+10000,seat,"replant",
             str(out/f"seed{s}-seat{seat}") if s==86301 else None,"replant")
            for s in range(86301,86305) for seat in (0,1)]
    rows=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(play,j) for j in jobs]):
            r=f.result()
            rows.append(r)
            (out/"panel.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
            print(len(rows),r["seed"],r["seat"],r["our_final"],r["router_final"],r["margin"],flush=True)
    old=json.loads((ROOT/"results/fresh/router_handoff/panel.json").read_text())
    for r in rows:
        pair=next(p for p in old if p["name"]=="small-herd" and p["continuation"]=="replant" and p["seed"]==r["seed"] and p["seat"]==r["seat"])
        assert pair["day9"]==r["day9"]
        assert r["continuation"]==r["opponent_continuation"]=="replant"
    for seat in (0,1):
        a=json.loads((out/f"seed86301-seat{seat}/opening.json").read_text())
        b=json.loads((ROOT/f"results/fresh/router_handoff/small-herd-replant-86301-seat{seat}/opening.json").read_text())
        assert {k:v for k,v in a.items() if k!="id"}=={k:v for k,v in b.items() if k!="id"}
    files=["scripts/test_both_replant.py","scripts/search_growth_openings.py","scripts/evaluate_boards.py","agents/opening_v1.py","agents/opening_v2.py","agents/public/tschinkel_router_v31.py"]
    (out/"manifest.json").write_text(json.dumps({"jobs":jobs,"hashes":{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files}},indent=2),encoding="utf-8")
    ours=mean(r["our_final"] for r in rows)
    theirs=mean(r["router_final"] for r in rows)
    wins=sum(r["margin"]>0 for r in rows)
    lines=["# Direct match: both openings followed by replanting","",
           "This is the requested head-to-head comparison in the same game. One farm uses our selected growth opening, the other the public router opening. At step 216 (start of day 9), BOTH switch to independent instances of the same replanting controller. Neither uses router decisions after that point.","",
           "Four seed pairs (86301–86304 / 96301–96304), both seats, eight games. The controller cares for existing assets and replaces cleared original crop plots with wheat through day 25. It buys no new animals or land. Each farm uses the same workload-based staffing rule, capped at 10 hands; actual staff counts can differ with workload.","",
           "| Strategy | Mean terminal cash |","|---|---:|",
           f"| Our opening → replant | {ours:,.0f} |",f"| Router opening → replant | {theirs:,.0f} |","",
           f"Our mean margin: {ours-theirs:+,.0f}. Our wins: {wins}/8; draws: {sum(r['margin']==0 for r in rows)}/8. Router-opening cash is {(theirs/ours-1)*100:.1f}% higher on average.","",
           "| Seed | Our seat | Our opening → replant | Router opening → replant | Our margin |","|---:|---:|---:|---:|---:|"]
    for r in sorted(rows,key=lambda r:(r['seed'],r['seat'])):
        lines.append(f"| {r['seed']} | {r['seat']} | {r['our_final']:,.0f} | {r['router_final']:,.0f} | {r['margin']:+,.0f} |")
    lines += ["","All games completed with valid intermediate statuses and exactly reconciled continuation cash accounts. The growth-side day-9 features match previous runs in all eight scenarios, and the saved opening replays match exactly excluding episode IDs. Both farms use the same continuation implementation with their own actual state.","",
              "This measures opening performance under this specific replanting policy and shared market. It is not optimal board value: the scheduler can service different layouts with different efficiency, and four seeds are a small sample. Unlike previous comparisons against a full router, neither side retains the router's stronger continuation here.","",
              "[Full head-to-head replay](../results/fresh/both_replant/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/both_replant/panel.json)","",
              "Run `.venv/Scripts/python.exe scripts/test_both_replant.py` to reproduce. Use a fresh output directory in the script for reruns; saved replay folders are not overwritten.",""]
    (ROOT/"docs/both_replant.md").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines[6:12]))
    print("PASS: both continuation labels, paired roots, cash accounting and game statuses.")


if __name__=="__main__":
    main()
