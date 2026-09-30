# V9-lite + Y3 release, output-capture correction

This artifact derives from the independently developed V9-lite package promoted
unchanged into `submissions/2026-09-24-v9lite-candidate-01a0`.

- Parent archive SHA-256: `6f5e2c2781325a91525b56343dd6fb73f6aeba2fabde63e55cfeae9fdb390f3b`
- Release archive SHA-256: `372237589610a204abd156db65f865a41f9c0535744ff2cfe251e94438961c9e`
- Entry SHA-256 (unchanged): `04e4a5e89d801b6fd6fcabd3f420782e1c3aabd822068a2367d9b88420176114`
- Native Y3 SHA-256 (unchanged): `416ab6977af12644c39ba26b269cecc261c47daffe35997fb51e4cf5fbbb7073`

The only changed package file is `scripts/research_labour_profit.py`. Its two
global stdout/stderr redirect contexts are replaced with `nullcontext`; the
engine import, construction, and reset calls inside remain intact. This prevents
background forecast warm-up from racing the official loader's stream capture.
All other 184 files, including policy, search, entrypoint, and libraries, match
the parent manifest. The original archive and its evidence are preserved.

The original archive's frozen 384-game test covered 64 new worlds, original m1 and
V56 as live opponents, three paired arms, and balanced seats. V9-lite versus m1
improved own cash by 538.43 and competitive margin by 913.83 on average. The margin
95% world bootstrap interval was [413.46, 1476.93]. Versus Y3, margin improved by
604.49 [144.83, 1113.88]. All games completed; all768 seat ledgers reconciled;
128 pre-switch prefixes and103 no-switch complete action/cash pairs matched.

The derived archive passed fresh-process official file-loader checks in both
seats, including decompressed JSON data. Both completed720 recorded steps with
DONE/DONE, zero search errors and intact process output streams; minimum banks
56.85 and54.52 seconds. These are local checks, not Kaggle server timings.

The 384-game economic test belongs to the parent archive. No claim is made that
another384 games were run on the output-capture-only derivative. See the
structural/state-equivalence audit and exact derived-archive loader results in
`results/fresh/coherent_switch_20260924_01a0/release_lite_qualification/`.

Full report: `docs/tape_release_20260924.md`.
