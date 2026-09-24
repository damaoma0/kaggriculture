# Do prices move DSM's production plans? (2026-09-24, 109 DSM farm-games, observational, no games simulated)

Replay extraction re-resolves every step with the engine's own functions: 0 money / market-inventory mismatches in
108 episodes. Out-of-sample R² (leave-one-episode-out), bootstrap CIs. Scripts: extract_dsm_price_panel.py,
analyze_price_awareness.py, report_price_awareness.py, analyze_price_awareness_shopprice.py,
price_awareness_season_value.py. Tables: tables.md, shopprice.md, season_value.json.

1. Plan versus prices / cash / opponent, visible shops held constant. Using only shops DSM could see (the earlier
   table included the shop revealed at the day-d boundary) the shop-only R² days 9 -> 24 is sheep 0.98 -> 0.80,
   cows 0.94 -> 0.78, strawberry 0.95 -> 0.67, wheat 0.50-0.92, carrot 0.56-0.74. With DSM's own board three days
   earlier in the base, prices + cash + opponent add median -0.001 (2 of 43 item x day cells with CI above 0; cash
   alone never, max +0.011). Early "price effects" were shop-timing and own-herd proxies (shop-implied prices raise
   goose d24 R² 0.43 -> 0.77; the player-caused price part then adds median -0.003). Not for lack of variation: day-21
   price SDs 42-76 coins.
2. Significant but small channels (each ~0.3-1k per SD of the price): strawberry tiles kept at d24 (+0.9/SD), sheep
   kept d21/24 (+0.3-0.45/SD), late wheat planting (+1.3-2.0 tiles/SD of 25), carrot planting d18-23, day-6 cash ->
   +0.28 animals/SD on days 6-8. Season production value (board x revenue per item-day, days 6-29): mean 128k,
   SD 7.2k; shops R² 0.80, prices/cash/opponent +0.018 [-0.014, +0.053] (<= ~1.7k). Final cash SD 18.7k, shops 0.42.
3. Cash moves timing, not quantity: 2nd quadrant step 149 and first cow step 150 in all 109 games; 3rd quadrant SD
   1.2 h; 1 SD more cash at day 9 = 0.38 fewer animals on day 10, caught up within days (d11-18 herd -0.1..-0.2, n.s.).
4. Feasibility, not planning, breaks a recording: day-start cash median 4 / 3 / 8 coins on days 1-3; engine clips
   34% of opening hires, 52% of seed buys, 72% of wheat buys; day-1 hands 2-9; 90 of 109 distinct day 0-5 order
   streams, yet the day-6 board is one of two variants one tile apart (88 / 21 games).
Conclusion: a price-aware planning layer is worth at most ~1-2k; the prize is an executor that reaches the
shop-predicted board from our own state (fidelity probe: 95.5k replayed vs DSM's own 109.2k, ~14k a game).
Caveats: observational, n=109, a different opponent in almost every game; sell-side timing not studied.
