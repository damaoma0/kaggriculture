#!/usr/bin/env bash
# router4q smokes (2026-09-30): queue 1 = b2b games (dsm3q worlds 114393058, 114514221), queue 2 = the ladder game vs
# matu997; one game process per queue (two at a time). Router traces: MGT_TRACE_DIR per arm and game.
# usage: bash results/fresh/router4q_20260930/run_smokes.sh b2b|ladder ARM [ARM ...]
cd /c/Users/xyygl/Documents/kaggriculture
TR=/c/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/6d41efd9-2702-44ee-9a16-7709427fd202/scratchpad/r4q/traces
LOG=results/fresh/router4q_20260930/smoke_logs
q=$1; shift
for arm in "$@"; do
  if [ "$q" = b2b ]; then
    for w in 114393058 114514221; do
      mkdir -p "$TR/${arm}_b2b-$w"
      MGT_TRACE_DIR="$(cygpath -w "$TR/${arm}_b2b-$w")" PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/b2b_replay_20260929.py dsm3q-$w --cand $arm --prefix 0 --label "$arm smoke" > $LOG/b2b_${arm}_$w.log 2>&1
      echo "$(date +%T) done b2b $arm $w: $(tail -1 $LOG/b2b_${arm}_$w.log | cut -c1-160)"
    done
  else
    mkdir -p "$TR/${arm}_lad-115287820"
    MGT_TRACE_DIR="$(cygpath -w "$TR/${arm}_lad-115287820")" PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/sem_panel_multi_20260929.py --candidates $arm --panel results/fresh/ladder_live_20260930/56676484/cases.json:results/fresh/semantic_h2h_20260929/livex_credit --only lad-115287820 --leader-credit-exact --leader-weeds --workers 1 --no-timeout > $LOG/lad_${arm}.log 2>&1
    echo "$(date +%T) done ladder $arm: $(grep -E 'valid|margin' $LOG/lad_${arm}.log | tail -1 | cut -c1-160)"
  fi
done
