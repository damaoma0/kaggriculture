# Optional animal harvests in KB115LT2 polish

The suspected removal bug is not present. Polish assigns no score to optional
HARVEST, but it also excludes HARVEST from its add, drop and exchange operation
sets. Existing harvests stay attached to their stops through relocation or swap.
Their source values therefore add a constant to every reachable plan; restoring
that score alone cannot improve its decisions.

This is intentional in the documented scope: the `sd_polish` comment says
harvests and plantings are never dropped. The source comment and implementation
agree. A separate limitation is that unassigned optional animal harvests are
outside polish's search even when an exchange could fit them after refinement.
That would be a new search capability, not a correction to lost harvests.

## Captured evidence

The four verified V8 live01 fixtures reproduce 648 shadow actions, both full
cash totals and ledgers, and all dawn states. This audit reads their complete
before/after argument graphs and exposes the original nested scoring functions
in memory. It constructs no environment, runs no agent or hill-climb, and edits
no executor. Original KB2 remains SHA256
`527d4c48b5d6bbef7854d430797e8691858724242d50eeec1e1636665ee124e7`.

| Day | Planned optional animal harvests, before→after | Held units in those harvests | Unassigned harvests | Unassigned held units | Their source value |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7 | 0→0 | 0 | 0 | 0 | 0 |
| 12 | 5→5 | 22 | 0 | 0 | 0 |
| 18 | 2→2 | 7 | 10 | 26 | 915.3 |
| 26 | 3→3 | 7 | 4 | 8 | 78.0 |

All animal harvest multisets, mandatory and optional, are preserved. The D26
goose73 harvest moves between workers but remains planned. The unassigned
harvest multisets are also unchanged.

The ignored planned values are1386.6 onD12,268.5 onD18 and162.3 onD26. They are
the same before and after. Including them leaves the measured polish gains
exactly123.8,305.0 and43.2 respectively. These are modeled objective values,
not realized dollar gains.

## Labor and storage still matter

`_tier_pre` deliberately makes a harvest optional only when it can wait without
overflowing the animal tonight and it is before the end-season mandatory window.
Its value is0.3 × held units × current price. Holding these goods does not itself
destroy them, so that value rewards earlier collection rather than proving an
incremental seasonal sale.

The earlier delivery pass also explicitly defers holdable harvests when storage
is tight. In the D26 fixture its projection falls from105 to94 units, including
eight deferred harvest units. Those deferrals must not be blindly reintroduced.
The four unassigned harvests cannot all be attributed to this storage pass from
the captured polish boundary alone; the counts happen to total eight units.

Polish retains delivery/drop/placement stops and assesses remaining midnight load
through `_tier_load`. Final modeled loads are11,47,79 and97 forD7/12/18/26.
Its respective total load limits are95,95,95 and99. D18 has16 units of final
modeled headroom; D26 has only two. Adding a harvest before an existing delivery
can have a different midnight-load effect from collecting it after that delivery.

## Bounded single-exchange screen

The diagnostic considers only unassigned optional animal harvests already in
`rest`, at a tile the final route already visits. It preserves any associated
PLACE_HARVEST operation, every fixed delivery/drop/placement stop, and all
mandatory work. Each trial either adds the harvest bundle or exchanges it for
one optional maintenance operation. It enforces completion byH23, no increased
supply/lateness violations, and the existing midnight-load limit.

Seven of the ten D18 targets have a positive feasible single exchange under the
source0.3 valuation. Three of four D26 targets do. Examples:

| Day/target | Single exchange | Modeled gain | Final route end, exclusive | Total midnight load / limit |
| --- | --- | ---: | ---: | ---: |
| D18 sheep36, four wool | Replace cow35 fertilizer collection | +136.8 | 24 | 82 /95 |
| D18 sheep46, four wool | Replace fertilizer collection at45 | +136.8 | 24 | 82 /95 |
| D18 cow35, three milk | Replace its fertilizer collection | +35.7 | 24 | 81 /95 |
| D26 goose55, two eggs | Replace optional WATER at92 | +5.8 | 24 | 97 /99 |

These opportunities cannot be summed: several consume the same route slot, and
each was tested separately against the same final plan. All best positive moves
are exchanges; extra harvesting consumes an action even on an existing visit.
The small D26 differences also depend on the heuristic water and harvest values.
No harvest success, price impact or profit was simulated.

## Narrow next option

Do not change `stop_val` alone or call this a missing-value bug. If a separate
experiment is warranted after runtime is addressed, add an explicitly enabled,
bounded exchange pass for existing `rest` animal harvests at already-visited
tiles. Use the source harvest value, keep previously planned harvests protected,
preserve paired immediate delivery operations, and retain hard time, supply and
midnight-capacity checks. Do not reopen harvests removed by storage deferral
without provenance identifying why they were deferred. Limit candidates and
evaluate runtime separately before any eight-world performance gate.

Reproduction script:
`scripts/audit_kb115lt2_optional_harvest_20260928.py`.
Detailed artifact:
`results/fresh/semantic_kb115lt2_recovery/optional_harvest_audit.json`.
The artifact records input/source/script hashes and every single-move result.
