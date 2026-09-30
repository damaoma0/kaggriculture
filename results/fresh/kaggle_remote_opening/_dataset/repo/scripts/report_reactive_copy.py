"""Verify and compare the observation-only reactive copying baseline."""
from copy import deepcopy
import json
from statistics import mean, median
from evaluate_boards import ROOT, module_at, observation


def main():
    out = ROOT / "results/fresh/reactive_copy"
    rows = json.loads((out/"panel.json").read_text())
    reference = json.loads((ROOT/"results/fresh/router_handoff/panel.json").read_text())
    assert len(rows) == 8
    verified = 0
    lags = []
    for seat in (0,1):
        replay = json.loads((out/f"seed86301-seat{seat}/full_replay.json").read_text())
        module = module_at("verify_copier",ROOT/"agents/reactive_copy.py")
        for t in range(719):
            obs = observation(replay["steps"][t],seat)
            original = deepcopy(obs)
            assert module.agent(obs) == replay["steps"][t+1][seat]["action"]
            assert obs == original
            verified += 1
        farms = replay["steps"][216][0]["observation"]["farms"]
        for y in range(10):
            for x in range(10):
                a,b = farms[seat]["tiles"][y][x],farms[1-seat]["tiles"][y][x]
                if isinstance(a,dict) and isinstance(b,dict) and a.get("kind") == b.get("kind") == "PLANT" and a["crop"] == b["crop"]:
                    lags.append(a["planted_day"]-b["planted_day"])
    groups = [("Reactive copy throughout",rows)]
    for name,mode,label in (("small-herd","replant","Growth → replant"),("small-herd","router","Growth → router"),("public-router","router","Router throughout (self-play)")):
        groups.append((label,[r for r in reference if r["name"]==name and r["continuation"]==mode]))
    lines = ["# Reactive public-board copying", "", "## Definition", "",
             "The copier sees the opponent's currently occupied crop/animal tiles, land ownership and worker count. It targets the same coordinates on its own farm and uses the observation-driven worker scheduler from opening_v2. It does not read opponent actions, private inventories, recorded routes or future state. Copying therefore starts after the opponent's investment becomes visible.", "",
             "It protects and finishes existing own crops even after the opponent changes the matching tile. Empty plots adopt the opponent's current crop or animal. It matches visible crew up to 12 hands, buys NE only after the opponent owns it and cash permits, and keeps a 300 cash land buffer. It does not apply fertilizer or synchronize harvest timing; its own scheduler sells produce. New animals stop at day 20, new crops must have time to mature by day 29, and the last seven turns return and sell stock. This version supports the two quadrants used by the reference router. It is one specific copying baseline, not the best achievable copying strategy.", "",
             "## Matched comparison", "",
             "Four seed pairs (86301–86304 / 96301–96304), both seats; same scenarios as the handoff experiment. The copier continues its own state across the day-9 checkpoint. The opponent runs the full public router throughout. All scores are terminal cash. Opening-dependent market and random-draw differences remain part of each strategy's outcome.", "",
             "| Strategy | Our mean cash | Opponent mean cash | Mean margin |", "|---|---:|---:|---:|"]
    for label,group in groups:
        lines.append(f"| {label} | {mean(r['our_final'] for r in group):,.0f} | {mean(r['router_final'] for r in group):,.0f} | {mean(r['margin'] for r in group):+,.0f} |")
    handoff = {(r["seed"],r["seat"]):r for r in groups[2][1]}
    gains = [r["margin"]-handoff[r["seed"],r["seat"]]["margin"] for r in rows]
    lines += ["", f"Relative to growth → router, copying improved margin in {sum(g>0 for g in gains)}/8 matched scenarios, with mean margin change {mean(gains):+,.0f}. Copying won {sum(r['margin']>0 for r in rows)}/8 matches against the router.", "",
              "## Checks and limits", "",
              f"All eight games completed with valid intermediate statuses and exact continuation cash accounting. Verified {verified:,} full-game actions through the copier's file entry point with no observation mutation. Seed allocation was checked on every decision. Opening losses: {sum(sum(r['opening_losses'].values()) for r in rows)}; later premature crop losses: {sum(r['tail_losses'].get('premature_crop',0) for r in rows)}; later animal losses: {sum(r['tail_losses'].get('animal',0) for r in rows)}.", "",
              f"In the saved seed-86301 games, {len(lags)} matching day-9 crop tiles across both seats had median planting delay {median(lags) if lags else 'N/A'} days. This is a diagnostic on matching surviving crops, not a population-wide estimate of copying delay.", "",
              "The two newly supported scheduler cases are TOMATO seed purchases and harvesting at age 8; previous opening layouts contain no tomatoes. Existing opening and router-handoff entry-point checks passed unchanged. The copier is a local multi-file agent and is not a standalone submission bundle.", "",
              "## Per-scenario results", "", "| Seed | Seat | Copier cash | Router cash | Margin change vs growth → router |", "|---:|---:|---:|---:|---:|"]
    for r in sorted(rows,key=lambda r:(r['seed'],r['seat'])):
        gain=r['margin']-handoff[r['seed'],r['seat']]['margin']
        lines.append(f"| {r['seed']} | {r['seat']} | {r['our_final']:,.0f} | {r['router_final']:,.0f} | {gain:+,.0f} |")
    lines += ["", "[Full replay](../results/fresh/reactive_copy/seed86301-seat0/full_replay.json) · [Raw results](../results/fresh/reactive_copy/panel.json)", "", "```powershell", ".venv/Scripts/python.exe scripts/test_reactive_copy.py", ".venv/Scripts/python.exe scripts/report_reactive_copy.py", "```", "", "The test runner refuses to overwrite saved replay folders; use a fresh output directory in the script for reruns.", ""]
    (ROOT/"docs/reactive_copy.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"PASS {verified} actions.")
    print("\n".join(lines[12:20]))


if __name__ == "__main__":
    main()
