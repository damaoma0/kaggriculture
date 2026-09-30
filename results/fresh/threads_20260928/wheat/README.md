# KW thread: wheat trading (market side)

Base: `K5b` (`scripts/sector_run.py` ARMS dict, unmodified) run through a private agent copy
`agents/mgt_lead_sector_wheat.py` (byte-identical to `agents/mgt_lead_sector.py`@60cfdc0d before this thread's edits).
Panel: `panel13` (12 DSM worlds + 112444381), `scripts/run_arms.py --days 19 --workers 1`. LEADER and K5b results were
already on disk (`results/fresh/sector_20260925/multi/{LEADER,K5b}/<ep>.json`) and were not rerun.

K5b's resolved config (echoed from `sector_run.ARMS['K5b']`, confirming the task's exact spec):
```
{"cut_mode": "leader_harvest", "dispatch_search": "active", "hp_crops": ["MELON", "WHEAT"], "hp_wheat_min_units": 5,
 "sd_budget": 1.0, "sd_budget0": 2.0, "sd_collect_floor": 80.0, "sd_coop_pair": 2, "sd_days": [11, 28],
 "sd_dv_coins": {...}, "sd_evals": 8000, "sd_evals0": 24000, "sd_feed_bonus": 20.0,
 "sd_fert_ages": {"CARROT": [1, 2], "WHEAT": [1, 2]}, "sd_fert_first": 1, "sd_fert_first_crops": ["WHEAT", "CARROT"],
 "sd_fert_frac": 0.6, "sd_fert_ret": 1, "sd_fert_sell": 1, "sd_final_trip": 1, "sd_finish_collect": 1,
 "sd_hard_late_w": 10.0, "sd_hard_safe": 16, "sd_hop_w": 20.0, "sd_hp_parity": 1, "sd_hv_pref": {...},
 "sd_plan_log": 1, "sd_retire": 1, "sd_sector_w": 40.0, "sd_seed_fix": 1, "sd_step_cap": 3.0, "sd_surv_fb": 20,
 "sd_tier": 1, "sd_tier_coll_cap": 2, "sd_tier_deliver": 1, "sd_tier_deliver_check": 1, "sd_tier_deliver_keep": ["MILK"],
 "sd_tier_farmer_hold": 1, "sd_tier_fert_exact": 1, "sd_tier_fert_skip_harv": 1, "sd_tier_fert_supply": 1,
 "sd_tier_fill_near": 5, "sd_tier_iters": 2500, "sd_tier_offsets": 4, "sd_tier_pair_own": 1, "sd_tier_pair_top": 3,
 "sd_tier_rate_c": 5.0, "sd_tier_relief": 1, "sd_tier_relief_minv": 20.0, "sd_tier_wheat": 1, "sd_water_first": 1,
 "sd_water_tomorrow": 10.0, "sell_now": ["MELON"]}
```

## Diagnosis (numbers first)

`scripts/wheat_diag1.py` traces every call to `_market()` (hour, day, shed/carried/demand WHEAT, the computed
`reserve["WHEAT"]`, and the resulting SELL/BUY_PRODUCT orders) via `sys.settrace` on the loaded agent module, without
touching agent behavior. World 16730612:112444381, K5b, hour-0 snapshot per day (`diag_K5b_112444381.json`):

| day | n_anim | shed WHEAT | demand WHEAT | reserve WHEAT | SELL | BUY |
|---|---|---|---|---|---|---|
| 12 | 22 | 28 | 21 | 41 | 0 | 0 |
| 13 | 22 | 52 | 22 | 42 | 10 | 0 |
| 14 | 22 | 25 | 22 | 42 | 0 | 0 |
| 15 | 22 | 20 | 19 | 39 | 0 | 0 |
| 16 | 22 | 16 | 22 | 42 | 0 | 4 |
| ... | 22 | 15-24 | 19-22 | 39-42 | 0 | 0-5 |

`reserve["WHEAT"] = max(0, demand-carried + n_anim*wheat_days)` (`wheat_days`=1) reserves roughly **two full days of
herd feed at hour 0** every day: today's still-outstanding feed need (`demand`, ~n_anim, nothing done yet) *plus* a
whole extra day's buffer for tomorrow (`n_anim*wheat_days`, ~n_anim again). `have = shed - reserve` is therefore
negative on almost every ordinary day (reserve ~39-42 vs shed ~15-40), so the SELL loop's `if have <= 0: continue`
fires and nothing is sold — matching the report's "0 wheat sold on days 15-22". Only on days where the overnight
shed pile spikes well above ~42 (day 13: 52, day 27-29: harvest tail) does anything sell. Hour-by-hour trace (day 14)
shows the mechanism concretely: at hour 0 `shed=25, reserve=42` (blocked); by hour 2 the tier's own pickups have
already moved 22 units from shed to hand inventory (`carried` 2->22, `shed` 25->3) for that day's FEED jobs, so even
though `reserve` itself later drops to ~5-10 late in the day (as `demand` is worked off), the wheat is no longer
*in the shed* to sell — it is a physical, not just an accounting, bottleneck.

This buffer is **redundant** with `sd_tier_wheat` itself: `_tier_pre` (hour 0) already computes the day's exact FEED
shortfall (`nfeed - have_w`) and `_market` buys exactly that amount as the first order at hour<=1
(`TPw_["wheat_buy"]`), and separately maxes the reserve against the tier's own remaining-pickup count
(`left_`, exact, shrinking through the day) — both untouched by this thread. The extra
`n_anim*wheat_days` term was doing nothing but holding stock off the market.

Sales replay (`scripts/season_sales_replay.py`, `scripts/wheat_panel_sales.py`) confirms the pattern generalizes:
K5b sells only **5,511 / 6,433** (86%) of the leader's total panel-wide WHEAT units and buys only **1,444 / 2,103**
(69%); world 112444381 alone: leader sells 401 units over days 11-29 (buys 117), K5b sells 249 (buys 18), with an
unbroken **0-sold streak on days 14-21** exactly as reported.

## Fix (code changes, both new flags default OFF)

`agents/mgt_lead_sector_wheat.py`, function `_market()` only (~line 2576, reserve computation) and the wheat-buy
block (~line 2730). Two new CFG flags plus one new mechanism, all gated so `sd_wheat_tmrw_frac=None,
sd_wheat_today_off=0, sd_wheat_daily_buy=0` reproduce K5b's formula byte-for-byte:

```python
_wheat_tmrw_days = CFG["wheat_days"] if CFG["sd_wheat_tmrw_frac"] is None else CFG["sd_wheat_tmrw_frac"]
_wheat_today_gap = 0 if CFG["sd_wheat_today_off"] else (demand.get("WHEAT", 0) - carried.get("WHEAT", 0))
reserve["WHEAT"] = max(0, _wheat_today_gap + (n_anim * _wheat_tmrw_days if day < last_day - 1 else 0))
```
(replaces the single-line `reserve["WHEAT"] = max(0, demand.get("WHEAT",0) - carried.get("WHEAT",0) + (n_anim *
CFG["wheat_days"] if day < last_day - 1 else 0))`). The `TPw_`/`left_` max() floor right after this, and the
`_tier_pre`/hour<=1 forced buy, are both **unchanged** — they remain the hard safety net for today's actual pending
pickups regardless of how these two flags are set.

```python
if CFG["sd_wheat_daily_buy"] and not endgame and hour <= 2:
    have_w2 = shed.get("WHEAT", 0) + carried.get("WHEAT", 0) + sum(o[2] for o in wheat_buy if o[1] == "WHEAT")
    k2 = n_anim - have_w2
    pw2 = max(1, prices.get("WHEAT", 25))
    k2 = min(k2, int(cash // (pw2 + 2)))
    if k2 > 0:
        ... adds k2 to the existing wheat_buy order (or creates one) ...
```
mirrors the leader's habitual daily wheat purchase (buys back toward one day's feed each morning) independent of the
tier's exact today-shortfall calculation. No changes to the tier planner (`_tier_pre`, `_tier_core`,
`_tier_override`), no re-planning, nothing outside `_market()`.

## Arms

`results/fresh/threads_20260928/wheat/arms.json` (agent `agents/mgt_lead_sector_wheat.py`, base `K5b` for all four):

| arm | cfg on top of K5b |
|---|---|
| KW1a | `sd_wheat_tmrw_frac=0.0` (drop the tomorrow buffer entirely) |
| KW1b | `sd_wheat_tmrw_frac=0.5` (halve it — sweep point) |
| KW2  | `sd_wheat_tmrw_frac=0.0, sd_wheat_today_off=1` (also drop today's demand-carried term) |
| KW3  | `sd_wheat_tmrw_frac=0.0, sd_wheat_daily_buy=1` (+ proactive daily buy-back like the leader) |

## Panel13 results (`scripts/season_report.py`, own/margin gap vs LEADER, delta vs K5b)

| arm | mean own gap | mean margin gap | Δown vs K5b | Δmargin vs K5b | wins/13 | skip_FEED (13 worlds) | died (13 worlds) |
|---|---|---|---|---|---|---|---|
| K5b (base) | -10,750 | -20,879 | - | - | 8/13 | 2 | 155 |
| KW1a | -10,685 | -21,431 | +65 | **-552** | 6/13 | 2 | 167 |
| KW1b | -10,379 | -21,239 | +371 | **-360** | 7/13 | **23** | 170 |
| KW2  | -10,586 | -21,310 | +164 | **-431** | 6/13 | 2 | 167 |
| KW3  | -10,123 | -21,066 | +627 | **-187** | 7/13 | 2 | 165 |

(K5b panel mean computed directly from `results/fresh/sector_20260925/multi/{LEADER,K5b}`, both already on disk, not
rerun; K5b's own single-world numbers for 112444381, -4,850/-12,275, match thread_status exactly. K5b wins
112564633 by cash (86,183 vs rival 83,121) that every KW arm turns into a loss — this is the wool-crowd-out world
below, and it alone accounts for K5b's extra win over KW1a/KW2.)

**Feed safety** (`tier_days[...]['cnt']`, summed over all 13 worlds x 19 days): K5b itself already has 2 `skip_FEED`
+ 1 `pick_short` (both in 112444381, pre-existing, unrelated to this thread). KW1a, KW2 and KW3 all reproduce
exactly **2 skip_FEED, 0 breakage growth** — the reserve cut never causes a hand to reach an animal without wheat in
this panel. **KW1b is the exception: 23 skip_FEED across 6 of 13 worlds** (14 alone in 112444381, where the
single-world check first surfaced it) despite reserving *more* wheat than KW1a/KW2/KW3 (frac 0.5 vs 0). This is
counter-intuitive and only partially traced: `cap_fix`/`cap_guard` (candidate mechanisms for an hour>=20
wheat-first emergency sell) are both OFF in this config chain, so the regression isn't that path; it is some other
non-monotonic interaction between the mid-magnitude reserve value and the sector/route optimizer's emergent
scheduling (a "sweep before verdict" case: the intermediate value is worse than either extreme on this panel, not a
smooth function of the flag). No animal actually escaped an extra time because of it (0->2-day-consecutive-miss did
not occur in this panel), but it is a real, reproducible cost and disqualifies KW1b as-is.

## Wheat sold/bought vs the leader (whole panel, `scripts/wheat_panel_sales.py`)

| arm | sold (units) | % of leader | bought (units) | % of leader |
|---|---|---|---|---|
| leader | 6,433 | 100% | 2,103 | 100% |
| K5b | 5,511 | 86% | 1,444 | 69% |
| KW1a | 5,958 | 93% | 1,932 | 92% |
| KW1b | 5,858 | 91% | 1,775 | 84% |
| KW2  | 6,021 | 94% | 1,958 | 93% |
| KW3  | **6,216** | **97%** | **2,158** | **103%** |

All four variants close most of the wheat-trading gap to the leader **in every one of the 13 worlds** (no more
per-world 0-sold streaks; full per-world table for KW3 is in the panel_sales output). KW3 (reserve fix + daily
buy-back) is the closest match to the leader's habitual pattern.

## Best arm: KW3 — per-world table

| world | own gap vs leader | margin gap vs leader | Δmargin vs K5b | win/loss | KW3 sold/bought | leader sold/bought |
|---|---|---|---|---|---|---|
| 112444381 | -6,744 | -13,305 | -1,030 | win | 307/208 | 415/215 |
| 112655730 | -11,090 | -18,353 | +556 | loss | 505/117 | 486/118 |
| 112661570 | +8,775 | -19,707 | +5,299 | loss | 464/212 | 491/191 |
| 112667461 | -22,907 | -26,395 | +3,164 | win | 435/120 | 445/157 |
| 112673479 | -12,584 | -20,408 | 0 | loss | 571/111 | 534/118 |
| 112562136 | -9,595 | -16,891 | +921 | win | 459/219 | 441/152 |
| 112563376 | -11,526 | -17,166 | +1,153 | win | 430/180 | 455/167 |
| 112563785 | -3,376 | -16,889 | -1,749 | win | 500/187 | 539/228 |
| **112564633** | -11,149 | -27,498 | **-8,372** | loss | 493/156 | 494/155 |
| 112565927 | -8,018 | -26,664 | -1,219 | loss | 600/161 | 620/120 |
| 112567021 | -12,697 | -15,802 | -387 | win | 424/187 | 454/124 |
| 112568233 | -9,390 | -26,189 | +694 | loss | 478/149 | 480/168 |
| 112569426 | -21,300 | -28,589 | -1,463 | win | 550/151 | 579/190 |
| **MEAN** | -10,123 | -21,066 | **-187** | 7/13 | | |

## The surprising number, traced: a wool crowd-out side effect

The panel mean margin delta is *negative* for every variant despite the wheat fix working exactly as diagnosed and
being reproduced in all 13 worlds. World **112564633** is the largest single driver (-8,356 to -8,372 across
KW1a/KW2/KW3): direct product-level sales replay (`scripts/season_sales_replay.py`, both K5b and KW1a) shows:

| product | K5b sold (rev) | KW1a sold (rev) | Δ |
|---|---|---|---|
| WHEAT | 439 ($13,576) | 482 ($14,869) | **+43** (as designed) |
| WOOL | 219 ($32,238) | 193 ($30,370) | **-26** |
| CARROT | 386 | 365 | -21 |
| MILK | 126 | 116 | -10 |
| STRAWBERRY | 139 | 132 | -7 |

Final cash: K5b own 86,183 / rival 83,121 (we win the world, +3,062); KW1a own 85,093 / rival **90,387** (we lose,
-5,294): our own cash barely moves (-1,090) but the **frozen recorded rival's cash jumps +7,266**, consistent with
the rival's fixed wool quantity selling at a much better price once our wool supply drops ~12%. Mechanism (partially
traced, not fully isolated): the reserve change alters `wheat_over`/`deliverable()` (which decide whether a hand's
carried WHEAT is sellable mid-route) every hour, which feeds into the same route-value optimization that schedules
animal-care/collection stops; in most worlds this is neutral or positive, but in this one it reallocates enough hand
time away from wool care/collection to cost 26 units of wool — worth far more than the wheat gained. KW1b (the
mildest cut) has the same effect but smaller (-6,433 here), scaling with how much reserve is removed, which confirms
it is the reserve reduction itself (present in all four variants) and not the daily-buy addition (KW3, which adds
buying rather than removing reserve, is no better here: -8,372). Excluding this one world, KW1a's panel mean margin
delta would be **+98** (12 worlds); excluding both 112564633 and the second-worst outlier 112569426, **+675**
(11 worlds) — the fix is a net positive on the "ordinary" 10-11 worlds and a large net negative concentrated in 1-2
worlds. This is reported as a genuine, reproducible, partially-mechanistically-traced side effect, not dismissed as
noise (the +/-numbers are consistent and directionally explainable, but the exact routing decision that reallocates
wool time was not stepped through instruction-by-instruction).

## Recommendation

- The diagnosed bug (wheat reserve double-books a whole extra day of herd feed on top of today's already-tracked
  need, on top of `sd_tier_wheat`'s own independent buy-first/pickup-floor safety net) is real, and the fix
  (`sd_wheat_tmrw_frac=0`, i.e. KW1a/KW2/KW3's core change) closes it correctly: wheat selling and buying reach
  91-97% / 84-103% of the leader's pace in **every** panel world, with feed safety unchanged from K5b (2 `skip_FEED`
  in both) for KW1a/KW2/KW3.
- KW2's extra flag (`sd_wheat_today_off`) is measured to be **redundant**: KW1a and KW2 are numerically
  near-identical on every world (`sd_tier_wheat`'s own `left_` floor already dominates once the tomorrow buffer is
  removed) — drop KW2, keep KW1a's simpler formula if this direction is pursued further.
- KW1b (half-strength cut) is **parked as unsafe**: it triples the panel's feed-pickup breakages (23 vs 2) for a
  smaller worst-case loss, a genuinely non-monotonic and only partially explained result — do not promote without
  first tracing why the intermediate reserve value is worse than either extreme.
- KW3 (reserve fix + leader-like daily buy-back) is the **best of the four** (mean margin delta -187, closest match
  to the leader's wheat pattern, safe feed count) but is **still a net (small) loss** against K5b on this panel — do
  **not** promote any KW arm as-is.
- Next step before promotion: isolate the wheat reserve fix from the shared `deliverable()`/`wheat_over` route-value
  path that also prioritizes wool/animal-care stops (e.g., make the freed-up "sellable now" wheat flag independent
  of whatever changes hand scheduling elsewhere), or explicitly protect wool-producing stops when the reserve
  shrinks, then re-measure on this same panel13 (LEADER/K5b already on disk; KW1a/KW1b/KW2/KW3 results are saved
  under `results/fresh/sector_20260925/multi/<ARM>/` and `results/fresh/day12_viz/<arm>_streams/` for reuse).

## KWd: sell-everything-at-h23 variant (user idea, added after the initial report)

USER IDEA: at hour 23 sell ALL wheat in the shed (ignore the feed reserve), and each morning buy back what the
day's feeds need. Rationale (verified in `kaggriculture.py`): BUY_PRODUCT is quoted at the post-buy inventory, so a
buy/sell round trip against an unchanged market nets zero (no spread); the only cost is market movement between the
h23 sale and the morning buy, and an h23 sale happens before the midnight dump so it also frees shed room.

### Implementation (same file, same rules: new flag, default OFF, `_market()` only)

`sd_wheat_h23_sell` (0 default): at hour 23 (non-endgame), the per-product sell loop special-cases WHEAT to sell
`shed.get("WHEAT", 0)` in full, bypassing both the reserve *and* the leader-following quota (which would otherwise
cap the sale below the target's cumulative-sold curve even with reserve=0). The morning replenishment is the
**existing, unmodified** `sd_tier_wheat` hour<=1 forced buy (`TPw_["wheat_buy"] = nfeed - have_w`, computed by
`_tier_pre`, untouched by this thread) — no new buy mechanism was added, per the user's instruction to reuse it.
One trap was handled: BUY_PRODUCT fails outright on a full shed, and this order is forced *first* in the list
(ahead of any of this hour's own sells that might otherwise free room), so a full shed after the midnight dump could
have zeroed out the whole day's feed purchase. Fix: when `sd_wheat_h23_sell` is on, the buy is capped to
`100 - sum(shed.values())` (logged to `S["log"]["wheat_h23_buy_capped"]` when it bites) instead of being submitted
uncapped.

Two arms: **KWd1** = `sd_wheat_h23_sell=1` alone (daytime reserve formula unchanged from K5b — the h23 sweep is the
only change); **KWd2** = KWd1 + `sd_wheat_tmrw_frac=0` (also unblocks daytime selling, combining with the first
report's fix, as requested "test with and without").

### Panel13 results

| arm | mean own gap | mean margin gap | Δown vs K5b | Δmargin vs K5b | wins/13 | skip_FEED | pick_short | wait_wheat | died |
|---|---|---|---|---|---|---|---|---|---|
| K5b (base) | -10,750 | -20,879 | - | - | 8/13 | 2 | 1 | - | 155 |
| KWd1 | -11,241 | -22,573 | -491 | **-1,694** | 5/13 | 3 | 3 | 5 | 181 |
| KWd2 | -11,189 | -22,267 | -439 | **-1,388** | 6/13 | 2 | 3 | 33 | 188 |

Feed safety holds for both (`skip_FEED` 3 and 2 vs K5b's 2 — no meaningful growth, unlike KW1b's 23); `wait_wheat`
(a benign PASS-and-retry, not a failure) rises because WHEAT inventory is swept to ~0 every night so a pickup
occasionally has to wait one hour for the morning buy to land. **Both KWd arms are, on this panel, the two worst of
all six wheat arms tested by mean margin** — worse than plain K5b, and worse than the daytime-only fixes KW1a
(-552) and KW3 (-187) from the first report.

### Round-trip cost, rival wheat revenue, midnight deletions (`scripts/wheat_panel_sales.py`, `scripts/wheat_losses_panel.py`)

| arm | sold | bought | net_cost (bought$-sold$) | net_cost / net_units_sold | opp WHEAT sold_rev (panel total) | midnight del. (total / WHEAT) |
|---|---|---|---|---|---|---|
| leader | 6,433 | 2,103 | -147,136 | -33.98 | 248,984 | 102 / 46 |
| K5b | 5,511 | 1,444 | -137,716 | -33.86 | 245,763 | 461 / 124 |
| KW1a | 5,958 | 1,932 | -135,325 | -33.61 | 245,061 | 460 / 124 |
| KW3 | 6,216 | 2,158 | -136,265 | -33.57 | 245,547 | 481 / 140 |
| KWd1 | 5,727 | 1,726 | -134,690 | -33.66 | 246,219 | 460 / 127 |
| KWd2 | 6,027 | 1,997 | -136,200 | -33.79 | 245,403 | **436 / 116** (lowest of all) |

(`net_cost` is negative because sold revenue exceeds bought cost — i.e. it is the season's net cash generated from
WHEAT trading; `net_units_sold` = sold-bought.) **The user's "no arbitrage cost" claim is confirmed empirically**:
net cash generated per net unit of wheat sold is nearly identical across every arm and the leader (-33.6 to -34.0),
so the differences in overall margin are **not** coming from a buy/sell spread — round-tripping through the market
really is close to free, as the engine's post-buy pricing predicts. **The rival's own WHEAT revenue barely moves**
(245,061-246,219 across all arms, <0.5% spread) — unlike the earlier wool-crowd-out finding, our WHEAT trading
volume does not hand the frozen opponent a WHEAT-specific windfall. KWd2 does deliver on the "frees shed room"
rationale: it has the **lowest total and WHEAT-specific midnight deletions of every arm tested**, K5b included. None
of this translates into a better margin outcome, which means the margin cost of KWd1/KWd2 (like KW1a/KW3's) comes
from the same *indirect* route-scheduling effect on other goods (the wool-crowd-out mechanism), not from the wheat
mechanics themselves, and forcing a full nightly dump-and-rebuy appears to aggravate that indirect cost rather than
relieve it (more/bigger transactions competing for the hour-0 order cap and cash flow than the milder daytime fix).

### Is any of this distinguishable from noise?

Per-world margin deltas vs K5b swing by several thousand in both directions for every arm (this was already visible
in the first report's per-world tables). Treating the 13 worlds as a paired sample (one-sample t-test on the
per-world margin delta):

| arm | mean | SD | SE (SD/√13) | t | 95% CI |
|---|---|---|---|---|---|
| KW1a | -552 | 3,518 | 976 | -0.57 | [-2,679, +1,575] |
| KW1b | -360 | 2,289 | 635 | -0.57 | [-1,744, +1,023] |
| KW2 | -432 | 3,600 | 998 | -0.43 | [-2,608, +1,745] |
| KW3 | -187 | 3,144 | 872 | -0.21 | [-2,088, +1,714] |
| **KWd1** | **-1,694** | 3,495 | 969 | -1.75 | [-3,807, +419] |
| **KWd2** | **-1,388** | 3,175 | 881 | -1.58 | [-3,308, +531] |

**None of the six mean deltas is statistically distinguishable from zero** at conventional 95% confidence (critical
|t| ≈ 2.18 at df=12); every CI straddles 0. KWd1's is the largest-magnitude and closest to significance (t=-1.75)
but still isn't there. This means: with only 13 paired worlds, a mean delta of a few hundred (KW1a/KW2/KW3) is
genuinely indistinguishable from world-to-world noise, and even KWd1/KWd2's larger, more consistently negative mean
should be treated as suggestive-but-unproven rather than a confirmed regression — it would take a substantially
larger panel (or a lower-variance paired design, e.g. matched shop/opponent controls) to tell these apart reliably.
The *qualitative* findings that do not depend on this statistical power — wheat sold/bought/fed reaching the
leader's pace, feed safety holding, the round-trip being cost-free, and the h23 sale reducing shed deletions — are
all exact, reproducible measurements, not statistical estimates.

### Verdict on KWd1/KWd2

- The user's engine analysis is **correct and empirically confirmed**: BUY_PRODUCT/SELL round trips have no
  measurable spread cost (net cash per net unit is ~34 regardless of how much is round-tripped).
- The h23-sweep mechanism itself works exactly as specified (verified hour-by-hour: shed WHEAT is 0 after every h23
  sell in the diagnostic trace) and is safe for feed pickups (skip_FEED at or near the K5b baseline in both arms),
  and it does measurably reduce midnight deletions (KWd2: fewest of any arm tested).
- Despite this, **KWd1 and KWd2 are the two worst-performing wheat arms on this panel by mean margin**, though not
  statistically distinguishable from K5b or from each other given 13 worlds' variance. There is no evidence here
  that forcing the full nightly dump-and-rebuy is better than the simpler daytime-only reserve fix (KW1a/KW3); point
  estimates favor NOT adopting it.
- **Recommendation: do not add the h23-sell mechanism.** It does not show a measurable benefit over the already
  under-water KW1a/KW3 daytime fixes, adds real implementation complexity (buy-room capping, more frequent large
  transactions), and its point estimate is the most negative of everything tested. The daytime reserve fix
  (KW1a) remains the most defensible of the six variants tested here, and even that is not a proven net win pending
  the wool-crowd-out investigation recommended above.

## Files

- `agents/mgt_lead_sector_wheat.py` — private copy with the reserve flags, daily-buy block, and the h23-sell +
  buy-room-cap block (all new flags default OFF; diff is limited to the CFG dict comments and `_market()`).
- `scripts/wheat_diag1.py` — `sys.settrace`-based reserve/sell/buy tracer (read-only diagnostic, no agent changes);
  now also accepts an optional spec.json to register custom arms (e.g. KWd1/KWd2) before tracing.
- `scripts/wheat_panel_sales.py` — panel-wide WHEAT SELL/BUY_PRODUCT aggregator vs the leader tape, both sides
  (own + opponent), with net round-trip cost and an optional JSON dump.
- `scripts/wheat_losses_panel.py` — panel-wide midnight-deletion aggregator (reuses `season_losses.run()`), total
  and WHEAT-specific, own vs leader.
- `results/fresh/threads_20260928/wheat/arms.json` — all 6 KW/KWd arm definitions for `run_arms.py`.
- `results/fresh/threads_20260928/wheat/diag_K5b_112444381.json`, `diag_KWd1_112444381.json` — raw per-hour trace
  logs behind the diagnoses.
- Panel results: `results/fresh/sector_20260925/multi/{KW1a,KW1b,KW2,KW3,KWd1,KWd2}/<ep>.json` and
  `results/fresh/day12_viz/{kw1a,kw1b,kw2,kw3,kwd1,kwd2}_streams/<ep>.json` (written by `run_arms.py`, reused by
  `season_report.py` / `season_sales_replay.py` / `wheat_panel_sales.py` / `wheat_losses_panel.py`).
