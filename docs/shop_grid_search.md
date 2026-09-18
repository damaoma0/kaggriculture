# Systematic opening search across shop scenarios

Validation-selected experimental policy: **shop-adaptive**, fixed before the test panel. Local experimental entry point: `agents/opening_v3.py`. It did not beat the router on the held-out test mean; **keep the unchanged public-router opening as the baseline**. This grid found no reliable improvement over it.

## Experimental design

The first shop unlocks on day 3. All searched policies use the exact public-router prefix through action 71, then choose a numerical configuration using the first visible shop. This spends starting capital before seeing any shop; the search optimizes reinvestment after the first reveal, not different day-0 allocations. The old growth opening is retained as a separate control.

Full factorial grid: cow target {4, 8} × sheep target {4, 8} × crop for vacant expansion plots {WHEAT, STRAWBERRY} × daily hand target {8, 10}: **16 configurations**. Existing crops/animals are preserved. New animal targets take nearby free plots; NE becomes eligible when cash covers its cost plus 50. Buying and worker movement remain observation-driven. All agents hand off at day 9 to the same replanting rule, and face the router opening followed by that same rule.

| Panel | Independent scenario seeds | Games | Purpose |
|---|---:|---:|---|
| Training | 16 (two per first shop) | 288 | Full grid plus router and old-growth controls; one seat per scenario, balanced across repetitions |
| Validation | 16 new (two per first shop) | 128 | Four policies, both seats; choose final policy |
| Test | 16 new (two per first shop) | 128 | Four frozen policies, both seats; no tuning |

The fixture balances all eight first shops and generates seven later shop draws independently for each scenario. A shop replaces the engine draw only when its normal unlock time arrives; policies never receive future shops or seeds. Weather is not modeled by this game. Weeds and all other mechanics still use the official engine. This is a controlled shop experiment, not a claim that these exact trajectories follow unmodified seed RNG. Different farms can change weed draws; prices and opponent responses are endogenous.

The fixed policy is the best training-wide mean margin. The adaptive policy chooses a configuration per first-shop type, using a 50/50 blend of that shop’s mean margin and the global mean to reduce overfitting. The selector can keep the original router. It chooses only at day 3 and never consults future shops. This is a deterministic shop-dependent mixture of configurations, not randomized play.

## Untouched test results

| Policy | Our mean cash | Opponent mean cash | Mean margin | Wins / draws / losses | Mean day-1 cash |
|---|---:|---:|---:|---:|---:|
| public-router | 64,392 | 64,392 | +0 | 0 / 32 / 0 | 24 |
| growth-control | 62,181 | 81,501 | -19,320 | 0 / 0 / 32 | 9 |
| shop-fixed | 64,392 | 64,392 | +0 | 0 / 32 / 0 | 24 |
| shop-adaptive | 65,557 | 67,413 | -1,856 | 4 / 24 / 4 | 24 |

shop-adaptive versus shop-fixed: paired margin change -1,856; descriptive 95% stratified seed-bootstrap interval [-6,208, +2,495]. Both seats are averaged within each seed before resampling. Only two seeds per shop are available; these intervals do not establish broad generalization.

shop-adaptive versus growth-control: paired margin change +17,464; descriptive 95% stratified seed-bootstrap interval [+15,087, +19,961]. Both seats are averaged within each seed before resampling. Only two seeds per shop are available; these intervals do not establish broad generalization.

## Performance by first shop (test mean margin)

| First shop | Old growth | Fixed | Adaptive |
|---|---:|---:|---:|
| BAKERY | -19,607 | +0 | -13,375 |
| BRUNCH_SPOT | -16,312 | +0 | +0 |
| FARMERS_MARKET | -13,306 | +0 | +0 |
| ICE_CREAM_SHOP | -21,422 | +0 | +0 |
| PET_CAFE | -3,466 | +0 | +0 |
| PIZZA_SHOP | -32,890 | +0 | +0 |
| SMOOTHIE_SHOP | -31,016 | +0 | +0 |
| YARN_STORE | -16,545 | +0 | -1,474 |

## Learned policy

```json
{
  "fixed_name": "public-router",
  "fixed": {
    "default": "router"
  },
  "adaptive": {
    "default": "router",
    "by_shop": {
      "BAKERY": {
        "COW": 4,
        "SHEEP": 8,
        "crop": "STRAWBERRY",
        "hands": 8
      },
      "BRUNCH_SPOT": "router",
      "FARMERS_MARKET": "router",
      "ICE_CREAM_SHOP": "router",
      "PET_CAFE": "router",
      "PIZZA_SHOP": "router",
      "SMOOTHIE_SHOP": "router",
      "YARN_STORE": {
        "COW": 4,
        "SHEEP": 8,
        "crop": "STRAWBERRY",
        "hands": 8
      }
    }
  }
}
```

## Validation ranking

| Policy | Mean margin |
|---|---:|
| shop-adaptive | +45 |
| public-router | +0 |
| shop-fixed | +0 |
| growth-control | -18,956 |

## Training grid

| Configuration | Mean margin | Worst first-shop mean margin |
|---|---:|---:|
| public-router | +174 | -2 |
| shop-c8s8-wheat-h8 | -5,943 | -10,518 |
| shop-c8s8-strawberry-h8 | -6,481 | -10,356 |
| shop-c4s4-strawberry-h10 | -6,675 | -19,572 |
| shop-c4s8-strawberry-h8 | -6,770 | -27,984 |
| shop-c8s4-wheat-h10 | -6,984 | -10,025 |
| shop-c8s4-strawberry-h8 | -7,302 | -10,234 |
| shop-c4s4-strawberry-h8 | -7,343 | -21,475 |
| shop-c8s4-strawberry-h10 | -7,896 | -10,140 |
| shop-c4s8-wheat-h8 | -7,959 | -30,024 |
| shop-c8s8-wheat-h10 | -9,304 | -18,122 |
| shop-c4s8-wheat-h10 | -9,742 | -28,922 |
| shop-c8s4-wheat-h8 | -9,744 | -13,624 |
| shop-c4s8-strawberry-h10 | -10,937 | -30,773 |
| shop-c8s8-strawberry-h10 | -11,761 | -19,330 |
| growth-control | -14,362 | -29,036 |
| shop-c4s4-wheat-h10 | -14,748 | -29,706 |
| shop-c4s4-wheat-h8 | -15,318 | -30,451 |

## Checks and limits

All 544 games completed with valid intermediate statuses and exact continuation cash accounting. Verified 432 selected file-entry actions with no observation mutation. Saved fixed/adaptive trajectories share the exact first 72 actions and resulting states with the router. Source hashes and scenarios are recorded in the manifests; the rebooted training run resumed from its 36 saved results.

This evaluates one opponent opening and one simple continuation. The continuation replaces cleared crop plots with wheat through day 25, buys no land/animals, and caps staff at 10 using the same workload rule on both farms. It can service different layouts with different efficiency. Only the first shop selects the opening configuration; adaptation to the second shop, fertilizer use, alternative day-0 allocations, and a wider parameter range are not searched here.

The earlier two-seed semantic screen was interrupted by an unsupported tomato-root case and superseded by this design. Its partial results were not used to fit or select these policies.

[Selected opening moves](../results/fresh/shop_grid/test-shop-adaptive-89000-seat0/moves.md) · [Full replay](../results/fresh/shop_grid/test-shop-adaptive-89000-seat0/full_replay.json)

Reproduce with `scripts/search_shop_grid.py --stage train`, then `--stage fit`, `--stage validate`, and `--stage test`. Each simulation stage resumes saved results and verifies scenario/source consistency. `--workers` controls local simulator processes. The local opening entry point requires sibling source files.
