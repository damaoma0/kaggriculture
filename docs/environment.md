# Environment notes

Source: competition Overview page, read 2026-09-06. Authoritative code is `kaggriculture.py` inside
the `kaggle-environments` package (`pip install -U kaggle-environments`). Built-in agents: "pass",
"random", "starter".

## Game shape
- 2 players, separate farms, shared market and town. Winner = most money in bank after 720 turns
  (24 turns/day x 30 days). Unsold inventory counts for nothing. Ties possible.
- Start: 3000 coins, one 5x5 quadrant (NW) of a 10x10 board unlocked. Farmer starts at (4,4).
- Rating: Elo-style on win/loss/tie only; margin irrelevant. Final leaderboard via Bradley-Terry
  over ~2 weeks of games after the 2026-09-30 deadline.
- Submissions: 5/day, latest 2 active. Files land in /kaggle_simulations/agent/. `main.py` at root
  with `agent(obs)` (single arg in the docs' examples). 100 MiB max, 6.5 GiB RAM, 1.6 vCPU.
  Validation episode = self-play; failures give downloadable logs.

## Turn structure
Each turn each unit (farmer + each hired hand) gets one action, plus up to 10 market orders
(`maxMarketOrdersPerTurn`, extras silently dropped). Both players act simultaneously.

Processing order per turn: validate -> unit actions -> market orders (one unit at a time,
interleaved between players) -> town consumption -> observations -> day refresh (if day boundary)
-> market price refresh -> income update -> farm update.

## Action format
```
{"farmer": ["PLANT", "WHEAT"], "hands": [["WATER"], ...], "market": [["BUY_SEED", "WHEAT", 1], ...]}
```
Unit actions: NORTH SOUTH EAST WEST | PICKUP item [n] | DROP | PLACE item [n] | PLANT crop |
WATER | HARVEST | FERTILIZE | FEED | CARE | COLLECT_FERTILIZER | BUILD_COOP | BUILD_PASTURE | DIG | PASS

Market orders: BUY_SEED crop n | BUY_ANIMAL animal n | BUY_PRODUCT (WHEAT|FERTILIZER) n |
SELL item n | HIRE | BUY_LAND

Notes:
- Moves off-board are no-ops. Locked tiles are passable but tile actions on them no-op.
- Shed is at board center, not a tile. "Adjacent" = standing on (4,4),(5,4),(4,5),(5,5). Only (4,4)
  is unlocked at start; shed actions still work from locked adjacent tiles.
- Seeds live in a separate slot, auto-available to every unit; PLANT consumes directly. If more
  PLANT orders than seeds in one turn, none are planted.
- WATER/FEED/CARE once per day; repeats are no-ops.
- Shed capacity 100 non-seed items; overflow discarded (at PLACE/DROP and at end-of-day auto-drop).
- Farmer + hands spawn at shed each day; all unit inventories dump to shed at end of day.
- Hands: HIRE cost = fib(n) for n hires already today (1,1,2,3,5,8,13...). Hands vanish at day end.
  First hire spawns at (5,4) (locked until NE bought); it can walk back.
- BUY_LAND: 1000, 2000, 4000 for 2nd/3rd/4th quadrant.
- DIG clears plant/weed/empty structure; no-op on occupied coop/pasture.
- Weeds spawn on empty unlocked tiles with p=0.005 per tile per day.

## Crops and animals
| Item | Seed | Base price | First yield | Max yield age | Subsequent | Max yield | Yield/tile/day |
|---|---|---|---|---|---|---|---|
| Wheat | 10 | 25 | day 2 | day 4 | none | 6 (4 unfert.) | 0.80 |
| Carrot | 20 | 35 | day 2 | day 3 | none | 4 (3 unfert.) | 0.75 |
| Tomato | 50 | 60 | day 8 | day 11 | daily x4 (ages 8-11) | 4 | 0.33 |
| Strawberry | 100 | 120 | day 10 | day 16 | every other day x4 (10,12,14,16) | 4 | 0.24 |
| Melon | 80 | 250 | day 10 | day 10 | none | 6 | 0.55 |
| Goose/Egg | 300 | 50 | day 4 | - | daily, forever | 4 held | 1.00 |
| Cow/Milk | 400 | 160 | day 8 | - | every 2 days | 6 held | 0.50 |
| Sheep/Wool | 500 | 200 | day 6 | - | every 3 days | 6 held | 0.33 |
| Fertilizer | 100 | 100 | - | - | - | - | - |

Animals need a coop (goose) or pasture (cow/sheep) built first: BUY_ANIMAL -> PICKUP from shed ->
walk to structure -> PLACE.

Care rules:
- Plants: water daily. New seed starts consecutive_unwatered=1, so it must be watered the day it is
  planted or it becomes a weed that night. 2 consecutive unwatered days -> weed.
- Animals: FEED daily with wheat (from inventory). New animal starts consecutive_unfed=0. 2
  consecutive unfed days -> animal escapes, lost.
- One-time crops: from ceil(max_yield_day/2), each watered day adds +1 yield (+2 if fertilized).
  Wheat/carrot only hit listed max with fertilizer.
- Ongoing crops: 1 unit per scheduled production, 2 if fertilized AND watered that day.
- FERTILIZE: doubles daily bonus for 3 days, only on watered days.
- Decay: one day after max lifespan (one-time) or after 4th scheduled production (ongoing), yield
  drops by 1 every other turn until 0 -> weed. Harvest promptly.
- CARE: if fed AND cared that day, bank +1; paid out on next production if fed that day. Unfed on
  production day -> base 1 only, bank resets.
- COLLECT_FERTILIZER: every surviving animal offers 1 fertilizer/day; it does not accumulate.

## Market
- Seeds and animals: unlimited, fixed prices. Products: dynamic sell price, persists across days.
- Only WHEAT and FERTILIZER can be bought back (BUY_PRODUCT). Everything can be sold.
- Orders resolved one unit at a time, interleaved across players. Buy price quoted post-buy,
  sell price pre-sell. Price floor $1 (at floor, sold units are not added to inventory).
- Town center consumes 1 of every product (not fertilizer) every 24 turns, flat all season.
- Shops unlock every 3 days, random with replacement, max 8 instances. Each consumes 1 of each
  demanded product every 4 turns (single-product shops consume 2x). Visible in obs["town"]["unlocked_shops"].

| Shop | Demands |
|---|---|
| Bakery | eggs, wheat |
| Pizza Shop | milk, tomatoes, wheat |
| Brunch Spot | eggs, wheat, strawberries |
| Yarn Store | wool (2x) |
| Ice Cream Shop | strawberries, milk, wheat |
| Pet Cafe | carrots (2x) |
| Smoothie Shop | strawberries, milk |
| Farmers Market | wheat, carrots, tomatoes, strawberries |

Price function: price(inv) = base + sign*amp*f(|inv - I0|), I0 = 10000, amp = target*base/f(T),
floored at $1, rounded. hinge(u=x/T) = u + 8*max(0,u-1)^2.

| Resource | Base | T | Below f/target | Above f/target | P(I0-T) | P(I0+T) | P(I0+2T) |
|---|---|---|---|---|---|---|---|
| Wheat | 25 | 400 | sqrt 0.80 | log 0.20 | 45 | 20 | 19 |
| Carrot | 35 | 450 | hinge 1.00 | sqrt 0.70 | 70 | 10 | 1 |
| Tomato | 60 | 200 | hinge 0.40 | sqrt 0.60 | 84 | 24 | 9 |
| Strawberry | 120 | 100 | sqrt 0.70 | linear 1.60 | 204 | 1 | 1 |
| Melon | 250 | 300 | log 0.20 | sq 3.60 | 300 | 1 | 1 |
| Egg | 50 | 332 | hinge 0.40 | log 0.20 | 70 | 40 | 39 |
| Milk | 160 | 122 | sqrt 0.60 | linear 1.60 | 256 | 1 | 1 |
| Wool | 200 | 105 | log 0.20 | sq 3.20 | 240 | 1 | 1 |
| Fertilizer | 100 | 200 | linear 0.40 | linear 0.40 | 140 | 60 | 20 |

Key: premium goods (strawberry, melon, milk, wool) crash to $1 on gluts of about T units. Wheat and
egg absorb gluts well. Both players share the market, so opponent dumping hurts you.

## Observation schema
```
{
  "player": int, "day": int, "hour": int,          # "step" also used by quick start example
  "farms": [farm, farm],                            # public, both visible
  "market": {"inventory": {...}, "prices": {...}},
  "town": {"unlocked_shops": [...]},
  "private": {"shed": {...}, "seeds": {...}, "inventories": [farmer_inv, hand_inv, ...]}
}
farm = {"money": float, "tiles": [[tile]], "farmer": [x,y], "hands": [[x,y]],
        "unlocked_quadrants": [...], "hires_today": int}
tile = None | "LOCKED" | {"kind":"WEED"}
     | {"kind":"PLANT","crop","planted_day","watered_today","consecutive_unwatered",
        "yield_units","max_lifespan_step","fertilized_until_day"}
     | {"kind":"COOP"|"PASTURE","animal","placed_day","yield_units","fed_today",
        "consecutive_unfed","cared_today","fertilizer_available","pending_care_bonus"}
```
tiles are indexed tiles[y][x].

## Config defaults
episodeSteps 720, boardSize 10, startingMoney 3000, maxMarketOrdersPerTurn 10, turnsPerDay 24,
shedCapacity 100, weedSpawnChance 0.005, townShopUnlockInterval 3, townShopSellInterval 4,
townCenterSellInterval 24, marketParams overrides allowed.

## Confirmed from package (kaggle-environments 1.32.7)
- actTimeout = 1 second per turn. Keep per-turn compute well under that.
- Agent signature is `agent(obs)` (one argument). `obs["step"]` is the 0-indexed turn.
- Full rules and tables ship inside the package: `envs/kaggriculture/README.md` and `AGENTS.md`.
- Local baseline, starter vs random: starter finished with 3482 coins, random with 0.

## Valuation-relevant rules, re-verified against the engine code (2026-09-25)
Read directly from kaggle_environments/envs/kaggriculture/kaggriculture.py (1.32.7). These were partly documented above
but our valuation code did not use them; any value model must.
- **Demand per day** (whole market, shared by both players): the town center takes 1 unit of every product except
  FERTILIZER per day; every unlocked shop instance takes each listed product every 4 turns = 6 units/day per listed
  product (12/day for single-product shops: Yarn Store = wool, Pet Cafe = carrots). One shop unlocks every 3 days
  (drawn with replacement, max 8 instances).
  - FERTILIZER: no demand at all. Its price = 100 - 0.2 x (cumulative units sold by both players - units bought back);
    it never recovers. Leader worlds: ~70 on day 11, 49 on day 15, 34 on day 19, 14 on day 29.
  - MELON: no shop buys melons; only the town center's 1 a day. Price = 250 - 0.01 x (excess supply)^2 ("sq" glut
    curve), so when both players harvest ~60 melons around days 10-12 the first units sold fetch ~220-250 and later
    ones far less. A melon's value depends on selling before the other player's melons, not only on its units.
  - Milk, wool, strawberry also have steep glut curves (linear 1.6 x base over T=122 / sq 3.2 x base over T=105 /
    linear 1.6 x base over T=100); wheat, carrot, egg absorb gluts well.
- **Every unit sold moves the price for the next unit** (orders are resolved unit by unit, interleaved between the two
  players); a unit sold at the $1 floor does not add to market inventory. Only WHEAT and FERTILIZER can be bought back.
- **One-time crops** (wheat, carrot, melon): planted with 1 unit; each WATER on a day inside the growth window
  [(max_yield_day+1)//2, max_yield_day] adds +1 (+2 if fertilized that day), capped at max_yield: wheat ages 2-4 (cap
  6, i.e. 4 unfertilized / 6 fertilized), carrot ages 2-3 (cap 4), melon ages 6-12 (cap 6). HARVEST only from
  first_yield_day (wheat 2, carrot 2, melon 10). After the end of age max_yield_day the plant decays by 1 unit every 2
  hours and becomes a weed at 0. HARVEST clears the tile.
- **Ongoing crops** (tomato, strawberry): produce every `interval` days from first_yield_day, up to 4 productions;
  +1 per production, +2 if watered and fertilized that day; a plant not watered two days in a row becomes a weed.
- **FERTILIZE** lasts 3 days (the day applied and the next two); its bonus needs the plant watered that day.
- **Animals**: a production pays 1 + the banked care bonus only if fed that day (else 1 and the bank is lost); a fed +
  cared day banks +1; unfed two days in a row -> the animal escapes (the structure stays). COLLECT_FERTILIZER gives 1
  per animal per day (does not accumulate).
- **Shed**: capacity 100 items INCLUDING animals bought and waiting there. Overflow is deleted both at midnight (all
  units' inventories are dumped into the shed) AND on any DROP / PLACE at the shed (items that don't fit are lost).
- **Units**: HIRE cost = fib(n) for the n-th hire of the day (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377...);
  a hand spawns on the least-occupied shed-access tile and acts from the next turn; all hands vanish at midnight and
  the farmer returns to (4,4). BUILD_COOP / BUILD_PASTURE are free but need an empty tile. If a turn's PLANT requests
  for a crop exceed the seeds held at the start of the turn, ALL of that turn's PLANTs of that crop fail.
- **Turn order**: unit actions -> market orders (hire / land first, then buys and sells unit by unit) -> town
  consumption -> plant decay -> (after the last turn of a day) crop / animal refresh, weeds (on empty tiles only),
  inventory dump into the shed, shop unlock every 3 days.
