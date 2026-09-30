#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture/scripts
until grep -q "v50 vs v48 done" ../results/fresh/queue_v50.out 2>/dev/null; do sleep 20; done
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=v50_public ../.venv/Scripts/python.exe selfplay_gate.py x50_panel x50_econ2 x50_econ2_nohands > ../results/fresh/x50_panel.log 2>&1
echo "x50 panel done $(date +%H:%M)"
