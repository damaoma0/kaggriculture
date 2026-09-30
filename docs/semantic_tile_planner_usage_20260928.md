# Semantic tile planner usage

The builder turns daily tile-change counts into a spatial plan for the frozen
`agents/mgt_lead_kb115lt.py` executor. Defaults are **strict inputs, reuse
placement, and zero polishing rounds**. It plans zero-based days **11–29** from
the public D11 morning state; the benchmark replays the recorded opening on
days 0–10. Building a plan does not run a game or establish competition readiness.

From the repository root in PowerShell:

```powershell
.venv/Scripts/python.exe scripts/build_semantic_tile_stack_20260928.py `
  --inputs results/fresh/semantic_tile_20260928/semantic_inputs_strict_clean.json `
  --out results/fresh/semantic_tile_20260928/my_plans.json
```

This writes `my_plans.json` and `my_plans.spec.json`, with arm `ST28STACK`.
`--spec` and `--arm` override those names. The spec preserves the frozen KB115LT
recipe and changes only `sd_tp_file` among its configuration values. It expects
the existing repository executor, runner, maintenance code, and learned pace
tables. The CLI verifies executor SHA256
`2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.

For one world, the Python API returns an independent dictionary:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from build_semantic_tile_stack_20260928 import make_plan

worlds = json.loads(Path("results/fresh/semantic_tile_20260928/semantic_inputs_strict_clean.json").read_text())
plan = make_plan(worlds["112570602"])  # strict, reuse, polish_rounds=0
```

`variant="cohort"` or `"distance"`, and `polish_rounds=2`, are explicit options.
`mode="expanded"` / `--mode expanded` enables the older diagnostic input with
copied ongoing-crop first-harvest counts. Strict mode discards those counts even
when given a legacy input. It derives its own first-harvest markers from crop
clocks and anonymous feasible lifetimes. Neither mode reads opponent outcomes
or source worker actions during compilation.

## Input

The CLI accepts one semantic object, `{episode: semantic}`, or
`{"worlds": {episode: semantic}}`. Each semantic object has `n: 30`,
`handoff_day: 11`, `initial_state`, `opening_plan`, and thirty ordered `days`
entries. The extracted strict objects also identify
`semantic_scope: "tile_changes_only"`. The final clean input omits terminal
maintenance counts as well as recorded ongoing first-harvest timing.

Coordinates appear only in the observed opening and D11 state. For example,
`initial_state.tiles["44"]` can be
`{"kind":"PASTURE","animal":"COW","placed_day":0}`. Opening arrays stop
before D11, except `board`, which includes the D11 morning. Tile index is
`10*y+x`. The builder rejects future-dated opening events or land purchases.

A real D11 daily entry, shown with compact conservation totals:

```json
{
  "day": 11,
  "plant_counts": {"STRAWBERRY": 2, "TOMATO": 3, "WHEAT": 10},
  "build_counts": {"COOP": 1}, "remove_structure_counts": {},
  "animal_add_counts": {"GOOSE": 1},
  "animal_exit_counts": {}, "animal_retire_counts": {},
  "crop_end_counts": {"MELON": 4, "WHEAT": 5},
  "crop_remove_counts": {}, "crop_disappear_counts": {},
  "hands": 11, "land_add_count": 0,
  "end_occupancy_counts": {
    "crops": {"STRAWBERRY": 21, "TOMATO": 8, "WHEAT": 33},
    "structures": {"COOP": 1, "PASTURE": 22},
    "animals": {"COW": 13, "GOOSE": 1, "SHEEP": 9},
    "empty_structures": {}, "locked": 0, "empty_or_weed": 15
  }
}
```

`hands` is that day's hired hands, excluding the farmer. All count mappings are
required, including empty ones. `crop_disappear_counts` and
`end_occupancy_counts` can be `null` for the censored final archive boundary.
No future tile IDs, cohort identities, action sequences, or first-harvest-count
field belong in strict daily input.

## Output

The plan carries the eleven `TilePlanView` fields:

| Fields | Meaning |
|---|---|
| `n`, `hands[d]` | Season length and daily hires |
| `plant[d]`, `events` | Chosen tile/crop plantings and their dated list |
| `struct_by_day[d]`, `animals_by_day[d]` | End-of-day structures and physically present animals |
| `board[d]` | **Start-of-day** 100-label board |
| `harv_tiles[d]`, `removals[d]` | Cohort-ending/first-harvest markers and crop removals |
| `land_day`, `cum_sold` | Land dates and opening-only cumulative sales |

Use `planner_metadata.daily` for the explicit **end-of-day** plan. Each entry
has `day`, `hands`, `end_board`, all 100 `tiles`, `retirements_started`, and
`animal_exits`. For example, the generated D24 plan for episode 112570602 marks:

```json
{
  "retirements_started": [
    {"tile": 38, "animal": "COW", "first_unfed_day": 24, "expected_exit_day": 25}
  ],
  "tiles": {
    "38": {"kind": "PASTURE", "animal": "COW", "placed_day": 8, "retiring_since": 24}
  }
}
```

This excerpt shows retirement while the cow still occupies its pen. The animal
remains in `animals_by_day[24]` and is absent after its planned D25 exit; the
pasture can remain. The generated metadata reports the retirement explicitly
rather than representing that occupied tile as already empty.

The default builder reconstructed all forty strict reference plans byte for
byte; `results/fresh/semantic_tile_20260928/build_verification/rebuild_audit.json`
records that packaging check. Gameplay acceptance is measured separately.
