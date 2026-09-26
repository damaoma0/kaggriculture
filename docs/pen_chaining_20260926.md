# How DSM chains pen work, and a design for us (2026-09-26)

Data: `scripts/season_pen_visits.py` and `scripts/season_pen_chains.py`, KE7 vs DSM on the 40 DSM confirmation worlds,
days 11-28 (results `results/fresh/threads_20260928/pens_ke7_40.json`, `chains_ke7_40.json`). A visit = consecutive
work steps of one unit on one animal tile; a chain = consecutive pen visits of one unit with no other work in between.

## What DSM does differently

| per farm-day | DSM | KE7 |
|---|---|---|
| pen visits / ops per visit | 32.0 / 2.20 | 39.0 / 1.68 |
| visits doing feed + care + collect together (incl. with a harvest) | 36% | 7% |
| single-op visits (collect / feed / care alone) | 28% | 38% |
| animal-days served in one visit | 62% | 47% |
| animal-days with feed, care and collect all done | 74% | 52% |
| chains, pens per chain, gap between pens | 13.9, 2.30, 1.17 tiles | 15.4, 2.53, 1.29 |
| chains starting at hours 0-3 (from the spawn) / followed by a crop patch | 68% / 85% | 64% / 80% |
| hands doing pen work / top-4 units' share of pen visits | 91% / 49% | 94% / 51% |
| animal-product deliveries a day (units each) | 2.41 (4.6) | 1.39 (4.6) |

The route SHAPE is the same (a morning pen chain from the shed, then out to the crops). The difference is inside each
visit: DSM does the whole service (feed, care, collect; the harvest when due) in one stop, then carries the collected
fertilizer out to its crops. We split a pen's day over hands: the mandatory search places the keep-alive FEED and a
due HARVEST; phase C pairs the COLLECT with some hand's FERTILIZE; phases D/E give the non-keep-alive FEED and CARE to
whoever has leftover time. Result: more visits, more walking, and service completed on fewer animal-days.

## Design (not yet built)

1. Pen service stop: on every live animal tile, FEED (not fed today), CARE, COLLECT (fertilizer available) and the
   due HARVEST (cap rule) form ONE mandatory stop, so the sector search gives each pen to one hand. Justification: DSM's
   dominant visit is FCK and it completes the service on 74% of animal-days; geese included (DSM serves them 77-79%).
2. The collected fertilizer then supplies the same hand's crop fertilizes (the time model already counts supply along
   a route), as DSM's collect-on-the-way-out.
3. Shed return in the initial plan: after the crop leg, a hand whose next work is pens near the centre stops at the
   shed (one DROP, then pick up the next round's feed wheat), with the stop's cost in the time model.
4. Check before tuning: pen visits a day, ops per visit, full-service share, cares, units made, deletions, margin.
   Risk: the mandatory load rises (about 22 animals x 2.5 ops); the search must still fit it without lateness.

Related earlier result: the animal thread's KA2 (FEED / CARE mandatory when worth >= 60-200, no COLLECT, no single
owner) was +0.4..+2.1k own / +1.6..+2.5k margin on panel13 (not confirmed on 40 worlds).
