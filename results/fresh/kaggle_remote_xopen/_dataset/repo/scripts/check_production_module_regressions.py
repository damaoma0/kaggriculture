"""Small regressions for production-module delivery and carrot scheduling.

This loads only the actual helper functions from the generated fragment. It
does not import or execute the multi-megabyte competition agent.
"""
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "scripts" / "fragments" / "mgt_production_modules.py"
OUTPUT = ROOT / "results" / "fresh" / "production_modules" / "regressions.json"


def load_helpers():
    tree = ast.parse(FRAGMENT.read_text(encoding="utf-8"))
    wanted = {"_mpm_note", "_mpm_usable", "_mpm_visits", "_mpm_plan", "_mpm_reconcile"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {n.name for n in nodes} != wanted:
        raise RuntimeError("production-module helper set changed: %r" % sorted(n.name for n in nodes))
    ns = {
        "_MPM_CFG": {"day_lo": 12, "day_hi": 21},
        "_MPM_REPORT": {"mismatches": 0, "events": []},
        "_mpm_mapping": lambda obs, player: [0],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(FRAGMENT), "exec"), ns)
    return ns


def assert_delivery(ns, actor_exists, shed_before, shed_after, expected_credit, label):
    st = {
        "mapping": [0, 1],
        "prev_inv": {0: 0, 1: 2},
        "prev_shed": shed_before,
        "carry": {1: 2},
        "pending": {},
        "credit": 0,
        "programs": {},
    }
    inventories = [{"CARROT": 0}]
    if actor_exists:
        inventories.append({"CARROT": 0})
    obs = {"private": {"inventories": inventories, "shed": {"CARROT": shed_after}}}
    ns["_MPM_REPORT"].clear()
    ns["_MPM_REPORT"].update({"mismatches": 0, "events": []})
    ns["_mpm_reconcile"](st, obs, 0)
    assert st["credit"] == expected_credit, (label, st)
    assert st["carry"].get(1, 0) == 0, (label, st)
    return {"case": label, "credit": st["credit"], "remaining_carry": st["carry"].get(1, 0)}


def visit(sim, step, tile=(2, 3), unit=0, cmd=("PASS",)):
    sim.setdefault(step, []).append((tile[0], tile[1], list(cmd)))


def plan_case(ns, label, age2_steps, age3_steps=()):
    day = 12
    t0 = day * 24 + 4
    sim = {}
    visit(sim, t0 + 1)
    for step, unit in age2_steps:
        visit(sim, step, unit=unit)
    for step, unit in age3_steps:
        visit(sim, step, unit=unit)
    st = {"sim": sim}
    plan, why = ns["_mpm_plan"](st, t0, 0, (2, 3))
    return plan, why


def main():
    ns = load_helpers()
    cases = []
    cases.append(assert_delivery(ns, False, 10, 12, 2, "midnight_delivery_once"))
    cases.append(assert_delivery(ns, False, 10, 10, 0, "midnight_shed_overflow_uncredited"))

    same_time = [(14 * 24 + 5, 0), (14 * 24 + 5, 1)]
    plan, why = plan_case(ns, "duplicate_age2_falls_back", same_time, [(15 * 24 + 6, 0)])
    assert plan is not None and why is None and plan["harvest_day"] == 15, (plan, why)
    assert plan["jobs"][14 * 24 + 5][1] == ["WATER"]
    assert plan["jobs"][15 * 24 + 6][1] == ["HARVEST"]
    cases.append({"case": "duplicate_age2_falls_back", "result": "age3_fallback",
                  "jobs": len(plan["jobs"]), "harvest_day": plan["harvest_day"]})

    plan, why = plan_case(ns, "duplicate_age2_without_fallback", same_time)
    assert plan is None and why == "care_proof", (plan, why)
    cases.append({"case": "duplicate_age2_without_fallback", "result": why})

    distinct = [(14 * 24 + 5, 0), (14 * 24 + 6, 1)]
    plan, why = plan_case(ns, "distinct_age2", distinct)
    assert plan is not None and why is None and plan["harvest_day"] == 14, (plan, why)
    assert plan["jobs"][14 * 24 + 5][1] == ["WATER"]
    assert plan["jobs"][14 * 24 + 6][1] == ["HARVEST"]
    cases.append({"case": "distinct_age2", "result": "age2_water_then_harvest",
                  "jobs": len(plan["jobs"]), "harvest_day": plan["harvest_day"]})

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = {"status": "passed", "checks": len(cases), "cases": cases}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
