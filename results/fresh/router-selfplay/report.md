# Match log

Seed: 20260915; kaggle-environments: 1.32.7

- Seat 0: `agents/public/tschinkel_router_v31.py`
- Seat 1: `agents/public/tschinkel_router_v31.py`

The replay contains both players' private state for offline analysis. An agent cannot see its opponent's private state during play.

Orders in the turn log are requests, not proof of successful execution. Cash changes are exact net changes, including purchases and hires.

## Daily checkpoints

Day/hour are zero-based; checkpoints show the start of each day and the terminal state.

| Step | Day:hour | Seat 0 cash | Seat 1 cash | Seat 0 crops / animals | Seat 1 crops / animals |
|---:|---:|---:|---:|---|---|
| 0 | 0:00 | 3000 | 3000 | {} / {} | {} / {} |
| 24 | 1:00 | 24 | 24 | {'WHEAT': 7, 'MELON': 12} / {'SHEEP': 2, 'COW': 2} | {'WHEAT': 7, 'MELON': 12} / {'SHEEP': 2, 'COW': 2} |
| 48 | 2:00 | 149 | 149 | {'WHEAT': 7, 'MELON': 12} / {'SHEEP': 2, 'COW': 2} | {'WHEAT': 7, 'MELON': 12} / {'SHEEP': 2, 'COW': 2} |
| 72 | 3:00 | 144 | 144 | {'WHEAT': 7, 'MELON': 12} / {'COW': 3, 'SHEEP': 2} | {'WHEAT': 7, 'MELON': 12} / {'COW': 3, 'SHEEP': 2} |
| 96 | 4:00 | 127 | 127 | {'WHEAT': 7, 'MELON': 12} / {'COW': 3, 'SHEEP': 2} | {'WHEAT': 7, 'MELON': 12} / {'COW': 4, 'SHEEP': 2} |
| 120 | 5:00 | 49 | 142 | {'WHEAT': 7, 'MELON': 12} / {'COW': 3, 'SHEEP': 2} | {'WHEAT': 7, 'MELON': 12} / {'COW': 4, 'SHEEP': 2} |
| 144 | 6:00 | 225 | 213 | {'WHEAT': 3, 'STRAWBERRY': 4, 'MELON': 12} / {'COW': 3, 'SHEEP': 2} | {'WHEAT': 3, 'STRAWBERRY': 4, 'MELON': 12} / {'COW': 4, 'SHEEP': 2} |
| 168 | 7:00 | 581 | 617 | {'STRAWBERRY': 10, 'MELON': 12, 'WHEAT': 5} / {'COW': 5, 'SHEEP': 2} | {'STRAWBERRY': 12, 'MELON': 12, 'WHEAT': 5} / {'COW': 6, 'SHEEP': 2} |
| 192 | 8:00 | 186 | 309 | {'WHEAT': 9, 'STRAWBERRY': 14, 'MELON': 12} / {'COW': 7, 'SHEEP': 2} | {'WHEAT': 9, 'STRAWBERRY': 16, 'MELON': 12} / {'COW': 8, 'SHEEP': 2} |
| 216 | 9:00 | 661 | 684 | {'WHEAT': 5, 'STRAWBERRY': 17, 'MELON': 12} / {'COW': 8, 'SHEEP': 4} | {'WHEAT': 5, 'STRAWBERRY': 20, 'MELON': 12} / {'COW': 9, 'SHEEP': 4} |
| 240 | 10:00 | 1551 | 1735 | {'WHEAT': 5, 'STRAWBERRY': 17, 'MELON': 12} / {'COW': 8, 'SHEEP': 4} | {'WHEAT': 5, 'STRAWBERRY': 20, 'MELON': 12} / {'COW': 9, 'SHEEP': 4} |
| 264 | 11:00 | 14700 | 14884 | {'WHEAT': 12, 'STRAWBERRY': 17} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 4} | {'WHEAT': 12, 'STRAWBERRY': 20} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 4} |
| 288 | 12:00 | 12531 | 13816 | {'STRAWBERRY': 30, 'WHEAT': 20} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'STRAWBERRY': 33, 'WHEAT': 20} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 312 | 13:00 | 16148 | 17565 | {'WHEAT': 24, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 24, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 336 | 14:00 | 17879 | 19899 | {'WHEAT': 24, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 24, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 360 | 15:00 | 22439 | 24459 | {'WHEAT': 24, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 24, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 384 | 16:00 | 25009 | 27029 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 408 | 17:00 | 31630 | 35066 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 432 | 18:00 | 37823 | 41259 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 456 | 19:00 | 44650 | 49864 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 480 | 20:00 | 50407 | 55621 | {'WHEAT': 24, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 24, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 504 | 21:00 | 56401 | 63180 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 528 | 22:00 | 64194 | 71054 | {'WHEAT': 25, 'STRAWBERRY': 30} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 25, 'STRAWBERRY': 33} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 552 | 23:00 | 71781 | 79920 | {'WHEAT': 29, 'STRAWBERRY': 26} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 29, 'STRAWBERRY': 29} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 576 | 24:00 | 75597 | 83752 | {'WHEAT': 37, 'STRAWBERRY': 20} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 37, 'STRAWBERRY': 21} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 600 | 25:00 | 78606 | 86940 | {'WHEAT': 41, 'STRAWBERRY': 16} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 41, 'STRAWBERRY': 17} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 624 | 26:00 | 81273 | 89756 | {'WHEAT': 39, 'CARROT': 5, 'STRAWBERRY': 13} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 39, 'CARROT': 5, 'STRAWBERRY': 13} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 648 | 27:00 | 84378 | 94044 | {'WHEAT': 27, 'CARROT': 17, 'STRAWBERRY': 13} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 27, 'CARROT': 17, 'STRAWBERRY': 13} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 672 | 28:00 | 86375 | 96041 | {'WHEAT': 15, 'CARROT': 30, 'STRAWBERRY': 3} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'WHEAT': 15, 'CARROT': 30, 'STRAWBERRY': 3} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 696 | 29:00 | 92661 | 102356 | {'CARROT': 24} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {'CARROT': 24} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |
| 719 | 29:23 | 101540 | 110930 | {} / {'GOOSE': 3, 'COW': 8, 'SHEEP': 5} | {} / {'GOOSE': 3, 'COW': 9, 'SHEEP': 5} |

## Final result

Rewards: [101540.0, 110930.0]; statuses: ['DONE', 'DONE']

Files: `replay.json` (full state/action history), `turns.jsonl` (one action/result pair per line), `summary.json` (provenance and result).

`replay.html` is the environment's native visual replay.
