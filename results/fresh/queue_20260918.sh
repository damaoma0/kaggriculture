#!/bin/bash
# sequential queue: fertilized-tomato isolation -> geese (both directions) -> flip vs V48
cd /c/Users/xyygl/Documents/kaggriculture/scripts
until grep -q "wrote .*summary-build_vs_v48\|Traceback" ../results/fresh/selfplay_build_vs_v48.log 2>/dev/null; do sleep 20; done
echo "build_vs_v48 done $(date +%H:%M)"
../.venv/Scripts/python.exe verify_mg_slots.py mg7_fert_t11 30 > ../results/fresh/mg_slots_fert.log 2>&1
echo "fert done $(date +%H:%M): $(ls ../results/fresh/mg_slots/mg7_fert_t11-* | wc -l) games, failed $(grep -c FAILED ../results/fresh/mg_slots_fert.log)"
../.venv/Scripts/python.exe verify_mg_slots.py mg6_herd_mg,mg6_herd_noyarn,mg6_herd_v48 30 > ../results/fresh/mg_slots_herd.log 2>&1
echo "herd done $(date +%H:%M): $(ls ../results/fresh/mg_slots/mg6_herd_* | wc -l) games, failed $(grep -c FAILED ../results/fresh/mg_slots_herd.log)"
GATE_RIVAL=v48_public GATE_SEED_BASE=174000 GATE_SEEDS=32 ../.venv/Scripts/python.exe selfplay_gate.py flip_vs_v48 mg6_flip5 mg6_nash5 > ../results/fresh/selfplay_flip_vs_v48.log 2>&1
echo "flip done $(date +%H:%M)"
