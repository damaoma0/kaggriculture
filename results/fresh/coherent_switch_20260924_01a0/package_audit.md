# Package audit: v9y3 and v9lite

Read-only audit. No games were launched, package files were not edited, and no submission was made.

## Artifact identity

- Durable v9y3 package: `submissions/2026-09-24-mgt_v9y3/NOTES.txt` (the actual notes filename), `MANIFEST.json`, and `submission.tar.gz`. Archive SHA-256: `3191f44db763646c017f7cd91b9663ae6a0e58eaa5d5d6dc78a446aa22a045ec`; manifest archive digest matches, and all 184 packaged member hashes match. `pkg/main.py` SHA-256: `2d69c34905eae95a01ec3e9e7e5d944ff5451d6fc53b6d7d9a646dd10a8f014c`.
- v9lite package: the archive/manifest/pkg are in a Claude Temp scratchpad, not a durable submissions folder. Archive SHA-256: `6f5e2c2781325a91525b56343dd6fb73f6aeba2fabde63e55cfeae9fdb390f3b`; manifest archive digest and all 185 member hashes match. `pkg/main.py` SHA-256: `04e4a5e89d801b6fd6fcabd3f420782e1c3aabd822068a2367d9b88420176114`.
- Exact entry-byte equivalences: v9y3 main equals both `agents/mgt_v9y3pkg.py` and `agents/mgt_v9y3pkg1w.py`; v9lite main equals `agents/mgt_v9litepkg.py`. Thus v9y3 `pkg1w` is the same build, with a different evaluation concurrency setting.

## Loader and budget evidence

The v9y3 package notes describe the bank-aware budget `min(20, (remainingOverageTime - 8) / reveals_left)`, with 3-second minimum; unfinished/failed searches retain the native route, and gzip fallback is supported. The recorded isolated package test on the official Kaggle CPU runner was 8/8 DONE, bank end 45.4–50.8 of 60, largest step 9.6 seconds. Its p2750 panel search logs show 0/555 errors; at four games per kernel, contention reduced its gain substantially, whereas one game per kernel matched the unbudgeted research build.

v9lite uses warm background construction from step 2 and a throwaway rollout at step 240; it freezes GC during search. Its isolated archive gunzip check is saved at `results/fresh/v9lite_20260924/pkg/isolated_gunzip.json`: both seats ran 720 steps DONE/DONE, bank minima 32.58/35.01, maximum bank drop 10.39/9.72 seconds. Its 185-game p2750 package logs show 555 decisions and zero search errors; shard maximum search times 9.18/9.20 seconds, with warm build runtime about 11.24/11.47 seconds. One separate `iso_lite` log ended with a teardown `ValueError('I/O operation on closed file')` and has no `iso.json`; this makes that log incomplete, but does not invalidate the separately saved direct archive `isolated_gunzip.json` result. A shadow/non-production v9lite run, episode 112200188, is explicitly marked INVALID due to bank exhaustion; do not use it as package-run evidence.

## 185-game results against y3

- v9lite package: +611.081 mean paired delta; 32 better, 145 ties, 8 worse; wins 96 vs baseline 87.
- v9y3 package under four-game kernel contention: +163.865 mean; 9 better, 172 ties, 4 worse; wins 89 vs 87.
- v9y3 `pkg1w` (single game per kernel): +472.151 mean; 23 better, 157 ties, 5 worse; wins 93 vs 87.

These are existing panel results, not a fresh re-run.

## Recommendation

The strongest observed outcome is v9lite (+611.081), and its exact scratchpad archive has manifest/member integrity plus a successful direct archive load check. However, that archive is only in Temp, so it is not a durable deployment artifact until copied/promoted with the same verified hash and manifest. For an immediately reproducible repository fallback, use the frozen v9y3 archive at `submissions/2026-09-24-mgt_v9y3/submission.tar.gz` (SHA-256 above); its `pkg1w` evaluation is the more representative strong operating point (+472.151 vs y3), while the four-worker panel shows the cost of contention.

Full machine-readable evidence and artifact paths are in [package_audit.json](package_audit.json).
