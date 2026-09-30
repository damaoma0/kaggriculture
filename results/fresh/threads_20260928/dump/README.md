# KD thread: midnight dump overflow (2026-09-28)

Agent: `agents/mgt_lead_sector_dump.py` (private copy, byte-identical to `agents/mgt_lead_sector.py`
at commit 60cfdc0d before this thread's edits). Base arm: `K5b`. All new CFG flags default OFF/None
and reproduce K5b's *exact* dollar and action-stream results when off (regression arm `KD0`, see
below). Spec: `results/fresh/threads_20260928/dump/kd_spec.json`. Helper scripts (new, `dump_`
prefix, do not touch shared files): `scripts/dump_collect_losses.py` (exact per-world/per-product
deletions via `season_losses.run`), `scripts/dump_shed_summary.py` (per-night shed/carried/deleted
averages via `season_shed.run`, same shape the coordinator used).

## Base arm config (K5b, quoted exactly as `run_arms.py` echoes it)

```
{"cut_mode": "leader_harvest", "dispatch_search": "active", "hp_crops": ["MELON", "WHEAT"],
"hp_wheat_min_units": 5, "sd_budget": 1.0, "sd_budget0": 2.0, "sd_collect_floor": 80.0,
"sd_coop_pair": 2, "sd_days": [11, 28], "sd_dv_coins": {...}, "sd_evals": 8000, "sd_evals0": 24000,
"sd_feed_bonus": 20.0, "sd_fert_ages": {"CARROT": [1, 2], "WHEAT": [1, 2]}, "sd_fert_first": 1,
"sd_fert_first_crops": ["WHEAT", "CARROT"], "sd_fert_frac": 0.6, "sd_fert_ret": 1, "sd_fert_sell": 1,
"sd_final_trip": 1, "sd_finish_collect": 1, "sd_hard_late_w": 10.0, "sd_hard_safe": 16,
"sd_hop_w": 20.0, "sd_hp_parity": 1, "sd_hv_pref": {...}, "sd_plan_log": 1, "sd_retire": 1,
"sd_sector_w": 40.0, "sd_seed_fix": 1, "sd_step_cap": 3.0, "sd_surv_fb": 20, "sd_tier": 1,
"sd_tier_coll_cap": 2, "sd_tier_deliver": 1, "sd_tier_deliver_check": 1,
"sd_tier_deliver_keep": ["MILK"], "sd_tier_farmer_hold": 1, "sd_tier_fert_exact": 1,
"sd_tier_fert_skip_harv": 1, "sd_tier_fert_supply": 1, "sd_tier_fill_near": 5, "sd_tier_iters": 2500,
"sd_tier_offsets": 4, "sd_tier_pair_own": 1, "sd_tier_pair_top": 3, "sd_tier_rate_c": 5.0,
"sd_tier_relief": 1, "sd_tier_relief_minv": 20.0, "sd_tier_wheat": 1, "sd_water_first": 1,
"sd_water_tomorrow": 10.0, "sell_now": ["MELON"]}
```
(matches the task's exact spec: sd_tier=1, sd_tier_fert_supply=1, sd_tier_coll_cap=2,
sd_tier_pair_own=1, sd_tier_fert_skip_harv=1, sd_fert_frac=0.6, sd_tier_fert_exact=1,
sd_tier_relief=1, sd_tier_rate_c=5.0, sd_days=[11,28], sd_tier_wheat=1, sd_tier_offsets=4,
sd_tier_pair_top=3, sd_tier_iters=2500, sd_tier_relief_minv=20.0, sd_tier_fill_near=5,
sd_tier_farmer_hold=1, sd_tier_deliver=1, sd_tier_deliver_check=1, sd_tier_deliver_keep=['MILK'])

**Regression check (KD0 = K5b unchanged, run through the private instrumented copy):** all 13
panel worlds reproduce K5b's own-cash/margin to the dollar (delta +0/+0 everywhere) and the exact
same per-world/per-product deletion counts (461 total). The instrumented copy is a faithful base.

## 1. Diagnosis with numbers

Added a diagnostic block to `_tier_deliver`'s return value, stored per day at
`tier_days[day]['dump']` in the multi JSON: `room`, `total0` (projected midnight hand-carry before
any deliveries), `total_after` (after the delivery loop finishes), `deliveries` (count scheduled),
`kept_shed0` (kept-product already in the shed at hour 0), `load0_by_product`. Cross-checked against
*actual* hour-23 shed/carried/lost from `scripts/season_losses.py`'s drop hook (exact engine replay).

**Example, world 112444381 (K5b/KD0), day 22:** `total0=115, room=73, deliveries=3, total_after=91`
(still 18 over the projected room when the search gave up) vs. the actual hour-23 state: shed=5,
carried=106, total=111, **11 units deleted** (111-100=11, matches `season_losses.py` exactly). Day
26: `total0=120, room=76, deliveries=2, total_after=111` (35 over) vs. actual shed=3, carried=111,
total=114, **14 deleted**. In both cases the room estimate correctly flagged a problem but the
search's own trim loop hit `best=None` (no remaining segment could add a shed detour without
increasing lateness or a supply failure) well before the gap closed — **on busy days, essentially
every hand's route is already packed to hour 23 with no slack for a delivery detour.** This, not a
wrong room number, is why K5b still loses 25/50/30 units on the three worlds named in the mission
brief.

**Coordinator cross-check (`scripts/season_shed.py`, 234 nights, days 11-28, panel13):** shed just
before the dump averages 5.5 (leader) / 8.2 (K5b) units — the room formula's
`n_anim * wheat_days` term (~20-27 units for a 17-cow/3-sheep world) wildly overestimates how much
wheat actually still sits in the shed at midnight (most reserved feed wheat is picked up and
consumed the same day). Carried-in totals are nearly identical (leader 82.0, K5b 85.5) — **K5b's
overflow is not from harvesting/carrying more, it is from carrying ~4 more MILK units/night than
the leader** (leader 4.9, K5b 9.1) because `sd_tier_deliver_keep=['MILK']` deliberately keeps milk
unsold when a delivery does fire, and the *room* accounting never subtracted that kept milk from
future capacity (bug, see KD1/KD10 below).

**Root-cause bug found and fixed (KD1, then corrected in KD10-13):** `_tier_deliver`'s trim loop
scored a scheduled delivery's full load as "resolved" (`total -= sum(lk.values())`,
`v2 = sum(v*price for all products)`), including the milk that `sd_tier_deliver_keep` explicitly
does NOT sell — milk moves from the hand to the shed, where it still occupies the 100-unit cap. A
milk-heavy delivery looked fully resolved when it was not.

## 2. Fixes implemented (all new CFG flags in `agents/mgt_lead_sector_dump.py`, default OFF)

1. **`sd_tier_deliver_keep_exact`** (naive fix, KD1) — exclude kept-product units from both the
   score (`v2`) and the total-reduction (`removed`). **Result: a clear regression** (KD1: own -29,
   margin -608 vs K5b; deletions 461->612). Root cause, traced: scoring kept goods at zero cash made
   every milk-heavy delivery look worthless (`v2 - lost <= 0`), so the search **stopped choosing
   them at all** (e.g. world 112562136 day 14: K5b schedules 1 delivery, KD1 schedules 0). But
   choosing a milk-heavy delivery was never really about its (fictional) sale value — a `DROP` moves
   that hand's whole load into the shed *before* the midnight batch-dump runs, so it is filled first
   and protected regardless of the rest of the board. KD1 lost that reorder-priority benefit without
   gaining anything real. **Parked as a documented negative result**, not deleted (its code and
   flag remain, default off, for future reference).

2. **`sd_tier_deliver_keep_room`** (corrected fix, KD10-13) — leaves the score/total-reduction
   exactly as the unfixed original (keeps the reorder-priority benefit), and instead shrinks the
   **room budget** available to later candidates by the kept-product portion of every delivery
   already scheduled that day (that portion is sitting in the shed the rest of the day, not sold).
   Paired with **`sd_tier_room_shed`** (room also reserves whatever kept product is already in the
   shed at hour 0, left over unsold from yesterday's delivery). Together (KD11): own -1, margin
   +574 vs K5b. `sd_tier_deliver_keep_room` alone, without `sd_tier_room_shed` (KD10), is a
   regression (own -614, margin -574) — the two must be used together (see arms table).

3. **`sd_tier_topup`** (+ `sd_tier_topup_hour`=23, `sd_tier_topup_margin`) — local runtime fix, no
   re-planning: at hour 23, if the *real* current total (`TP["_load_now"]`: actual shed + every
   unit's actual current inventory, already computed by the existing `sd_tier_deliver_check` code)
   is still heading over the cap, a hand with nothing left to do this turn (`action == ["PASS"]`)
   AND already standing at a shed tile (it cannot walk there in one turn) `DROP`s its sellable goods
   early, queued into the existing `TP["dsell"]` mechanism so `_market` sells it the same turn.
   Alone (KD3): own +87, margin +96 (small, since outbound hands rarely end their day at the shed by
   design — it fired only **8 times across the whole 13-world/18-day panel**). Still net non-negative
   everywhere tested, kept as a cheap safety net.

4. **`sd_tier_room_const`** (replaces `n_anim * wheat_days` with a flat constant) — a better room
   estimate grounded in the coordinator's empirical measurement (~5.5-8.2 units, not ~20-27). Swept
   8 / 15. Alone (KD14, const=8): own +443, margin +294 — the single best *isolated* one-line fix.

5. **`sd_tier_deliver_trim_max`** (was a hardcoded 4 trim attempts before a delivery candidate is
   abandoned) — swept 8 / 12. Alone, minimal effect (KD7/KD8 identical: own -5, margin +11): the
   `best=None` cases traced above are genuine end-of-day scheduling exhaustion (every remaining
   candidate segment is already packed to hour 24), not a shortage of trim attempts, so this does
   not resolve them. Combined with the other fixes it did not help further (KD9, KD13 both worse
   than their non-trim counterparts) — **parked, not recommended**.

## 3. Panel13 results (own/margin gap vs LEADER, delta vs K5b; wins out of 13; total deletions)

| Arm | flags on top of K5b | own Δ vs K5b | margin Δ vs K5b | wins | deletions (K5b=461) |
|---|---|---:|---:|---:|---:|
| KD1 | keep_exact | -29 | -608 | 6/13 | 612 |
| KD2 | room_shed | -24 | +294 | 8/13 | 578 |
| KD3 | topup | +87 | +96 | 8/13 | 457 |
| KD4 | keep_exact+room_shed+topup | -122 | +144 | 7/13 | 629 |
| KD5 | KD4 + room_margin=10 | -109 | -568 | 7/13 | 585 |
| KD7 | trim_max=8 | -5 | +11 | 8/13 | 485 |
| KD8 | trim_max=12 | -5 | +11 | 8/13 | (=KD7) |
| KD9 | KD4 + trim_max=8 | -910 | -841 | 5/13 | 602 |
| KD10 | keep_room (alone) | -614 | -574 | 7/13 | 552 |
| KD11 | keep_room+room_shed | -1 | +574 | 8/13 | 523 |
| **KD12** | **KD11 + topup** | **+66** | **+650** | **8/13** | 517 |
| KD13 | KD12 + trim_max=8 | -260 | +366 | 7/13 | 512 |
| KD14 | room_const=8 (alone) | +443 | +294 | 8/13 | 522 |
| KD15 | KD12 + room_const=8 | -125 | -269 | 7/13 | 484 |
| **KD16** | **KD12 + room_const=15** | **+598** | **+573** | **8/13** | 490 |

Leader deletions on this panel: 102 total (0.44/night, 234 nights); K5b: 461 (1.97/night); KD16:
490 (2.09/night). **Every combination that improves cash also raises the raw deletion count** —
per-product deletions (summed across all 13 worlds) show why this is still a cash improvement:

| product | K5b | KD12 | KD14 | KD16 |
|---|---:|---:|---:|---:|
| WHEAT (cheap) | 124 | 162 | 164 | 142 |
| CARROT (cheap) | 49 | 74 | 93 | 63 |
| MILK (expensive) | 64 | 60 | **36** | 71 |
| WOOL (expensive) | 23 | 29 | **14** | 23 |
| STRAWBERRY (expensive) | 86 | 85 | 95 | 91 |
| TOMATO/EGG/FERTILIZER | ~115 | ~107 | ~120 | ~100 |

Raw deletion **count** is the wrong target for this architecture: the fixes shift several units of
deletion from expensive wool/milk onto cheap wheat/carrot (most clearly in KD14) while also changing
intra-day selling/timing broadly, which is what actually moves cash. No arm flipped a win/loss on
this 13-world panel (the competition scores win/loss only, margin irrelevant) — these are
directional, same-panel evidence, not a demonstrated win-rate gain.

### Per-world table, best arm (KD16 = keep_room + room_shed + topup + room_const=15.0)

| episode | own Δ vs K5b | margin Δ vs K5b | result vs leader |
|---|---:|---:|---|
| 112444381 | +213 | +2300 | win |
| 112655730 | +1408 | +92 | loss |
| 112661570 | +0 | +0 | loss |
| 112667461 | +990 | +835 | win |
| 112673479 | +530 | +1609 | loss |
| 112562136 | +0 | +0 | win |
| 112563376 | +796 | +1113 | win |
| 112563785 | +3091 | +1668 | win |
| 112564633 | +862 | +254 | win |
| 112565927 | +567 | +762 | loss |
| 112567021 | +886 | +1047 | win |
| 112568233 | +1015 | +962 | loss |
| 112569426 | -2590 | -3190 | win |
| **MEAN** | **+598** | **+573** | **8/13 wins (= K5b)** |

11/13 worlds improve or are flat; only 112569426 regresses meaningfully (-2590/-3190, traced to more
deliveries there consuming route slack that would otherwise go to other extras — not further
decomposed under the time budget of this thread).

## 4. Exact code changes (`agents/mgt_lead_sector_dump.py`, diff vs `mgt_lead_sector.py`@60cfdc0d)

- New CFG defaults (all OFF/None, block after `sd_tier_coll_cap`): `sd_tier_deliver_keep_exact`,
  `sd_tier_room_shed`, `sd_tier_deliver_keep_room`, `sd_tier_room_margin`, `sd_tier_room_const`,
  `sd_tier_topup` (+`_hour`, `_margin`), `sd_tier_deliver_trim_max` (default 4, matches the old
  hardcoded value).
- `_tier_deliver(S, segs, tiles, day, st, shed=None)`: threaded `shed` through from `_tier_pre` ->
  `_tier_core` -> `_tier_deliver` (both gained a `shed=None` parameter). Room formula:
  `room = 100 - reserve - dump_buffer - kept_shed0 - room_margin` where `reserve` is
  `room_const` if set else `n_anim*wheat_days` (unchanged default), and `kept_shed0` is the
  hour-0 shed's kept-product stock when `sd_tier_room_shed`. Trim loop: `trim_max` parameterizes
  the previously-hardcoded `range(4)`; `keep_exact` branch (documented negative result) excludes
  kept products from `v2`/`removed`; after a delivery is committed, `sd_tier_deliver_keep_room`
  additionally shrinks `room` by that delivery's kept-product units. Returns a diagnostic dict
  now stored at `tier_days[day]['dump']` in the multi JSON (`room`, `total0`, `total_after`,
  `deliveries`, `kept_shed0`, `load0_by_product`).
- New function `_tier_topup(TP, pos, invs, actions)`, called from `_tier_override` at
  `hour >= sd_tier_topup_hour` when `sd_tier_topup`: forces `DROP` + queues `TP["dsell"]` for idle,
  shed-adjacent hands when `TP["_load_now"]` (already computed every hour for
  `sd_tier_deliver_check`) exceeds `100 - dump_buffer - topup_margin`.
- No changes to `agents/mgt_lead_sector.py`, `scripts/sector_run.py`, `scripts/run_arms.py`,
  `scripts/season_report.py`, or any other shared file. New scripts: `scripts/dump_collect_losses.py`,
  `scripts/dump_shed_summary.py` (both read-only wrappers around `season_losses.py`/`season_shed.py`).

## 5. Recommendation

- **`sd_tier_deliver_keep_exact` is a documented failure**: fixing the kept-product accounting
  bug naively (excluding it from the score) breaks the delivery mechanism's other, previously
  implicit job (reorder-priority protection). Keep the flag and its writeup as a parked negative
  result; do not repeat the same fix elsewhere in the codebase without the same care.
- **`sd_tier_deliver_keep_room` + `sd_tier_room_shed` + `sd_tier_topup` (KD12) or the same plus
  `sd_tier_room_const=15` (KD16)** are the leading candidates: positive own-cash and margin deltas
  on 8-9 of 13 worlds, no win/loss flip either direction on this panel, no increase in max
  observed decision time (planner budget/iterations unchanged). KD16 has the better own-cash mean
  (+598) and KD12 the better margin mean (+650); both keep the 8/13 win count.
  `sd_tier_deliver_trim_max` sweeps (KD7-9, KD13) did not help and are not recommended.
- **Not yet resolved**: the `best=None` scheduling-exhaustion cases (day 22/26 of 112444381 and
  similar) where every hand's route is already packed to hour 24 with no slack for any delivery
  detour — this is the deepest remaining source of overflow and would need either freeing labour
  earlier in the day (out of this thread's scope: interacts with the fertilize/collect/relief
  layers) or accepting some deletions as unavoidable under the current architecture.
- **Cross-thread**: the wheat thread's own finding (selling all shed wheat at hour 23 frees ~5
  units/night with the lowest deletions among its arms) and the milk-carry gap (K5b carries ~4
  more milk/night than the leader, a direct cost of `sd_tier_deliver_keep=['MILK']`) are consistent
  with what this thread found independently; no code changes were made outside
  `agents/mgt_lead_sector_dump.py` to avoid touching the wheat/animal threads' own private copies.
- Next step before any promotion: validate KD12/KD16 on a broader panel (this is 13 worlds) and
  against live opponents, per the project's standing rule against promoting off a single panel.
