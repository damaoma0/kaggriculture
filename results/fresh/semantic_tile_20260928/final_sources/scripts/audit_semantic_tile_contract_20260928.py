"""Independent poisoned-field audit of the strict semantic tile compiler.

Recompile every frozen input through the default public compile_plan entrypoint
with guards which fail on any non-contract future field access.  Injected
first-harvest counts/coordinates/prices/outcomes must remain unread. Compare all
executor interface fields to the previously frozen strict plan, not just counts.
This is an offline compilation audit, never a game or simulation run.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from semantic_tile_planner_20260928 import compile_plan

ROOT=Path(__file__).resolve().parents[1]
FIELDS=("n","plant","events","struct_by_day","animals_by_day","board",
        "harv_tiles","removals","land_day","hands","cum_sold")
DAY_FIELDS={"day","hands","land_add_count","plant_counts","build_counts",
            "remove_structure_counts","animal_add_counts","animal_exit_counts",
            "animal_retire_counts","crop_end_counts","crop_remove_counts",
            "crop_disappear_counts","end_occupancy_counts"}
TOP_FIELDS={"n","handoff_day","initial_state","opening_plan","days"}


class GuardedFields(dict):
    def __init__(self,data,allowed,label,reads):
        super().__init__(data)
        self.allowed,self.label,self.reads=allowed,label,reads

    def _read(self,key):
        if key not in self.allowed:
            raise AssertionError(f"non-contract access {self.label}.{key}")
        self.reads.add(f"{self.label}.{key}")

    def __getitem__(self,key):
        self._read(key)
        return super().__getitem__(key)

    def get(self,key,default=None):
        self._read(key)
        return super().get(key,default)


def poison(semantic):
    data=deepcopy(semantic)
    reads=set()
    days=[]
    for day,row in enumerate(data["days"]):
        row.update(first_harvest_counts={"STRAWBERRY":987654,"TOMATO":876543},
                   future_board=["POISON"]*100,maintenance={"FEED":[99]},
                   market={"sold_units":{"WOOL":999999}},reward=999999,
                   source_tiles=list(range(100)))
        days.append(GuardedFields(row,DAY_FIELDS,"day"+str(day),reads))
    data["days"]=days
    data.update(episode="POISON",source_board=[["POISON"]*100]*30,
                opponent_actions="POISON",rewards=[999999,-999999])
    return GuardedFields(data,TOP_FIELDS,"semantic",reads),reads


def audit_one(semantic,frozen):
    assert semantic.get("semantic_scope")=="tile_changes_only"
    assert all(set(row)==DAY_FIELDS for row in semantic["days"])
    h=semantic["handoff_day"]
    prefix=semantic["opening_plan"]
    assert all(len(prefix[f])==h for f in ("plant","struct_by_day","animals_by_day","harv_tiles","removals","hands","cum_sold"))
    assert len(prefix["board"])==h+1
    assert all(e[0]<h for e in prefix["events"])
    assert all(d<h for d in prefix["land_day"].values())
    guarded,reads=poison(semantic)
    result=compile_plan(guarded)
    assert result["planner_metadata"]["input_contract"]=="strict"
    mismatch=[f for f in FIELDS if result[f]!=frozen[f]]
    assert not mismatch,("frozen interface mismatch",mismatch)
    return dict(interface_fields_equal=list(FIELDS),forbidden_reads=0,
                fields_read=sorted(reads),warnings=result["planner_metadata"]["warnings"])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs",type=Path,default=ROOT/"results/fresh/semantic_tile_20260928/semantic_inputs_strict.json")
    ap.add_argument("--plans",type=Path,default=ROOT/"results/fresh/semantic_tile_20260928/plans/reuse_strict.json")
    ap.add_argument("--out",type=Path,default=ROOT/"results/fresh/semantic_tile_20260928/strict_contract_independent_audit.json")
    a=ap.parse_args()
    inputs=json.loads(a.inputs.read_text(encoding="utf-8"))
    plans=json.loads(a.plans.read_text(encoding="utf-8"))
    started=time.perf_counter();rows={}
    for ep,semantic in inputs.items():
        rows[ep]=audit_one(semantic,plans[ep])
    sources=[Path(__file__),ROOT/"scripts/semantic_tile_planner_20260928.py",
             ROOT/"scripts/semantic_tile_lifetimes_20260928.py",ROOT/"scripts/semantic_tile_allocator_20260928.py",
             a.inputs,a.plans]
    audit=dict(worlds=len(rows),passed=len(rows),forbidden_reads=0,
               elapsed_seconds=time.perf_counter()-started,
               hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
               records=rows)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k not in ("records","hashes")}))


if __name__=="__main__":
    main()
