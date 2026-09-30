#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture
export KGR_DATASET=yiyangxudmm/kaggriculture-panel-bundle-y2
export KGR_STAGE=results/fresh/kaggle_remote_y2
for i in $(seq 1 150); do
  st=$(.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py status p2750eval 2>&1 | grep -v "OpenSpiel\|^[a-z_0-9]*$")
  echo "[$i] $st"
  case "$st" in
    *COMPLETE*) break ;;
    *ERROR*) break ;;
    *CANCELLED*) break ;;
  esac
  sleep 45
done
echo "=== fetch ==="
.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py fetch p2750eval 2>&1 | grep -v "OpenSpiel\|^[a-z_0-9]*$"
echo "=== compare (sanity vs local cache, if any) ==="
.venv/Scripts/python.exe scripts/kaggle_remote/remote_panel.py compare p2750eval results/fresh/ladder_panel 2>&1 | grep -v "OpenSpiel\|^[a-z_0-9]*$"
