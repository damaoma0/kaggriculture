# Leader semantics (2026-09-24)

Built by `scripts/extract_leader_semantics.py` from compact leader tapes
(`scripts/harvest_leader_tapes.py`, `data/leader_tapes/<team_id>_<submission>/`).

For each source tape, BOTH seats' recorded actions are replayed through the official
`kaggle_environments` kaggriculture engine with the recorded seed and a forced
shop-reveal schedule (reconstructed from the tape's flat reveal-order list under the
default rule: a new shop unlocks every 3 days, up to 8 total). `E._commit_unit`,
`E._apply_unit_action` and `E._do_hire` are wrapped (restored in `finally`) to see
which commands took effect and on which tile, the way `scripts/value_tape_search.py`
does it. Final cash for both players is checked against the tape's recorded rewards.

One file per game, **the leader's seat only**:
`data/leader_semantics/<team_id>/<episode>.json.gz`

## Schema

```
{
  "meta": {
    "episode": int, "team": str, "seat": 0|1, "seed": int,
    "rewards": [p0_final, p1_final],       # from the source tape
    "final_cash": [p0_final, p1_final],    # from this replay
    "opponent": str, "cash_match": bool    # final_cash == rewards (rounded)
  },
  "shops": [ {"shop": SHOP_NAME, "reveal_day": int}, ... up to 8 ],
  "days": [ <30 day objects, d = 0..29>, ... ]
}
```

Each day object reflects the leader's farm **at the start of day d** (board/cash) plus
everything that happened **during** day d (hours d*24 .. d*24+23):

- `board`: 100 two-char tile labels at day start, row-major (`tiles[y][x]`, index =
  y*10+x). Same encoding as `scripts/build_mg_tape_agent.py::_mgt_label`: crop code
  (`ST` strawberry, `ME` melon, `TO` tomato, `WH` wheat, `CA` carrot), animal
  (`sh`/`co`/`go` sheep/cow/goose, lowercase), `' .'` empty or weed, `' L'` locked,
  other structures lowercased 2-char kind (e.g. `'pa'` empty pasture, `'co'` is only
  used when an animal occupies the tile - an empty coop/pasture uses its own `kind`).
- `board_counts`: `Counter` of the above labels.
- `planted`: `{crop: [tile_index,...]}` for PLANT commands that took effect this day.
- `harvested`: `{"units": {product: units}, "tiles": [tile_index,...]}` for HARVEST
  commands that took effect (product = crop name or animal product, e.g. WOOL).
- `animals`: `{"bought": {species: n}, "placed": [tile_index,...], "sold": {species: n},
  "culled": [tile_index,...]}`. `bought` = successful BUY_ANIMAL market orders.
  `placed` = successful PLACE onto an empty matching structure. `sold` = successful
  SELL of a live animal itself (should be empty in valid games - animals aren't
  market products, only their output is). `culled` = an animal tile present at this
  day's start is gone (reverted to bare structure) by the next day's start, without a
  PLACE recorded on that tile the next day - i.e. it starved (2 consecutive unfed
  days), detected by diffing consecutive day-start boards, not by a hook.
- `built`: `{"BUILD_COOP": [tile_index,...], "BUILD_PASTURE": [tile_index,...]}` for
  successful builds. `dug`: tile indexes where DIG cleared a tile.
- `maintenance`: `{"WATER"|"FEED"|"CARE"|"FERTILIZE": [tile_index,...]}` - tiles where
  that command took effect (flag flipped / fertilized_until_day advanced) this day.
- `eligible`: `{"crops": {crop: n}, "animals": {species: n}}` - counts of live crop/
  animal tiles from the day-start board, i.e. what maintenance *could* have targeted.
- `labour`: `{"hires_asked": n, "hires_arrived": n, "hands_present": n,
  "command_counts": {op_or_"MOVE": n}, "no_effect_commands": n}`. `hires_asked` sums
  `["HIRE"]` market orders across the day's 24 hours (post the engine's 10-order/turn
  cap). `hires_arrived` = successful `_do_hire` calls. `hands_present` = number of
  hired hands active that day (captured just before the day-end reset). NORTH/SOUTH/
  EAST/WEST are folded into a single `"MOVE"` bucket; every other farmer/hand command
  type (including PASS) is its own key. `no_effect_commands` counts unit commands
  (excluding PASS) whose position, tile and inventory were unchanged by the call
  (blocked moves, out-of-range hand indexes, failed PLANT/HARVEST/etc).
- `cash_start`: leader's money at day start.
- `market`: `{"sold_units": {product: n}, "sold_revenue": {product: $}, "bought_units":
  {item: n}, "bought_spend": {item: $}}` for the leader's successful market orders
  that day (SELL; BUY_PRODUCT for wheat/fertilizer, BUY_SEED per crop, BUY_ANIMAL per
  species - the last three all count toward `bought_units`/`bought_spend`, keyed by
  item name, e.g. `"WHEAT"`, `"MELON"` (seed), `"SHEEP"`).

`shops[i].reveal_day` is `3*(i+1)` under the competition's default
`townShopUnlockInterval=3`/`MAX_SHOP_INSTANCES=8` (see `docs/environment.md`); it is
not read off the replay per game, since the source tape only stores the flat
reveal-order list, not a per-day snapshot.

## Coverage note

`data/leader_tapes/` may hold more than one submission directory for a team (its
tapes were topped up on 2026-09-24 and some teams' currently-*active* Kaggle
submission had changed, in one case to a submission with too few completed games and
a much lower score than the team's established ~3000-rated one - see
`scripts/topup_leader_tape_by_submission.py`). This extraction was run against the
established >=3000-rated submission directory for every team; any other directories
under `data/leader_tapes/<team_id>_*` were not extracted.
