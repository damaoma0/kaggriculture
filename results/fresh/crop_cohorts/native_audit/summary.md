# Native crop cohorts and worker slack

Two complete official-engine games were run with the corrected baseline in seat 0 against the downloaded public V45, using hidden controlled shop schedules (seeds 157900 and 157901). Every returned action was checked.

## Validation

- 720 states per game; 1438 baseline actions and 2876 total actions checked.
- All actions were dictionaries: **True**.
- Corrected five-unit opening feed purchase appeared in both games: **True**.

## Native transitions after day 12

- One-time harvest/replant cells: WHEAT->CARROT = 52, WHEAT->WHEAT = 176
- Final harvests from exhausted ongoing crops: STRAWBERRY = 62

### Stable small native cohorts

These cohorts appeared in both seeds and already have native WHEAT replant commands. Changing those commands is zero-extra-labor at planting time (later service is not established).

| Harvest/replant day | Cells | Size |
|---:|---|---:|
| 12 | `[[0,1]]` | 1 |
| 12 | `[[2,1]]` | 1 |
| 12 | `[[3,0]]` | 1 |
| 12 | `[[9,1]]` | 1 |
| 13 | `[[1,2],[1,3],[2,2]]` | 3 |
| 13 | `[[0,4]]` | 1 |
| 13 | `[[0,8]]` | 1 |
| 13 | `[[3,1]]` | 1 |
| 15 | `[[3,9],[4,9]]` | 2 |
| 15 | `[[0,0]]` | 1 |
| 15 | `[[0,5]]` | 1 |
| 15 | `[[0,9]]` | 1 |

### Native tape width guard

The input-tour overlay derives the native hand count from the selected tape and abstains unless every real hand is either native or owned by a known overlay. The action layer then pads/truncates only to the real observed hand count.

- Seed 157900: route 106 (terminal route 2); extra known-overlay hand maxima: day 22 (+1), day 23 (+1), day 27 (+2).
- Seed 157901: route 105 (terminal route 2); extra known-overlay hand maxima: day 19 (+1), day 22 (+2), day 23 (+1), day 27 (+1).

## Reachable terminal slack

Raw PASS counts are not treated as capacity. For exhausted strawberries, a worker qualifies only when its final commands of the weed day are all PASS and it can walk from the recorded suffix-start position, DIG, and PLANT before midnight.

Every mechanically reachable case below occurs on day 28. These are mutually exclusive alternatives for the same worker suffix within a seed, and none can produce a crop before the season ends. They are therefore evidence about route slack, not useful replacement targets.

| Seed | Day | Cell | Native transition | Worker | PASS suffix | Start | Held | Distance | Spare actions |
|---:|---:|---|---|---|---:|---|---|---:|---:|
| 157900 | 28 | (2, 7) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 4}` | 2 | 1 |
| 157900 | 28 | (3, 8) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 4}` | 2 | 1 |
| 157901 | 28 | (2, 7) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 3}` | 2 | 1 |
| 157901 | 28 | (3, 8) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 3}` | 2 | 1 |
| 157900 | 28 | (2, 6) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 4}` | 3 | 0 |
| 157900 | 28 | (3, 7) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 4}` | 3 | 0 |
| 157900 | 28 | (4, 8) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 4}` | 3 | 0 |
| 157901 | 28 | (2, 6) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 3}` | 3 | 0 |
| 157901 | 28 | (3, 7) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 3}` | 3 | 0 |
| 157901 | 28 | (4, 8) | STRAWBERRY weed → replacement | hand_7 | 5 | (2, 9) | `{"CARROT": 3}` | 3 | 0 |

## Interpretation

The native wheat cohorts are the lowest-risk mechanical insertion points because the planting command already exists. Any exhausted-strawberry row above is stronger evidence: a real worker can also perform both removal and replanting after decay. Neither is yet an economic recommendation; each substitution still needs seeds plus a feasible remaining-season watering, harvest, delivery, and price plan.

Detailed per-cell event histories and the original daily command timelines for every reachable worker are retained in the two game JSON files.
