# Production modules: first execution experiment

## Result

**24/24 official-engine execution probes reproduced their expected crop outputs.** The mixed UMG/Majkel bundle worked through independently generated routes on new tiles. This establishes a small execution building block, not a superior full-farm strategy. No competition agent was changed or uploaded.

## Extracted plans and cheaper-model analysis

GPT-5.6 Terra extracted 40 completed single-yield crop cycles, 20 per leader, from fixed submissions UMG 56266758 and Majkel 56216119. Each cycle was planted on elapsed day 12–21 and finished within six days. The artifact records planting-visible shops, tile and worker provenance, effective planting/watering/fertilizing/harvesting actions, relative day offsets, and verified harvested units. Future shops are not module-selection features. Snapshot extraction excludes unverified midnight harvests; this is a conservative sample, not exhaustive coverage.

GPT-5.6 Luna reviewed the existing segment evidence for potential demand-conditioned modules. The strongest subsequent production-policy candidate is a tomato cohort planted on days 12–14, but its longer care and delivery commitments make it a later executor milestone. Its proposed demand gate is a hypothesis, not a recovered leader rule.

## What was tested

Four representative carrot cycles (two tiles from each of two episodes) were used:

- UMG episode 109712554, original planting day 14: plant and water at age 0; fertilize then water at age 2; water and harvest at age 3. Output: four carrots per tile.
- Majkel episode 109155294, original planting day 12: plant and water at age 0; water then harvest at age 2. Output: two carrots per tile.

Three four-plot bundles: four UMG cycles, four Majkel cycles, or two from each. Each bundle starts at elapsed day 12 on tiles (2,3), (3,2), (1,3), (3,1), which differ from the original cohorts' layout. Repeated copies test composition, not independent source examples.

The compiler preserves crop age and within-day operation order, discards original movement and worker identities, enumerates the daily tile-visit permutations, and selects a shortest route. It buys required seeds/fertilizer, picks up fertilizer, clears actual weeds at planting, completes the jobs, and returns produce to the shed. It rejects a route longer than the available 22 action slots. This small search enumerates at most 24 permutations; it is not the general multi-worker scheduler.

## Validation

Four natural seeds 171000–171003, both seats, all three bundles: 24 distinct full-season engine configurations. An active public V50 agent operates the other farm. Kaggle's actual last-callable loader loads both agents. Existing instrumentation checks 720 states, final DONE statuses and exact cash-ledger reconciliation. Every expected harvest total matched, with no route rejection or missing fertilizer input. After independent review, the same 24 configurations were rerun with per-tile execution instrumentation: all 96 plot instances had exactly one successful planting and the expected individual harvest. These are 48 executions of 24 distinct configurations, not 48 independent tests. Longest daily route: 22 commands. Movement, care, input use, and transport execute through the official engine.

| Bundle | Games | Exact harvest matches | Carrots from four plots | Mean cash gain above starting cash |
|---|---:|---:|---:|---:|
| UMG | 8 | 8 | 16 | +228.50 |
| Majkel | 8 | 8 | 8 | +230.00 |
| Mixed | 8 | 8 | 12 | +229.25 |

Mean scheduled route commands across the cycle: 64 UMG, 42 Majkel, 56 mixed. These include travel, weed clearing when needed, pickup and delivery, not just crop work. All bundles use 80 in seeds; UMG uses four fertilizer units, mixed two, Majkel none. Purchased fertilizer costs depend on the evolving market. These results explain why maximizing crop output alone is insufficient.

## Limits and decision

The probe reserves four plots and the main farmer and otherwise leaves that farm idle. It does not displace the main farmer's existing jobs, hire additional workers, value earlier release of land, preserve a full UMG board, or learn which module to choose. Its final score and win/loss against V50 are therefore not useful competition metrics. The reported cash gains omit the opportunity cost of this reserved capacity. Natural shop paths can diverge between bundles even with the same seed. Four worlds and four selected source cycles do not establish reliability across all modules or shop setups.

**Decision: the module representation and small route compiler pass this initial feasibility gate; there is no measured reason to promote the mixed bundle as a farming policy.** The next implementation gate is reservation of a real baseline tile and future worker time before replacing a crop. This must include displaced production and fertilizer opportunity cost. Only then is a UMG-only / second-leader-only / mixed policy comparison on fresh worlds meaningful.

## Artifacts

- `scripts/extract_production_modules.py` and `results/fresh/production_modules/extracted.json`
- `scripts/fragments/production_module_agent.py`: small route compiler
- `scripts/probe_production_modules.py`: builds and evaluates the three isolated probes
- `results/fresh/production_modules/probe/summary.json`: frozen selected modules, source hashes and per-game results
- `docs/production_module_candidates.md`: cheaper-model analysis and candidate conditions

Reproduce with `.venv/Scripts/python.exe scripts/probe_production_modules.py`. The runner rebuilds only isolated probe files under results and leaves competition submissions untouched.
