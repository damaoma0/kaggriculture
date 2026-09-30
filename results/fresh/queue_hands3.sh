#!/bin/bash
cd /c/Users/xyygl/Documents/kaggriculture/scripts
until grep -q "bench-2 done" ../results/fresh/queue_hands.out 2>/dev/null; do sleep 20; done
../.venv/Scripts/python.exe verify_mg_slots.py mg11_econ2 30 > ../results/fresh/mg_slots_v3.log 2>&1
echo "v3 worlds done $(date +%H:%M): $(ls ../results/fresh/mg_slots/mg11_econ2-* | wc -l) games, failed $(grep -c FAILED ../results/fresh/mg_slots_v3.log)" >> ../results/fresh/queue_hands.out
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=v48_public ../.venv/Scripts/python.exe selfplay_gate.py h3_v48 mg11_econ2 > ../results/fresh/h3_v48.log 2>&1
echo "v48-3 done $(date +%H:%M)" >> ../results/fresh/queue_hands.out
GATE_RIVAL=benchmark_frozen_56280048 ../.venv/Scripts/python.exe selfplay_gate.py h3_bench mg11_econ2 > ../results/fresh/h3_bench.log 2>&1
echo "bench-3 done $(date +%H:%M)" >> ../results/fresh/queue_hands.out
