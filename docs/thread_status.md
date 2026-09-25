# Thread status (kept by the coordinator; updated whenever a thread starts, stops or reports)

Last update: 2026-09-25 16:45 (London)

| thread | goal | state | latest result / where |
|---|---|---|---|
| Day-11 defect hunt (exact-opening agent) | Tile-exact parity: fix why our executor falls behind the leader on day 11 from the leader's exact morning state; then port confirmed fixes into agents/mgt_lead.py and the deploy | RUNNING | cause table done (replant moved off the leader's tile after its early melon/wheat harvests; wheat fertilize ignored/deferred; fertilizer hoarded; coop+goose job never wins the dispatcher; idle h19-23). Fixes being built in agents/mgt_lead_fix.py: replant_leader, fert_follow, fert_gross, fert_shadow (incl. collect values and animals kept for fertilizer), place bonus, night fertilizer delivery. Next: day-11 test on 42 worlds, then full games on 12 + 48 |
| Route-search dispatcher (restarted) | Rolling-horizon route search for crop-care labour, T first | RUNNING | fetching the previous agent's finished shadow/active runs (kgr-sdg1a, kgr-sdg1b), shadow must equal off to the dollar |
| Plant-upkeep marginal value (restarted) | Marginal benefit/cost of keeping up a plant; leader skips; single-day scenarios; fertilizer shadow value in retirement | RUNNING | - |
| E1: executor owner | - | STOPPED (unintended); its remaining items (porting, plan continuation) were folded into the day-11 thread | last results: T on the leader's exact harvest days +36 (-3,058..+3,130), with early harvest -2,265; cap_fix on 48 worlds +259 (-309..+828), n.s. (12-world +957 did not hold) |
| Exact opening to the cash-safe day | Follow the leader action-exact until day 11, then our executor | DONE | results/fresh/xopen_20260925/report.md: no gain (48 worlds -2.3k vs T, n.s.) |
| Fertilizer market trend | Supply vs demand | DONE (coordinator) | no demand: price = 100 - 0.2 x cumulative units sold by both players; 70 on day 11, 49 on day 15, 34 on day 19, 14 on day 29 |

Live submissions unchanged: V9-lite+y3 (56525017) and m1 (56395605).
