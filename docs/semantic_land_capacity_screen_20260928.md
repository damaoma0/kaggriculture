# Land capacity diagnostic

The eight frozen V8 games all show the fourth quadrant by day-11 dawn. The
semantic farms peak at 95–100 crop/animal/structure cells, compared with 74–75
for the live MGT opponent, which never buys the fourth quadrant. Our farms use
more than 75 asset cells on most mornings from day 12 through day 28.

This rules out treating the fourth quadrant's $4,000 price as unused land that
can simply be removed while preserving all current quantities. A three-quadrant
variant would need a different crop/cohort mix and feasible replacement timing.
Cell counts do not establish the marginal profitability of those extra assets,
the value of their effect on rival prices, or the required labor and travel.
No land-policy change or game was run for this diagnostic.

The read-only script is `scripts/audit_semantic_land_capacity_20260928.py`.
The corrected, hash-bound evidence is
`results/fresh/semantic_kb115lt2_recovery/diagnostics/land_capacity_v2/audit.json`,
SHA256 `12de49f61fd85d912babd3acc8b238040fba15e7b5c0d6cbf0cab926e8ca91e9`.
It records both farms' cell types and southeast-quadrant occupancy at all 30
dawns in all eight games. These are development diagnostics, not a new test set.

The initial v1 artifact incorrectly subtracted shed-access coordinates from
geometric capacity. It is retained as invalid geometry and superseded by v2.
Official engine `_apply_unit_action` permits planting at those owned cells;
shed access does not consume a board tile. Three quadrants contain 75 usable
cells, although current assets cannot be moved between quadrants.
