# Marked per-tape sequence variants

Watch the [before → after replay](../viz/tape-109740300-before-after.html): the full original game plays first, then the revised game. The replay selector preserves the current hour for direct comparison; shortcuts highlight D17, D19, D21 and the D23 retirement guard. Both exported 720-state replays reproduce the frozen experiment's actions, cash ledgers and harvest totals. Build with `scripts/build_tape_variant_replays.py`; browser checks are in `scripts/check_tape_variant_replays.cjs`.

Start with a small revision to one existing sequence and keep its identity, applicability and measured outcome. The original UMG tapes and mgt_m1 remain unchanged. The register includes all 584 original tapes; one has an experimental revision. Every other tape is explicitly marked unmodified.

## First revision: 109740300-milk-care-to-wool-v1

This donor came from a world with no Yarn Store. In the diagnosed m1 loss 111678108, the actual world revealed two; m1 harvested 90 wool versus 155 for its opponent. It harvested 69 of its 116 milk while the milk quote was at most 40 (59 milk units were actually sold at those low prices). This is a scenario mismatch, not a claim that the original tape is intrinsically poor.

The revision moves one worker’s existing PICKUP, COLLECT_FERTILIZER and WEST commands one hour earlier, then performs CARE on the adjacent sheep instead of the cow. Four commands change on an active day. At hour 5 the worker rejoins the original sequence; all later positions and commands match. Hires, travel, purchases and non-care work are unchanged in the compiled sequence.

It applies only to donor 109740300 with a revealed Yarn Store, milk quote ≤40 and wool quote at least 20 higher, the expected cow and sheep cohort, room in the sheep’s care bank, and a wool harvest before the donor’s D26 pasture conversion. Days are zero-based, as in the engine. The actual replay applied it on D17, D19 and D21. It rejected D15 on prices and D23 because the next harvest would conflict with retirement.

| Measurement, complete recorded-game replay | Original m1 | Revised tape | Change |
|---|---:|---:|---:|
| Own final cash | 87,878 | 88,192 | +314 |
| Opponent final cash | 98,302 | 98,528 | +226 |
| Cash margin | −10,424 | −10,336 | +88 |
| Wool harvested and sold | 90 | 91 | +1 |
| Milk harvested and sold | 116 | 113 | −3 |
| Total spending | Same | Same | 0 |

Own wool revenue rose 230 and own milk revenue rose 84 despite lower volume: reducing supply improved later milk prices. The opponent also benefited, so own-cash improvement overstates the competitive gain. Two of the three redirected cares replaced care that the existing overlay would otherwise supply; only one was additional care overall. All other harvested product totals were unchanged. The final action stream changed at 38 steps because subsequent overlay work and sales responded to the 12 edited tape commands.

**Mark: diagnostic improvement; broader validation pending.** This is the discovery case with recorded opponent commands and recorded shops. It demonstrates a small feasible improvement in this scenario, not a general win-rate or rating improvement. Three other-donor full-game controls reproduced identical actions and cash. All eight baseline/candidate executions completed with reconciled cash ledgers, no policy fallbacks and no own action over one second. The prior wool-forecast change was not combined into this experiment.

## Register and next revisions

The register links 76 tapes to final-donor associations from the 89 audited losses. 13 tapes have a milk-glut/wool-shortage review flag. These are candidates for inspection: they are not automatically marked bad, and missing flags do not imply a good tape.

Each revision records its base tape and hashes, production change, exact command edits, observable activation conditions, retirement boundary, paired cash/output changes, scope controls and evidence status. Failed revisions and regressions should stay in the register. Promotion requires applicable tests with a responsive opponent; inactive controls cannot establish effectiveness.

Artifacts: [all-tape register](../data/tape_variants/index.json), [marked revision](../data/tape_variants/109740300-milk-care-to-wool-v1.json), [candidate](../agents/mgt_tape_care_v1.py), [paired results](../results/fresh/tape_variants_20260922/summary.json), [frozen design](../results/fresh/tape_variants_20260922/design.json).

Reproduce with scripts/experiment_tape_variants.py freeze, then historical --workers 3, then scripts/report_tape_variants.py. The project’s bundled Python fallback uses the existing engine 1.32.7; no dependencies changed.
