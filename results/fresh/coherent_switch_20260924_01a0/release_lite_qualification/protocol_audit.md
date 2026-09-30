# Preliminary v9lite qualification protocol audit

**Phase:** preliminary source/protocol audit. I did not read profit or outcome records, and did not launch games. Final game-record validation is pending.

## Checks that passed

- The driver loads `baseline`, `y3`, and `v9lite` from the frozen `release_lite_qualification/package` tree through `get_last_callable`. The frozen package root is appended to `sys.path`; the v9lite root resolver searches it first. Entry function `v9lite_agent` is the last callable in `main.py`.
- The policy sees only a deep copy of its live seat observation, with its own overage bank supplied. The world seed and future shop list are not passed. Future shop forecasts inside V9 are sampled from a local scenario RNG using only the currently unlocked shops and observed day.
- The protocol locks an empty shop list at step 0, then the persisted sequence prefix after days 3, 6, …, 24, and asserts the visible prefix before every candidate call. Both opponents are paired on each world and each of the three arms is run in a fresh subprocess. The 64 seed values are distinct; the `i % 2` seat rule gives 32 worlds per seat for each opponent.
- The research simulator records successful transactions through its engine hooks and reconciles each seat’s final cash against the ledger. Candidate rollout search uses a separate `ModuleType` engine clone; its hook mutations are restored inside `finally`, so they do not alter the outer engine’s ledger hooks.
- First-call timing adds `get_last_callable` source evaluation/load time to the first policy call, subtracts only time over the one-second allowance from the candidate bank, and fails if the bank goes negative. Opponent call time is excluded from the candidate bank.
- Frozen archive digest and every package file are checked against the package manifest.
- Worktree and frozen package research helper files match byte-for-byte: `value_tape_search.py`, `value_tape_search_v8.py`, `value_tape_search_v9.py`, `value_tape_search_lite.py`, and `rival_trajectory_model_v3.py`. Worktree `scripts/research_labour_profit.py` also equals `package/scripts/research_labour_profit.py` (SHA-256 `06b457c9efeceefe58eb235aaacf69e812aecc64c4351896614c65988be949bc`).

## Caveats for the final audit

- Per-case child processes do not revalidate frozen driver hashes; the outer process checks them at batch start and end. Avoid edits during the panel.
- The environment manifest pins Kaggle Environments 1.32.7 and 16 vendored framework files, but was recorded after initial evaluation worlds. It cannot retroactively prove what the first processes loaded; the parent will verify the environment again at the end.
- Daily records from this driver include cash, but `H.asset_counts` is absent, so `own_assets` is null. They do not retain full daily private inventory, tile counts, or hire totals. Final records do retain ledgers and action/prefix hashes.

Machine-readable checks and exact hashes are in [protocol_audit.json](protocol_audit.json).
