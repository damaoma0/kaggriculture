# Derived archive I/O fix audit

- Derived archive SHA-256: 372237589610a204abd156db65f865a41f9c0535744ff2cfe251e94438961c9e; original archive SHA-256: 6f5e2c2781325a91525b56343dd6fb73f6aeba2fabde63e55cfeae9fdb390f3b.
- Manifest/member comparison: only scripts/research_labour_profit.py changed.
- AST proof: engine() and Simulator.__init__ bodies are unchanged after removing the old redirect wrapper / new nullcontext wrapper; all other module AST is equal.
- Direct constructors: two qualification seeds produced identical initial state, configuration, info, and game settings.
- Public-observation project_input code path is unchanged by AST/module comparison; no rollout or projection call was run in this bounded audit.
- This is equivalence evidence, not a full game qualification. The 384-game results in final_audit.* apply to the original archive; the derived archive still needs the official loader/runtime checks.
- No policy entrypoint was called and no full game was run.
