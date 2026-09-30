# Fresh DSM traces

Each compressed trace stores the original actions, market fills aligned to requested order slots, daily farm/private states, successful physical jobs, public shops, and successful pickup quantities from worker inventory deltas. Extraction replays each source through the Kaggle engine and checks farms, market, town, private state, and cash at every transition. The first source also receives a full normalized-action parity replay.
