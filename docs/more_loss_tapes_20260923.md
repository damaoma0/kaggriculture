# More large-loss m1 tapes to inspect — 23 September 2026

These are six distinct recorded ladder games of the current m1 agent.
Each is an exact recorded-action replay with zero failed hires. The shop
comparison is between the actual world and the final selected donor tape;
it establishes a visible demand mismatch, but a revenue gap alone does
not prove that changing the tape would recover the full loss.

| Episode | Margin | Actual shops versus final donor | Largest negative product revenue gap |
|---|---:|---|---|
| 111262874 | -12,585 | +2 Ice Cream Shops, -1 Yarn Store | Strawberry -19,465; 141 sold versus 248 |
| 111269605 | -11,836 | +2 Yarn Stores, -2 Smoothie Shops | Wool -13,840; 80 sold versus 155 |
| 111337545 | -10,336 | +2 Yarn Stores | Wool -13,762; 58 sold versus 133 |
| 111324547 | -9,571 | +2 Yarn Stores | Wool -10,072; 78 sold versus 133 |
| 111284610 | -8,732 | +1 Yarn Store | Wool -10,993; 227 sold versus 273 |
| 111261836 | -8,636 | +1 Yarn Store | Wool -8,328 and milk -5,316; strawberry is a surplus |

The first case is a useful contrast with the repaired world, episode
111287532: it has more Ice Cream Shop demand and a much larger strawberry
revenue gap, while its final donor expected one more Yarn Store. The next
five cases give several sizes and timings of wool-demand mismatch. The
last case is useful because overproducing strawberry coexists with a
large loss in wool and milk.

Open these per-game artifacts to inspect the ledger, donor tape and action
diagnosis:

| Episode | Exact economic ledger | Donor and router history | Lifecycle diagnosis |
|---|---|---|---|
| 111262874 | [ledger](../results/fresh/all_umg_m1/losses/111262874.json) | [plan](../results/fresh/all_umg_m1/plans/111262874.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111262874.json) |
| 111269605 | [ledger](../results/fresh/all_umg_m1/losses/111269605.json) | [plan](../results/fresh/all_umg_m1/plans/111269605.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111269605.json) |
| 111337545 | [ledger](../results/fresh/all_umg_m1/losses/111337545.json) | [plan](../results/fresh/all_umg_m1/plans/111337545.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111337545.json) |
| 111324547 | [ledger](../results/fresh/all_umg_m1/losses/111324547.json) | [plan](../results/fresh/all_umg_m1/plans/111324547.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111324547.json) |
| 111284610 | [ledger](../results/fresh/all_umg_m1/losses/111284610.json) | [plan](../results/fresh/all_umg_m1/plans/111284610.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111284610.json) |
| 111261836 | [ledger](../results/fresh/all_umg_m1/losses/111261836.json) | [plan](../results/fresh/all_umg_m1/plans/111261836.json) | [lifecycle](../results/fresh/all_umg_m1/diagnosis/111261836.json) |

The underlying recorded games, with both farms' actions and their shop
sequence, are in `data/ladder_panel/56395605/<episode>.json.gz`.
