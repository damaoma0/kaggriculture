#!/usr/bin/env bash
# router4q extra panel (2026-09-30): the retrain4q day-11 test bed (6 DSM-new worlds, our seat = DSM, recorded opponent,
# exact leader credit, leader weeds) WITHOUT the prefix: the arm plays from day 0, so our 4Q library opening builds the farm.
# MGT_EXCLUDE = the world's own episode (the DSM library holds these 6 tapes). Controls: read-only copies of
# results/fresh/retrain4q_20260930/dsm4q_p264/_controls. One game process per queue.
# usage: bash results/fresh/router4q_20260930/run_dsm4q_p0.sh ARM [ARM ...]
cd /c/Users/xyygl/Documents/kaggriculture
TR=/c/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/6d41efd9-2702-44ee-9a16-7709427fd202/scratchpad/r4q/traces
LOG=results/fresh/router4q_20260930/smoke_logs
for arm in "$@"; do
  for ep in 115561922 115563541 115561000 115557062 115550561 115547341; do
    mkdir -p "$TR/${arm}_dsm4q-$ep"
    MGT_EXCLUDE=$ep MGT_TRACE_DIR="$(cygpath -w "$TR/${arm}_dsm4q-$ep")" PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/semantic_h2h_20260929.py run --study results/fresh/semantic_h2h_20260929/study --candidate $arm --seeds results/fresh/retrain4q_20260930/dsm4q_cases.json --out results/fresh/router4q_20260930/dsm4q_p0 --workers 1 --no-timeout --leader-credit-exact --leader-weeds --only dsm4q-$ep > $LOG/dsm4q_${arm}_$ep.log 2>&1
    echo "$(date +%T) done dsm4q $arm $ep: $(grep -E 'margin' $LOG/dsm4q_${arm}_$ep.log | tail -1 | cut -c1-200)"
  done
done
