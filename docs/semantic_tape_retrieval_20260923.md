# Semantic tape retrieval investigation — 23 September 2026

The active `mgt_m1` agent was not changed. This investigation adds extracted
semantic profiles and an offline retrieval audit. No new competitive policy or
submission was run.

## Exact current picker

The library has 584 historical UMG tapes. At the start of each day from day 3
through day 28, the router compares the live board with each tape's recorded
day-start board. Each tile is reduced to two characters: empty/weed, locked,
the first two crop letters, or the first two animal letters. Age, held yield,
care, money, inventory and workers do not enter this board distance. A new
route must have at most eight mismatching tiles. The incumbent route remains
eligible even above eight and receives a four-point penalty in that case.

For each visible shop prefix of length `k`, the router forms weighted cumulative
product-demand vectors. It compares at checkpoints `2,4,5,6,8`, using
`min(checkpoint,k)` and stopping at the first checkpoint at or beyond `k`.
Weights are strawberry 3, tomato/wool 2, carrot/milk 1.5, egg 1 and wheat 0.5.
It subtracts `0.01 × common ordered prefix length`. The configured future-shop
weight is zero; the latent future-shop expectation code is inactive.

For an eligible tape, the score is:

`revealed-history demand distance − ordered-prefix bonus + tile Hamming
 + 4 × incumbent animals with no candidate animal on their tile today or
 two days later + (4 if incumbent and tile Hamming > 8 else 0)`.

Ties prefer the current route, then fewer tile mismatches, then library order.
The selected tape's hourly worker commands are replayed at their original
coordinates. The selector neither matches a production-count target nor
translates the tape's actions to the actual farm. Code: `agents/mgt_m1.py`,
`_mgt_distance` and `_mgt_router`.

## What can be extracted semantically

`scripts/extract_semantic_tapes.py` now produces two evidence levels:

- All 584 compact tapes: dated *requested* crop planting, animal placement and
  animal orders, plus *realized* crop/animal counts at day starts. A requested
  command may fail or be deliberately over-requested.
- 630 three-day windows from 105 full UMG replays: successful planting, actual
  cow/sheep/goose placement, feed/care visits to starting animals, recorded
  product output, and same-tile crop transitions derived from before/after
  states. These jobs contain native tile age and care in the source snapshots.

The full windows contain 15,995 verified plantings, 99 verified animal
placements, and 5,328 changes from one known crop to a different crop on the
same tile. Every counted successful planting/animal placement was checked
against the corresponding compact tape's requested command count. One example
is UMG episode 110003132, seat 1: cows were placed on days 12 and 14. Another
is episode 109887724, seat 1: wheat tiles were replanted with strawberries on
day 13 (five tiles) and day 14 (one tile) in its day-12 window.

For “stop servicing sheep,” the record can state exact last feed/care visits
and whether each starting sheep survives the window. It cannot prove that a
missed service was intentional. For example, two sheep in episode 109712554's
day-27 window have no successful feed or care and are absent at the end. Calling
that a chosen retirement would require evidence beyond the tape.

Artifacts: `results/fresh/semantic_tapes/compact_profiles.json`,
`verified_segments.json`, and `summary.json`.

## Retrieval frontier on our recorded checkpoints

`scripts/audit_semantic_tape_retrieval.py` queries the same 430 day-12/15/18/21/24
checkpoints from 86 m1 games against all 584 tapes. Selection sees only visible
shops and current crop/animal counts. Candidate plan edits use the next three
days of requested planting/animal-placement commands; these are not successful
output or cash. The unconstrained comparison exactly reproduces the prior
position-free demand result and tie break.

| Rule | Different tape | Mean revealed-history demand mismatch | Mean live-asset count gap |
|---|---:|---:|---:|
| Actual m1 route | — | 20.28 | 2.46 |
| Best demand fit, no conversion bound | 349/430 | 12.40 | 14.62 |
| Asset count gap no worse than actual route | 18/430 | 20.15 | 2.43 |
| Asset gap ≤ actual +4, dated plant edit ≤8, no extra animal-count shortfall | 38/430 | 19.99 | 2.63 |
| Same, dated plant edit ≤16 | 73/430 | 19.65 | 2.80 |

The plan-edit budget is an exploratory L1 count of changed crop/day requests;
the asset and animal limits are count proxies, not coin costs or feasibility
certificates. At the eight-edit setting, 36/430 checkpoints have strictly
better demand-history fit, but the mean improvement is only 1.4%. Relaxing
the constraints makes matching much better while pulling in physically
different farms. This shows why a lower demand-distance score alone is a poor
switch trigger.

For a concrete candidate, our episode 111289768 at day 21 has history-distance
32 on its incumbent route. An unrestricted donor scores 17.5 but differs by
22 live assets and has three fewer animals by species count. A constrained
donor scores 23, differs by four assets, requests five dated planting edits,
and has no extra animal-count shortfall. None of these values predicts cash.

## Better selection and handoff algorithm to test

1. **Represent plans as dated obligations.** For each source, retain visible
   demand, existing cohort state, next-reveal planting and animal additions,
   service requirements, expected output by deadline, and terminal cohorts.
   Record a retirement as an *option* with a projected opportunity cost, not
   as a label inferred from one missed feed.
2. **Retrieve a Pareto set.** Keep the incumbent and candidates that improve
   visible-demand fit or predicted output while limiting live-cohort and
   investment-calendar changes. Use the rich 105 donors for age/care-aware
   residual output, the broader 584 for weak calendar candidates. A small
   regularized model can suggest targets for unseen shop mixes; grouped
   shop-composition validation is already available in the prefix-prediction
   research. The model should learn production targets, not hallucinate
   successful actions from compact requests.
3. **Compile each candidate onto the actual farm.** Preserve and service all
   valuable live cohorts. Assign new crops and animals to available tiles by
   minimum added travel/clearing cost, schedule workers and purchases, and
   simulate the next reveal with the official engine. The donor's coordinates
   are never copied. An intentional animal retirement must be priced against
   remaining yield and terminal value.
4. **Price the handoff over the remaining season.** Compare candidate and
   incumbent from the same checkpoint, including replacement crop cycles,
   future maintenance, cash, market response and terminal assets. Switch only
   if the projected gain exceeds a conservative uncertainty allowance and
   the plan has an executable successor. Reconsider at the next reveal.
5. **Validate against unchanged m1.** The candidate must beat the baseline on
   fresh natural worlds in both seats, with switch-specific fixed-shop traces,
   no catastrophic lower tail, and measured execution time. A purely offline
   retrieval metric cannot certify any of those.

This design responds to the observed failure: a forced exact-world day-18 tape
switch lost 21,885 margin and added 268 flagged invalid tile commands, despite
perfect shop matching. A previous continuation compiler could execute 8/12
native windows, but its full-game policy lost because profitable replacement
planting stopped after the handoff. The next experiment must test complete
economic continuity, not just more accurate retrieval or immediate service.

## Reproduction

Run `scripts/extract_semantic_tapes.py`, then
`scripts/audit_semantic_tape_retrieval.py` with Python 3.12. The audit asserts
584 profiles and 430 queries, and rechecks each incumbent demand and asset
distance against the earlier independent audit. Source windows and limitations
are recorded in `results/fresh/semantic_tapes/`.

## Follow-up: using the labor scheduler, 23 September 2026

The existing 48-hour `choose(observation, own_window, ...)` labor scheduler
requires a complete supplied action plan. It preserves that plan's projected
production while changing worker routes and sale timing. It does not generate
seed orders, vacant crop sites, establishment work or later crop service from
semantic targets. The separate `continuation_executor` can compile fresh jobs
from actual worker positions, so the first handoff probe used it to build a
plan, then used `choose` on the resulting first 48 hours.

The offline search produced 38 conservative candidate switches among 430
checkpoints. Both incumbent and candidate semantic calendars were compiled
from the **same actual checkpoint** for the next three days. Candidate
projection passed in 20/38, incumbent projection in 20/38, and both in 17/38.
All 20 passing candidate projections preserved the starting animal counts.
The projector holds shops, removes new weeds and assumes no rival trades;
failures include nine planning-budget limits, eight day-capacity failures and
one unfulfilled job. Those are feasibility outcomes, not profit estimates.

For the first five both-feasible cases in saved query order, the compiled
plans were then executed with the official interpreter under each target
world's recorded shops and opponent action stream. The semantic candidate
beat the *compiled* incumbent in two cases. Its mean cash difference was
**-290** at the three-day boundary. Relative to actual recorded m1 actions,
all five compiled candidates lost **944–3,274 cash** by that boundary. The
compiled incumbent also lost 984–2,717 cash in these cases. This identifies
the generated production calendar/execution as the larger immediate gap;
the donor search score alone cannot repair it.

The working labor scheduler was then applied to those five candidate action
plans. It changed all five 48-hour windows and gained **89, 89, 89, 89 and
144 cash**, with identical terminal asset counts and sales revenue in each
exact-engine comparison. This verifies its conditional benefit on these new
plans. The slowest `choose` call took about **1.30 seconds**, above the
default one-second action limit. These runs are offline research, not an
integrated competition agent.

Finally, a narrow in-place semantic edit was tested without replacing the
whole tape. At day 21 of episode 111291994, the candidate calendar requests
one more tomato and one fewer wheat. The experiment bought one tomato seed
and changed one known-successful wheat planting to tomato at the same tile;
all other recorded actions remained. The seed purchase and tomato planting
both succeeded. At day 24 the margin was 50 lower, exactly the extra seed
cost, with one extra tomato plant and one fewer wheat plant. At the fixed
recorded season end the margin was **945 lower**. The day-21 tomato is not
mature until day 29. On day 24 the tape's harvest therefore did nothing and
its wheat replant was blocked by the occupied tile. The same happened to a
day-27 wheat harvest/carrot replant. On this tile, the original route harvested
five wheat on day 24, five more on day 27 and two carrots on day 29; the edit
harvested one tomato on day 29, which remained unsold in the shed.

The missing five wheat after day 24 depleted feed stock. On day 25, recorded
FEED commands for a cow, a goose and a sheep failed. Their later harvests
included two fewer milk, one fewer egg and three fewer wool on day 26. At the
end, our cash was 406 lower: 50 for the seed and 356 in net sales revenue.
The rival produced and sold the same quantities, but earned 539 more because
our reduced selling kept shared-market prices higher. Thus the margin fell
by 406 + 539 = **945**. This fixed-action diagnostic does not represent a
live agent that could adapt later sales and jobs.
The labor scheduler returned the unchanged edited window in this example.
This one selected case is a failure demonstration, not an estimate of the
average value of tomato substitution.

The next implementation needs to modify the *intact m1 plan* with a small
dated delta and synthesize every follow-on job for the changed cohort. The
result must be projected with the official engine through harvest and checked
against m1's unchanged obligations. The labor scheduler can then optimize
the complete supplied plan. A retrieved calendar that only specifies the
planting action is insufficient.

Follow-up scripts and artifacts:

- `scripts/probe_semantic_handoff.py` → `handoff_probe.json`.
- `scripts/execute_semantic_handoff.py` → `handoff_exact_probe.json`.
- `scripts/schedule_semantic_handoff.py` → `scheduled_handoff_probe.json`.
- `scripts/probe_semantic_inplace_edit.py` → `inplace_edit_probe.json`.
- `scripts/trace_inplace_edit_cause.py` → `inplace_edit_cause.json`.

All artifacts are under `results/fresh/semantic_tapes/`. The selected
competitive agent remains `agents/mgt_m1.py`; no submission was made.

## Correction and funded repair of the one-tile probe

The day-21 case **is a real revealed-shop mismatch, but it is not evidence
for a wheat-to-tomato change driven by those shops**. Product order below is
strawberry, tomato, wool, carrot, milk, egg, wheat. The demand vectors from
the seven shops visible at the decision are:

| Source | Revealed-shop demand vector |
|---|---|
| Actual world | (5, 0, 2, 2, 3, 2, 3) |
| Incumbent tape 110059839 | (3, 2, 2, 2, 4, 1, 3) |
| Retrieved tape 110408336 | (5, 1, 2, 1, 3, 2, 3) |

All three agree on wheat demand (3). The actual shops demand *less* tomato
than either tape, not more. The retrieved tape fits the revealed shops much
better overall (history distance 19 versus 28 for the incumbent), mainly
because its strawberry, milk and egg mix is closer. Yet its next-three-day
request calendar has two fewer wheat plantings and one extra tomato planting.
The probe copied only the day-21 wheat-to-tomato difference. It was a
convenient small action edit from a better-matching donor, not a proven
tomato-specific mismatch. A later pizza-shop reveal cannot justify the
day-21 decision because it was unavailable then.

An additional directional audit checked all 38 conservative retrieved
switches. Among their 71 nonzero crop-request changes, 24 point in the same
direction as the product's revealed-demand gap against the incumbent tape,
17 point opposite, and 30 have zero revealed gap. This screening diagnostic
does not account for stock or crop age; it demonstrates that the aggregate
retrieval score alone does not establish a reason for an individual planting
edit. One different checkpoint, episode 111289863 on day 15, does have the
requested *direction*: actual tomato demand exceeds its incumbent by one,
wheat is lower by one, and its retrieved calendar requests one more tomato
and three fewer wheat over three days. That case has not yet had a funded
exact-engine handoff test.

We replayed explicit repairs under the same recorded shops, rival and
otherwise unchanged actions. Relative to the unedited baseline, final margin
was:

| One-tile edit and repair | Final margin change | Day-25 successful feeds |
|---|---:|---:|
| Tomato planting only | -945 | 16 |
| Also sell the tomato harvested on day 29 | -879 | 16 |
| Also reserve 3 wheat from the day-24 sale | -397 | 19 |
| Instead buy 3 more wheat before feeding | -397 | 19 |

The baseline had 19 successful day-25 feeds. Both wheat repairs restored all
three missed feeds and the baseline's milk, egg and wool output; the terminal
tomato sale realized 66 cash. Together these simple repairs recovered 548 of
the raw 945 margin loss. Holding five rather than three wheat gave -401, so
three was sufficient in this fixed replay. The remaining -397 comprises 324
less own cash and 73 more rival cash. Our residual cash loss is 50 seed cost
plus 274 net sales revenue: 252 less wheat, 88 less carrot and 66 more tomato.
The wheat and carrot shortfall comes from the two blocked replacement cycles
on the changed tile. These numbers show that the catastrophic feed cascade
was repairable, while the crop substitution still had a real opportunity cost
in this case.

This experiment cannot establish the value of semantic switching. A fair
selection test must first require a product-level reason for each proposed
production delta, then compile the crop's entire replacement and sale plan,
reserve feed from realized inventory, and compare exact-engine continuations
from the same checkpoint. The selected case should be treated as a negative
control for that preflight, not as evidence that semantic tape matching fails.
Reproduction: `scripts/probe_inplace_repair.py` writes
`results/fresh/semantic_tapes/inplace_repair_probe.json`;
`scripts/audit_semantic_tape_direction.py` writes `direction_audit.json`.

## Directionally aligned day-15 experiment

We tested the separate checkpoint identified above: target episode 111289863,
seat 1, day 15. The visible product demands for wheat/tomato were **2/1**;
the incumbent tape 109593970 expected **3/0**. The retrieved tape 110025609
requested one more tomato planting and three fewer wheat plantings over the
next three days, although its own revealed wheat/tomato vector was 1/0. Thus
the *planting delta* follows the actual demand gap, but this is still not a
perfect tomato-demand donor.

The dated calendar matters: the donor asks for one extra tomato and one
extra carrot on day 15 while keeping the incumbent's five wheat requests;
its three fewer wheat requests occur on day 16, and its second extra carrot
on day 17. A day-15 wheat-to-tomato substitution is therefore a bounded
local alternative, not a faithful implementation of the donor calendar.

On the actual farm, five day-15 wheat plantings were verified successful.
For each, we bought one tomato seed, changed exactly that planting to tomato,
and retained the recorded worker routes, future shops and rival. All five
tomato plantings succeeded. The recorded tape later visited each tile often
enough to harvest tomato. This probe tests one feasible delta, not the
retrieved tape's entire three-day calendar. Day-15 cash was sufficient to buy
the extra seed; no successful FEED commands were lost in any variant.

| Changed planting (hour, tile) | One extra tomato sale | Sell remaining tomatoes at tape sale hours |
|---|---:|---:|
| 368, (3,7) | -803 | -514 |
| 373, (2,7) | -748 | -459 |
| 376, (1,7) | -626 | -337 |
| 378, (8,0) | -685 | **-182** |
| 381, (0,7) | -590 | -375 |

Entries are final cash-margin changes against unchanged m1 in the same fixed
world. The first sale column orders one tomato sold immediately after the
first expected harvest; it often leaves more of the new crop unsold. The
second appends a sell order after m1's existing tomato orders at each later
tomato-sale hour and once at the end. It clears all extra tomato from the
shed. In the (8,0) trial, the immediate sale did not fill, despite a tomato
harvest; the later orders did. Thus even an apparently available harvest is
not a guaranteed sale under market limits.

The best tested tile, (8,0), produced six extra tomatoes and 17 fewer wheat
over the remaining season, with no change to animal output. Its extra tomato
revenue was 434, lost wheat revenue 375, and additional seed and wheat-buy
costs 50 and 5. Our cash therefore rose **4**. The rival's cash rose **186**
under the shared market after our wheat sales fell, so margin fell **182**.
The result is much less severe than the prior unfunded splice and is a
concrete demonstration that a semantic substitution can be physically
executed and sold. It is not a profitable switch in this fixed world.

The five tile outcomes were inspected post hoc on one recorded future; the
best result is not an out-of-sample policy estimate. A live matcher also
cannot know the unrevealed shops and rival continuation used in this replay.
The useful preflight rule is to simulate through the first full tomato
harvest and displaced wheat cycles, account for sale fills and rival market
response, and decline a switch whose estimated margin gain is not positive
with an uncertainty allowance. Reproduction: `scripts/inspect_directional_case.py`
inspects candidate tile visits; `scripts/probe_directional_tomato_switch.py`
writes `results/fresh/semantic_tapes/directional_tomato_probe.json`.

We also retried the **full three-day donor calendar** through the existing
state-based job compiler. Its previous 0.6-second planning cutoff had marked
this candidate infeasible; a five-second offline allowance found a plan in
0.76 seconds. In the exact engine at the day-18 boundary, it planted three
tomatoes, two carrots and eleven wheat, versus actual m1's two tomatoes and
seventeen wheat. The compiled candidate was 2,447 own cash and 2,952 margin
below actual m1. Compiling the *incumbent* calendar with the same machinery
also lost 2,302 cash and 2,794 margin. The compiler, including its unplaced
wheat work, is therefore a major confounder.

For a diagnostic full-season graft, we ran those compiled day-15–17 actions
and then replayed recorded m1 actions. The candidate ended **11,630 margin
below** unchanged m1, versus **13,172 below** for the compiled incumbent.
Candidate output from day 15 onward was 131 fewer wheat, 26 fewer
strawberries, ten fewer milk and 18 fewer wool; the terminal herd had one
fewer cow and one fewer sheep. Our cash was 1,527 lower and the rival's
10,103 higher, mainly through the shared market. Worker positions matched at
the day-18 boundary, so the continuing loss is a production and service
continuity problem, not simply misplaced workers. Adding more tomato sell
orders did not help this full graft: no tomato remained in the shed already,
and margin worsened by 16.

The full graft does **not** refute the donor's economic plan: the compiler
did not preserve enough profitable incumbent work or later obligations.
Conversely, the bounded intact-tape edit shows the demand-aligned crop change
can be executed with a much smaller loss, but not a gain in this world.
Reproduction: `scripts/probe_directional_full_calendar.py` writes
`directional_full_calendar_probe.json`, and
`scripts/evaluate_directional_full_calendar.py` writes
`directional_full_calendar_exact.json` in the same results directory.

## Larger losing tape and wider revealed mismatch

To avoid drawing conclusions from a small mismatch in a winning game, we
ranked recorded m1 losses by the incumbent tape's revealed-demand distance.
The most extreme case found, episode 111262874 at day 21, lost 12,585 margin
with demand-history distance 52. Its unrestricted best donor scores 12.5,
but differs from the actual farm by 28 live assets (the incumbent differs by
one), requests 53 dated planting edits, and has three more missing animals.
That is a clear retrieval gap but not a reasonable direct-switch candidate.

We therefore tested a closer losing case: episode **111287532**, seat 1, day
18. Unchanged m1 lost **6,063 margin**. Its incumbent tape 110344290 has
revealed-history mismatch **26**, versus **17.5** for nearby donor 109736053.
The donor's live-asset count gap is four versus two for the incumbent, with
no additional animal shortfall and six dated planting-request edits. The
visible shop demands versus the incumbent tape are:

| Product | Actual | Incumbent | Gap |
|---|---:|---:|---:|
| Strawberry | 3 | 1 | +2 |
| Wool | 4 | 2 | +2 |
| Wheat | 3 | 5 | -2 |
| Tomato | 1 | 2 | -1 |
| Egg | 2 | 3 | -1 |

At the checkpoint, the real farm held 22 wheat crops, 16 tomatoes, 18
strawberries and 11 sheep. The donor requests one fewer wheat and three more
carrot plantings across days 18–20. The wheat change follows visible demand;
the carrot change has no visible carrot gap, and the donor does not request
more strawberry or wool production. A better aggregate shop score again
fails to identify all of the product-level work this farm needs.

We replayed each of seven verified day-18 wheat replants as PASS, CARROT or
STRAWBERRY on the same tile, preserving the rest of m1 and the rival. The
farm already held an unused strawberry seed, so strawberry trials required
no seed purchase. Added crop sales were offered at existing m1 sale hours.
The best trial changed hour 437 on tile (4,6) to strawberry. It gained
**85 final margin**: our cash rose 128 and the rival's 43. It produced two
more strawberries and seven fewer wheat and eight fewer carrots, with no
lost feeds. The baseline loss improved from 6,063 to **5,978**. A second
tile yielded +22, while the other five strawberry substitutions lost money.
Among 35 tested two- and three-tile combinations that preserved feeding,
none beat unchanged m1; the best pair was -268. The tile and combination
rankings are post hoc in this single world.

The full donor calendar failed the existing compiler with one hour of daily
route overload even under a five-second offline planning allowance. Removing
one or two of its unsupported carrot jobs did not make it feasible; removing
all three did. That reduced plan was **1,472 margin below actual m1** at the
day-21 boundary, compared with **2,399 below** for a compiled incumbent
calendar. Grafting the reduced plan onto the remainder of the recorded m1
season lost 13,421 margin, showing the same later production-continuity
problem as earlier full-calendar grafts. These compiler outcomes do not
estimate the donor's attainable value with a better executor.

At the day-18 checkpoint, this larger losing example provides one verified
beneficial semantic crop edit, but its gain is small relative to the
pre-existing loss. A deployable
matcher needs to rank actual product shortfalls and the cost of displaced
crop cycles, use available seeds, preserve animal service, and abstain when
the projected margin improvement is uncertain. Reproduction:
`scripts/audit_large_losing_tape_candidates.py`,
`scripts/inspect_large_losing_case.py`,
`scripts/probe_large_losing_local_edits.py`,
`scripts/probe_large_losing_multi_tile.py`, and
`scripts/probe_large_losing_full_calendar.py`; their JSON artifacts are in
`results/fresh/semantic_tapes/`.

## Planting after the earlier shop reveals

The day-18 edit waits until a strawberry crop has little time left to yield.
For the same losing episode, we therefore replayed planting substitutions
only after earlier **shop reveals**. At the day-12 reveal, `BRUNCH_SPOT`
raises the visible strawberry demand from the incumbent tape's one to two.
The other visible product demands match. At the day-15 reveal,
`SMOOTHIE_SHOP` raises actual strawberry demand to three versus the tape's
one; actual wheat demand is three versus the tape's four. These are visible
gaps at each decision point. The first changed planting is at hour 302 on
day 12, after that day's reveal; the day-15 seed purchase is at hour 361
and its first changed planting at hour 365.

We changed successful wheat replantings on their original tiles, kept the
recorded worker calendar, funded any extra strawberry seeds, and offered the
extra crop for sale at existing strawberry sale hours. In the exact replay,
the best one-tile day-12 edit gained **382 margin**; the best day-15 edit
gained **196**. Replacing the wheat on tile (4,5) was destructive on either
day: it interrupted animal feeding and lost more than 3,500 margin. Thus a
visible demand gap does not by itself license every compatible-looking tile.

Among 63 subsets of six individually positive day-12/day-15 sites, the best
replaced two wheat plantings on day 12 (hours 302 and 306) and two on day 15
(hours 365 and 374). It bought one extra strawberry seed on day 12 and two
on day 15. All four new plantings succeeded, the original strawberry
planting succeeded, and every day's feed count was preserved. Relative to
unchanged m1, the season produced **23 more strawberries**, **63 fewer wheat**
and **24 fewer carrots**. Strawberry sales revenue rose 3,588, while wheat
and carrot revenue fell 1,454 and 645; extra seed purchases cost 300. Our
cash rose 1,150 and the rival's rose 578, leaving a **572 margin gain**.
The loss narrowed from **6,063 to 5,491**. The day-12 pair alone gained 516;
the day-15 pair alone gained 237.

The cash change reconciles as follows. Our strawberry sales gained 3,588;
wheat sales lost 1,454 and carrot sales lost 645, for **1,489 more revenue**.
We spent 300 more on strawberry seeds and 39 more buying wheat, leaving
**1,150 more cash**. The rival sold exactly the same product quantities as
before, but market prices changed its revenue by +889 wheat, +120 carrot and
-337 strawberry. It spent 94 more buying wheat, so its cash rose **578**.
Our margin therefore improved by `1,150 - 578 = 572`.

After the shift, our final cash was **112,034** versus the rival's **117,525**.
Our total sales revenue trailed by **5,808**, while the rival spent **317**
more than us, producing the remaining **5,491 margin deficit**. The largest
product revenue deficit was strawberry: 22,174 for us against 40,191 for
the rival (**18,017 gap**), with 127 versus 238 units sold. Revenue
advantages in tomato, wheat and carrot offset much of that gap. These
cross-farm totals describe the remaining loss; they do not imply that all
of it can be fixed by further strawberry planting.

### Production, reveal and labor timeline

The shop sequence contains repeats. `FARMERS_MARKET` first appears on day 9,
giving cumulative visible strawberry demand one. `BRUNCH_SPOT` on day 12
raises it to two and `SMOOTHIE_SHOP` on day 15 to three. A second
`YARN_STORE` on day 18 raises wool demand but adds no strawberry demand.
A second `FARMERS_MARKET` on day 21 raises strawberry demand to four;
`PIZZA_SHOP` on day 24 leaves it at four. Relative to the incumbent tape,
the strawberry demand gap is +1 on day 12, +2 on days 15 and 18, and +3
on days 21 and 24.

At the day-12 reveal, the rival already had **33 strawberry tiles** and we
had **17**. Our two day-12 replacements and two day-15 replacements raised
our peak to **22 tiles** by day 16; the rival held 33. No strawberry crop
had been harvested by either farm before day 15. The first extra harvest
from the shift is on day 22, just after the second `FARMERS_MARKET` reveal.

| Days and reveal | Our strawberry harvest, original → shifted | Rival harvest | Shifted sales, us / rival |
|---|---:|---:|---:|
| 15–17, `SMOOTHIE_SHOP` | 30 → 30 | 40 | 22 / 40 |
| 18–20, second `YARN_STORE` | 35 → 35 | 64 | 38 / 64 |
| 21–23, second `FARMERS_MARKET` | 17 → 21 | 87 | 24 / 62 |
| 24–26, `PIZZA_SHOP` | 4 → 6 | 32 | 7 / 46 |
| 27–29, no new shop | 20 → 37 | 26 | 36 / 26 |
| **Season** | **106 → 129** | **249** | **127 / 238** |

All **63 fewer wheat** and **24 fewer carrots** came from the four changed
tiles: the longer-lived strawberry crops blocked later tape replants there.
The worker roster, movement and hire cost stayed fixed; hire spending was
5,900 in both replays. Successful work fell by 14 plantings, 13 waterings and
nine harvest actions as some later tape commands ceased to apply. Feed and
care actions were unchanged. Fertilizer was unchanged on every audited day:
383 successful collections, 192 successful applications, identical day-start
stocks, and identical fertilizer sales. Of those applications, **17 on the
four switched tiles** now serviced strawberries instead of the wheat/carrot
cycles that occupied those tiles in the original replay; this was a
reallocation of fertilizer rather than extra fertilizer use. The rival's
physical work and crop output were unchanged; its cash gain came from
shared-market prices.

The detailed day-by-day and four-tile traces are in
`results/fresh/semantic_tapes/reveal_aligned_strawberry_timeline.json`,
generated by `scripts/trace_reveal_aligned_strawberry_timeline.py`.

This is a fixed-world, retrospective search. The six candidate tiles were
chosen after seeing their individual outcomes, and the rival's continuation
was replayed from the recorded game. The result shows that an earlier,
reveal-triggered planting shift can outperform the late day-18 edit in this
world; it does not establish a live tile-selection rule or explain the rest
of the loss. Reproduction: `scripts/inspect_reveal_aligned_shop_gaps.py`,
`scripts/inspect_earlier_strawberry_sites.py`,
`scripts/probe_earlier_strawberry_shift.py`, and
`scripts/probe_reveal_aligned_strawberry_portfolio.py`. Their JSON artifacts
are in `results/fresh/semantic_tapes/`.

## Upkeep and future-shop decisions

The official crop rules give every crop the same survival requirement: two
consecutive unwatered days turn it into a weed. The growth and renewal costs
differ. Wheat and carrots first become harvestable after two days, mature by
days four and three respectively, and clear their tile at harvest so the
tape can replant. Tomatoes first produce after eight days and then at
one-day intervals; strawberries first produce after ten days and then at
two-day intervals. Both are ongoing crops with at most four production
ticks. Fertilizer lasts three days and doubles a production tick only when
the crop was watered; a scheduled application still costs one fertilizer
and a worker action. Strawberry seeds cost 100, versus wheat 10 and carrot
20. The four-tile shift retained the same watering and fertilizing visits,
but the long-lived crop blocked 14 later tape plantings.

**Earliest strawberry reveal.** The first strawberry-buying shop in this
episode was `FARMERS_MARKET` on day 9, so a reveal-triggered decision could
first occur then. We separately screened its six successful wheat replants
using an existing seed, preserving all daily feeds and baseline strawberry
plantings. Two substitutions gained margin (+486 and +393); four lost
(-180 to -754). Those rankings use the known recorded future and do not
establish a prospective selector. Day 12 is the first reveal at which the
incumbent tape has a *visible strawberry demand mismatch* (+1). Its best
single tile gained 382 and its best funded pair 516, again selected post
hoc. We therefore have no validated rule that makes adding strawberries
reliably profitable at either checkpoint. Reproduction:
`scripts/probe_first_strawberry_reveal.py` and
`results/fresh/semantic_tapes/first_strawberry_reveal_probe.json`.

We also held each reveal's known shops and farm state fixed and drew 48
independent remaining-shop sequences from the actual uniform shop rule.
The rival and our tape then replayed their recorded future actions. These
are price-demand stress tests of *post hoc chosen sites*, not live policy
evaluations:

| Intervention | Gain in recorded future | Mean gain across 48 new shop futures | Positive futures | 10th-percentile gain |
|---|---:|---:|---:|---:|
| Day 9, one low-displacement tile | +393 | -92 | 27/48 | -716 |
| Day 12, two funded tiles | +516 | +137 | 31/48 | -730 |
| Day 15, two funded tiles | +237 | +320 | 46/48 | +36 |

For these sites, **day 15** is the first tested reveal where uncertainty
about the remaining shops alone rarely changes the sign. Its downside
margin is thin, and site choice and rival response are still unvalidated.
Day 9 is the earliest lawful signal, day 12 the earliest incumbent-tape
mismatch, and no checkpoint has yet produced a reliable deployed planting
rule. Reproduction: `scripts/probe_conditional_shop_scenarios.py` and
`results/fresh/semantic_tapes/conditional_shop_strawberry_scenarios.json`.

**Late sheep in this case.** The day-15 shop was `SMOOTHIE_SHOP`; the second
`YARN_STORE` appeared on day 18. Our farm already had 11 sheep and no empty
pasture at either day. The existing sheep overlay declined a day-18
one-sheep addition, estimating a 2,563 loss. To check its sign, a diagnostic
variant forced one sheep after the day-18 reveal, digging a wheat tile at
(4,6) and building a pasture there. The exact replay gained 535 wool sales
and 138 fertilizer sales, but spent 500 on the sheep, 289 more on wheat feed
and 432 more on hires. Other product changes left our cash 741 lower; the
rival's rose 667 through market prices, so margin fell **1,408**. This is
one forced integration, not the best possible sheep plan. Existing broader
late-sheep screens also lost money on day-15/16 additions. Reproduction:
`scripts/probe_late_yarn_sheep_case.py` and
`results/fresh/semantic_tapes/late_yarn_sheep_case/summary.json`.

**Exact shop prior.** At days 3, 6, ..., 24 the game draws one of eight shop
types uniformly *with replacement*. Four types buy strawberry, so each
unrevealed draw contributes an expected 0.5 strawberry shop; `YARN_STORE`
has probability 1/8 and consumes wool at twice the ordinary shop rate.
For this episode, expected final strawberry-shop counts at the day-9,
day-12 and day-15 reveals were 3.5, 4.0 and 4.5; the actual final count was
four. The probability of ending with at least four was 50%, 68.75% and
87.5% respectively. The shop composition is therefore not unusual by
final strawberry-shop count, though the timing of reveals still matters.
The implemented expectancy audit also weights each unseen shop by its
remaining days of market consumption. On day 12, the four unseen shops
would drain an expected 126 strawberry units through day 29; the actual
future shops drained 144. These are market withdrawals, not farm production
targets or profit forecasts. Reproduction: `scripts/audit_exact_shop_expectancy.py`
and `results/fresh/semantic_tapes/exact_shop_expectancy.json`.

The next policy experiment should value a *specific feasible planting or
animal job* under sampled remaining-shop sequences, paired against keeping
the incumbent work. Include maturity, watering, feed, fertilizer, worker
time, displaced output, sales fills and the rival's shared-market response.
Because prices are nonlinear, applying only the mean future-demand vector
to the tape distance is insufficient. A prior direct `future_weight` term
in the tape picker lost 2,371 margin at weight 0.25 on an 80-world test;
it was not kept. The shop prior belongs in a bounded economic continuation
test at each reveal, with abstention unless the expected margin gain has a
safe lower bound.

### Strawberry sale hours and plant yields in the four-tile replay

The exact shifted replay sells strawberries on the following days. Workers
can drop harvested fruit at the shed for same-day sale; remaining inventory
is deposited there at day end, subject to shed capacity. A range gives the
first and last sale hour within that day; sales can be discontinuous inside
the range.

| Day | Our units (sale hours) | Rival units (sale hours) |
|---:|---:|---:|
| 16 | 18 (0–17) | 22 (1–21) |
| 17 | 4 (5) | 18 (13–21) |
| 18 | 24 (0–22) | 24 (20–21) |
| 19 | 0 | 13 (21–23) |
| 20 | 14 (0–21) | 27 (11–22) |
| 21 | 5 (17) | 24 (13–19) |
| 22 | 12 (17–23) | 30 (1–22) |
| 23 | 7 (9) | 8 (14) |
| 24 | 0 | 14 (0) |
| 25 | 0 | 14 (13–19) |
| 26 | 7 (21) | 18 (19) |
| 27 | 0 | 6 (20) |
| 28 | 19 (5–13) | 20 (0–21) |
| 29 | 17 (1–22) | 0 |

The first strawberry harvest for both farms is day 15 and the first sale
for both is day 16. Our four added plants first produce on days 22 and 25,
so the shift changes sales only from day 22 onward. Across days 16–20 we
sell 60 units versus the rival's 104; on days 21–25, 24 versus 90; and
on days 26–29, 43 versus 44. Total shifted sales are 127 units for 22,174
revenue against the rival's 238 units for 40,191. Our average sale price
is about 174.60 versus 168.87 for the rival: the large revenue gap is
mostly volume, not our sales being systematically cheaper. Relative to
our unshifted tape, we sell 22 more units and earn 3,588 more strawberry
revenue. The rival sells the same 238 units but earns 337 less because
the extra supply changes shared market prices.

Strawberries have **four scheduled production ticks**, starting ten days
after planting and repeating every two days. A tick makes one unit, or two
when watered and fertilized, so eight harvested units is the per-plant
maximum; four is only the maximum units the tile can *hold at once*.
In this replay, all 18 original plants and both day-12 additions get all
four ticks before the game ends. The two day-15 additions get only three
ticks (their fourth would be on day 31, after the game). Only 4 of our 22
plants reach the eight-unit maximum, versus 25 of the rival's 33. Most
of our production gap comes from fewer planted tiles and fewer doubled
fertilizer ticks, rather than missed harvests.

| Added plant | First production | Ticks before end | Produced and harvested | Maximum within game |
|---|---:|---:|---:|---:|
| Day 12, (2,3) | Day 22 | 4 | 7 | 8 |
| Day 12, (1,9) | Day 22 | 4 | 6 | 8 |
| Day 15, (4,6) | Day 25 | 3 | 5 | 6 |
| Day 15, (1,6) | Day 25 | 3 | 5 | 6 |

All 129 units generated on our strawberry tiles were harvested. Two more
potential units were prevented by the tiles' four-unit holding cap (one
on an original plant and one on a day-12 addition). Two harvested units
were discarded when the shed was full at the ends of days 26 and 27,
leaving 127 sold. The rival likewise harvested 249, lost 11 to shed
overflow, and sold 238. The four additions generated and yielded 23
units against a within-game maximum of 28. Four of the five missed units
come from production ticks following unwatered days: the (2,3) plant on
day 24, (1,9) on day 26, (4,6) on day 29, and (1,6) on day 25 each made
one instead of two. The fifth was a tile-cap loss at (1,9) on day 28:
three berries were already waiting, and a two-unit tick could add only
one before the next harvest. The two day-15 plants' fourth ticks would
occur on day 31, outside the game, so these are not part of the five-unit
within-game gap. The detailed per-sale hour, production tick and harvest trace is in
`results/fresh/semantic_tapes/strawberry_sales_and_yields.json`, generated
by `scripts/trace_strawberry_sales_and_yields.py`.

### Care and shed-capacity repair of the same four-tile switch

An exact-engine follow-up rerouted existing workers for six successful
care visits and one extra harvest. The added jobs watered (2,3) on day 23;
fertilized and watered (1,6) on day 24; fertilized (1,9) on day 24 and
watered it on day 25; harvested (1,9) on day 27 before its fourth tick;
and watered (4,6) on day 28. The two fertilizer visits matter: simply
adding water left those ticks at one unit because fertilizer was inactive.
The scheduler kept every previously successful physical job on those
days when inserting each visit. All four added plants then produced their
maximum within the game: **8, 8, 6, and 6 units**, up from 7, 6, 5, and
5. This care-only replay harvested 134 strawberries but sold only 128;
six were discarded at the shed capacity limit. Its margin improved only
115, from -5,491 to -5,376.

A capacity-aware continuation found no extra early shed delivery that
preserved the other daily jobs. It instead deferred four successful
late harvest/collection actions: two tomatoes and one fertilizer on day
26, then five wheat and two tomatoes on day 27. Some deferred output was
collected later; final output changes relative to the uncorrected switch
were +5 strawberry, -2 tomato, -5 wheat, and -1 fertilizer. All 314
recorded successful feeds were preserved, as were the other goods' output.

| Replay | Our strawberry harvest | Our strawberry sales | Our cash | Rival cash | Margin |
|---|---:|---:|---:|---:|---:|
| Original tape | 106 | 105 | 110,884 | 116,947 | -6,063 |
| Four-tile switch, unchanged care | 129 | 127 | 112,034 | 117,525 | -5,491 |
| Four-tile switch, repaired care only | 134 | 128 | 112,144 | 117,520 | -5,376 |
| Care plus capacity priority | 134 | 134 | 112,782 | 117,487 | **-4,705** |

The final continuation gains **786 margin** over the uncorrected switch,
or 1,358 over the original tape. Relative to the uncorrected switch, our
strawberry revenue rises 1,121; tomato, wheat and fertilizer revenues fall
216, 123 and 34. Our cash rises 748 and the rival's falls 38 through the
shared market. Hires, purchases and successful animal feeds are unchanged.
This is an offline, retrospectively selected repair in one recorded world
with fixed rival actions and shops. The four deferred visits were chosen
by exact full-game margin among locally feasible candidates, so the gain
is not evidence that a deployed policy could choose the same jobs from
information available at the time.

Reproduction: `scripts/probe_strawberry_care_repair.py 24`; full tick,
route, sacrifice, cash and sales records:
`results/fresh/semantic_tapes/strawberry_care_repair_fert_day24.json`.
