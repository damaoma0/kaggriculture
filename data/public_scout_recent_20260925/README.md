# Recent-results scouting — 2026-09-25

Architecture work remains paused. Historical-agent testing is stopped. No additional matches, submissions or notebook publishing were performed for this refresh.

## Result

No downloadable public source examined here qualifies as a verified currently strong 2750–3000 opponent. Recent publication dates, notebook titles and displayed historical scores are insufficient. The strong current candidates below are replay-study targets: matching public source has not been found, so they cannot yet be offered as runnable closed-loop opponents.

## Active submissions with recent results

Official authenticated Kaggle API snapshot, September 25, approximately 22:15 UTC. Ratings move during the research window. Select the stronger active submission, not simply the newest upload. Leaderboard team score and its latest submission date need not describe the same artifact.

| Team | Exact active submission | Submission rating observed | Latest 20 completed returned games W–L | Use |
|---|---:|---:|---:|---|
| Boey | 56521745 | 3057.7 | 12–8 | 3000+ study target |
| M & M & P & Q | 56544748 | 3003.8 | 16–4 | 3000+ study target |
| DSM | 56553722 | 2983.0 | 16–4 | Upper benchmark-band target |
| Unknown Mother-Goose | 56538672 | 2975.7 | 11–9 | Upper benchmark-band target |
| Vadim Vasilenko | 56556874 | 2962.8 | 15–5 | Upper benchmark-band target |
| DECEM | 56552482 | 2949.2 | 11–9 | Benchmark-band target |
| Smackaveli | 56550788 | 2935.0 | 14–6 | Benchmark-band target |
| Majkel1337 | 56538379 | 2916.9 | 9–11 | Benchmark-band target |

All 20-game windows are from September 25 and end after 22:00 UTC. These are matchmaking-selected games against different opposition, not comparable independent win-rate estimates. See `current_leader_evidence.json` for exact timestamps, episode IDs, opponent submission IDs and rewards. Raw snapshots: `leaderboard_top200.json`, `current_leader_submissions.json`. Source discovery searches did not locate matching public implementations for these exact IDs; this is not proof that none exists.

## Public-code exclusions and unresolved candidates

Scores below are notebook **Public Score** labels observed in the live UI, not assumed current active-submission ratings. Latest notebook dates were obtained from Kaggle API listings in `recent_notebooks.json`. A missing current score does not mean zero. Every recommendation requires independent recent episode evidence tied to the downloadable artifact.

| Notebook | Version / script ID | Displayed public score | Decision |
|---|---|---:|---|
| [TOP 2 Master Engine V4](https://www.kaggle.com/code/guruprasaathas111/kaggriculture-top-2-master-engine-v4) | V8 / 352725134 | 1870.3 | Reject title-based strength claim |
| [2965 Master Hybrid](https://www.kaggle.com/code/haideptry/the-2965-master-hybrid-engine) | Selected V9 of 10 / 352574450 | 2159.7 | Displayed selected version insufficient; newest V10 not verified |
| [Demand-Preserving](https://www.kaggle.com/code/tetsutani/demand-preserving-turn-sale-timing) | V11 / 352455733 | 2365.1 | Below requested band |
| [cha22](https://www.kaggle.com/code/abhinav0370/cha22-agent) | V5 / 352364888 | 2396.3 | Below requested band |
| [Harvest Ledger](https://www.kaggle.com/code/haodou092/kaggriculture-harvest-ledger) | V72 / 352764409 | 1746.3 | Below requested band; its latest markdown reports no improvement from V72 in 16 cases |
| [Population Robust Economy](https://www.kaggle.com/code/nihilisticneuralnet/kaggriculture-population-robust-economy) | V13 / 352412700 | 1709.6 | Below requested band; embedded validation reports 0–6 vs cha22 |
| [Evgen Dvorkin](https://www.kaggle.com/code/evgendvorkin/kaggriculture) | V31 / 352464992 | 2176.1 | Below requested band |
| [More Wheat, Smarter Sales](https://www.kaggle.com/code/dmitriigluzdov/kaggriculture-more-wheat-smarter-sales) | V9 / 351901992 | 2603.7 | Below requested band |
| [Late Purchase V16](https://www.kaggle.com/code/yasutakababa/kaggriculture-late-purchase-v16-submit) | V1 / 352134005 | 2061.7 | Below requested band |
| [V15 Stack](https://www.kaggle.com/code/wzhengbiao/kaggriculture-v15stack-submit) | V1 / 351944329 | 2327.6 | Below requested band |
| [Herd-Safe Race ca25](https://www.kaggle.com/code/statma/kaggriculture-herd-safe-sale-window-race-ca25) | V1 / 352126792 | 2332.3 | Below requested band |
| [Thomas's 2945 Farm](https://www.kaggle.com/code/thomastschinkel/the-2945-farm-96-vs-the-top-10-public-bots) | V2 / 350939229 | 2825.1 | Exact notebook source claims submission 56269928; API's most recent returned episode ended September 17. Does not establish recent strength. |
| [Four-Turn Forecast](https://www.kaggle.com/code/leoprovorov/four-turn-forecast-notebook-version-2) | V11 | No current label | September 25 local evidence: 20–4 against three related public opponents, four independent confirmation seeds. Author explicitly says leaderboard improvement is unestablished. Research lead only. |
| [Ice and Fire](https://www.kaggle.com/code/leoprovorov/a-song-of-ice-and-fire-fixed-flexible) | Latest viewed | No current label | Replay analysis and embedded derivative; no verified current strength |

Nine notebooks were downloaded into named subdirectories using `kernels_pull`, with metadata. Their notebook code was read as data, not executed. Thomas's submission episode list is preserved in `thomas2945/episodes.json`. Other downloads (Shepherd's Ledger and Ahmed V57) contain local comparison claims, but no verified recent target-band result was established. Neither is promoted.

## Admission rule for the next runnable candidate

Require an exact public source version/hash tied to a submission, completed recent games on the current engine, and evidence against the current target band. An upload timestamp alone is not recent performance. Local results against related public ancestors are supporting evidence only. Do not restart a broad historical-agent panel on the strength of notebook marketing or old maxima.
