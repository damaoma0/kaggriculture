# Preserve readiness of observed initial crops

Frozen V5 derives each current annual crop's release date from its observed yield and fertilizer state, but then discards that association. The compiler groups initial lifetimes by crop, birth day and prior harvest status, and reassigns them by shed distance. Same-age plants with different current yields can therefore exchange today's and tomorrow's release dates. This concerns public current state; fixing it does not require any future source coordinates.

The static audit reconstructs all eight V5 live development games at every D6–29 dawn using only saved public observations and that day's proposal. With the frozen adapter/compiler, the resulting current end-board equals the saved end-board in all 192 cases. Readiness assignments disagree with the adapter's per-cell calculation on 133 dawns and 724 cells: 492 wheat, 228 carrot and four melon. Forty affected cells occur on D6–10, and 684 later.

Each disagreement swaps a premature release with a deferred ready crop, so these 724 cells correspond to 362 crops scheduled before their own readiness date. Of those, 293 also receive a planned replacement. Only three still contain the original crop at the next dawn. That last observation does not distinguish successful early harvest from other removal; it should not be described as proof of 293 blocked replants or a measured yield loss.

The two inspected D10 examples are concrete:

| Case | Crop/birth | Ready tile held | Underfull tile scheduled | Next observed morning |
|---|---|---|---|---|
| live-01 | Wheat, D7 | Tile 39, projected yield 5 | Tile 9, projected yield 3, wheat replacement | Both original crops remain; tile 39 now holds 5, tile 9 still 2 |
| live-02 | Wheat, D7 | Tile 8, projected yield 5 | Tile 9, projected yield 3 | Both original crops remain; tile 8 holds 5, tile 9 holds 4 |

This explains one wrong release choice in each case. It does not yet explain every idle worker or unused seed on D10; no replay was run because the shared memory check fell below the authorized 2.5 GiB threshold.

The corrected adapter sets a current-public `harvest_not_before` bound on observed underfull annual crops. The compiler assigns constrained initial lifetimes first and retains anonymous allocation for future births. Repeating the same 192 saved dawns gives zero readiness mismatches, with identical admitted daily counts in all 192. The end-board changes in 84 cases; in the others, different cohort/release assignments can still produce the same tile-type labels. This is a correctness result, not yet a gameplay gain.

Artifacts under `results/fresh/semantic_strategy_20260928/`:

- Frozen audit: `v5_initial_readiness_audit.json`, SHA256 `befdb9636229b11659cbd22c63f09a8a309884362c49a0c7aaef179088b91c98`.
- Corrected audit: `v5_initial_readiness_fixed_audit.json`, SHA256 `50f0bf776d3761fa8a59d8a1d37ecb0f54eaea0cbcae50ad98297a29a0c2da02`.
- Corrected compiler SHA256: `e53474e53ec8f3335fb2711245e00700295b1b52b1a8ae2106bace083ae44dac`.
- Corrected adapter SHA256: `18f7042d78ae3fc268aaf1bdb77809ae30a96e548748e9de63a5ebd8385af34e`.

`scripts/audit_semantic_strategy_readiness_20260928.py` performs the read-only reconstruction; `--current` selects the corrected editable adapter/compiler. Original V5 outcomes and frozen runtime are unchanged. No engine or policy matchup was executed by this audit.
