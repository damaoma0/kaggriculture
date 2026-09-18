# Router production routines

Four actual router trajectories were reconstructed and every action checked against the public source. The work-order library also compiles all four recorded branch streams, including branches not visited in these four games. Planned tasks and successful farm transitions are kept separate.

## Production calendar

| Trace / route | Day | New crop cohorts | Animals placed | Land purchases |
|---|---:|---|---|---|
| 1 | 0 | {'WHEAT': 7, 'MELON': 12} | {'COW': 2, 'SHEEP': 2} | [] |
| 1 | 2 | {'WHEAT': 3} | {'COW': 1} | [] |
| 1 | 3 | {'WHEAT': 4} | {'COW': 1} | [] |
| 1 | 4 | {'WHEAT': 3} | {} | [] |
| 1 | 5 | {'STRAWBERRY': 4} | {} | [] |
| 1 | 6 | {'WHEAT': 5, 'STRAWBERRY': 8} | {'COW': 2} | [['NW', 'NE']] |
| 1 | 7 | {'WHEAT': 4, 'STRAWBERRY': 4} | {'COW': 2} | [] |
| 1 | 8 | {'WHEAT': 1, 'STRAWBERRY': 4} | {'COW': 1, 'SHEEP': 2} | [] |
| 1 | 9 | {'WHEAT': 4} | {} | [] |
| 1 | 10 | {'WHEAT': 7} | {'GOOSE': 3} | [] |
| 1 | 11 | {'WHEAT': 11, 'STRAWBERRY': 13} | {'SHEEP': 1} | [['NW', 'NE', 'SW']] |
| 1 | 12 | {'WHEAT': 8} | {} | [] |
| 1 | 13 | {'WHEAT': 6} | {} | [] |
| 1 | 14 | {'WHEAT': 7} | {} | [] |
| 1 | 15 | {'WHEAT': 8} | {} | [] |
| 1 | 16 | {'WHEAT': 7} | {} | [] |
| 1 | 17 | {'WHEAT': 7} | {} | [] |
| 1 | 18 | {'WHEAT': 7} | {} | [] |
| 1 | 19 | {'WHEAT': 7} | {} | [] |
| 1 | 20 | {'WHEAT': 8} | {} | [] |
| 1 | 21 | {'WHEAT': 6} | {} | [] |
| 1 | 22 | {'WHEAT': 10} | {} | [] |
| 1 | 23 | {'WHEAT': 14} | {} | [] |
| 1 | 24 | {'WHEAT': 12} | {} | [] |
| 1 | 25 | {'CARROT': 5, 'WHEAT': 8} | {} | [] |
| 1 | 26 | {'CARROT': 12} | {} | [] |
| 1 | 27 | {'CARROT': 14} | {} | [] |
| 2 | 0 | {'WHEAT': 7, 'MELON': 12} | {'COW': 2, 'SHEEP': 2} | [] |
| 2 | 2 | {'WHEAT': 3} | {'COW': 1} | [] |
| 2 | 3 | {'WHEAT': 4} | {'COW': 1} | [] |
| 2 | 4 | {'WHEAT': 3} | {} | [] |
| 2 | 5 | {'STRAWBERRY': 4} | {} | [] |
| 2 | 6 | {'WHEAT': 5, 'STRAWBERRY': 8} | {'COW': 2} | [['NW', 'NE']] |
| 2 | 7 | {'WHEAT': 4, 'STRAWBERRY': 4} | {'COW': 2} | [] |
| 2 | 8 | {'WHEAT': 1, 'STRAWBERRY': 4} | {'COW': 1, 'SHEEP': 2} | [] |
| 2 | 9 | {'WHEAT': 4} | {} | [] |
| 2 | 10 | {'WHEAT': 7} | {'GOOSE': 3} | [] |
| 2 | 11 | {'WHEAT': 11, 'STRAWBERRY': 13} | {'SHEEP': 1} | [['NW', 'NE', 'SW']] |
| 2 | 12 | {'WHEAT': 8} | {} | [] |
| 2 | 13 | {'WHEAT': 6} | {} | [] |
| 2 | 14 | {'WHEAT': 7} | {} | [] |
| 2 | 15 | {'WHEAT': 8} | {} | [] |
| 2 | 16 | {'WHEAT': 7} | {} | [] |
| 2 | 17 | {'WHEAT': 7} | {} | [] |
| 2 | 18 | {'WHEAT': 7} | {} | [] |
| 2 | 19 | {'WHEAT': 7} | {} | [] |
| 2 | 20 | {'WHEAT': 8} | {} | [] |
| 2 | 21 | {'WHEAT': 6} | {} | [] |
| 2 | 22 | {'WHEAT': 10} | {} | [] |
| 2 | 23 | {'WHEAT': 14} | {} | [] |
| 2 | 24 | {'WHEAT': 12} | {} | [] |
| 2 | 25 | {'CARROT': 5, 'WHEAT': 8} | {} | [] |
| 2 | 26 | {'CARROT': 12} | {} | [] |
| 2 | 27 | {'CARROT': 14} | {} | [] |
| 3 | 0 | {'WHEAT': 7, 'MELON': 12} | {'COW': 2, 'SHEEP': 2} | [] |
| 3 | 2 | {'WHEAT': 3} | {'COW': 1} | [] |
| 3 | 3 | {'WHEAT': 4} | {'COW': 1} | [] |
| 3 | 4 | {'WHEAT': 3} | {} | [] |
| 3 | 5 | {'STRAWBERRY': 4} | {} | [] |
| 3 | 6 | {'WHEAT': 5, 'STRAWBERRY': 8} | {'COW': 2} | [['NW', 'NE']] |
| 3 | 7 | {'WHEAT': 4, 'STRAWBERRY': 4} | {'COW': 2} | [] |
| 3 | 8 | {'WHEAT': 1, 'STRAWBERRY': 4} | {'COW': 1, 'SHEEP': 2} | [] |
| 3 | 9 | {'WHEAT': 4} | {} | [] |
| 3 | 10 | {'WHEAT': 7} | {'SHEEP': 3} | [] |
| 3 | 11 | {'WHEAT': 11, 'STRAWBERRY': 13} | {'SHEEP': 1} | [['NW', 'NE', 'SW']] |
| 3 | 12 | {'WHEAT': 8} | {} | [] |
| 3 | 13 | {'WHEAT': 6} | {} | [] |
| 3 | 14 | {'WHEAT': 7} | {} | [] |
| 3 | 15 | {'WHEAT': 7} | {} | [] |
| 3 | 16 | {'WHEAT': 8} | {} | [] |
| 3 | 17 | {'WHEAT': 7} | {} | [] |
| 3 | 18 | {'WHEAT': 7} | {} | [] |
| 3 | 19 | {'WHEAT': 7} | {} | [] |
| 3 | 20 | {'WHEAT': 8} | {} | [] |
| 3 | 21 | {'WHEAT': 6} | {} | [] |
| 3 | 22 | {'WHEAT': 10} | {} | [] |
| 3 | 23 | {'WHEAT': 14} | {} | [] |
| 3 | 24 | {'WHEAT': 12} | {} | [] |
| 3 | 25 | {'CARROT': 5, 'WHEAT': 8} | {} | [] |
| 3 | 26 | {'WHEAT': 12} | {} | [] |
| 3 | 27 | {'WHEAT': 12} | {} | [] |
| 4 | 0 | {'WHEAT': 7, 'MELON': 12} | {'COW': 2, 'SHEEP': 2} | [] |
| 4 | 2 | {'WHEAT': 3} | {'COW': 1} | [] |
| 4 | 3 | {'WHEAT': 4} | {'COW': 1} | [] |
| 4 | 4 | {'WHEAT': 3} | {} | [] |
| 4 | 5 | {'STRAWBERRY': 4} | {} | [] |
| 4 | 6 | {'WHEAT': 5, 'STRAWBERRY': 8} | {'COW': 2} | [['NW', 'NE']] |
| 4 | 7 | {'WHEAT': 4, 'STRAWBERRY': 4} | {'COW': 2} | [] |
| 4 | 8 | {'WHEAT': 1, 'STRAWBERRY': 4} | {'COW': 1, 'SHEEP': 2} | [] |
| 4 | 9 | {'WHEAT': 4} | {} | [] |
| 4 | 10 | {'WHEAT': 7} | {'SHEEP': 3} | [] |
| 4 | 11 | {'WHEAT': 11, 'STRAWBERRY': 13} | {'SHEEP': 1} | [['NW', 'NE', 'SW']] |
| 4 | 12 | {'WHEAT': 8} | {} | [] |
| 4 | 13 | {'WHEAT': 6} | {} | [] |
| 4 | 14 | {'WHEAT': 7} | {} | [] |
| 4 | 15 | {'WHEAT': 8} | {} | [] |
| 4 | 16 | {'WHEAT': 7} | {} | [] |
| 4 | 17 | {'WHEAT': 7} | {} | [] |
| 4 | 18 | {'WHEAT': 7} | {} | [] |
| 4 | 19 | {'WHEAT': 7} | {} | [] |
| 4 | 20 | {'WHEAT': 8} | {} | [] |
| 4 | 21 | {'WHEAT': 6} | {} | [] |
| 4 | 22 | {'WHEAT': 10} | {} | [] |
| 4 | 23 | {'WHEAT': 14} | {} | [] |
| 4 | 24 | {'WHEAT': 12} | {} | [] |
| 4 | 25 | {'CARROT': 5, 'WHEAT': 8} | {} | [] |
| 4 | 26 | {'CARROT': 12} | {} | [] |
| 4 | 27 | {'CARROT': 14} | {} | [] |

## Representative crop routines (trace 1)

Actions below are issued operations matched to live crop cohorts; they are not all guaranteed successful actions.

| Crop / tile | Planted | Fertilizer days | Harvest days | Harvest yield observed before action |
|---|---:|---|---|---|
| WHEAT [0, 1] | 0 | [] | [2] | [2] |
| WHEAT [0, 1] | 2 | [] | [4] | [2] |
| WHEAT [2, 0] | 3 | [] | [5] | [2] |
| WHEAT [1, 0] | 4 | [] | [6] | [2] |
| WHEAT [5, 0] | 6 | [] | [8] | [2] |
| WHEAT [9, 1] | 7 | [] | [9] | [2] |
| MELON [1, 3] | 0 | [] | [10] | [6] |
| WHEAT [0, 0] | 9 | [] | [11] | [2] |
| WHEAT [8, 0] | 8 | [] | [11] | [3] |
| WHEAT [3, 0] | 10 | [] | [12] | [2] |
| WHEAT [0, 8] | 11 | [] | [13] | [2] |
| WHEAT [0, 0] | 12 | [] | [15] | [3] |
| WHEAT [1, 2] | 13 | [] | [16] | [3] |
| WHEAT [0, 7] | 14 | [] | [17] | [3] |
| WHEAT [3, 9] | 15 | [] | [18] | [3] |
| WHEAT [0, 1] | 16 | [] | [19] | [3] |
| WHEAT [0, 4] | 17 | [] | [] | [] |
| WHEAT [0, 9] | 18 | [] | [21] | [3] |
| STRAWBERRY [2, 0] | 5 | [14, 18] | [15, 17, 19, 21] | [2, 2, 2, 2] |
| WHEAT [0, 1] | 19 | [] | [22] | [3] |
| STRAWBERRY [5, 1] | 6 | [15, 19] | [16, 18, 20, 22] | [2, 2, 2, 2] |
| WHEAT [1, 9] | 20 | [] | [23] | [3] |
| STRAWBERRY [1, 0] | 7 | [16, 20] | [17, 19, 21, 23] | [2, 2, 2, 2] |
| WHEAT [0, 0] | 21 | [] | [24] | [3] |
| STRAWBERRY [5, 0] | 8 | [17, 21, 24] | [18, 20, 22, 24] | [2, 2, 2, 2] |
| WHEAT [2, 0] | 22 | [] | [25] | [3] |
| WHEAT [4, 0] | 23 | [] | [26] | [3] |
| STRAWBERRY [3, 6] | 11 | [20, 24] | [21, 23, 25, 27] | [2, 2, 2, 2] |
| CARROT [0, 9] | 25 | [] | [27] | [1] |
| WHEAT [1, 0] | 24 | [] | [27] | [3] |
| WHEAT [2, 2] | 25 | [] | [28] | [3] |
| CARROT [9, 1] | 26 | [] | [28] | [2] |
| CARROT [2, 5] | 27 | [29] | [29] | [3] |

## Work-order model

Each worker/day has an ordered queue of operations with a target tile, preferred execution turn, operation arguments, inferred asset label and predecessor. Zero-duration position waypoints preserve shed occupancy at hiring times, which determines new-worker spawn positions. Movement is not stored as a policy action in the queue; the scheduler can compute a path from the actual position. Resource availability and crop validity still need checking at execution time. Branch selection remains the original public-state router.

The first prototype intentionally preserves the production calendar, worker ownership and market plan. Its purpose is to reproduce output while replacing movement replay with a constraint-based task executor. It is not yet a new farm-layout planner or a solver that reallocates jobs between workers.

[Machine-readable routines](../results/fresh/router_routines/routines.json) · [Compiled work orders](../data/router_work_orders.json)
