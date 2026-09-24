#!/usr/bin/env bash
# usage: run_phase.sh <label> <act: v9|lite> <shadow 0|1> <ckpt 0|1> ep1 ep2 ...
# one game at a time; waits for >= 3.0 GB free before each game
cd /c/Users/xyygl/Documents/kaggriculture
label=$1; act=$2; shadow=$3; ckpt=$4; shift 4
R=results/fresh/v9lite_20260924
mkdir -p $R/$label
for ep in "$@"; do
  while true; do
    free=$(.venv/Scripts/python.exe -c "import psutil;print(int(psutil.virtual_memory().available/1e8))")
    if [ "$free" -ge 30 ]; then break; fi
    echo "$(date +%T) waiting for memory ($free00 MB)"; sleep 30
  done
  echo "$(date +%T) start $ep free=${free}00MB"
  export V9LITE_TAG=$ep V9LITE_REPORT_DIR=$R/$label V9LITE_ACT=$act
  if [ "$shadow" = 1 ]; then export V9LITE_SHADOW=1; else unset V9LITE_SHADOW; fi
  if [ "$ckpt" = 1 ]; then export V9LITE_CKPT_DIR=$R/ckpt; else unset V9LITE_CKPT_DIR; fi
  [ -n "$V9LITE_PARAMS_SET" ] && export V9LITE_PARAMS="$V9LITE_PARAMS_SET"
  t0=$(date +%s)
  MGT_FORCE=1 LP_WORKERS=1 .venv/Scripts/python.exe scripts/ladder_panel.py run mgt_v9lite p2750 $ep 2>&1 | tail -3
  mv results/fresh/ladder_panel/mgt_v9lite/$ep.json $R/$label/$ep.json 2>/dev/null
  echo "$(date +%T) done $ep in $(( $(date +%s) - t0 ))s"
done
echo ALLDONE
