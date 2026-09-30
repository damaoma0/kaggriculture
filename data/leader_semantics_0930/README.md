# data/leader_semantics_0930 (2026-09-30, meta-openings / 4Q study)

One folder per leader tape folder `<team_id>_<submission>` (several submissions of one team side by side), one gzip
json per game: `<team_id>_<submission>/<episode>.json.gz`.

Written by `meta_extract_0930.py` (sale-rules / meta scratchpad
`C:\Users\xyygl\AppData\Local\Temp\claude\C--Users-xyygl-Documents-kaggriculture\6d41efd9-2702-44ee-9a16-7709427fd202\scratchpad`),
a copy of `scripts/extract_leader_semantics_dsmc_20260929.py`: both seats' recorded actions are replayed through the
official engine (kaggle-environments 1.32.7) with the recorded seed and forced shops; `meta.cash_match` says whether
both final cash values equal the recorded rewards.

Schema = `data/leader_semantics/README.md` plus:
- **Day fix.** `market.*`, `animals.bought` and `labour.hires_arrived` are dated by the day the event happened
  (`meta.day_fix = true`). Do NOT apply the one-day shift described in data/leader_semantics/README.md (KNOWN ISSUE)
  to these files.
- `days[d].board_detail`: exact dawn counts per quadrant (`NW` start, `NE` second / $1,000, `SW` third / $2,000,
  `SE` fourth / $4,000): crops `WH CA TO ST ME`, animals `sheep cow goose` (from `tile['animal']`, so cows are not
  confused with empty coops), `empty_coop`, `empty_pasture`, `WEED`, `EMPTY`, `LOCKED`.
- `days[d].requested`: the leader's market requests that day after the engine's 10-order cap (`'OP:ITEM'` -> units;
  `HIRE` / `BUY_LAND` -> orders). `days[d].bought_by_op`: successful buys `'OP:ITEM'` -> units (seed wheat and bought
  wheat apart; `market.bought_units` merges them as before). `days[d].land`: successful BUY_LAND (hour, step, cost,
  quadrant). `days[d].harvested.by_quad`: units harvested per quadrant and product (exact, per HARVEST action).
- `opp_days[d]`: the opponent seat's `board_detail`, `cash_start`, `hands_present`, `hires_arrived`, `land`,
  `requested`, `bought_units`, `bought_spend`, `bought_by_op`.
- `meta.quadrants_by_day`, `meta.source` (the tape file).

Games per folder were chosen with `--prefer-top20` (games against current top-20 teams first, then newest), 30 each.
