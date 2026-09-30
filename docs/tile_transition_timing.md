# Tile production changes and their timestamps

108 DSM games from submission 56444344 and 105 historical UMG games from submission 56266758. All use full hourly recorded states. The samples are different worlds, so differences are descriptive.

## Definitions and verification

A switch is a change between consecutive nonempty crop/animal identities. Empty tiles, weeds, locked tiles and empty buildings are skipped. Same-type replanting and initial establishment are recorded separately. The action timestamp is the observation from which PLANT/PLACE was issued; the new type first appears one frame later. Days and hours are zero-based.

All 17,462 switches match a PLANT or PLACE command for the new type by a worker standing on that tile. Full-season totals reproduce the earlier maps exactly (DSM 9,595; UMG 7,867). The extractor also passes synthetic checks for empty intervals, same-type replanting, direct replacements and a switch across the day-12 boundary.

For each switch the ledger retains coordinates, both timestamps, source cohort birth day and age, last productive frame, first nonproductive frame, intervening empty hours, commands at release and establishment, current prices, cash and revealed shops. The recorded release commands are evidence, not a general causal attribution: several workers can occupy the same tile.

## Main findings

The most conspicuous difference is the earlier DSM strawberry rotation: wheat-to-strawberry changes concentrate on days 2–3 in DSM and days 5 and 8 in UMG. DSM subsequently records 325 strawberry-to-tomato changes (3.01/game), 299 on days 18–19. UMG records only five (0.048/game). This is a candidate strategy difference, not evidence that the DSM choice earns more in the same world.

### DSM

9,595 type switches (88.8/game), plus 11,535 same-type replantings. Median vacancy between old and new type: 1 hour; 73.5% of switches have at most three nonproductive hourly states.

- melon: 1101 replacements; 100.0% leave the old type at age 10 days. 0/1101 have zero stored yield in the last old-type state.
- strawberry: 2560 replacements; 81.0% leave the old type at age 16 days. 2545/2560 have zero stored yield in the last old-type state.
- tomato: 636 replacements; 93.4% leave the old type at age 11 days. 633/636 have zero stored yield in the last old-type state.

| Transition | Events / games containing it | Median replacement action | Middle 80% of timestamps | Median source age at release | Median vacant hours |
|---|---:|---|---|---:|---:|
| WHEAT → CARROT | 1719 / 105 | D24 11:00 | D13 20:00–D26 18:00 | 3 | 1 |
| STRAWBERRY → WHEAT | 1685 / 108 | D22 16:00 | D19 15:00–D25 13:00 | 16 | 1 |
| WHEAT → STRAWBERRY | 1371 / 108 | D3 19:00 | D2 16:00–D13 15:00 | 3 | 1 |
| WHEAT → TOMATO | 734 / 102 | D14 22:00 | D12 17:00–D17 20:00 | 3 | 1 |
| CARROT → WHEAT | 618 / 77 | D23 09:00 | D13 15:00–D27 15:00 | 3 | 1 |
| MELON → WHEAT | 567 / 108 | D10 19:00 | D10 13:00–D11 17:00 | 10 | 12 |
| STRAWBERRY → CARROT | 547 / 94 | D24 20:00 | D19 16:00–D26 19:00 | 16 | 1 |
| TOMATO → CARROT | 399 / 89 | D24 21:00 | D22 16:00–D26 20:00 | 11 | 1 |
| STRAWBERRY → TOMATO | 325 / 104 | D18 19:00 | D18 11:00–D19 21:00 | 16 | 1 |
| MELON → STRAWBERRY | 242 / 101 | D11 14:00 | D10 16:00–D11 21:00 | 10 | 6 |
| TOMATO → WHEAT | 236 / 69 | D24 14:00 | D20 21:00–D27 13:00 | 11 | 1 |
| MELON → GOOSE | 189 / 107 | D11 14:00 | D10 16:00–D11 14:00 | 10 | 8 |

These are event-weighted descriptive quantiles; they are not confidence intervals. Wide or multimodal distributions should not be reduced to a single fixed replacement day.

Tile (0,0): 108/108 games change type. Most common path: **WHEAT → STRAWBERRY → TOMATO**, in 94 games. Among games that change, the first switch's middle 80% is D2 15:00–D2 17:00.

### UMG

7,867 type switches (74.9/game), plus 10,687 same-type replantings. Median vacancy between old and new type: 1 hour; 76.4% of switches have at most three nonproductive hourly states.

- melon: 1440 replacements; 99.9% leave the old type at age 10 days. 0/1440 have zero stored yield in the last old-type state.
- strawberry: 2066 replacements; 93.4% leave the old type at age 16 days. 2044/2066 have zero stored yield in the last old-type state.
- tomato: 850 replacements; 90.6% leave the old type at age 11 days. 840/850 have zero stored yield in the last old-type state.

| Transition | Events / games containing it | Median replacement action | Middle 80% of timestamps | Median source age at release | Median vacant hours |
|---|---:|---|---|---:|---:|
| WHEAT → CARROT | 1354 / 104 | D25 13:00 | D16 09:00–D27 15:00 | 3 | 1 |
| STRAWBERRY → WHEAT | 1292 / 105 | D22 20:00 | D21 19:00–D24 20:00 | 16 | 1 |
| MELON → WHEAT | 986 / 105 | D10 20:00 | D10 15:00–D18 16:00 | 10 | 8 |
| WHEAT → STRAWBERRY | 863 / 105 | D8 10:00 | D5 11:00–D13 12:00 | 2 | 1 |
| STRAWBERRY → CARROT | 768 / 105 | D23 08:00 | D22 06:00–D27 12:00 | 16 | 1 |
| TOMATO → WHEAT | 539 / 96 | D23 22:00 | D23 14:00–D26 14:00 | 11 | 1 |
| WHEAT → TOMATO | 503 / 97 | D16 09:00 | D13 14:00–D18 20:00 | 4 | 1 |
| CARROT → WHEAT | 384 / 62 | D25 14:00 | D19 14:00–D26 19:00 | 3 | 1 |
| TOMATO → CARROT | 308 / 83 | D24 14:00 | D23 11:00–D26 16:00 | 11 | 1 |
| SHEEP → CARROT | 180 / 56 | D26 04:00 | D25 04:00–D26 12:00 | 17 | 7 |
| MELON → GOOSE | 144 / 63 | D10 19:00 | D10 18:00–D10 20:00 | 10 | 13 |
| MELON → COW | 98 / 54 | D10 20:00 | D10 18:00–D10 20:00 | 10 | 14 |

These are event-weighted descriptive quantiles; they are not confidence intervals. Wide or multimodal distributions should not be reduced to a single fixed replacement day.

Tile (0,0): 11/105 games change type. Most common path: **WHEAT**, in 94 games. Among games that change, the first switch's middle 80% is D13 20:00–D22 19:00.

## Interpretation for the planner

The source lifecycle gives a strong candidate clock for when a tile can change. Destination type is a separate decision, conditioned on remaining season, visible demand, prices, existing farm output and feasible worker visits. The data do not yet establish which of those variables causes the observed choices.

Both policies commonly harvest a short crop or clear an exhausted long-lived crop and establish its replacement one hour later. This suggests transferring a complete release-and-replant appointment with its following maintenance and delivery commitments. Crop age is often more stable than calendar day; exact tile coordinates differ between leaders.

A useful next dataset treats same-type replantings as competing choices, rather than learning only from type switches. This audit already retains them, along with initial establishments and terminal vacancies. Policy evaluation must additionally include waiting/retaining a crop, input feasibility, output and profits; imitation frequencies alone are not optimization evidence.

## Day-12 boundary correction

The earlier heatmaps restarted each tile history at day 12. This event audit instead follows source identity across the boundary and dates the actual replacement action. Thus it includes replacements after day 12 of tiles whose old type disappeared before day 12. The resulting late counts are DSM 7,206 and UMG 5,961; applying the earlier within-window convention reproduces 7,176 and 5,777 exactly. This is a definition difference, not new games or a failed reconciliation.

## Reproduction

Run `node scripts/investigate_tile_transitions.cjs`, then `node scripts/report_tile_transition_timing.cjs <absolute-visualization-path>`. Event ledgers and summaries are in `results/fresh/tile_transition_timing/`. No agent policy was changed.
