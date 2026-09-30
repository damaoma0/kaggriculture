#!/bin/sh
# animal thread: animal_diag.py for each arm (stream dir name, lowercase) over panel13 -> results/fresh/threads_20260928/animal/diag/<ep>_<arm>.json
# usage: sh scripts/animal_diag_panel.sh ka1 ka3 ...
cd "$(dirname "$0")/.."
for arm in "$@"; do
  for g in 16730612:112444381 16732748:112655730 16732748:112661570 16732748:112667461 16732748:112673479 16732748:112562136 16732748:112563376 16732748:112563785 16732748:112564633 16732748:112565927 16732748:112567021 16732748:112568233 16732748:112569426; do
    ep=${g#*:}
    .venv/Scripts/python.exe scripts/animal_diag.py $g $arm > results/fresh/threads_20260928/animal/diag/${ep}_${arm}.json || echo FAIL $g $arm
  done
done
