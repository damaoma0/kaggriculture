# Public agent scouting — 2026-09-25

> SUPERSEDED: these historical-score recommendations were withdrawn. The MGT screen was stopped at the user's request after all 15 completed games were MGT wins. See `../../results/fresh/public_scout_20260925/STOPPED.json` and the replacement research in `../public_scout_recent_20260925/README.md`. The table below is an archived discovery record, not the current shortlist.

Architecture development remains paused. This is a source-discovery snapshot, not a new benchmark or submission.

## Shortlist

| Priority | Exact artifact | Kaggle score observed | Source saved here | Assessment |
|---|---|---:|---|---|
| 1 | Kaito Fukami, sparse-shop hybrid v43; notebook V13, script 344404785 | Public and best 2882.0 | `kaito_v13/main.py` | Best starting point: downloadable scored version, compact source, shop-conditioned branching. |
| 2 | Rayk Kretzschmar, C70 impact-first; notebook V11, script 341319585 | Public and best 2990.4 | `rayk_v11/main.py` | Strong historical result, but old engine/evaluation era; current-engine comparison is necessary. |
| 3 | Flexonafft, multi-route agent; notebook V59, script 342313226 | Public and best 2767.3 | `flex_v59/main.py` | Exact historical best recovered; suitable additional reference opponent. |
| 4 | Ahmed Berat Ozer, V55; notebook V1, script 351565110 | Public and best 2595.8 | `ahmed_v55/main.py` | Recent mechanism study, below the requested rating band. |

All four scores and exact version links above were verified on the live Kaggle notebook UI during this search. These are notebook-associated scores, not measurements of current strength against our 2750–3000 opponent panel. No independently verified 3000+ open-source agent was established by this search.

Sources:

- [Kaito V13 / v43](https://www.kaggle.com/code/kaitofukami/103-128-fresh-public-v43-sparse-shop-hybrid?scriptVersionId=344404785)
- [Rayk V11 / C70](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-rank-your-agent?scriptVersionId=341319585)
- [Flexonafft V59](https://www.kaggle.com/code/flexonafft/kaggriculture-multi-route-farming-agent?scriptVersionId=342313226)
- [Ahmed V55](https://www.kaggle.com/code/ahmedberatozer/kaggriculture-v55-one-turn-market-race-edge?scriptVersionId=351565110)

## What is worth studying

**Kaito:** three compatible replay-derived plans, with YARN-first and YARN-second branches becoming active at steps 88 and 153. Child planners remain synchronized before selection; feedback primarily repairs weeds and changes sale ordering. The author reports 103 wins in 128 fresh interactive games against eight public agents, separately from replay holdouts. Those local results were not reproduced here. Public replays from BurntPotato and ActiveMusyoku are credited. The artifact contains its auxiliary Python modules inside the single file.

**C70:** a THUNDER THUNDER replay-derived production trajectory with a market controller that prioritizes sales by estimated price impact. The historical notebook describes selection on engine 1.32.6 and a separate reference-ladder run on 1.32.3. This distinction matters: its own older-engine ladder output includes losses, despite the strong selection-tournament claim. Do not transplant either the old results or 2990.4 rating into a current-engine performance claim.

**Flexonafft V59:** the notebook describes retaining modal-route and RC5 parents and correcting a visible board failure. The exact artifact is only 29,465 bytes. Its usefulness relative to our existing V56 needs an actual paired comparison.

**Ahmed V55:** extends a premium-sale reservation horizon from 40 to 41 turns while retaining V54 production and field actions. The author reports 91/15/4 across 110 games, combining selection and confirmation panels; this aggregate is not an independent holdout. It is useful for studying market timing, but the observed Kaggle score is below our target.

## Latest is not the historical best

- Rayk latest notebook V27 (script 349567011) shows 2461.6 and embeds a V38 low-pressure opening, not C70. Saved separately in `rayk_latest/`.
- Flexonafft latest notebook V97 (script 352732210) shows 1003.7. Its downloaded payload is a repackaged V70 snapshot, not V59. Saved separately in `flex_latest/`. The V70 score mentioned in that notebook was not independently verified here.
- Ahmed V38 shows best 2625.2 at notebook V1; its popularity does not establish target-band strength.

## Acquisition and checks completed

Six notebooks and six extracted `main.py` files are saved. Latest notebooks were pulled with the authenticated Kaggle CLI. Version-qualified CLI pulls returned HTTP 403; exact Rayk V11 and Flexonafft V59 notebooks were recovered using the download menu on their version-pinned pages. Kaito's older URL aliases returned 404 through the CLI; its current canonical slug worked.

Payloads were extracted by parsing literal data and decoding base85/zlib, without executing notebook cells or agents. All six source hashes match their notebook's declared hash and all six pass Python syntax parsing. Kaito's eleven bundled modules also pass syntax parsing. `source_manifest.json` records paths, byte sizes and SHA-256 values. Original notebooks preserve attribution/license material; the four shortlisted notebook pages display Apache-2.0 licenses.

No exact source-hash matches were found within `agents/`, `data/public_candidates/`, `data/public_notebooks/` or `data/router_refresh_20260922/`. This checks byte identity only; these agents still share public lineages. It is not a claim of independent design.

No gameplay tests, package execution, submissions, or architecture changes were performed. Recommended next evaluation order: Kaito v43, C70, Flexonafft V59, then Ahmed V55; use the current official engine, fresh paired seeds and both seats, and compare with our incumbent and target-band opponents.

## GitHub results screened

- [COK-ZhangZiliang/Kaggriculture](https://github.com/COK-ZhangZiliang/Kaggriculture): public V10 source, but its 2600+ figure is a target rather than a verified achieved score.
- [sidhulyalkar/kaggriculture](https://github.com/sidhulyalkar/kaggriculture): substantial public implementation; no sufficiently attributable rating was verified in this search.
- [deepeshumrao/kaggriculture-agent](https://github.com/deepeshumrao/kaggriculture-agent): the cited 3005 result is local cash against an idle baseline, not leaderboard rating.

For this task, the versioned Kaggle artifacts provide stronger performance evidence than the GitHub candidates located.
