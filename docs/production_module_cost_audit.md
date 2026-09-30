# Production-module integration cost audit

## Scope and artifact integrity

This audit covers the completed natural-RNG integration panel in
`results/fresh/production_modules/integration`: 80 games, four seeds
(172000–172003), two active public opponents (V48 and V50), and both seats.
There are 16 games for each of `mgt_m1`, forced, visible-value, pin-only, and
off.

The records' `sha256` values are hashes of normalized LF source text. They
match the current generated sources: baseline/off
`729f9f098868bd9a2f5959a8f76b20d1ea2a9924f25e53a7105400226ae0a90b`, forced
`ab8499cc21afc8076a32522f641ed2a2e3ac1d3800fd7f8c03da823a23764f74`, value
`8d87742368326d1624bfb87166a4f979ca03f8a9b723dece49662b756da90b28`, and
pin-only `b8ce5779aba58d937f35bca3e64ee8c5ffa3c125027c2fa5dd6b1bd8a4823288`.
The manifest's differing hashes are raw Windows-byte hashes; this is newline
normalization, not a source mismatch. Off is byte-identical to `mgt_m1` and
reproduced all 16 baseline action streams, shops, cash values, and margins.

## Execution result

Forced committed two planned WHEAT slots in every game: 32 commitments, 32
plant requests and confirmations, 32 harvest confirmations, and 64 credited
and sold carrot units. It reported no errors, crop mismatches, unused module
seeds, movement mutations, or hire mutations. The selected tiles repeat by
seed across both opponents and seats:

| Seed | Committed native-WHEAT tiles and planting day |
| --- | --- |
| 172000 | (0,1) day 13; (8,0) day 19 |
| 172001 | (4,0) day 12; (1,7) day 18 |
| 172002 | (3,0) day 13; (8,1) day 19 |
| 172003 | (2,2) day 13; (2,1) day 19 |

These are engine-confirmed carrot executions. The regenerated 48-record
baseline/forced/pin subset carries `event_schema=2` engine events, which gives
an exact matched counterfactual for the pinned route. For every forced
commitment, the matching pin-only record has a successful WHEAT PLANT on the
same tile and step. Summing each tile's subsequent WHEAT harvests until its
next PLANT or the forced program's original-wheat release gives **164 wheat
units across 32 matched cycles (5.125 per cycle)**, versus **64 confirmed
module carrots (2.0 per cycle)**.

The unpinned baseline matches the same WHEAT plant in 28 of 32 windows and
produces 128 wheat in those matched windows (4.57 per matched cycle). The
four missing baseline matches are evidence that route selection already
diverged; they should not be imputed as zero wheat. Pin-only is the appropriate
physical crop counterfactual for this executor. `displaced_wheat=32` is now
corroborated as 32 actual replacement appointments, although it remains a
quantity/cost comparison rather than a revenue comparison because the products
sell in different market states.

## Paired whole-farm deltas

Numbers below are means of each 16-game arm minus its same seed/opponent/seat
baseline record. They are whole-farm outcomes after feedback through market,
shops, and routing, so product deltas cannot be assigned solely to the two
carrot programs.

| Arm | Cash | Margin | Revenue | Spend | Moves | Hire spend | Carrots produced | Wheat produced |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Forced | +495.50 | +1,158.50 | +905.88 | +410.38 | -4.75 | 0.00 | +7.25 | -10.75 |
| Pin-only | +929.38 | +1,623.38 | +1,174.25 | +244.88 | -4.75 | 0.00 | +3.25 | -0.50 |
| Visible value | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Off | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Forced changed aggregate carrot production by +7.25 on average although its
module ledger confirmed four sold module carrots per game. The larger net
change reflects whole-farm substitution and route feedback; it must not be
treated as module output. The largest average forced
revenue changes were carrot +495.13 and tomato +776.25, offset by wool
-401.25, egg -220.88, wheat -130.00, and other product changes. Its largest
spend changes were bought wheat +331.38, sheep +125.00, carrot seed +50.00,
and tomato seed +50.00, partly offset by strawberry seed -125.00.

Pin-only is the essential warning: it has no module seed, rewritten crop care,
or module sale, yet it moves cash +929.38 and margin +1,623.38 on the same
small panel. The forced arm cannot be credited with its apparent positive
whole-farm result until the route-pin intervention is separated or eliminated.
Both active arms changed aggregate moves by -4.75 despite zero reported
in-action movement mutations, showing downstream route selection changes.

The visible-demand value arm made no commitments. Its gate was conservative:
it needs a presently visible carrot buyer and compares two carrot units against
the 20 seed cost plus six wheat units at current price. Its exact no-op result
is useful only as an ablation check, not as evidence that carrot conversion is
unprofitable.

## Cost-accounting conclusion

The panel validates the narrow executor: all forced plants, harvests,
deliveries, and credited sales completed, with no reported scheduling contract
failure. It does not validate a production policy or net carrot value. The
current evidence is too entangled with the route pin to call positive, and four
seed clusters are insufficient for a promotion decision.

Next measurement should add matched sale-price and feed-shortfall accounting to
these tile-level WHEAT traces, then compare a route-stable crop rewrite against
that full counterfactual. Keep the current visible-value arm as a no-op control
until a less conservative value model is separately specified and tested.
