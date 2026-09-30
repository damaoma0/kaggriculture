# Historical v9lite result fact-check

**Finding:** The reported +611.081 is correctly labeled a mean paired **competitive-margin** delta, not an own-cash delta. Each row's `margin` is `final - rival`; paired change is v9lite `margin` minus Y3 `margin`. Recalculation from 185 matching episode files gives +611.081 per game. Own-cash change averaged only +212.643; the mean opponent-cash change was -398.438.

## Historical panel scope

- Candidate: `results/fresh/ladder_panel/mgt_v9litepkg/*.json` (185 rows). Y3 baseline: `results/fresh/kaggle_remote_y2/p2750eval/output/kgr-p2750eval-s0/out/mgt_y3/*.json` (185 rows). All 185 IDs pair exactly on episode, seat, and original recorded rewards.
- Source replay set: `data/ladder_panel/p2750/*.json.gz` (185 games). The saved p2750 run metadata lists 185 episode IDs, four original evaluation agents (mgt_t10, mgt_m1, mgt_y2, mgt_y3), 740 games, engine 1.32.7, Python 3.12.13. `results/fresh/newphase_20260923/queue_h.json` records the v9lite run on the same p2750 episode set.
- `scripts/ladder_panel.py` states that the runner forces recorded shops and replays the opponent's recorded actions while the candidate acts live. The opponent cannot react. These are counterfactual replay results, not a live-opponent rating/Elo estimate.
- Raw 185-game results: margin delta +611.081, 32 better / 145 ties / 8 worse; own-cash delta +212.643; candidate wins 96 vs Y3 87.
- Applying the panel report's `opp_dead` difference >40 filter excludes one episode (112611793). On the remaining 184, mean margin delta is +614.913, with 32 better / 145 ties / 7 worse. The published +611.081 corresponds to raw all-185, not this filtered subset.

The report's +611.081 metric needs no correction; add the replay-only scope and the one-row filter distinction wherever these historical results are used. See [historical_lite_factcheck.json](historical_lite_factcheck.json) for fields and source hashes.
