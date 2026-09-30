"""Summarize frozen labour experiments, keeping local and season evidence apart."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics as st
import research_labour_profit as R


def load(tag):
    folder = R.OUT / tag
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json")) if p.stem.isdigit()]


def details(rows):
    blocks = [(r, b) for r in rows for b in r["blocks"]]
    reject = sum((Counter(b["rejected"]) for _, b in blocks), Counter())
    methods = {}
    for family in ("distance", "tile_value", "remove_worker", "minus", "relocate", "harvest_first"):
        selected = []
        feasible = 0
        for r, b in blocks:
            candidates = [c for c in b["candidates"] if family in c["name"]]
            feasible += bool(candidates)
            chosen = max([b["candidates"][0], *candidates], key=lambda c: c["gain"])
            selected.append(chosen["gain"])
        methods[family] = dict(blocks_with_feasible_candidate=feasible,
                               oracle_gain_sum=sum(selected), positive_blocks=sum(x > 0 for x in selected))
    profitable = sorted([(c["gain"], r["episode"], b["day"], c["name"], c["wage"], c["revenue"])
                         for r, b in blocks for c in b["candidates"] if c["gain"] > 0], reverse=True)
    opportunity = sorted([(b["selected"]["oracle"]["gain"] - b["selected"]["wage"]["gain"],
                           r["episode"], b["day"], b["selected"]["oracle"])
                          for r, b in blocks], key=lambda x: x[0], reverse=True)
    costly_delays = sorted([(c["gain"], r["episode"], b["day"], c["name"], c["wage"], c["revenue"])
                           for r, b in blocks for c in b["candidates"] if c["wage"] > 0 and c["gain"] < c["wage"]])
    chosen_names = Counter(b["selected"]["oracle"]["name"] for _, b in blocks)
    opponents = Counter(str((r.get("opponent") or {}).get("team") or (r.get("opponent") or {}).get("name") or r.get("opponent")) for r in rows)
    return dict(rejections=dict(reject), methods=methods, best_candidates=profitable[:12],
                largest_timing_opportunities=opportunity[:8], wage_revenue_tradeoffs=costly_delays[:12],
                oracle_choices=dict(chosen_names), opponents=dict(opponents),
                mean_baseline_cash=st.mean(r["baseline"][r["seat"]] for r in rows),
                mean_original_wages=st.mean(r["baseline_economics"]["spend"].get("HIRE", 0) for r in rows),
                mean_elapsed_seconds=st.mean(r["seconds"] for r in rows),
                submissions=dict(Counter(str(r.get("submission")) for r in rows)))


def main():
    result = {}
    for tag, expected in (("ladder_holdout", 12), ("leaders_holdout", 8),
                          ("fixed_ladder_v2", 12), ("fixed_leaders_v2", 8)):
        rows = load(tag)
        assert len(rows) == expected, (tag, len(rows))
        summary = R.summarize(rows)
        result[tag] = dict(protocol=("Final fixed-plan experiment with corrected snapshot timestamps."
                                    if tag.startswith("fixed_") else
                                    "Historical raw-tape diagnostic. Forecast snapshot timestamps lagged one turn; do not use its forecast figures as final results."),
                           summary=summary, analysis=details(rows))
        # Independent whole-season deltas and exact revenue/cost decomposition.
        for mode in ("wage", "forecast", "oracle"):
            records = []
            for r in rows:
                c = r["chained"][mode]
                b = r["baseline_economics"]
                wage = b["spend"].get("HIRE", 0) - c["economics"]["spend"].get("HIRE", 0)
                revenue = sum(c["economics"]["revenue"].values()) - sum(b["revenue"].values())
                other = sum(b["spend"].values()) - sum(c["economics"]["spend"].values()) - wage
                assert c["gain"] == wage + revenue + other
                records.append(dict(episode=r["episode"], gain=c["gain"], wage=wage, revenue=revenue, other=other,
                                    final_contract=c["final_contract"]))
            result[tag][mode + "_seasons"] = records
    (R.OUT / "research_summary.json").write_text(json.dumps(result, indent=2))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, sharex=True)
    colors = ["#335c81", "#38a3a5", "#dc9f35"]
    fixed = {k: v for k, v in result.items() if k.startswith("fixed_")}
    for ax, (tag, data) in zip(axes, fixed.items()):
        labels = ["Preserve sale times", "Public-price heuristic*", "Recorded-market hindsight*"]
        for i, mode in enumerate(("wage", "forecast", "oracle")):
            vals = [r["gain"] for r in data[mode + "_seasons"]]
            avg = st.mean(vals)
            ax.barh(i, avg, color=colors[i], height=.54)
            ax.scatter(vals, [i] * len(vals), color="#333333", s=17, alpha=.55, zorder=3)
            ax.annotate(f"{avg:+,.1f}", (avg, i), xytext=(5 if avg >= 0 else -5, 0),
                        textcoords="offset points", ha="left" if avg >= 0 else "right", va="center", fontsize=9,
                        bbox=dict(facecolor="white", edgecolor="none", alpha=.85, pad=1.5))
        ax.set_yticks(range(3), labels)
        ax.axvline(0, color="#888888", lw=.8)
        ax.set_title("Our ladder plans (12 games)" if tag == "fixed_ladder_v2" else "Mother-Goose plans (8 games)")
        ax.set_xlabel("Actual change in final cash")
        ax.grid(axis="x", alpha=.16)
        ax.spines[["top", "right"]].set_visible(False)
        ax.margins(x=.28)
    axes[0].invert_yaxis()
    fig.suptitle("Labour arrangement with unchanged production", fontsize=16, y=.98)
    fig.text(.02, .02, "Bars: means; dots: games. Only alternate production days rescheduled.\n*Every method uses recorded jobs and a hindsight feasibility filter; these are offline experiments.", fontsize=9)
    fig.tight_layout(rect=(0, .11, 1, .93))
    fig.savefig(R.OUT / "profit_comparison.png", dpi=180, bbox_inches="tight")
    print(json.dumps({tag: v["summary"]["selectors"] for tag, v in result.items()}, indent=2))


if __name__ == "__main__":
    main()
