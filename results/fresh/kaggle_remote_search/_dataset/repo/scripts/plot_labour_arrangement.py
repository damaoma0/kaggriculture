"""Plot an exported concrete daily arrangement (real executed commands)."""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import research_labour_profit as R

path = Path(sys.argv[1])
data = json.loads(path.read_text())
colors = {"Tile work": "#286b8e", "Travel": "#bbc8cf", "Pickup / deposit": "#e2a44d", "Idle": "#f1f3f4"}
fig, axes = plt.subplots(1, 2, figsize=(13, 6.4), sharex=True, sharey=True)
maximum = max(w["id"] for h in data["baseline_worker_timeline"] for w in h["workers"])
for ax, key, title in zip(axes, ("baseline_worker_timeline", "worker_timeline"), ("Recorded arrangement", "Optimized arrangement")):
    for h in data[key]:
        for worker in h["workers"]:
            op = worker["command"][0]
            category = "Travel" if op in R.MOVES else "Pickup / deposit" if op in ("PICKUP", "DROP") else "Idle" if op == "PASS" else "Tile work"
            ax.broken_barh([(h["hour"], 1)], (worker["id"] - .36, .72), facecolors=colors[category], edgecolors="white", linewidth=.3)
    ax.set_title(title)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hour (0–23)")
    ax.set_yticks(range(maximum + 1), ["Farmer"] + [f"Hand {i}" for i in range(1, maximum + 1)])
    ax.spines[["top", "right"]].set_visible(False)
axes[0].invert_yaxis()
fig.suptitle(f"Same production and sales; {data['selection']['wage']:,.0f} less in wages", fontsize=16)
fig.legend(handles=[Patch(facecolor=c, label=k) for k, c in colors.items()], loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(.5, .04))
fig.text(.02, .01, f"Episode {data['episode']}; zero-based day {data['day_zero_based']}. Worker IDs are renumbered after removing a hire. Blank cells: worker absent.", fontsize=9)
fig.tight_layout(rect=(0, .12, 1, .93))
target = R.OUT / "labour_arrangement_example.png"
fig.savefig(target, dpi=180, bbox_inches="tight")
print(target)
