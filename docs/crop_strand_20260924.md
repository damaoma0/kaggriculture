# Crop version of the strand rule: rejected (2026-09-24)

Idea (from V9's cohort preservation): the router penalises switching to a tape that grows neither today nor two days
on a live strawberry / melon / tomato of ours (`--cfg crop_strand_penalty=<w>`, `scripts/build_mg_tape_agent.py`,
default off). Offline, router switches abandon about 0.8 such tiles a game on the 2750-3000 panel (146 tiles in 183
y3 games, 94 of them strawberries, days 9-21; `scripts/crop_strand_at_switches.py`).

| panel | y3c1 (w = 1.0) vs y3 | y3c3 (w = 3.0) vs y3 |
|---|---|---|
| 180 ladder worlds (frozen opponents) | +168 (-111..+450), 17 better / 12 worse | +256 (-120..+634), 28 / 22 |
| 2750-3000, 136 of 185 (frozen, run stopped) | +289 (+44..+564) | +152 (-294..+545) |
| live V56, 20 seeds x 2 seats | **-785 (-1,415..-262), 0 better / 8 worse** | -608 (-1,313..+32), 4 / 8 |

The penalty does not only block switches, it redirects the router to other tapes (single worlds swing -11.2k to
+9.5k). Positive against frozen recorded opponents, clearly negative against the responsive one: rejected. Builds
`agents/mgt_y3c1.py`, `agents/mgt_y3c3.py` stay as research files; y3 is unchanged.
