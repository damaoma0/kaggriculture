# Frozen block-policy shadow diagnostic

The frozen block policy eliminates changes to its quantity budget inside a reveal
block, and avoids many of the recorded policies' retirement requests shortly
after animal purchases. This is useful mechanism evidence, not evidence that the
candidate wins more games. Its total retirement requests are higher, and its early
capital plan still relies on intraday sales.

## Scope and provenance

The diagnostic replays 384 morning decisions: D6–29 on the eight fixed-shop B
development games and eight natural v3 development games. It supplies both
current public farms, current market and shops, and the player's actual private
seeds, shed and carried inventories. No future observation, result, opponent
private state, or qualification case enters a decision. Hourly inferred rival
flow history is unavailable in these daily snapshots and is left empty.

The candidate sees the recorded policy's actual progress and validated retirement
intentions. This is an **off-policy shadow**, not a closed-loop counterfactual:
the recorded farm does not execute the shadow requests. Missing work therefore
can remain outstanding and be requested again. Daily request totals below must
not be read as numbers of purchases or unique commitments.

Reproducer: `scripts/check_semantic_block_shadow_20260928.py`.
Complete observations, decisions, input hashes and unique block budgets:
`results/fresh/semantic_strategy_20260928/block_shadow_development_diagnostic.json`.

Source/model hashes were checked against `block_prototype_manifest.json` before
and after the replay and did not change:

| Artifact | SHA256 |
|---|---|
| Block policy | d568c8064e555a377e813412606c7a1f56f98f94fa9a5307682bf1849f2a12a5 |
| Base admission/forecast policy | 8e414b8cc82cc67598d71a24a254bbb1f2d56fb009a08e2a42bcc90e0c566a00 |
| Modern100 block model | 6ff0140191eb8d451bfe178d758fe6eee53abd432786c7f0bf67bdacaefd5426 |

The shadow uses land limit four. Fixed B used land limit three and the older
144-seat library; v3 used land limit four and modern60. Thus neither comparison
isolates block memory alone, and B also has a land-limit difference. The candidate
was frozen separately as `strategy_v5_blocks100_finance`; this diagnostic does not
change that snapshot or test the financing helper's hourly behavior.

## Quantities and stability

Recorded nearest-donor indexes change 24 times in B and 17 times in v3 across the
128 within-block transitions per group. Training rows retain the same donor
ordering at every day, so these indexes identify donor changes. The shadow's
stored block totals change zero times. It subtracts observed successful births
instead of adopting a new donor's ending farm each morning.

The closest comparison, v3, changes the following admitted daily requests summed
over 192 mornings. Outstanding jobs can appear more than once.

| Quantity | Recorded v3 | Block shadow |
|---|---:|---:|
| Wheat planting | 1,223 | 1,357 |
| Carrot planting | 484 | 502 |
| Tomato planting | 173 | 159 |
| Strawberry planting | 217 | 188 |
| Cow additions | 90 | 91 |
| Sheep additions | 74 | 89 |
| Goose additions | 95 | 85 |
| Cow retirements | 17 | 56 |
| Sheep retirements | 55 | 57 |
| Goose retirements | 7 | 11 |

The increase in cow retirements is substantial; stable budgets do not by
themselves imply good herd economics. The independently counted, unique v3-state
block budgets contain 57 cows, 55 sheep and 52 goose additions, with retirement
budgets of 29 cows, 56 sheep and eight geese. These numbers are smaller than
daily request sums because they count each reveal's budget once.

Among actual recorded retirement events involving animals at most six days old,
the shadow asks for zero retirements of that species on nine of 11 B events and
seven of 11 v3 events. All 11 B events and five v3 events occur before first
production under the policy calendar. These are animal events, not independent
worlds; multiple animals can share one decision. The shadow chooses quantities,
so this does not prove which individual animal its tiler would retain.

The improvement is partial. Total daily retirement requests rise from 84 to128
on B and from79 to124 on v3. Six v3 block/species combinations still contain both
an addition and retirement budget (five sheep, one cow), though no individual
shadow day simultaneously requests both for the same species. Across reveals,
the learned strategy can still change herd direction. Do not claim that animal
buy/retire oscillation is solved before closed-loop testing.

## Admission and financing

Giving the same observed state a billion cash changes only three admitted units
on three D7 decisions in each group. On v3, ordinary daily admission drops259
outstanding units on66 of192 mornings, so almost all clipping is physical capacity
or planting/production deadlines, not lack of modelled cash. B has86 clipped units
on23 mornings, but its extra land request makes the physical comparison different.

For a separate check, each reveal is projected for three days assuming its own
admitted work succeeds. Replacing initial cash with a billion changes **none** of
the resulting three-day species totals in either group. On v3:

| Unique budget | Predicted | Admitted under modeled success |
|---|---:|---:|
| Wheat | 1,283 | 1,216 |
| Carrot | 559 | 532 |
| Tomato | 157 | 157 |
| Strawberry | 147 | 147 |
| Cows | 57 | 57 |
| Sheep | 55 | 46 |
| Geese | 52 | 52 |

The shared D6 block loses38 wheat and seven sheep across eight states despite
unlimited cash. At D27, v3 budgets41 wheat and28 carrots but admits12 and one;
inherited final-production deadlines reject late work. Two late sheep budgets
also cannot produce by the admission cutoff. These are concrete places where
the learned budget and inherited feasibility rules disagree.

Low cash clipping is **not** a funding guarantee. On every D6 observation the
admitted capital bill exceeds morning cash by $3,401–4,196, before counting all
day's operating costs. On39 of40 v3 D6–10 mornings, capital exceeds current cash.
The inherited admission credits modeled same-day output and held non-feed goods;
successful harvesting, return-to-shed routing and selling are still necessary.
The financing helper and reactive land routing address execution of this credit,
but their effectiveness cannot be inferred from this shadow.

B repeatedly asks for its missing fourth quadrant on176 mornings because the
recorded three-quadrant policy never executes that shadow request. This is an
off-policy divergence artifact, not176 intended land purchases. V3's25 land-add
request days match the recorded proposal count.

## Next bounded use of public market evidence

Current revealed demand and own cohorts choose the block totals. Rival cohorts,
current inventory/prices and inferred flows affect unit values used to order
admission. Once all requests fit, those values cannot change the quantities.
For example, v3 shadow admits eight cow, eleven sheep and one goose daily
requests with negative estimated marginal value;18 of these20 requests occur
where current cash already exceeds the admitted capital cost. Requests can
repeat. These approximate values are not proof that buying those animals loses
money, but they demonstrate the missing decision path.

A bounded next ablation should modify a reveal's budget once, after the untouched
block baseline is evaluated. Start with an optional veto of at most **one new,
unbought animal per reveal**, rather than increasing the weight of every unit
value. Only enable it when actual current cash plus safely sellable shed lots
cover the remaining budget, wages and feed; preserve already purchased animals,
existing cohorts, retirement intentions and annual feed-replacement jobs. A veto
should require negative marginal competitive value across a small prespecified
range of current-rival-supply and future-demand assumptions. Lock the changed
budget until the next reveal and record the counterfactual estimate.

Use current public crop/animal age cohorts, market inventory and observed harvest
or net-trade history to forecast rival deliveries. Current high prices alone
are insufficient: an observed rival cohort may deliver before ours matures.
Marginal competitive value must include feed and labor costs, joint price impact
on both farms and the remaining production window. Only after this conservative
veto is tested should an expansion variant consider one animal or two long-lived
crop seedlings above the learned budget, within existing capacity and labor.

The available model assumes average care, ongoing-crop output and delivery dates;
it does not observe rival private stocks or future policy. The earlier large
economic selector weight already performed poorly, so these forecasts need
separate calibration against excluded training episodes and a separate gameplay
ablation. No proposed bound is claimed optimal, and no qualification outcome was
consulted to select it.
