# Fresh V13 versus canonical V9-lite: quantity and cost diagnosis

All four games are technically valid losses, mean margin **−$3,685**. V13 earns more revenue in three games, but pays more in every game. Across four worlds, its mean revenue advantage is $3,145 versus $6,830 extra spending. This is observed ledger accounting; removing a purchase also changes production, service, timing and shared prices, so the spending differences are not free recoverable savings.

| Fresh case | Margin | Revenue advantage | Extra spending | Extra land | Extra wages | Hired hand-days, V13 / V9-lite |
|---|---:|---:|---:|---:|---:|---:|
| 00 | −2,295 | +5,174 | +7,469 | +4,000 | +2,354 | 302 / 279 |
| 01 | −1,773 | +4,744 | +6,517 | +4,000 | +2,176 | 302 / 281 |
| 02 | −1,027 | +3,481 | +4,508 | +4,000 | +1,401 | 303 / 288 |
| 03 | −9,645 | −819 | +8,826 | +4,000 | +2,113 | 300 / 280 |

Successful daily hires are inferred uniquely from actual HIRE spending and the official Fibonacci wage schedule, not requested orders. V13 usually hires 12 hands in the middle season, versus V9-lite's usual 11; the last hand is expensive. Every V13 buys land on D6/D9/D10, spending $7,000 total; every opponent buys on D6/D11, spending $3,000. The fourth quadrant is used: its D12–29 dawn occupancy averages 22.8–23.7 crops/animals out of 25 tiles. A smaller land plan must deliberately change production and service obligations, not merely suppress the purchase.

## A concrete early execution loss

Five cows and one goose placed on D6 disappear at D8 dawn without producing, across cases01–03. None receives a FEED command on either D6 or D7, while **all six are revisited D7 for fertilizer collection and CARE by workers carrying zero wheat**. D6/D7 admitted retirement lists are empty. These are missing newborn maintenance, separate from later intentional retirement:

| Case | Newborns lost | D7 visits without feed |
|---|---|---|
| 01 | Cows27,36,37 | Collection/CARE at H12/13, H4/5, H9/10 |
| 02 | Cow37 | H15/16 |
| 03 | Cow5, goose36 | Cow collection H13, CARE H17; goose H8/9 |

Case01 cow36 is placed D6 H19 by a worker still carrying two wheat, yet receives no feed that day; this is not solely an absence of global wheat stock. The other placement workers have no wheat. The saved evidence identifies missed feeding but does not establish the scheduler's internal rejection reason or a profitable counterfactual rescue. The already-known route/feed-stock and newborn task-commitment mechanism warrants checking on prior development fixtures before another economic policy adjustment. These fresh cases remain evaluation evidence, not a fitting set.

## What the crop and animal mix earns

V13's opening sells 58–60 melons versus V9-lite's 78–84, a consistent **$5,755–$6,555 melon revenue deficit**. Its extra eggs, wheat and other crops offset much of that gap, but require more capital and labor. By D12 dawn it trails by $7,979–$11,010 despite having been $402–$562 ahead at D6 dawn. This locates a recurring financing/production gap around the larger expansion and first melon harvest; it does not prove that either opening should be copied without a feasibility test.

There is no uniform failure to earn revenue from extra crops. Case00 gains $3,799 tomato revenue and $5,085 egg revenue; case01 gains $4,783 strawberry and $4,831 egg revenue; case02 gains $4,561 wheat and $4,532 strawberry revenue. Their total revenue gains remain smaller than the added costs. Fertilizer sales revenue is lower in every case ($2,131–$4,965), partly because V9-lite buys $892–$1,151 fertilizer while V13 buys none. Gross fertilizer revenue should therefore not be treated as an equal-sized production deficit.

Case03 makes the tradeoff most visible. Both farms buy five cows and twelve sheep, but V13 sells 68 milk / 235 wool versus 135 / 280. Milk's 67-unit shortfall is 62 fewer retained biological units plus five held units lost at exits; wool's 45-unit shortfall is 42 fewer biological units plus three held exit losses. Own animal cap losses and animal-product private-stock discards are zero. This is primarily lower realized output and exit losses, rather than an unsold shed backlog. The two farms' animal birth dates and later retirement/service differ; not all missing output is an execution failure.

In that case V13 gains 242 carrot sales (+$12,388 revenue), 49 eggs (+$2,210), and 69 wheat sales (+$3,386). It loses $8,993 wool, $6,083 melon, $4,965 fertilizer and $2,065 milk revenue. Extra carrot seed cost alone is $1,560, alongside $4,000 land and $2,113 wages. Calling the carrots intrinsically unprofitable would exceed the evidence: they earn substantial revenue, but the complete portfolio has slightly lower revenue and much higher cost.

The practical priorities are therefore (1) verify newborn feed commitments and local stock delivery using established development fixtures, (2) evaluate land/labor admission together with the full crop/animal plan and its marginal costs, and (3) assess opening financing and melon timing using the authorized training/development corpus. No world-specific rule, model fitting or additional game was performed in this audit. Intentional late retirements should retain their economic meaning.

## Provenance and limits

The frozen manifest verifies the canonical 185-file V9-lite package and `v9lite_agent` entry. It performed twelve additional value searches and zero extra overrides across these games. That counter **does not count native tape selection, routing, maintenance or other native adaptations**; zero overrides does not mean a fixed opponent plan.

Source: `results/fresh/semantic_strategy_20260928/fresh_smokes/v13_canonical_v9lite_fresh4_v1/` in the main workspace. The new script `scripts/audit_semantic_v13_v9fresh_20260928.py` reads only these declared four cases and existing official engine constants. All cash identities and daily animal collection ledgers reconcile; animal biological output uses observed public cohorts and the verified official refresh order. Crops' `produced:` ledger fields are labelled collection, not biological growth.

Detailed quantity/cost tables, daily hires/land/occupancy, newborn hourly inventory evidence and all source hashes are in the recovery worktree's `results/fresh/semantic_kb115lt2_recovery/v13_v9fresh4_accounting.json`, SHA `51de5bc7d9bed542a7efa05d2e6c3cd1ac88d72879bc8761d50515c4fadae202`. Frozen agents and results are unchanged. Four worlds are a small smoke sample and these findings do not replace a qualification result.
