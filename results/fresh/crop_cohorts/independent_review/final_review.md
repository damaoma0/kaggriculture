# Independent crop-cohort review

## Verdict

**INCONCLUSIVE — do not promote the value-gated policy yet.** Reject the ungated
two- and four-plot native swaps.

The natural holdout gives the value gate a positive mean margin delta (+60.2)
when all five opponents and both seats are pooled within seed, and none of its
six pooled seed means is negative (three positive, three exact zero). However,
only three independent natural seeds activate the overlay. Mean own-cash delta
is -14.1, and opponent-specific margin regresses against Pasture2700 (-58.2)
and Two Coins (-19.0). This is promising interaction evidence, not enough
independent active-gate evidence for promotion.

## Panel integrity

| Panel | Valid | Failed/missing | Complete clusters | Telemetry errors | Expired yield |
|---|---:|---:|---:|---:|---:|
| Ungated native | 96/96 | 0 | 32/32 | 0 | 0 |
| Controlled value gate | 64/64 | 0 | 16/16 | 0 | 0 |
| Natural holdout | 120/120 | 0 | 30/30 | 0 | 0 |

Every natural candidate/baseline pair realized the same shop sequence (60/60).
Thus the holdout differences are not confounded by divergent realized shops.

## Ungated native policies

| Variant | Opponent | Mean cash delta | Mean margin delta | Delta cluster W/T/L |
|---|---:|---:|---:|---:|
| Two plots | Two Coins | -382.6 | -318.7 | 2/0/6 |
| Two plots | V45 | -293.8 | -182.3 | 2/0/6 |
| Four plots | Two Coins | -1,034.3 | -812.3 | 1/0/7 |
| Four plots | V45 | -545.5 | -564.8 | 1/0/7 |

All 64 candidate cells were active. Worst raw paired margin changes were -692
and -595 for the two-plot policy, and -1,257 and -1,335 for the four-plot
policy. These variants fail consistently enough to reject.

## Controlled value gate

| Opponent | Mean cash delta | Mean margin delta | Delta cluster W/T/L | Active / zero-action cells |
|---|---:|---:|---:|---:|
| Two Coins | -36.5 | +83.5 | 1/7/0 | 2 / 14 |
| V45 | +27.3 | +172.0 | 1/7/0 | 2 / 14 |

All 28 zero-action cells were exact final-cash, ledger, and shop identities.
Only seed 158003 activated: pooled across both opponents and seats it produced
-37.0 cash and +1,022.0 margin. The worst paired cash change was -292; no paired
margin change was negative.

## Natural five-opponent holdout

| Opponent | Mean cash delta | Mean margin delta | Delta cluster W/T/L | Active / zero-action cells | Worst paired cash / margin |
|---|---:|---:|---:|---:|---:|
| Farming V5 | +35.8 | +116.5 | 3/3/0 | 6 / 6 | -24 / 0 |
| Pasture2700 | -109.7 | -58.2 | 0/3/3 | 6 / 6 | -337 / -160 |
| Two Coins | -93.8 | -19.0 | 1/3/2 | 6 / 6 | -235 / -137 |
| V44 | +48.5 | +130.8 | 3/3/0 | 6 / 6 | -45 / 0 |
| V45 | +48.5 | +130.8 | 3/3/0 | 6 / 6 | -45 / 0 |

The new-opponent result is mixed: Farming V5 and V44 improve, but Pasture2700
is a clear regression. Two Coins also regresses despite being present in the
controlled development panel.

Opponent-pooled seed means (five opponents and both seats):

| Seed | Cash delta | Margin delta | Active / zero-action cells |
|---|---:|---:|---:|
| 159000 | +18.2 | +313.4 | 10 / 0 |
| 159001 | 0.0 | 0.0 | 0 / 10 |
| 159002 | 0.0 | 0.0 | 0 / 10 |
| 159003 | 0.0 | 0.0 | 0 / 10 |
| 159004 | +13.8 | +17.0 | 10 / 0 |
| 159005 | -116.8 | +30.8 | 10 / 0 |

All 30 zero-action cells were exact identities. Across the 30 active cells,
mean cash delta was negative for Pasture2700 (-219.3) and Two Coins (-187.7),
while active mean margin was -116.3 and -38.0 respectively.

## Limits

- Effective gate evidence is three active natural seeds plus one active
  controlled seed; seat and opponent replicates are correlated within seed.
- Positive overall margin is partly an opponent-interaction effect: natural
  own cash averages slightly lower and one active seed loses 116.8 cash.
- Opponents are a small, related source-code panel. There is no ladder evidence.
- Zero-action identity and clean telemetry validate the gate's abstention path,
  but do not increase the sample size for its active decision.

