# Stages and adaptation in the leaders' recorded games

Evidence: eleven exact-replay audits in `results/fresh/leader_strategy/audit-*.json`. Majkel1337 uses submission 56156662 throughout. M & M & P & Q uses 56254996 in five head-to-head games and 56254995 in episode 109668602. These observations describe those submissions, not unpublished code or every newer version. Days below are elapsed-day checkpoints.

## Majkel1337

- All eleven games have the same day-three core: 2 cows, 3 sheep, 2 strawberries, 12 melons and 6 wheat. At day six, all retain 2 cows, 3 sheep and 12 melons, with 7–8 strawberries. This is strong evidence for a staged opening.
- Later animal portfolios diverge: episode 109662252 (Yarn/Pizza opening shops) has 4 cows and 10 sheep at day nine; 109668602 (Ice Cream/Pizza) has 8 cows and 3 sheep; 109687905 (Bakery/Brunch) has 4 cows, 3 sheep and 4 geese. This is consistent with demand-sensitive investment, but does not isolate its trigger.
- First daily checkpoint with tomatoes ranges from day 7 to 19; carrots from day 11 to 27. These are observed board appearances, not exact planting times.
- Day-eighteen portfolios range from 17–43 strawberries, 0–11 tomatoes and 0–15 carrots. Later crop replacement is not a single universal dated conversion.
- Mean strawberries decline from 29.4 at day eighteen to 5.6 at day twenty-seven, while carrots rise from 1.9 to 18.2. A common seasonal transition coexists with variable crop choices.
- Recorded sell quantities and selected products vary between turns. This establishes variable trading behavior, but not a particular forecasting algorithm; stock, delivery, capacity and cash needs are alternative explanations.

## M & M & P & Q

- Within submission 56254996, all five recorded third-quadrant requests occur at step 216 (nine elapsed days).
- Its second-quadrant requests occur at steps 96, 120, 144 or 168. Fourth-quadrant requests occur at steps 360, 384 or 408; one game has no fourth purchase. This supports scheduled milestones plus conditional expansion.
- Across the six team games, the first tomato daily checkpoint ranges from day 10 to 18. At day eighteen there are 15–29 tomatoes and 8–43 strawberries. Carrots already appear at the day-one checkpoint in every game.
- Opening boards vary even within the same submission before the first shop reveal. Therefore not every difference can be attributed to shops. Weed/execution differences, market interaction and other state-dependent decisions may contribute.
- Both teams issue large final-turn liquidation orders; rank 2 often also has large orders on the penultimate turn. Sale requests alone are not successful transaction totals.

## What remains unproven

The strongest supported interpretation is staged plans with state-dependent choices. Logs do not establish continuous global replanning, exact policy-switch conditions, or direct opponent modeling. Opponent selling changes shared prices, so reacting to those prices can look opponent-aware without inspecting the opponent's board. Demonstrating direct opponent adaptation would require policy access and controlled observation changes, or substantially stronger matched-state evidence.

Practical implication: retain feasible opening and service schedules, but allow later animal investment, crop replacement and expansion to respond to expected net returns. Evaluate direct opponent forecasting as a separate mechanism rather than assuming it explains the leaders' advantage.
