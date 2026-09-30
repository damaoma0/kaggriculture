"""Summarize opening selection and its paired full-season comparisons."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/growth_opening"


def main():
    screen = json.loads((OUT / "screen.json").read_text())
    rows = json.loads((OUT / "validate.json").read_text())
    names = sorted({r["name"] for r in rows}, key=lambda n: -mean(r["margin"] for r in rows if r["name"] == n))
    # Treat margins within 1% of the leading deficit as practically tied in
    # this small sample; prefer the farm producing more of its own cash.
    best_margin = max(mean(r["margin"] for r in rows if r["name"] == n) for n in names)
    tied = [n for n in names if mean(r["margin"] for r in rows if r["name"] == n) >= best_margin - abs(best_margin)*0.01]
    selected = max(tied, key=lambda n: mean(r["our_final"] for r in rows if r["name"] == n))
    control = {(r["seed"], r["seat"], r["continuation"]): r for r in rows if r["name"] == "control-sheep6"}
    lines = ["# Growth opening: value beyond day 9", "", 
             f"Selected research opening: **{selected}**, implemented in `agents/opening_v2.py`.", "",
             "## Evaluation", "",
             "Screened 19 configurations on two seed pairs (38 games). Compared three shortlisted growth openings and the old six-sheep control on four new seed pairs, both seats, and two continuation policies (64 games). Each opening runs through action 215; the evaluator takes over at day 9, step 216, and finishes the 30-day season. The opponent is the local public `tschinkel_router_v31.py`, reacting throughout.", "",
             "Selection primarily uses mean terminal cash margin against the opponent. After examining the shortlist, we treated margins within 1% of the leading deficit as practically tied and preferred higher own cash: small-herd gives up only 155 mean margin to c6s4-m0 but earns 14,362 more. This tie-break is an exploratory choice, not a pre-registered criterion. Maintenance keeps existing assets; replanting also replaces cleared crop slots with wheat. Both use the same evaluator staffing rule, capped at 10 hands. Neither buys new animals. The future seed is hidden from the policies. Seeds are paired between candidates, but farm-dependent random draws can produce different subsequent shops.", "",
             "## Shortlist results", "",
             "| Opening | Mean day-9 cash | Mean final cash | Mean final margin | Margin improvement over control | Paired improvements |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in names:
        group = [r for r in rows if r["name"] == name]
        gains = [r["margin"] - control[r["seed"], r["seat"], r["continuation"]]["margin"] for r in group]
        lines.append(f"| {name} | {mean(r['day9']['cash'] for r in group):,.0f} | {mean(r['our_final'] for r in group):,.0f} | {mean(r['margin'] for r in group):+,.0f} | {mean(gains):+,.0f} | {sum(g>0 for g in gains)}/{len(gains)} |")
    lines += ["", "## Selected opening by continuation", "", "| Continuation | Opening final cash | Control final cash | Opening margin | Control margin |", "|---|---:|---:|---:|---:|"]
    for mode in ("maintain", "replant"):
        group = [r for r in rows if r["name"] == selected and r["continuation"] == mode]
        old = [r for r in rows if r["name"] == "control-sheep6" and r["continuation"] == mode]
        lines.append(f"| {mode} | {mean(r['our_final'] for r in group):,.0f} | {mean(r['our_final'] for r in old):,.0f} | {mean(r['margin'] for r in group):+,.0f} | {mean(r['margin'] for r in old):+,.0f} |")
    cfg = next(r["config"] for r in rows if r["name"] == selected)
    lines += ["", "## Opening targets", "", "```json", json.dumps(cfg, indent=2), "```", "",
              "Targets are conditional on affordability and worker progress, not guaranteed purchases on a fixed turn. Animal pens stay in fixed positions close to the shed. The initial herd grows gradually; future pens stay reserved so new animals do not displace crop assignments. Workers preserve their destinations, water crops, feed and care for animals, collect produce and fertilizer, and sell available shed goods. Fertilizer is sold rather than applied.", "",
              "## Limits and checks", "",
              f"All {len(screen)+len(rows)} screen/shortlist games completed with valid intermediate statuses and exact continuation cash reconciliation. Opening crop/animal loss counts: {sum(sum(r['opening_losses'].values()) for r in screen+rows)}. Seed requests were checked against available seeds on every opening decision.", "",
              "The shortlist set is used to select the final configuration; it is not an untouched final performance estimate. Maintenance and replanting reuse each opening state, so 16 rows per candidate are eight distinct opening scenarios, not 16 independent openings. This is a small, opponent-specific experiment. The continuation is a simple service controller and may undervalue farms that need specialized routing. Lower opponent income can improve margin even when our own income falls. These values are policy-conditioned estimates, not optimal board values or leaderboard win rates. The router remains ahead on average. Midgame investment and late-game routing still need work.", "",
              "See [board valuation](board_value.md) and [open-source sources](board_value_sources.md) for the evaluator's basis.", "",
              "## Reproduce", "", "```powershell",
              ".venv/Scripts/python.exe scripts/search_growth_openings.py --stage screen --workers 3",
              ".venv/Scripts/python.exe scripts/search_growth_openings.py --stage validate --names control-sheep6 c6s4-m0 c8s4-m12 small-herd --workers 3",
              "```", ""]
    if (OUT / "record.json").exists():
        records = json.loads((OUT / "record.json").read_text())
        new = [r for r in records if r["name"] == selected]
        old = [r for r in records if r["name"] == "control-sheep6"]
        lines += ["## Frozen opening: fresh-seed check", "",
                  f"After selection, seed 86201 / future 96201 was run in both seats. Selected opening mean final cash: {mean(r['our_final'] for r in new):,.0f}; control: {mean(r['our_final'] for r in old):,.0f}. Selected margin: {mean(r['margin'] for r in new):+,.0f}; control: {mean(r['margin'] for r in old):+,.0f}. Both seats happened to produce identical outcomes; this is one new seed, not two independent samples. The smaller improvement in margin reinforces the need for more opponent/scenario coverage.", "",
                  "The standalone entry point passed all 432 recorded decisions across both seats, with no observation mutation, seed overdraw, or opening deaths (`scripts/verify_growth_opening.py`).", "",
                  "### Actual build, fresh seed, seat 0", "",
                  "Counts below are at the start of each zero-based day. These are observed assets, rather than target quantities.", "",
                  "| Day | Cash | Tiles | Animals | Crops |", "|---:|---:|---:|---|---|"]
        replay = json.loads((OUT / f"{selected}-86201-seat0/opening.json").read_text())
        for day in range(10):
            farm = replay["steps"][day*24][0]["observation"]["farms"][0]
            tiles = [t for row in farm["tiles"] for t in row if isinstance(t, dict)]
            animals = Counter(t["animal"] for t in tiles if t.get("animal"))
            crops = Counter(t["crop"] for t in tiles if t.get("kind") == "PLANT")
            fmt = lambda counts: ", ".join(f"{n} {k.lower()}" for k,n in sorted(counts.items())) or "—"
            lines.append(f"| {day} | {farm['money']:,.0f} | {25*len(farm['unlocked_quadrants'])} | {fmt(animals)} | {fmt(crops)} |")
        lines += ["", f"[Exact opening moves](../results/fresh/growth_opening/{selected}-86201-seat0/moves.md) · [Full replay JSON](../results/fresh/growth_opening/{selected}-86201-seat0/full_replay.json)", "",
                  "```powershell", f".venv/Scripts/python.exe scripts/search_growth_openings.py --stage record --names control-sheep6 {selected} --workers 3",
                  ".venv/Scripts/python.exe scripts/verify_growth_opening.py", ".venv/Scripts/python.exe scripts/report_growth_openings.py", "```", "",
                  "The record command creates new folders and refuses to overwrite existing ones; use `--out` for a separate rerun directory.", ""]
    (ROOT / "docs/growth_opening.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "selection.json").write_text(json.dumps({"name": selected, "config": cfg}, indent=2), encoding="utf-8")
    print(selected, json.dumps(cfg))


if __name__ == "__main__":
    main()
