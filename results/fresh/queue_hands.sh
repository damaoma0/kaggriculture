#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture/scripts
../.venv/Scripts/python.exe verify_mg_slots.py mg9_hands_t11,mg9_hands_econ 30 > ../results/fresh/mg_slots_hands.log 2>&1
echo "isolation done $(date +%H:%M): $(ls ../results/fresh/mg_slots/mg9_hands_* | wc -l) games, failed $(grep -c FAILED ../results/fresh/mg_slots_hands.log)"
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=v48_public ../.venv/Scripts/python.exe selfplay_gate.py h_v48 mg9_hands_econ > ../results/fresh/h_v48.log 2>&1
echo "v48 done $(date +%H:%M)"
GATE_RIVAL=benchmark_frozen_56280048 ../.venv/Scripts/python.exe selfplay_gate.py h_bench mg9_hands_econ > ../results/fresh/h_bench.log 2>&1
echo "bench done $(date +%H:%M)"
