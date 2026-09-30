"""Summarize the frozen direct supplied-plan self-play experiment."""
import json
import statistics
import test_labour_selfplay as S

R = S.R


def signed(value):
    return f"{value:+,.2f}"


def main():
    folder = R.OUT / "selfplay_causal_v1"
    rows = [json.loads(p.read_text()) for p in sorted(folder.glob("[0-9]*.json"))]
    recomputed = S.summary(rows)
    result = json.loads((folder / "summary.json").read_text())
    # The archived bootstrap used process-completion world order. Reordering
    # worlds changes finite Monte Carlo draws, but must not change any result
    # statistic. Keep the interval actually recorded by the frozen run.
    for panel, selectors in result.items():
        for mode, stats in selectors.items():
            for key, value in stats.items():
                if key != "paired_world_margin_bootstrap_95":
                    assert recomputed[panel][mode][key] == value, (panel, mode, key)
    assert len(rows) == 20
    checks = json.loads((folder / "verification.json").read_text())
    assert checks["passed"]
    forecast, wage = result["all"]["forecast"], result["all"]["wage"]
    labels = dict(wage="Preserve sale times; minimize wages", forecast="Labor plus forecast sale timing")
    lines = [
        "# Direct labor-scheduling self-play",
        "",
        "Follow-up to [the labor-profit research](labour_profit_research.md), 2026-09-21.",
        "",
        f"The forecast-guided scheduler scores **{forecast['wins']} wins, {forecast['ties']} ties and {forecast['losses']} losses** "
        f"against the identical supplied plan without rescheduling, with **{signed(forecast['mean_margin'])} mean head-to-head cash margin**. "
        f"The labor-only scheduler scores **{wage['wins']} wins, {wage['ties']} ties and {wage['losses']} loss**, "
        f"with **{signed(wage['mean_margin'])} mean margin**.",
        "",
        "These are actual simultaneous matches with shared market impact, not separate replays against the original recorded opponent. "
        "Scheduling decisions use only the current observation and the player's supplied production/action plan. "
        "No candidate is accepted or rejected using the real future opponent actions or realized future state.",
        "",
        "## Results",
        "",
        "| Panel | Scheduler | W–T–L | Mean match margin | Paired-world 95% bootstrap |",
        "|---|---|---:|---:|---:|",
    ]
    for panel in ("ladder", "leaders", "all"):
        for mode in ("wage", "forecast"):
            s = result[panel][mode]
            lo, hi = s["paired_world_margin_bootstrap_95"]
            lines.append(f"| {panel} ({s['worlds']} worlds, {s['games']} games) | {labels[mode]} | "
                         f"{s['wins']}–{s['ties']}–{s['losses']} | {signed(s['mean_margin'])} | {signed(lo)} to {signed(hi)} |")
    lines += ["", "The two seats of each world form one bootstrap cluster; they are not treated as independent worlds. "
              "These 20 plans/worlds were already used in the preceding research. The intervals describe this panel, not an unseen-world generalization test.",
              "", "The single labor-only loss is episode 111240681 in seat 1: that seat loses by 459 in the unscheduled mirror control, "
              "and scheduling saves 327, narrowing the loss to 132. Its seat-swapped partner wins by 786. "
              "Thus the labor-only policy improves 15 paired worlds and ties five; it worsens none of the paired worlds.",
              "", "## Where the gain comes from", "",
              "Each world also runs the same unscheduled plan against itself. Comparing each treated player's cash with that control separates own profit from damage to the rival's sale prices.",
              "", "| Scheduler | Own cash gain | Wages saved | Extra revenue | Other input saving | Rival cash change |", "|---|---:|---:|---:|---:|---:|"]
    for mode in ("wage", "forecast"):
        s = result["all"][mode]
        lines.append(f"| {labels[mode]} | {signed(s['mean_own_gain'])} | {signed(s['mean_wage_saving'])} | "
                     f"{signed(s['mean_revenue_gain'])} | {signed(s['mean_other_saving'])} | {signed(s['mean_rival_gain'])} |")
    lines += ["", "Means are per match. Head-to-head margin is the difference between the two players' final cash; own profit improvement is measured against that seat in the unscheduled control.",
              "", "The sale-timing forecast is not uniformly better than labor-only scheduling. In episode 110003096 it gains 182 own cash "
              "versus 202 for labor-only, and its match margin falls from 202 to 173. The ability to hold goods preserves an option; "
              "a forecast can still choose the wrong sale time. The average benefit beyond wage-only is 5.95 own cash and 15.30 match margin on this panel.",
              "", "## Production and correctness", ""]
    for mode in ("wage", "forecast"):
        s = result["all"][mode]
        lines.append(f"- {labels[mode]}: {s['own_production_changed']}/{s['games']} games changed our harvested/collected quantities; "
                     f"{s['rival_production_changed']}/{s['games']} changed the rival's quantities. "
                     f"Our final farm/inventory changed in {s['own_terminal_changed']}/{s['games']}; "
                     f"the rival's changed in {s['rival_terminal_changed']}/{s['games']}.")
    framework_checks = [c for c in checks["checks"] if c["check"] == "independent_official_framework_replay"]
    lines += [
        "",
        f"All 80 treated full seasons and 20 mirror controls reach DONE and reconcile final cash with the successful transaction ledger. "
        f"An independent replay through Kaggle's normal framework checks every transition of {len(framework_checks)} selected treated games "
        "(both selectors and seats, one world from each panel). Public farms, private inventories, market, town, time and final scores match. "
        "Every source file and archived executable schedule is hash-checked.",
        "",
        "The information-isolation check uses a decision that actually changes the schedule. Altering the rival's private inventory and supplying bogus hidden-seed, future-shop and future-rival-action fields leaves that decision unchanged. Episode-file loading is disabled during the check.",
        "",
        "## Exact protocol",
        "",
        "1. Use the same 12 ladder-derived and 8 Mother-Goose-derived explicit plans as the prior study. Both contestants receive the source player's own plan, including its capped input and sale quantities. The original opposing action tape is never played in these matches.",
        "2. Start both farms through the official engine with 3,000 cash, the recorded world seed, normal weeds and the recorded shop-opening history. Only the evaluator knows the future shop history. Run an unscheduled-versus-unscheduled mirror control.",
        "3. For each selector, run a full game with the scheduler in seat 0 and another with it in seat 1. The other side executes the identical original plan. Future scheduled actions of the other side are not supplied to the planner, even though the experiment uses matching plans.",
        "4. At each selected day boundary, provide the scheduler its current observation and the next 48 hours of its own plan. Optimize the first day's labor with the next day as a continuation check. Ladder plans use zero-based days 3,5,…,27; Mother-Goose plans use 4,6,…,26.",
        "5. Project the physical engine with the rival taking PASS, unknown rival inventories empty, existing shops held constant, and no speculative new weeds. Require all planned input purchases, land purchases and hires to succeed in the baseline projection; otherwise retain the original schedule. This check uses predicted feasibility, not the actual future.",
        "6. Generate the same bounded relocation, insertion, worker-removal and delivery candidates as the research prototype. Retain candidates preserving projected production, inventories and trade quantities. The wage selector preserves projected sale times; the forecast selector compares public-market scenarios using current shops and visible rival production. Do not use the realized-profit oracle.",
        "7. Materialize all chosen physical and market actions and execute them in the real shared market. Record every resulting season, including losses and any production mismatch. There is no hindsight rollback or exclusion of bad outcomes.",
        "",
        "The opponent here is a fixed-plan executor. This validates labor scheduling conditional on a supplied plan; it does not test an integrated, adaptive mgt_m1 production planner or a reacting rival policy.",
        "",
        "## Search and runtime limits",
        "",
    ]
    for mode in ("wage", "forecast"):
        s = result["all"][mode]
        lines.append(f"- {labels[mode]} changes {s['nonbaseline_decisions']} of {s['decisions']} decision windows; "
                     f"{s['input_shortfall_fallbacks']} windows fall back because of projected input shortfalls. "
                     f"Maximum observed planning time is {s['max_planning_seconds']:.2f} seconds under this four-process local run.")
    lines += [
        "",
        "This Python research executor is not a competition-ready agent: the environment's default per-action limit is 1 second, and these matches precompute each selected window outside that limit. The algorithm still needs runtime work and integration before a live submission. It optimizes alternate days and a bounded candidate pool; neither minimum staffing nor global profit optimality is established.",
        "",
        "A discarded engineering pilot (`selfplay_causal_pilot`) initialized projected observations incorrectly because Kaggle's Struct requires attribute assignment to synchronize attribute and dictionary values. It is not performance evidence. The fix and a projected-initial-state assertion precede the frozen run. The corrected pilot (`selfplay_causal_pilot_v2`) checks one of the 20 panel worlds. No algorithm changes were made during or after the final panel run.",
        "",
        "## Per-world paired margins",
        "",
        "Margins below average the two seat assignments. The last column counts any own production-quantity or terminal-farm/inventory mismatch over all four treated games in that world.",
        "",
        "| Source episode | Panel | Labor-only margin | Forecast margin | Games with own mismatch |",
        "|---|---|---:|---:|---:|",
    ]
    for row in rows:
        means = {m: statistics.mean(g["margin"] for g in row["games"] if g["mode"] == m) for m in ("wage", "forecast")}
        mismatch = sum(not g["same_production"][g["seat"]] or not g["same_terminal_farm_inventory"][g["seat"]] for g in row["games"])
        lines.append(f"| {row['episode']} | {row['panel']} | {signed(means['wage'])} | {signed(means['forecast'])} | {mismatch} |")
    lines += [
        "",
        "## Reproduction and artifacts",
        "",
        "```powershell",
        ".venv/Scripts/python.exe scripts/test_labour_selfplay.py --count 20 --workers 4 --tag selfplay_causal_v1",
        ".venv/Scripts/python.exe scripts/check_labour_selfplay.py --tag selfplay_causal_v1",
        ".venv/Scripts/python.exe scripts/report_labour_selfplay.py",
        "```",
        "",
        "Frozen inputs, code/engine hashes, all decisions and the exact compressed action pairs are in "
        "[selfplay_causal_v1](../results/fresh/labour_profit/selfplay_causal_v1/). "
        "See [summary.json](../results/fresh/labour_profit/selfplay_causal_v1/summary.json) and "
        "[verification.json](../results/fresh/labour_profit/selfplay_causal_v1/verification.json). "
        "The live agent and submissions are unchanged.",
        "",
    ]
    target = R.ROOT / "docs/labour_selfplay.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
