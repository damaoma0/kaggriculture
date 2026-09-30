# Coherent switch targeted development pilot audit

Four targeted specs were compared against matched opening qualification v5 games for baseline, semantic_inputs, and semantic_bank. These results are development evidence, not qualification evidence.

| Version / arm | N | Mean cash | Mean margin | Failed hires total (mean) | Failed spending mean | Mean contract decisions | Mean probe rollouts | Live layer / entry fallback totals | Shadow layer / entry fallback totals | Mean max action (s) | Worst max action (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v6r2/contracts | 4 | $120,644 | $-10,490 | 4 (1.00) | 4.00 | 26.0 | 0.0 | 0 / 0 | 0 / 0 | 0.0069 | 0.007 |
| v6r2/guarded | 4 | $120,644 | $-10,490 | 4 (1.00) | 4.00 | 26.0 | 8.8 | 0 / 0 | 0 / 0 | 0.0302 | 0.034 |
| v7/market_guard | 4 | $120,644 | $-10,490 | 4 (1.00) | 4.00 | 26.0 | 8.8 | 0 / 0 | 0 / 0 | 0.2165 | 0.412 |
| v8/complete_guard | 4 | $119,951 | $-4,615 | 3 (0.75) | 3.00 | 26.0 | 8.8 | 0 / 0 | 0 / 0 | 0.6259 | 1.493 |
| v9/safe_guard | 4 | $118,281 | $-9,358 | 0 (0.00) | 1.25 | 26.0 | 9.8 | 0 / 0 | 0 / 0 | 0.6230 | 1.451 |

## Matched deltas

Each case-level cash/margin delta versus all three controls is recorded in the JSON.
- v6r2/contracts w06-v56 vs v56: baseline cash -2,715, margin -16,257; semantic_inputs cash +18,092, margin +15,943; semantic_bank cash +18,092, margin +15,943. Failed hires/spending 0/1; contract decisions 26; probe rollouts 0; max action 0.0072s.
- v6r2/guarded w06-v56 vs v56: baseline cash -2,715, margin -16,257; semantic_inputs cash +18,092, margin +15,943; semantic_bank cash +18,092, margin +15,943. Failed hires/spending 0/1; contract decisions 26; probe rollouts 5; max action 0.0274s.
- v6r2/contracts w08-mgt_m1 vs mgt_m1: baseline cash +1,170, margin +11,604; semantic_inputs cash +51,071, margin +62,140; semantic_bank cash +50,860, margin +61,647. Failed hires/spending 0/7; contract decisions 26; probe rollouts 0; max action 0.0067s.
- v6r2/guarded w08-mgt_m1 vs mgt_m1: baseline cash +1,170, margin +11,604; semantic_inputs cash +51,071, margin +62,140; semantic_bank cash +50,860, margin +61,647. Failed hires/spending 0/7; contract decisions 26; probe rollouts 10; max action 0.0301s.
- v6r2/contracts w14-mgt_m1 vs mgt_m1: baseline cash -7,624, margin -10,408; semantic_inputs cash -3,393, margin -7,375; semantic_bank cash -3,393, margin -7,375. Failed hires/spending 1/5; contract decisions 26; probe rollouts 0; max action 0.0069s.
- v6r2/guarded w14-mgt_m1 vs mgt_m1: baseline cash -7,624, margin -10,408; semantic_inputs cash -3,393, margin -7,375; semantic_bank cash -3,393, margin -7,375. Failed hires/spending 1/5; contract decisions 26; probe rollouts 10; max action 0.0339s.
- v6r2/contracts w26-v56 vs v56: baseline cash -20,728, margin -21,494; semantic_inputs cash -22,830, margin -21,207; semantic_bank cash +6,706, margin +7,636. Failed hires/spending 3/3; contract decisions 26; probe rollouts 0; max action 0.0070s.
- v6r2/guarded w26-v56 vs v56: baseline cash -20,728, margin -21,494; semantic_inputs cash -22,830, margin -21,207; semantic_bank cash +6,706, margin +7,636. Failed hires/spending 3/3; contract decisions 26; probe rollouts 10; max action 0.0296s.
- v7/market_guard w06-v56 vs v56: baseline cash -2,715, margin -16,257; semantic_inputs cash +18,092, margin +15,943; semantic_bank cash +18,092, margin +15,943. Failed hires/spending 0/1; contract decisions 26; probe rollouts 5; max action 0.4118s.
- v7/market_guard w08-mgt_m1 vs mgt_m1: baseline cash +1,170, margin +11,604; semantic_inputs cash +51,071, margin +62,140; semantic_bank cash +50,860, margin +61,647. Failed hires/spending 0/7; contract decisions 26; probe rollouts 10; max action 0.1614s.
- v7/market_guard w14-mgt_m1 vs mgt_m1: baseline cash -7,624, margin -10,408; semantic_inputs cash -3,393, margin -7,375; semantic_bank cash -3,393, margin -7,375. Failed hires/spending 1/5; contract decisions 26; probe rollouts 10; max action 0.1551s.
- v7/market_guard w26-v56 vs v56: baseline cash -20,728, margin -21,494; semantic_inputs cash -22,830, margin -21,207; semantic_bank cash +6,706, margin +7,636. Failed hires/spending 3/3; contract decisions 26; probe rollouts 10; max action 0.1378s.
- v8/complete_guard w06-v56 vs v56: baseline cash -2,715, margin -16,257; semantic_inputs cash +18,092, margin +15,943; semantic_bank cash +18,092, margin +15,943. Failed hires/spending 0/1; contract decisions 26; probe rollouts 5; max action 0.5143s.
- v8/complete_guard w08-mgt_m1 vs mgt_m1: baseline cash +1,170, margin +11,604; semantic_inputs cash +51,071, margin +62,140; semantic_bank cash +50,860, margin +61,647. Failed hires/spending 0/7; contract decisions 26; probe rollouts 10; max action 1.4930s.
- v8/complete_guard w14-mgt_m1 vs mgt_m1: baseline cash -10,394, margin +13,091; semantic_inputs cash -6,163, margin +16,124; semantic_bank cash -6,163, margin +16,124. Failed hires/spending 0/1; contract decisions 26; probe rollouts 10; max action 0.2550s.
- v8/complete_guard w26-v56 vs v56: baseline cash -20,728, margin -21,494; semantic_inputs cash -22,830, margin -21,207; semantic_bank cash +6,706, margin +7,636. Failed hires/spending 3/3; contract decisions 26; probe rollouts 10; max action 0.2411s.
- v9/safe_guard w06-v56 vs v56: baseline cash -2,715, margin -16,257; semantic_inputs cash +18,092, margin +15,943; semantic_bank cash +18,092, margin +15,943. Failed hires/spending 0/1; contract decisions 26; probe rollouts 5; max action 0.5326s.
- v9/safe_guard w08-mgt_m1 vs mgt_m1: baseline cash -9,548, margin -10,706; semantic_inputs cash +40,353, margin +39,830; semantic_bank cash +40,142, margin +39,337. Failed hires/spending 0/1; contract decisions 26; probe rollouts 14; max action 1.4506s.
- v9/safe_guard w14-mgt_m1 vs mgt_m1: baseline cash -10,394, margin +13,091; semantic_inputs cash -6,163, margin +16,124; semantic_bank cash -6,163, margin +16,124. Failed hires/spending 0/1; contract decisions 26; probe rollouts 10; max action 0.2562s.
- v9/safe_guard w26-v56 vs v56: baseline cash -16,690, margin -18,156; semantic_inputs cash -18,792, margin -17,869; semantic_bank cash +10,744, margin +10,974. Failed hires/spending 0/2; contract decisions 26; probe rollouts 10; max action 0.2528s.

## Probe/live and shadow evidence

The v8/v9 source creates a separate full-agent shadow entry, shares tape/action/config/route banks, and deep-copies the listed mutable memory keys from live state at each probe reset. Each shadow step executes the complete agent entry plus the seed-deadline overlay. Saved `policy.stats` contains separate live and shadow layer/entry fallback counters. Per-selection probes and actual hire events are compared in the JSON. Actual failed-spending totals are seat-level only, so their exact overlap with a specific probe interval cannot be established. Probe forecasts cover three modeled scenarios and extend three steps beyond the next selector; live policy can switch again at the daily boundary.

## Exclusion and limits

- Excluded the known invalid first v6guarded run (None hire return bug); the corrected v6r2 files are included.
- These four targeted cases are development evidence, not qualification evidence.
- No evaluation games were rerun.

Saved evidence shows one hire-failure disagreement in v8: at w26-v56 step 144, selected route 140's probe recorded 0 failed hires (and 1 failed-spending event in its modeled scenarios); live execution then recorded three failed hire events at steps 168, 168, and 169. Route 140 was selected again at step 168, so the failures occurred while the same route remained active. In v9, all four cases had zero actual failed hires and selected probes recorded no failure flags; failed spending still occurred in three cases, but the run schema only stores aggregate per-seat spending-failure totals, so no step-matched comparison is available.
