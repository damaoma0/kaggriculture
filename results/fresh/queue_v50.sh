#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture/scripts
until grep -q "tape vs v50 done" /c/Users/xyygl/AppData/Local/Temp/claude/C--Users-xyygl-Documents-kaggriculture/1f60a71e-e9d8-4b2a-bbcb-513fb2c98ec7/tasks/bm8izlc91.output 2>/dev/null; do sleep 20; done
echo "tape done $(date +%H:%M)"
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=v50_public ../.venv/Scripts/python.exe selfplay_gate.py v50_panel sp_null cand_v1_nash5 mg11_econ2 > ../results/fresh/v50_panel.log 2>&1
echo "v50 panel done $(date +%H:%M)"
GATE_RIVAL=v48_public ../.venv/Scripts/python.exe selfplay_gate.py v50_vs_v48 v50_public > ../results/fresh/v50_vs_v48.log 2>&1
echo "v50 vs v48 done $(date +%H:%M)"
