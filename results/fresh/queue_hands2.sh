#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture/scripts
until grep -q "bench done" ../results/fresh/queue_hands.out 2>/dev/null; do sleep 20; done
../.venv/Scripts/python.exe verify_mg_slots.py mg10_hands_t11,mg10_hands_econ 30 > ../results/fresh/mg_slots_hands2.log 2>&1
echo "isolation2 done $(date +%H:%M): $(ls ../results/fresh/mg_slots/mg10_hands_* | wc -l) games, failed $(grep -c FAILED ../results/fresh/mg_slots_hands2.log)" >> ../results/fresh/queue_hands.out
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=v48_public ../.venv/Scripts/python.exe selfplay_gate.py h2_v48 mg10_hands_econ > ../results/fresh/h2_v48.log 2>&1
echo "v48-2 done $(date +%H:%M)" >> ../results/fresh/queue_hands.out
GATE_RIVAL=benchmark_frozen_56280048 ../.venv/Scripts/python.exe selfplay_gate.py h2_bench mg10_hands_econ > ../results/fresh/h2_bench.log 2>&1
echo "bench-2 done $(date +%H:%M)" >> ../results/fresh/queue_hands.out
