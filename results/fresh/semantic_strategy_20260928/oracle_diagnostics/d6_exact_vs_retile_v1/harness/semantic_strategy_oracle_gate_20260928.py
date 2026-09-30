"""Prepare/run a separate D6 component ceiling; never a causal qualification.

Both original action prefixes run through step143. From step144, the same
frozen KB115LT executes either exact original layout or strict count-only
retiled layout. Recorded opponents and shop histories remain fixed.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

import semantic_strategy_gate_20260928 as G

ROOT = Path(__file__).resolve().parents[1]
SCOPE = "COMPONENT_DIAGNOSTIC_NOT_POLICY"
ARMS = ("exact", "retile")
ENTRY = "agents/semantic_strategy_oracle6_20260928.py"
HOOKS = "scripts/semantic_strategy_oracle_hooks_20260928.py"
BASE = "results/fresh/semantic_strategy_20260928/"
COMPILERS = ("build_semantic_tile_stack_20260928.py", "semantic_tile_inputs_20260928.py",
    "semantic_tile_planner_20260928.py", "semantic_tile_allocator_20260928.py",
    "semantic_tile_lifetimes_20260928.py", "semantic_tile_polish_20260928.py")


def ordered_episodes(episodes):
    return sorted(map(str, episodes), key=lambda ep: G.digest(["oracle6-component-20260928", ep]))


def prepare(study, identifier, reference):
    if not identifier or not identifier.replace("_", "").replace("-", "").isalnum():
        raise ValueError("A simple immutable --id is required")
    directory = study/"oracle_diagnostics"/identifier
    if directory.exists():
        raise ValueError("Oracle experiment already exists; use a new ID")
    semantics_path = study/"semantic_inputs_oracle_d6_40.json"
    audit_path = study/"semantic_inputs_oracle_d6_40_audit.json"
    semantics, audit = G.read(semantics_path), G.read(audit_path)
    assert G.sha(semantics_path) == audit["input_sha256"]
    exact_path = ROOT/"results/fresh/semantic_tile_20260928/plans/exact_corrected.json"
    exact = G.read(exact_path)
    order = ordered_episodes(semantics)
    if len(order) != 40 or set(order) != set(exact):
        raise ValueError("Oracle universe must be the complete previous DSM40")
    protocol = G.read(study/"protocol.json")
    reserved = {x["episode"] for split in ("development", "qualification") for x in protocol[split]["recorded"]}
    reserved.update(x["episode"] for x in protocol["recorded_reserve"])
    if reserved.intersection(order):
        raise ValueError("Oracle universe overlaps reserved causal recorded cases")
    reference_dir = study/"candidates"/reference
    reference_manifest = G.read(reference_dir/"manifest.json")
    G.verify_files(reference_dir/"project", reference_manifest["files"])
    options = G.read(reference_dir/"project"/(BASE+"candidate_config.json"))
    # Policy/model settings are deliberately not supplied to the oracle entry.
    options = {key: options[key] for key in ("reactive_land_unlock", "early_financing") if key in options}
    directory.mkdir(parents=True)
    compiler_hashes = {}
    for name in COMPILERS:
        target = directory/"compiler"/name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT/"scripts"/name, target)
        compiler_hashes[name] = G.sha(target)
    from build_semantic_tile_stack_20260928 import make_plan
    inputs, plans = {}, {arm:{} for arm in ARMS}
    cases = []
    for ep in order[:8]:
        item = audit["sources"][ep]
        tape_path = ROOT/item["tape_path"]
        if G.sha(tape_path) != item["tape_sha256"]:
            raise ValueError("Original recording changed")
        tape = json.loads(gzip.decompress(tape_path.read_bytes()))
        if len(tape["shops"]) != 8:
            raise ValueError("Expected eight original revealed shops")
        native = dict(episode=ep, seed=int(tape["seed"]), seat=int(tape["seat"]),
            names=tape["names"], rewards=tape["rewards"],
            shops=[tape["shops"][:min(8, day//3)] for day in range(31)],
            our_actions=tape["actions"], opp_actions=tape["opp_actions"])
        target = directory/"recordings"/f"{ep}.json.gz"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(gzip.compress(json.dumps(native,separators=(",", ":")).encode(),mtime=0))
        cases.append(dict(id="oracle6-"+ep, episode=ep, seed=native["seed"], seat=native["seat"],
            file=target.relative_to(study).as_posix(), sha256=G.sha(target), source=item))
        inputs[ep] = semantics[ep]
        if inputs[ep]["handoff_day"] != 6:
            raise ValueError("Oracle must start from observed day6")
        plans["exact"][ep] = exact[ep]
        plans["retile"][ep] = make_plan(inputs[ep], "reuse", 0, mode="strict")
        if plans["retile"][ep]["hands"] != plans["exact"][ep]["hands"]:
            raise ValueError("Exact and retiled daily hires differ")
    frozen_inputs = {}
    for name, value in [("semantic_inputs.json",inputs), *[(f"{arm}_plans.json",plans[arm]) for arm in ARMS]]:
        G.write(directory/name, value)
        frozen_inputs[name] = G.sha(directory/name)
    harness_hashes = {}
    for name in (Path(__file__).name, "semantic_strategy_gate_20260928.py", *G.HELPERS):
        target = directory/"harness"/name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT/"scripts"/name,target)
        harness_hashes[name] = G.sha(target)
    candidate_hashes = {}
    dependencies = [name for name in reference_manifest["files"] if name.startswith(BASE+"runtime/")
        or name == BASE+"executor_recipe_online.json" or name == "scripts/semantic_strategy_financing_20260928.py"]
    for arm in ARMS:
        candidate = directory/"candidates"/arm
        hashes = {}
        for name in [*dependencies,ENTRY,HOOKS]:
            source = ROOT/name if name in (ENTRY,HOOKS) else reference_dir/"project"/name
            target = candidate/"project"/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            hashes[name] = G.sha(target)
        shutil.copytree(directory/"harness",candidate/"harness")
        G.write(candidate/"manifest.json",dict(candidate_id=arm, scope=SCOPE,created_utc=G.utc(),
            repository_at_freeze=str(ROOT), protocol_sha256=G.sha(study/"protocol.json"),
            entry=ENTRY, files=hashes,harness_files=harness_hashes,training_episodes=order,
            interface="Configured TilePlanView oracle, inactive until original-prefix step144."))
        candidate_hashes[arm] = G.sha(candidate/"manifest.json")
    manifest = dict(id=identifier,scope=SCOPE,created_utc=G.utc(),games_executed_at_preparation=0,
        reference_candidate=reference,reference_manifest_sha256=G.sha(reference_dir/"manifest.json"),
        protocol_sha256=G.sha(study/"protocol.json"),universe=order,selection="First8 by hash of fixed namespace plus episode; no outcomes used.",
        cases=cases,handoff_step=144,options=options,arms=list(ARMS),candidate_manifest_sha256=candidate_hashes,
        harness_files=harness_hashes,compiler_files=compiler_hashes,input_files=frozen_inputs,
        source_semantics_sha256=G.sha(semantics_path),source_audit_sha256=G.sha(audit_path),source_exact_sha256=G.sha(exact_path),
        contrast="Same source prefix, native recorded rival and shops, KB115LT recipe, reactive unlock and financing options. Only suffix TilePlanView layout differs.",
        validity="All8 source controls must reproduce both original final cash totals. Each arm must reproduce both original action prefixes and both observations at step144, complete720 states with both ledgers and runtime valid, and pass recorded-rival integrity. No replacement or selective rerun.",
        limitation="Future source tile-change counts or exact coordinates are oracle inputs. This measures component execution on old training/development worlds, never causal policy strength or qualification.")
    G.write(directory/"manifest.json",manifest)
    return manifest


def verify(study,identifier):
    directory=study/"oracle_diagnostics"/identifier
    manifest=G.read(directory/"manifest.json")
    if manifest["scope"] != SCOPE or manifest["protocol_sha256"] != G.sha(study/"protocol.json"):
        raise ValueError("Oracle scope/protocol mismatch")
    for folder,key in (("harness","harness_files"),("compiler","compiler_files"),(".","input_files")):
        G.verify_files(directory/folder,manifest[key])
    for arm,expected in manifest["candidate_manifest_sha256"].items():
        if G.sha(directory/"candidates"/arm/"manifest.json") != expected:
            raise ValueError("Oracle candidate manifest changed")
    for case in manifest["cases"]:
        if G.sha(study/case["file"]) != case["sha256"]:
            raise ValueError("Oracle recording changed")
    return directory,manifest


def prefix_parity(row,control,actions,source_actions):
    return (row.get("handoff_observation_sha256") == control.get("handoff_observation_sha256")
        and set(row.get("handoff_observation_sha256",{})) == {"0","1"}
        and all(actions[seat][:144] == source_actions[seat][:144] for seat in (0,1)))


def run(study,identifier,arm):
    directory,manifest=verify(study,identifier)
    import psutil
    if psutil.virtual_memory().available/2**30 < 2.5:
        raise ValueError("At least2.5GiB free memory required for one oracle worker")
    controls=[]
    for case in manifest["cases"]:
        output=directory/"controls"/f'{case["id"]}.json'
        if not output.exists():
            controls.append(dict(study=str(study),case=case,kind="source_control",output=str(output),handoff_step=144))
    G.pool_run(controls,1)
    plans=G.read(directory/f"{arm}_plans.json")
    jobs=[]
    for case in manifest["cases"]:
        control=directory/"controls"/f'{case["id"]}.json'
        if not G.read(control).get("eligible"):
            continue
        output=directory/"runs"/arm/f'{case["id"]}.json'
        if output.exists():
            if G.read(output).get("candidate_manifest_sha256") != manifest["candidate_manifest_sha256"][arm]:
                raise ValueError("Existing result has different frozen source")
            continue
        jobs.append(dict(study=str(study),case=case,kind="recorded",candidate=arm,
            candidate_root=str(directory/"candidates"/arm),control=str(control),output=str(output),
            prefix_steps=144,handoff_step=144,configure_name="configure_oracle",
            configure_payload=dict(scope=SCOPE,plan=plans[case["episode"]],options=manifest["options"]),
            oracle_world=dict(experiment_manifest_sha256=G.sha(directory/"manifest.json"),arm=arm,
                plan_sha256=G.digest(plans[case["episode"]]),prefix_steps=144),
            harness_extension=dict(root=str(directory/"harness"),files=manifest["harness_files"])))
    G.pool_run(jobs,1)
    return report(study,identifier,arm)


def report(study,identifier,arm):
    directory,manifest=verify(study,identifier)
    checks=[]
    for case in manifest["cases"]:
        path=directory/"runs"/arm/f'{case["id"]}.json'
        control=directory/"controls"/path.name
        item=dict(id=case["id"],valid=False,recorded=path.exists())
        if path.exists() and control.exists():
            row,source=G.read(path),G.read(control)
            parity=prefix_parity(row,source,G.read(path.with_suffix(".actions.json")),G.read(control.with_suffix(".actions.json")))
            valid=bool(row.get("completed") and row.get("eligible") and source.get("eligible") and parity
                and row.get("candidate_manifest_sha256")==manifest["candidate_manifest_sha256"][arm]
                and row.get("oracle_world",{}).get("experiment_manifest_sha256")==G.sha(directory/"manifest.json"))
            item.update(valid=valid,prefix_and_handoff_equal=parity,margin=row.get("margin"),cash=row.get("cash"),
                phase_cash=row.get("phase_cash"),result_sha256=G.sha(path),source_sha256=G.sha(control))
        checks.append(item)
    valid=[x for x in checks if x["valid"]]
    result=dict(scope=SCOPE,experiment=identifier,arm=arm,expected=8,recorded=sum(x["recorded"] for x in checks),
        valid=len(valid),gate_complete=len(valid)==8,wins=sum(x["margin"]>0 for x in valid),
        mean_valid_margin=sum(x["margin"] for x in valid)/len(valid) if valid else None,cases=checks,
        warning="Component oracle on old training/development worlds; no competition or causal policy claim.")
    G.write(directory/"reports"/f"{arm}.json",result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("prepare","run","report"))
    p.add_argument("--study",type=Path,default=G.DEFAULT_STUDY)
    p.add_argument("--id",required=True)
    p.add_argument("--reference",default="strategy_v4_modern4_finance")
    p.add_argument("--arm",choices=ARMS,default="exact")
    p.add_argument("--frozen",action="store_true",help=argparse.SUPPRESS)
    a=p.parse_args();study=a.study.resolve()
    if a.command=="prepare":
        m=prepare(study,a.id,a.reference)
        print(json.dumps(dict(id=a.id,scope=SCOPE,prepared=len(m["cases"]),options=m["options"],episodes=[c["episode"] for c in m["cases"]])))
    elif a.command=="run" and not a.frozen:
        directory,_=verify(study,a.id)
        raise SystemExit(subprocess.call([sys.executable,str(directory/"harness"/Path(__file__).name),"run","--study",str(study),"--id",a.id,"--arm",a.arm,"--frozen"]))
    else:
        print(json.dumps((run if a.command=="run" else report)(study,a.id,a.arm),indent=2))


if __name__=="__main__":
    main()
