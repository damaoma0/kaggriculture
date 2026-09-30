# KB115LT2 compatibility and frozen V8 provenance

The read-only audit passes. KB115LT2 preserves the tile-plan interface and all existing function signatures. No new source-tape access or retirement bypass was found in its additions. This is a source and configuration audit; enabled planning behavior and runtime still require the frozen V8 game checks.

Old executor SHA-256: `2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0`.

Selected `agents/mgt_lead_kb115lt2.py` SHA-256: `527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7`.

Only three existing definitions change: `_tier_pre`, `_tier_core`, and `_tier_cmd`. The two added functions are `_tier_polish` and `_tier_idle_work`. `TilePlanView`, `_exact_retire`, `_own_retire`, the exact retirement filter in `_tier_pre`, `_tier_override`, and all inspected rolling scheduler/market functions are AST-identical. The new `_tier_cmd` branch calls optional idle work after the entire old execution body; the partial-pickup cursor behavior is unchanged.

The canonical seven recipe changes are `sd_collect_at_floor=1`, `sd_polish=3000`, `sd_polish_final=1`, `sd_polish_xch=0.2`, `sd_polish_water_c=20`, `sd_tier_dawn_shape="learned2"`, and `sd_tier_anim_harv_frac=0.3`. Source defaults leave new features off; the explicit recipe is necessary. `_tier_idle_work` remains off in this recipe.

The added polish reads actual tile state, current prices and the existing service catalog. It only relocates existing stops and adds or drops catalog-supplied optional operations. The exact retirement filter removes FEED and CARE before that catalog reaches the planner; polish does not synthesize replacement feed operations from a hidden recording. Floor collection adds COLLECT_FERTILIZER, not feed. The learned2 dawn branch uses current animal yields and distances plus static thresholds. A pure current-board invocation with `_dsm_data` replaced by an exception-raising stub completed without calling it. Its coarse thresholds were learned from the old DSM40 corpus, as documented by the executor author; that corpus is already declared stage-2 training.

The fixed V8 snapshot has manifest `f5133c24fdf845874c4fb3ba66760dfb3fe4eee3ee30a64b07fcc28364c56f5f`. Independent hash verification confirms every declared project and harness file. Relative to frozen V7, exactly two project files change: executor bytes at the existing compatibility path and the executor recipe with exactly the seven flags above. Wrapper, policy, model, opening, tiler, readiness fix, candidate config and harness are unchanged. The previous-manifest link and protocol hash match. Training provenance and all 243 declared episode identifiers are unchanged; none intersects the protocol's 183 reserved recorded episodes. No wheat-replenishment or stock-recovery prototype is included.

Both diagnosed wheat mechanisms remain in KB115LT2: global carried wheat still suppresses a local route's needed pickup purchase, and a positive partial fixed-tier pickup still advances its item cursor. The new route polish may alter their incidence, so this is not a prediction of how often they occur in V8.

Reproduce without games using `scripts/audit_kb115lt2_compatibility_20260928.py`. Full hashes, AST comparisons, config changes and frozen snapshot checks are in `results/fresh/semantic_strategy_20260928/kb115lt2_compatibility_audit.json`. The previous mechanism controls and bounded BUY-only results are documented separately in `docs/semantic_strategy_idle_route_wheat_20260928.md`.
