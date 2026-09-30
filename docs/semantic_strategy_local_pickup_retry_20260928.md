# Route-local wheat pickup retry: mechanism review

This is a read-only proposal. No runtime source was changed and no new games were
run for this review. It is an alternative to test alongside the broad V6 recovery,
not a demonstrated replacement. Completed natural development results are V5
4/8 wins, mean margin +242.375, and V6 4/8, +1629.625; their shops differ in 6/8
pairs. Those results do not isolate either recovery mechanism.

## Evidence

All 14 recorded V6 wheat-recovery triggers are `pick_short`; none is `pick_none`.
The first trigger in each of the eight cases has identical V5/V6 action prefixes
for both players and identical current own-private snapshots. This provides eight
matched decision states. Later V6 triggers occur after divergence.

At those eight first states, current shed stock, after the other baseline pickups
that hour, covers the missing quantity in four cases. Two more have zero stock
now but receive a wheat purchase at the following observation. Two have zero
stock throughout the next four baseline observations. None has a baseline PASS
as the immediate next action.

| Case | Retry time | Missing wheat | Shed now | Other same-hour pickups | Later baseline PASS hours | Immediate next action |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 00 | D8 H4 | 1 | 0 | 0 | 17–23 | NORTH |
| 01 | D8 H3 | 1 | 0 | 0 | 23 | FEED |
| 02 | D9 H2 | 2 | 10 | 5 | 22–23 | EAST |
| 03 | D7 H4 | 1 | 0 | 0 | none | NORTH |
| 04 | D7 H2 | 2 | 10 | 8 | 22–23 | FEED |
| 05 | D7 H3 | 2 | 0 | 0 | 23 | PICKUP GOOSE |
| 06 | D8 H3 | 1 | 3 | 0 | none | PICKUP SHEEP |
| 07 | D7 H3 | 2 | 2 | 0 | 15–23 | NORTH |

Case07 has the clearest diagnostic room for a retry. Case06 ends with
BUILD_PASTURE at H22 and PLACE SHEEP at H23, so delaying departure risks that
placement. Cases02/04 have two later idle hours, but two extra feeds plus a pickup
can require three additional actions relative to the recorded broken route.
Case04's baseline sells precisely the two residual wheat at the retry hour.

The later stock and PASS observations are diagnostic only. They are not available
to a causal runtime policy and do not establish forward feasibility. Current
stock must also protect later scheduled pickups, beyond the same-hour quantities
in this table.

Evidence and hashes: `results/fresh/semantic_strategy_20260928/partial_pickup_retry_mechanism_audit.json`
and `partial_pickup_first_event_diagnostic.json`. The audit records every result
and action-file hash for the 16 V5/V6 games, plus the inspected engine and executor.

## Why a narrow retry is possible

Frozen executor source is
`results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py`.

* `_tier_cmd`, lines11685–11724: a positive partial pickup debits `shed_left`,
  increments the cursor once, records the completed pickup, and immediately
  returns PICKUP. The unit stays at the shed. This is a usable checkpoint.
* A zero pickup after its wait limit logs `pick_none`, increments the cursor, and
  continues inside the same call. The returned command can already be a later
  pickup or movement. Blindly rewinding that event can duplicate work. Exclude it
  from the first local-retry version.
* `_tier_check`, lines11495–11532: FEED without carried wheat skips. Restoring
  wheat therefore restores FEED actions that the broken route omitted. Compared
  with the full-supply original plan, the added cost is one pickup; compared with
  the recorded short-supply execution, it can be pickup plus every restored feed.
* `_tier_override`, lines11824–11893, shares a shed ledger across units in sorted
  order and records `_picked_now`. `_market`, lines3424–3433, reserves remaining
  planned pickups and the current-step debits. A post-market action override
  would bypass these accounting paths.
* Retirement filtering, lines9924–9931, removes FEED and CARE for every key in
  `_xretire`, including a key whose value is false. A retry must retain that rule.

Official engine source is
`.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py`.
PICKUP at lines358 onward caps quantity by actual shed stock. Unit actions run
before `_process_market` at lines935–941. A BUY issued this hour cannot fund this
hour's pickup; it becomes available at the next observation.

## Proposed bounded mechanism

Initial scope would be D6–10, one residual pickup per verified original
`pick_short`, using only the present observation and saved own execution state.
Do not enable it while the separate route-local replenishment experiment is
being isolated.

1. Save the route identity/generation, day, unit, original pickup index and amount,
   pre-action inventory, returned action, position and resulting cursor. At the
   next observation require actual inventory confirmation, the same unit at the
   same shed tile, unchanged route identity, and cursor exactly one past that
   pickup. Reject remapping, replanning, movement, day changes or ambiguous state.
2. Compute eligible unmet FEED demand only in the remaining route segment before
   its next normal WHEAT pickup. Exclude already-fed/gone animals and all committed
   retirement identities. Subtract the unit's current wheat and any provable
   intervening wheat harvest supply. Do not add new animal-care targets.
3. Limit the top-up by original shortfall, remaining eligible feed deficit, and
   present spare shed stock. Preserve the other routes' existing wheat claims.
   A conservative first implementation reserves all unchanged future WHEAT
   pickup quantities before considering the residual. This can reject useful
   opportunities, but avoids stealing another worker's allocation. Reserving only
   earlier unit IDs is insufficient.
4. Require a forward route-duration certificate from current position/cursor,
   including the FEED actions that become executable with replenished stock,
   remaining pickup/service/movement actions and release waits. The route must
   still finish protected work by H23 with the extra pickup. `plan_hours` alone
   can be stale after earlier waits; later observed PASS hours are not a runtime
   certificate. Where shared-tile changes or unknown availability prevent this
   certificate, reject rather than assume a repair is free.
5. Reuse the normal pickup dispatch/accounting path. Temporarily substitute a
   residual-sized pickup at the original index and restore the cursor to that
   index for exactly this dispatch, then restore its original descriptive amount
   once consumed. Do not insert/remove route items: `wait` is indexed by item and
   sub-operation. Preserve the completed original pickup and append the retry as
   a separate completion. Preserve other route definitions, cursors and histories.
6. Let shared `shed_left` and `_picked_now` account for the retry before market
   orders are computed. A residual still pending during an explicitly allowed
   wait needs a corresponding reserve; otherwise `_market` can sell it. Verify
   the route was actually dispatched after any internal replan/remapping rather
   than assuming a wrapper-side rewind survived.

The strict version rejects zero current stock and allows no wait. A separate
one-wait option could keep the residual pending for one additional observation
while normal market logic tries to replenish, then retry only against actual
stock. It costs two elapsed slots relative to immediate
departure, not one, and requires a separate duration check. Do not assume an
unexecuted purchase will succeed. Cancel on departure or generation change.

There is a possible zero-added-slot variant: if the normal dispatcher would
already PASS at the shed while waiting for a different pickup, use that slot for
the residual wheat without advancing the current next-item cursor. It still
needs stock reservation and accounting, and must preserve the wait-budget effect
of the original PASS. None of the eight immediate first-event actions qualifies;
prevalence at later waits has not been measured.

These rules preserve other workers' route state, not a promise that every future
action or market price remains identical. Shared tiles, stock and later market
flows can produce legitimate downstream differences.

## Required tests before an experiment

* Actual pickup 2/5 permits at most three additional units, and less when current
  inventory or remaining live demand closes the gap; never retry the full five.
* Already-fed, escaped or deliberately retiring targets need no replacement
  wheat. Include `_xretire[tile] == false` and persistent intent after a surprise
  feed.
* A later unit's reserved stock remains available; normal dispatch and market
  accounting include the residual pickup exactly once.
* No same-hour credit from a BUY; stock received next step can be used only then.
* Retry is idempotent, limited once, and rejected after movement, remap, replan,
  day change or a `pick_none` that already advanced into a later action.
* Protected terminal WATER/PLACE makes an otherwise attractive retry fail its
  duration guard. Count restored FEED operations in this check.
* A verified existing PASS substitution consumes no extra elapsed slot and does
  not advance the waiting pickup or corrupt its wait counters.
* Other route objects, cursors, `sub`, waits and completed-work records remain
  unchanged by the repair hook. The original completed partial pickup remains.
* Inputs contain no world identity, future shops, future observed stock or later
  recorded actions. Saved later observations are used only by offline diagnostics.

The distinct rolling-dispatch stall identified by the extractor has empty local
inventory and shed despite ample wheat carried by other workers. A small actual
market replenishment may unblock it without touching tier cursors. That narrower
purchase experiment is owned separately and should be assessed before combining
these mechanisms.
