"""Summarize the completed board-value scenario panel and draw cash paths."""
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/board_value"
NAMES = {"maintain": "Maintain existing assets", "replant": "Replant wheat", "expand": "Expand land + wheat", "native": "Keep original policies"}


def distribution(values):
    values = sorted(values)
    return {"mean": mean(values), "minimum": values[0], "maximum": values[-1], "n": len(values)}


def main():
    rows = json.loads((OUT / "panel.json").read_text())
    assert len(rows) == 180, f"Panel incomplete: {len(rows)}"
    grouped = defaultdict(list)
    for row in rows:
        grouped[(tuple(row["modes"]), row["crew_cap"])].append(row)
    assert all(len(group) == 9 for group in grouped.values())
    native = grouped[(("native", "native"), 10)]
    representative = "sheep6-seed20261201-seat0"
    result = {"definition": "Scenario-weighted terminal cash under a specified continuation and opponent policy; not optimal board value",
              "equal_policy_comparisons": [], "against_native_router": [], "representative_root": []}
    lines = ["# Board value: the day-9 opening comparison", "",
             "## What value means", "",
             "V(policy, opponent, state) = mean final cash across the registered synthetic futures. Final cash is starting cash plus successfully executed sale proceeds minus all subsequent purchases and hires. Land, animals, plants, and seeds receive no separate terminal purchase-cost credit.", "",
             "This is an offline full-state audit: both private inventories are known at the checkpoint. The policies themselves only receive their normal observations. Future seeds are replaced after day 9 and never exposed to policies. A live evaluator would need a belief model for the opponent's hidden inventory.", "",
             "## Result", "",
             "The router's low-cash day-9 board produces substantially more terminal cash under common continuation rules as well as under its own policy. Early bank balance therefore gave the wrong impression of the relative positions. The numerical value depends materially on how well the continuation services and reinvests in the farm.", "",
             f"![Projected cash paths]({(OUT / 'cash_paths.png').as_posix()})", "",
             "## Common continuation comparison", "",
             "Three recorded day-9 positions x three synthetic future seeds = nine scenarios per row. The common controller uses the same workload-based staffing rule on each farm, capped at ten hired hands. These are conditional scenario means, not calibrated leaderboard forecasts.", "",
             "| Continuation on both boards | Our final cash, mean | Router final cash, mean | Our scenario range | Router scenario range |", "|---|---:|---:|---:|---:|"]
    for mode in ("maintain", "replant", "expand", "native"):
        group = grouped[((mode, mode), 10)]
        d = [distribution([r["final_cash"][i] for r in group]) for i in range(2)]
        result["equal_policy_comparisons"].append({"mode": mode, "our_value": d[0], "router_value": d[1]})
        lines.append(f"| {NAMES[mode]} | {d[0]['mean']:,.0f} | {d[1]['mean']:,.0f} | {d[0]['minimum']:,.0f}-{d[0]['maximum']:,.0f} | {d[1]['minimum']:,.0f}-{d[1]['maximum']:,.0f} |")
    lines += ["", "Native means each board retains its own original controller. It is a useful achievable-policy control, not an identical-controller comparison. The generic controllers do not apply new fertilizer or buy new animals; replanting uses wheat, and expansion buys at most three total quadrants. Native policies retain their original decisions.", "",
              "## A single current board pair", "",
              f"Root: {representative}, step 216. The following averages vary only the three synthetic futures, not the root board.", "",
              "| Mode on both boards | Our value | Router value |", "|---|---:|---:|"]
    for mode in ("maintain", "replant", "native"):
        group = [r for r in grouped[((mode, mode), 10)] if r["root"] == representative]
        values = [mean(r["final_cash"][i] for r in group) for i in range(2)]
        result["representative_root"].append({"mode": mode, "final_cash_mean": values})
        lines.append(f"| {NAMES[mode]} | {values[0]:,.0f} | {values[1]:,.0f} |")
    root = native[0]["root_features"]
    lines += ["", "## Where the money comes from: original-policy continuation", "",
              "These components are observed successful transactions in the engine, not requested order quantities times a quoted price. Each rollout's ledger reconciles exactly to terminal cash. Displayed means are rounded.", "",
              "| Component | Ours | Router |", "|---|---:|---:|"]
    components = [("Starting cash at day 9", lambda r, i: r["root_features"][i]["cash"]),
                  ("Future sale revenue", lambda r, i: sum(r["ledger"][i]["revenue"].values())),
                  ("Future purchases and hiring", lambda r, i: -sum(r["ledger"][i]["spend"].values())),
                  ("Final cash", lambda r, i: r["final_cash"][i])]
    for label, fn in components:
        vals = [mean(fn(r, i) for r in native) for i in range(2)]
        lines.append(f"| {label} | {vals[0]:,.0f} | {vals[1]:,.0f} |")
    lines += ["", "Future sales include output from newly purchased/replanted assets when the continuation allows them. They are not an intrinsic valuation of the starting assets alone. The maintenance row is the stricter existing-production comparison.", "",
              "## Our choices against the unchanged router", "",
              "The opponent uses its original router policy in every row. Select a policy by its mean across scenarios, not by choosing the best action separately after seeing each future.", "",
              "| Our continuation | Mean final cash | Minimum | Mean cash margin versus router |", "|---|---:|---:|---:|"]
    for mode in ("maintain", "replant", "expand", "native"):
        group = grouped[((mode, "native"), 10)]
        d = distribution([r["final_cash"][0] for r in group])
        margin = mean(r["margin"] for r in group)
        result["against_native_router"].append({"mode": mode, **d, "mean_margin": margin})
        lines.append(f"| {NAMES[mode]} | {d['mean']:,.0f} | {d['minimum']:,.0f} | {margin:+,.0f} |")
    lines += ["", "## Labour and execution sensitivity", "",
              "Premature losses count plants becoming weeds before their normal last-production/expiry age. They do not count natural expiry; harvests missed after expiry can still waste value and are not fully captured by this counter.", "",
              "| Common policy | Crew cap | Our mean cash | Router mean cash | Premature crop losses, ours/router, total across 9 runs |", "|---|---:|---:|---:|---:|"]
    for mode in ("maintain", "replant"):
        for cap in (6, 10, 12):
            group = grouped[((mode, mode), cap)]
            vals = [mean(r["final_cash"][i] for r in group) for i in range(2)]
            losses = [sum(r["diagnostics"][i].get("premature_crop_losses", 0) for r in group) for i in range(2)]
            lines.append(f"| {NAMES[mode]} | {cap} | {vals[0]:,.0f} | {vals[1]:,.0f} | {losses[0]} / {losses[1]} |")
    lines += ["", "The common scheduler sometimes fails to service the router's larger farm. Those results are policy-limited outcomes, not proof that the lost plants have no value. The native control checks the size and direction of this bias. None of these controllers establishes an optimal value or an upper bound.", "",
              "## Validation and scope", "",
              "- 180 full-season continuations: 144 policy-pair scenarios plus 36 labour-sensitivity scenarios. All reach state 719 and every cash ledger reconciles.",
              "- A separate 419-transition restore test reproduces terminal farms, market, town, inventories, and rewards from a saved full replay.",
              "- Restoring a checkpoint does not change its board/private state; replacing the future seed leaves the root unchanged. The preserved prefix keeps absolute turn numbering intact.",
              "- Native agents are warmed using past observations only, with exact action agreement required over all 216 prior decisions.",
              "- Liquidating shed inventory through the nonlinear price curve was checked against actual engine sales. Carried goods and seeds are not treated as immediately sellable cash.",
              "- Three root positions and three synthetic future seeds are a small sensitivity panel. The ranges are scenario ranges, not confidence intervals; the opponent-policy weights are not learned from the live population.",
              "- The current continuation scheduler covers the crops present in these roots; it explicitly rejects tomato roots. No new fertilizer optimization, opponent inventory inference, or policy learning is included.",
              "- No original opening code, submitted bot, or leaderboard entry was changed by this experiment.", "",
              "## How to use this evaluator next", "",
              "For an opening candidate, capture a day-9 state against the same reference opponent. Run the same frozen continuation/scenario panel and compare final cash margins, execution losses, and downside scenarios. Improve the continuation library where native controls reveal systematic undervaluation. Only then use the scalar to select openings or train a faster heuristic.", "",
              "[Public-source notes](board_value_sources.md) · [Raw panel](../results/fresh/board_value/panel.json) · [Machine-readable values](../results/fresh/board_value/values.json)", "",
              "## Reproduce", "", "```powershell",
              ".venv/Scripts/python.exe scripts/evaluate_boards.py --stage smoke --workers 3",
              ".venv/Scripts/python.exe scripts/verify_board_value.py",
              ".venv/Scripts/python.exe scripts/evaluate_boards.py --stage panel --workers 3",
              ".venv/Scripts/python.exe scripts/report_board_value.py", "```"]
    (OUT / "values.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / "docs/board_value.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    days = [9, 12, 15, 20, 25, 29]
    for ax, mode in zip(axes, ("replant", "native")):
        group = grouped[((mode, mode), 10)]
        for i, (name, colour) in enumerate((("Our opening", "#1b8b6f"), ("Router opening", "#c75b33"))):
            vals = [mean(r["cash_path"][str(d)][i] for r in group)/1000 for d in days]
            vals.append(mean(r["final_cash"][i] for r in group)/1000)
            ax.plot(days + [719/24], vals, marker="o", color=colour, label=name, linewidth=2.3, markersize=4)
        ax.set_title("Common replanting controller" if mode == "replant" else "Each original controller", fontsize=12)
        ax.set_xlabel("In-game day (zero-based)")
        ax.set_xticks([9, 12, 15, 20, 25, 30])
        ax.grid(axis="y", alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
    axes[0].set_ylabel("Cash (thousands of coins)")
    fig.suptitle("Cash at day 9 hides the router's productive capacity", fontsize=15, y=.98)
    fig.text(.5, .01, "Means across 3 root positions × 3 synthetic futures; conditional on the stated continuation rules.", ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0,.04,1,.93))
    fig.savefig(OUT / "cash_paths.png", dpi=170)
    plt.close(fig)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
