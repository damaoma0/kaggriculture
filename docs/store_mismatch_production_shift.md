# Store mismatches and production-shift evidence

The active `mgt_m1` tape disagreed with the newly revealed store in **383 slots across all 89 audited losses** (247 slots in the 58 losses against opponents below 2500). **All 56 directed store pairs occur.** Each slot uses the tape selected by the router *at that reveal*. This corrects the earlier final-donor comparison, which included earlier days when another tape was active. No losing game had only one mismatch, so a pair cannot be assigned its own share of a loss.

A store changes town demand by 6 units/day for each listed product, or 12 for the single-product Yarn Store and Pet Cafe. These are exact market drains from its reveal through day 29. **They are not production targets.** Opponent supply, existing farm cohorts, delay to new output, feed, labor, and the nonlinear price response set the economically useful shift.

I screened all 52 mixed-sign pairs by converting up to 0, 1, 2, 4, 6, 8 or 12 units/day of a planned sale of a lower-demand product into an equal planned sale of a higher-demand product, at the same market hour. The official engine repriced both farms and executed the remaining recorded actions. This is a deliberately generous **zero-cost sale-mix scenario**: it gives the farm the replacement good without planting, animal purchase, feed, maintenance, labor or lead time. The displayed amount is the best *requested* q/day on these losing games; actual converted units can be lower if source stock is unavailable. It must not be read as an optimal physical production shift or a bound on all other possible plans. Four pairs change only one product and have no one-for-one conversion.

## Full directed-pair screen

| Active tape → actual store | Events (<2500) | Δ town demand/day | Best free conversion, requested/day (season units) | Median margin Δ | Leave-one-game-out median / positive |
|---|---:|---|---|---:|---:|
| Pizza → Yarn | 15 (10) | Mlk -6, Tom -6, Wht -6, Wol +12 | Wht→Wol 8/d (90) | +9,364 | +7,798 / 13/15 |
| Ice cream → Yarn | 13 (9) | Mlk -6, Str -6, Wht -6, Wol +12 | Wht→Wol 12/d (115) | +15,277 | +15,277 / 13/13 |
| Pizza → Ice cream | 13 (7) | Str +6, Tom -6 | Tom→Str 8/d (40) | +2,450 | +2,450 / 8/13 |
| Smoothie → Yarn | 13 (9) | Mlk -6, Str -6, Wol +12 | Mlk→Wol 8/d (77) | +8,803 | +8,587 / 11/13 |
| Ice cream → Smoothie | 12 (7) | Wht -6 | — | — | — |
| Yarn → Smoothie | 12 (7) | Mlk +6, Str +6, Wol -12 | Wol→Str 4/d (36) | +1,194 | +601 / 7/12 |
| Bakery → Ice cream | 11 (8) | Egg -6, Mlk +6, Str +6 | Egg→Mlk 8/d (61) | +3,208 | +1,477 / 8/11 |
| Brunch → Smoothie | 11 (4) | Egg -6, Mlk +6, Wht -6 | Wht→Mlk 6/d (70) | +4,156 | +4,156 / 9/11 |
| Brunch → Yarn | 11 (8) | Egg -6, Str -6, Wht -6, Wol +12 | Wht→Wol 12/d (98) | +11,396 | +11,396 / 11/11 |
| Smoothie → Ice cream | 11 (10) | Wht +6 | — | — | — |
| Brunch → Bakery | 10 (7) | Str -6 | — | — | — |
| Pet cafe → Yarn | 10 (5) | Car -12, Wol +12 | Car→Wol 12/d (67.5) | +8,488 | +8,488 / 10/10 |
| Pizza → Pet cafe | 10 (6) | Car +12, Mlk -6, Tom -6, Wht -6 | Wht→Car 12/d (111.5) | +696 | +696 / 6/10 |
| Farmers market → Yarn | 9 (6) | Car -6, Str -6, Tom -6, Wht -6, Wol +12 | Wht→Wol 12/d (91) | +10,573 | +10,573 / 9/9 |
| Pizza → Brunch | 9 (7) | Egg +6, Mlk -6, Str +6, Tom -6 | Tom→Str 6/d (40) | +2,032 | -1,739 / 4/9 |
| Bakery → Brunch | 8 (6) | Str +6 | — | — | — |
| Bakery → Pizza | 8 (5) | Egg -6, Mlk +6, Tom +6 | Egg→Mlk 8/d (63) | +1,966 | +1,309 / 7/8 |
| Farmers market → Smoothie | 8 (6) | Car -6, Mlk +6, Tom -6, Wht -6 | Wht→Mlk 6/d (46) | +1,850 | +1,118 / 6/8 |
| Bakery → Pet cafe | 7 (2) | Car +12, Egg -6, Wht -6 | Wht→Car 8/d (119) | +522 | +325 / 5/7 |
| Bakery → Yarn | 7 (6) | Egg -6, Wht -6, Wol +12 | Wht→Wol 8/d (107) | +13,831 | +12,687 / 7/7 |
| Brunch → Pizza | 7 (1) | Egg -6, Mlk +6, Str -6, Tom +6 | Egg→Mlk 4/d (38) | +1,822 | +666 / 4/7 |
| Farmers market → Bakery | 7 (5) | Car -6, Egg +6, Str -6, Tom -6 | Car→Egg 12/d (24) | +469 | +469 / 7/7 |
| Farmers market → Brunch | 7 (6) | Car -6, Egg +6, Tom -6 | Car→Egg 12/d (56) | +191 | +191 / 6/7 |
| Farmers market → Pizza | 7 (5) | Car -6, Mlk +6, Str -6 | Car→Mlk 12/d (28) | +2,771 | +2,771 / 6/7 |
| Ice cream → Pet cafe | 7 (5) | Car +12, Mlk -6, Str -6, Wht -6 | Wht→Car 12/d (72) | +1,696 | +1,696 / 7/7 |
| Ice cream → Pizza | 7 (4) | Str -6, Tom +6 | Str→Tom 2/d (24) | +308 | +308 / 4/7 |
| Pet cafe → Pizza | 7 (4) | Car -12, Mlk +6, Tom +6, Wht +6 | Car→Tom 12/d (64) | +531 | -1,034 / 2/7 |
| Pizza → Farmers market | 7 (3) | Car +6, Mlk -6, Str +6 | Mlk→Str 4/d (56) | +3,965 | +1,450 / 5/7 |
| Yarn → Farmers market | 7 (4) | Car +6, Str +6, Tom +6, Wht +6, Wol -12 | 0/d (no gain) | +0 | -4,504 / 0/7 |
| Bakery → Smoothie | 6 (4) | Egg -6, Mlk +6, Str +6, Wht -6 | Wht→Str 12/d (102.5) | +5,621 | +5,621 / 5/6 |
| Farmers market → Ice cream | 6 (5) | Car -6, Mlk +6, Tom -6 | Car→Mlk 8/d (51.5) | +5,428 | +5,428 / 5/6 |
| Ice cream → Farmers market | 6 (4) | Car +6, Mlk -6, Tom +6 | Mlk→Tom 2/d (22) | +136 | -2 / 0/6 |
| Pet cafe → Brunch | 6 (4) | Car -12, Egg +6, Str +6, Wht +6 | Car→Str 4/d (26) | +742 | -468 / 3/6 |
| Pet cafe → Ice cream | 6 (4) | Car -12, Mlk +6, Str +6, Wht +6 | Car→Str 12/d (70) | +6,307 | +2,136 / 4/6 |
| Pizza → Bakery | 6 (6) | Egg +6, Mlk -6, Tom -6 | 0/d (no gain) | +0 | +0 / 0/6 |
| Bakery → Farmers market | 5 (4) | Car +6, Egg -6, Str +6, Tom +6 | Egg→Str 6/d (14) | +1,556 | +1,462 / 3/5 |
| Brunch → Ice cream | 5 (4) | Egg -6, Mlk +6 | Egg→Mlk 4/d (34) | +2,622 | +2,622 / 4/5 |
| Pet cafe → Bakery | 5 (4) | Car -12, Egg +6, Wht +6 | 0/d (no gain) | +0 | -255 / 0/5 |
| Pizza → Smoothie | 5 (4) | Str +6, Tom -6, Wht -6 | Wht→Str 6/d (36) | +1,545 | +1,536 / 3/5 |
| Smoothie → Brunch | 5 (2) | Egg +6, Mlk -6, Wht +6 | 0/d (no gain) | +0 | +0 / 0/5 |
| Smoothie → Pizza | 5 (4) | Str -6, Tom +6, Wht +6 | Str→Tom 12/d (101) | +1,478 | +1,180 / 3/5 |
| Yarn → Bakery | 5 (3) | Egg +6, Wht +6, Wol -12 | 0/d (no gain) | +0 | -296 / 0/5 |
| Ice cream → Brunch | 4 (2) | Egg +6, Mlk -6 | 0/d (no gain) | +0 | +0 / 0/4 |
| Pet cafe → Farmers market | 4 (2) | Car -6, Str +6, Tom +6, Wht +6 | Car→Str 4/d (13.5) | +280 | -260 / 1/4 |
| Smoothie → Farmers market | 4 (2) | Car +6, Mlk -6, Tom +6, Wht +6 | 0/d (no gain) | +0 | -2,601 / 0/4 |
| Yarn → Brunch | 4 (3) | Egg +6, Str +6, Wht +6, Wol -12 | 0/d (no gain) | +0 | +0 / 0/4 |
| Yarn → Pet cafe | 4 (2) | Car +12, Wol -12 | 0/d (no gain) | +0 | +0 / 0/4 |
| Brunch → Farmers market | 3 (1) | Car +6, Egg -6, Tom +6 | Egg→Tom 12/d (30) | +470 | +470 / 3/3 |
| Brunch → Pet cafe | 3 (1) | Car +12, Egg -6, Str -6, Wht -6 | Wht→Car 12/d (101) | +976 | +976 / 3/3 |
| Smoothie → Pet cafe | 3 (1) | Car +12, Mlk -6, Str -6 | 0/d (no gain) | +0 | +0 / 0/3 |
| Yarn → Ice cream | 3 (2) | Mlk +6, Str +6, Wht +6, Wol -12 | Wol→Str 6/d (66) | +7,421 | +7,421 / 3/3 |
| Yarn → Pizza | 3 (2) | Mlk +6, Tom +6, Wht +6, Wol -12 | 0/d (no gain) | +0 | +0 / 0/3 |
| Farmers market → Pet cafe | 2 (1) | Car +6, Str -6, Tom -6, Wht -6 | Wht→Car 8/d (45.5) | +120 | +68 / 1/2 |
| Pet cafe → Smoothie | 2 (2) | Car -12, Mlk +6, Str +6 | Car→Mlk 6/d (21.5) | +686 | -723 / 1/2 |
| Ice cream → Bakery | 1 (1) | Egg +6, Mlk -6, Str -6 | 0/d (no gain) | +0 | — |
| Smoothie → Bakery | 1 (1) | Egg +6, Mlk -6, Str -6, Wht +6 | 0/d (no gain) | +0 | — |

`Δ` is actual minus tape store. Positive means more town drain, negative less. The parenthesized unit count is the median actually converted from that reveal through season end; source stock can limit it below the requested rate. Margin changes are coins relative to unchanged replay, with both farms repriced; they are not recoverable profit estimates. The free-conversion arm and its q were chosen on the same games, so its displayed median is optimistic. Leave-one-game-out selection is a stricter stability check, but several pairs have only 1–3 cases, the cohort contains only losses, and events from one game share their future market. Full per-case and per-q curves are in `results/fresh/store_mismatch_shift_20260923/conversion/`; product addition/discard screens, which proved too unconstrained to select production amounts, are in `headroom_active/`.

## Feasible, small change tested in a complete game

The registered tape 109740300 milk-to-wool care edit was evaluated over all eight subsets of its three eligible days (17, 19, 21), with the live m1 agent and recorded opponent replayed for the full season. In the discovery case, **day 17 alone was best among these eight**: +1 wool, −1 milk harvested; our cash +229, opponent cash −8, competitive margin **+237**. The prior three-day edit gave only +88 margin. Day 19 or 21 alone removed one milk but produced no extra wool and raised opponent cash, so the exact engine rejected those added edits. This is a finite local optimum for one route and one world, not a general optimum or a validated policy. The baseline source and earlier before/after full replays are unchanged. The [new back-to-back replay](../viz/tape-109740300-before-after-d17.html) shows the day-17-only change against the same original baseline.

The day-17-only source and result are registered as a **diagnostic-only** candidate in `data/tape_variants/109740300-milk-care-to-wool-d17-diagnostic.json`. The next production test should construct similarly small, physically feasible route/cohort edits for the recurring strawberry↔tomato, wheat↔carrot, and egg/milk/wool mismatches. A shift should advance only if it improves full-game competitive margin across held-out worlds including wins. No broad routing or production policy was promoted from this screen.

Reproduce: `scripts/audit_store_mismatch_pairs.py`, `scripts/screen_store_shift_headroom.py`, `scripts/screen_store_conversion.py`, `scripts/optimize_tape_care_grid.py`, `scripts/build_care_d17_replays.py`, then `scripts/report_store_conversion.py`. Check with `scripts/check_store_mismatch_shift.py` and `scripts/check_care_d17_replays.cjs`. The exact pair/event rows and all product prices are in `active_store_pairs.json`; the source for the eight-arm care test is in `care_grid/`.
