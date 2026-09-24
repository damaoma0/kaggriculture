#!/usr/bin/env bash
cd /c/Users/xyygl/Documents/kaggriculture
R=results/fresh/v9lite_20260924
waitmem() {
  while true; do
    free=$(.venv/Scripts/python.exe -c "import psutil;print(int(psutil.virtual_memory().available/1e8))")
    if [ "$free" -ge 30 ]; then break; fi
    echo "$(date +%T) waiting for memory (${free}00 MB)"; sleep 30
  done
}
waitmem; echo "$(date +%T) iso lite"
V9Y3_REPORT_DIR="C:/Users/xyygl/Documents/kaggriculture/results/fresh/v9lite_20260924/iso_lite" .venv/Scripts/python.exe scripts/test_package_isolated.py "C:/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/6d41efd9-2702-44ee-9a16-7709427fd202/scratchpad/v9lite_pkg/submission.tar.gz" agents/mgt_y3.py "C:/Users/xyygl/Documents/kaggriculture/results/fresh/v9lite_20260924/iso_lite/iso.json" 1 --gunzip > $R/logs/iso_lite.out 2>&1
tail -3 $R/logs/iso_lite.out
waitmem; echo "$(date +%T) iso v9"
V9Y3_REPORT_DIR="C:/Users/xyygl/Documents/kaggriculture/results/fresh/v9lite_20260924/iso_v9" .venv/Scripts/python.exe scripts/test_package_isolated.py "C:/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/6d41efd9-2702-44ee-9a16-7709427fd202/scratchpad/v9y3_pkg/submission.tar.gz" agents/mgt_y3.py "C:/Users/xyygl/Documents/kaggriculture/results/fresh/v9lite_20260924/iso_v9/iso.json" 1 --gunzip > $R/logs/iso_v9.out 2>&1
tail -3 $R/logs/iso_v9.out
for ep in 112615140 112543358 112613947 112616960 112583218 112221082; do
  waitmem; echo "$(date +%T) pkg start $ep"
  V9Y3_REPORT_DIR=$R/pkg MGT_FORCE=1 LP_WORKERS=1 .venv/Scripts/python.exe scripts/ladder_panel.py run mgt_v9litepkg p2750 $ep 2>&1 | tail -1
  mv results/fresh/ladder_panel/mgt_v9litepkg/$ep.json $R/pkg/$ep.json 2>/dev/null
done
echo CHAIN2DONE
