# Nash audit of the initial wheat flip

## Result

**A pure Nash equilibrium is for both players to buy their five required feed wheat in the first market order and retain them. There is no need to randomize a speculative flip quantity.**

This is an exact result for the initial, default-rule **wheat-only trading subgame with five wheat required at the end**, not a Nash equilibrium for the entire 30-day farming game. If the problem instead requires both players to finish with zero wheat (a pure speculative round trip), **both declining to trade is also an exact Nash equilibrium**.

These are weak equilibria: some alternative sequences tie, but none improves unilaterally against the stated equilibrium opponent. This audit finds and certifies equilibria; it does not enumerate every equilibrium of the ten-order game.

The 70-unit flip inherited from V45 is **not** a Nash equilibrium. Matching another 70-unit trader gives no loss, but a smaller opposing trade exploits it.

## Game definition

- Two players, initially 3,000 cash and zero wheat each.
- Initial wheat market inventory 10,000, shed capacity 100, maximum ten market orders.
- Both players commit their entire order queue simultaneously. Orders are matched by list position, then executed one unit at a time with both players quoted before either commits.
- Actions are arbitrary legal wheat BUY_PRODUCT / SELL sequences, including idle slots. No observation or adaptation is possible inside the submitted queue.
- Practical model: each strategy must deliver five terminal wheat units, preserving the opening's feed requirement. Speculative model: terminal wheat must be zero. Without fixing a stock requirement or assigning inventory a continuation value, terminal cash alone would reward not buying necessary feed.
- We test two utilities separately: own terminal cash, and own cash minus opponent cash. The reported equilibria satisfy both.
- Other commodity trades, hiring, land, seeds, subsequent market demand and later farming decisions are outside this subgame. The result assumes default prices and configuration.

A Nash equilibrium requires that neither player can benefit by changing strategy alone. It suffices to check pure deviations: a mixture of non-improving deviations cannot improve expected utility. See [Daskalakis and Farina, MIT lecture on Nash equilibrium](https://www.mit.edu/~6.7980/nfgs_nash.html).

## Audited pricing and execution

For the reachable wheat shortages in this game, the engine price is

`p(d) = round(25 + sqrt(d))`, where `d = 10000 - market_inventory`.

Buys quote the post-buy inventory, `p(d+1)`; sells quote the current inventory, `p(d)`. Both players' quotes use the same pre-commit state. A failed purchase terminates that order; quantities above 100 cannot acquire more than the shed limit.

When both buy five, each pays **26 + 27 + 27 + 28 + 28 = 136**, finishing with **2,864 cash and five wheat**. Buying five immediately costs at most 136 against any wheat-only opponent queue: the opponent can buy only one unit alongside each of our first five units. If it does not buy simultaneously, our cost is lower.

The actual cash game is not assumed to be zero-sum. For example, some simultaneous trades create a few dollars through the shared quotation rule. The cash-*difference* objective is zero-sum by definition. We independently verify own-cash incentives rather than mistaking the margin solution for an own-cash equilibrium.

## Why 70 is exploitable

All rows below use the exact engine pricing, cash limits and order execution. Cash is measured after the displayed queues, before farming. Rows with different terminal wheat holdings must not be compared as equivalent wealth.

| Player A orders | Player B orders | A cash | B cash | Terminal wheat A / B |
|---|---|---:|---:|---:|
| Buy 70, sell 70 | Buy 70, sell 70 | 3,000 | 3,000 | 0 / 0 |
| Buy 28, sell 28 | Buy 70, sell 70 | 3,094 | 2,906 | 0 / 0 |
| Buy 29, sell 29 | Buy 70, sell 70 | 3,096 | 2,908 | 0 / 0 |
| Buy 70, sell 70 | Buy 14, sell 10 (BigAngel) | 2,958 | 2,936 | 0 / 4 |
| Buy 5 and keep | Buy 5 and keep | 2,864 | 2,864 | 5 / 5 |

Against a fixed 70-unit flip, buying 28 and selling back is one margin-maximizing response **within the two-order family**, giving a 188 cash advantage. Buying 29 is an own-cash-maximizing response in that family, earning 96. Neither is a universally safe policy. We have not claimed these are best responses among all ten-order queues.

BigAngel's smaller round trip therefore exposes a real opponent-interaction weakness, rather than shop randomness. V45's source comment describes a defense against large rival flips; it is not an equilibrium argument.

## Proof covering all ten-order wheat sequences

Fix the opponent to **buy five in slot 0, then stop**.

1. Our first order can only be a buy of some quantity, or an ineffective sale/idle because we start with zero wheat. Enumerating requested buys 0–100 covers every distinct purchase behavior; larger requests hit capacity or affordability before exceeding it.
2. After slot 0 the opponent holds five and never trades again. All later changes in wheat supply come from us.
3. Define `F(n) = p(1) + ... + p(n)`. If our stock after slot 0 is `h` and our cash is `c`, every subsequent legal sequence ending with five wheat has exactly the same final cash:

   `final_cash = c + F(h + 5) - F(10)`.

   Buying increases the potential and reduces cash by exactly that increase. Selling reverses it. Intermediate round trips therefore cancel. Cash/capacity constraints can rule out sequences, but cannot create a better terminal payoff.
4. Enumerating the first-order possibilities gives a maximum final cash of **2,864** and a maximum cash advantage of **0**. Both are attained by buying five immediately.
5. By symmetry, neither player improves unilaterally. Randomized deviations also cannot improve. Thus the profile is Nash for both utility choices.

Selected first-order deviations, followed by whatever solo trades restore five wheat:

| First buy quantity | Deviator final cash | Opponent final cash |
|---:|---:|---:|
| 0 (delay everything) | 2,861 | 2,867 |
| 1 | 2,862 | 2,866 |
| 2 | 2,863 | 2,865 |
| 3 | 2,864 | 2,864 |
| 5 | 2,864 | 2,864 |
| 14 | 2,864 | 2,864 |
| 70 | 2,864 | 2,864 |
| 100 requested, affordability enforced | 2,864 | 2,864 |

The same argument with an inactive opponent and terminal stock zero proves the no-trade equilibrium for pure flips: every solo closed round trip returns to 3,000 cash.

For the practical model, buying five immediately is also maximin for own cash: it guarantees at least 2,864, and an opponent buying five prevents any strategy delivering five wheat from guaranteeing more. It is not a dominant strategy: exploitable opponents can offer greater profit to a tailored trade.

## Numerical and engine verification

Script: `scripts/audit_wheat_equilibrium.py`.

- Simulator matched **303** official-engine cases: 300 random ten-order queue pairs plus three edge/replay examples.
- Every reduced first-order deviation, restored to the required terminal stock, was checked in the official engine in **both player seats**: **804 additional cases** across the zero-stock and five-stock certificates.
- Total: **1,107 official-engine comparisons**, all passed.
- Independently solved three finite cash-margin games by linear programming:
  - 101 buy-then-liquidate quantities, terminal zero: solver returns no trade.
  - 101 direct-feed / flip-then-rebuy-five choices: solver returns buy five directly.
  - 84 always-affordable buy-then-retain-five choices: solver returns buy six, sell one, another weak equilibrium in that restricted family; direct buy five is also an own-cash equilibrium there.
- Full-sequence certificates, not those restricted LP results, establish the broad claim for direct buying five.
- Maximum unilateral own-cash and margin gains against the certified candidates: **exactly zero**, in integer engine dollars.
- Engine and script SHA256 hashes and the price table are recorded in `results/fresh/wheat_equilibrium/verification.json`.

Artifacts: `full_sequence_certificates.json`, `examples.json`, the three restricted-game JSON files and `verification.json` under `results/fresh/wheat_equilibrium/`.

## Policy implication

Retain the already prepared capital fix: buy five feed wheat immediately, keep them, and remove the next-turn duplicate feed purchase. It funds the standard day-one farm with at least **22 cash** under this wheat-only opening analysis.

This does not prove that five feed units or the surrounding farm build is globally optimal. It establishes that, conditional on that feed requirement, the simple purchase is strategically stable in the initial wheat market. Exploiting predictable large-flip opponents is a separate, risk-bearing policy choice. No agent or Kaggle submission was changed during this audit.
