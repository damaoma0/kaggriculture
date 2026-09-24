#!/usr/bin/env bash
# bench (same checkpoints, one process) -> lite games (phase2) -> packaged-variant games (pkg); one process at a time
cd /c/Users/xyygl/Documents/kaggriculture
R=results/fresh/v9lite_20260924
waitmem() {
  while true; do
    free=$(.venv/Scripts/python.exe -c "import psutil;print(int(psutil.virtual_memory().available/1e8))")
    if [ "$free" -ge 30 ]; then break; fi
    echo "$(date +%T) waiting for memory (${free}00 MB)"; sleep 30
  done
}
waitmem
echo "$(date +%T) bench start"
.venv/Scripts/python.exe scripts/v9lite_bench.py $R/bench.json $(ls $R/ckpt/*.pkl | sort) --profile 2>&1 | grep -v "^OpenSpiel\|^[a-z0-9_]*$"
echo "$(date +%T) bench done"
bash $R/run_phase.sh phase2 lite 0 0 112617395 112200188 112460119 112615140 112543358 112613947 112616959 112616218 112531888 112617649 112612772
mkdir -p $R/pkg
for ep in 112200188 112617395; do
  waitmem
  echo "$(date +%T) pkg start $ep"
  V9Y3_REPORT_DIR=$R/pkg MGT_FORCE=1 LP_WORKERS=1 .venv/Scripts/python.exe scripts/ladder_panel.py run mgt_v9litepkg p2750 $ep 2>&1 | tail -2
  mv results/fresh/ladder_panel/mgt_v9litepkg/$ep.json $R/pkg/$ep.json 2>/dev/null
done
waitmem
echo "$(date +%T) isolated package test start"
.venv/Scripts/python.exe scripts/test_package_isolated.py "C:/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/6d41efd9-2702-44ee-9a16-7709427fd202/scratchpad/v9lite_pkg/submission.tar.gz" agents/mgt_y3.py $R/pkg/isolated_gunzip.json 1 --gunzip 2>&1 | grep -v "^OpenSpiel\|^[a-z0-9_]*$" | tail -3
echo CHAINDONE
