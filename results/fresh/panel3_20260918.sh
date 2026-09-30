#!/bin/bash
# three-opponent panel for cand_v1_nash5 on seeds 174000-174031 (both seats), plus her recorded moves in her worlds
cd /c/Users/xyygl/Documents/kaggriculture/scripts
export GATE_SEED_BASE=174000 GATE_SEEDS=32
GATE_RIVAL=benchmark_frozen_56280048 ../.venv/Scripts/python.exe selfplay_gate.py p3_bench cand_v1_nash5 > ../results/fresh/p3_bench.log 2>&1
echo "bench done $(date +%H:%M)"
GATE_RIVAL=v48_public ../.venv/Scripts/python.exe selfplay_gate.py p3_v48 cand_v1_nash5 > ../results/fresh/p3_v48.log 2>&1
echo "v48 done $(date +%H:%M)"
GATE_RIVAL=mg_live_crops ../.venv/Scripts/python.exe selfplay_gate.py p3_mg cand_v1_nash5 sp_null > ../results/fresh/p3_mg.log 2>&1
echo "mg done $(date +%H:%M)"
../.venv/Scripts/python.exe tape_vs_bench.py live cand_v1_nash5 40 > ../results/fresh/p3_tape.log 2>&1
echo "tape done $(date +%H:%M)"
