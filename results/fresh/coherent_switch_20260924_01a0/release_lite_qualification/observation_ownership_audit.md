# V9-lite borrowed-observation contract: Y3 audit

**Read-only source/metadata audit.** No active qualification profit records were read, no games were run, and the frozen package was not edited.

## Finding

The release package's `value_tape_search_v6.Runtime` guard does **not** prove the borrowed-observation contract for Y3. It asserts that `F.V.SOURCE_SHA256` equals the m1 constant `1152ef2e…a52470` (v6 lines 17, 35–38). The frozen entrypoint then replaces `_V9_V0.SOURCE_PATH`, `_V9_V0.SOURCE`, and `_V9_V0.CODE` with `agents/mgt_y3.py` at `main.py` lines 69–72 but leaves `_V9_V0.SOURCE_SHA256` unchanged. The runtime therefore clones Y3 code while validating stale m1 metadata.

Raw SHA-256 values: m1 `1152ef2e12c4535dbc381b9c54ac7d7a0b1a9ad3d0a8018a7567dcf5c4a52470`; Y3 `416ab6977af12644c39ba26b269cecc261c47daffe35997fb51e4cf5fbbb7073`.

## What differs in Y3

A bounded AST comparison of the frozen files (no large encoded rows printed) found six modified top-level items: `_SHP_CFG`, `_mgt_router`, `_shp_topups`, `_shp_runs`, `_shp_decide`, and `_shp_daily_hire`. The route/tape assignments and all other top-level definitions are AST-identical. Y3 adds Yarn service/gating and rescue-pinned animal tasks, and a fixed opening-route handoff.

Static review found no new observation writes or obvious retained observation aliases in those changes: the new `_mgt_router` code reads town/farm data and changes route/report state; `_shp_topups` copies the visible shop list and writes only policy-owned `orphans`/`rescue_pinned` state containing coordinates; `_shp_runs` handles policy-owned task lists; `_shp_decide` copies market orders before extending them and returns a new outer dict; `_shp_daily_hire` only forwards pinned state. This supports the contract, but does not replace runtime proof.

The prior direct runtime audit at `results/fresh/value_tape_speed_20260923/ownership_audit.json` reports 1,438 audited turns with unchanged observations/no retained mutable aliases, but its `native_sha256` is m1's `1152ef…a52470`. It is therefore evidence for m1 only, not Y3.

## Recommended closure

After the active panel ends, run a small separate-process `Runtime(audit=True)` check with the exact frozen Y3 source and a real Y3 observation/memory at a search point. Bind the audit assertion to Y3's raw hash `416ab6977af12644c39ba26b269cecc261c47daffe35997fb51e4cf5fbbb7073` explicitly; do not treat the current m1 `SOURCE_SHA256` assertion as proof.

Machine-readable hashes and source locations: [observation_ownership_audit.json](observation_ownership_audit.json).
