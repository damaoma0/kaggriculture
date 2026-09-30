# Semantic tile planner input boundary (2026-09-28)

The requested planner input is DSM's actual **daily counts of tile changes** in
the 40 benchmark worlds: additions by crop/animal/structure type, crop removals
and one-time harvest endings, animal retirement/escape counts, land additions,
and daily hands. The already-played opening supplies the public D11 farm and
cohort ages. Future DSM tile coordinates, worker routes, upkeep, transactions,
and realized outcomes are not planner inputs.

An audit of the first implementation identified an extra field:
`first_harvest_counts` for ongoing crops. The first harvest of a strawberry or
tomato does not change the tile's crop identity. Although these counts contain
no coordinates, they disclose DSM's actual production/collection timing beyond
the requested tile-change contract. The first anonymous-lifetime solver used
them as equality constraints, so omitting them from the final description would
overstate the scope of that experiment.

Consequently, the initial `ST28COHORTLIFE`, `ST28REUSELIFE`, and
`ST28REUSEPOLISH` experiments are **timing-extended ablations**, not the strict
shipping candidate. Their completed results and frozen sources are retained.
The 8-world development results are useful diagnostic evidence, but do not by
themselves satisfy the requested input boundary or the 40-world gate.

The strict candidate removes future recorded ongoing-first-harvest counts from
both the input schema and lifetime constraints. Its `harv_tiles` interface
markers for ongoing crops are instead generated from its own assigned cohort
births and the engine's first-yield rules. Harvested initial cohorts can be
identified from the already-played opening. One-time crop ending counts remain
valid semantic inputs because the crop actually leaves the tile.

The exact-tiling DSM control may retain its recorded interface: it is the
explicit comparator requested by the user. Candidate qualification must use a
separate frozen strict plan on the same worlds, executor, hands, market, and
runtime regime. A coordinate-free plan is not automatically a strict
tile-change-only plan; both properties must be checked.

No additional future DSM maintenance, production quantities, sale dates, or
price/outcome information should replace the removed field. The planner can use
engine-derived production clocks and its own planned states to construct the
interface and to evaluate layout heuristics.

## Independent strict compiler audit

`scripts/audit_semantic_tile_contract_20260928.py` recompiled all 40 inputs through
the default `compile_plan` API, with guarded fields that raise on any access to
non-contract future data. Injected ongoing first-harvest counts, source tile
coordinates, maintenance, market information, episode identity and outcomes were
all left unread. Every one of the eleven `TilePlanView` fields matched the frozen
`plans/reuse_strict.json` exactly in all 40 worlds. All opening arrays, events and
land purchases were also checked to remain within the already-played prefix.

The machine-readable record is
`results/fresh/semantic_tile_20260928/strict_contract_independent_audit.json`,
including source and artifact hashes. This is a compilation/input-isolation
check, not a gameplay qualification result.

## Final API and input cleanup

The public lifecycle APIs and CLI now default to strict mode; diagnostic timing
requires explicit opt-in. `semantic_inputs_strict_clean.json` also removes the
unused terminal unfed-count fields retained by the earlier serializer. Its
entire compiled plans, including retirement metadata, are byte-for-byte
identical to the frozen strict plans tested in gameplay. The original inputs
and plans remain preserved. See `strict_scope_cleanup_audit.json`,
`final_contract_audit.json`, and `build_verification/final_clean_plans.json` in
the mission results directory.
