"""Wheat intent -> field, day by day (full games, local_dsmfull, mean over the current-DSM worlds): per day
  plan     wheat plantings the planner / cassette asked for (proposal, after the cassette and the free-tile fill)
  tiler    wheat the tile compiler kept (realized plan) and what it clipped (capacity adjustments for today)
  planted  wheat seed bought that day / 10 (ours and DSM's)
  cash     money at dawn (end of the previous day), ours and DSM's
  land     quadrants at dawn (ours from the diagnostics, DSM from its land spend)
usage: wheat_chain_daywalk_20260929.py [CAND]"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"


def parse(v):
    if isinstance(v, (dict, list)):
        return v
    try:
        return ast.literal_eval(v)
    except Exception:
        return {}


def main():
    cand = sys.argv[1] if len(sys.argv) > 1 else "n18rc99"
    cases = [c["id"] for c in json.loads((H / "dsmseat_cases.json").read_text())["cases"] if c["id"].startswith("dsm3q-")]
    n = len(cases)
    rows = {d: dict(plan=0, kept=0, clip=0, ours=0, dsm=0, cash_o=0, cash_d=0, land_o=0, land_d=0, clip_what={}) for d in range(6, 29)}
    for cid in cases:
        r = json.loads((H / "local_dsmfull" / cand / f"{cid}.json").read_text())
        c = json.loads((H / "local_dsmfull/_controls" / f"{cid}.json").read_text())
        s = r["case"]["seat"]
        diag = {}
        for dd in r["diagnostics"][s]:
            for e in (dd.get("diagnostics") or []):
                if isinstance(e, dict) and e.get("phase") == "semantic":
                    diag[int(e["day"])] = e
        land_d = 1
        for d in range(0, 29):
            sp_d = c["daily"][s][d + 1]["spend"].get("BUY_LAND", 0) - c["daily"][s][d]["spend"].get("BUY_LAND", 0)
            if d in rows:
                R = rows[d]
                e = diag.get(d, {})
                pc = parse(e.get("proposal", {})).get("plant_counts", {}) if e else {}
                rp = parse(e.get("realized_plan", {})).get("plant_counts", {}) if e else {}
                clips = [x for x in parse(e.get("capacity_adjustments", "[]")) if isinstance(x, dict) and int(x.get("day", -1)) == d] if e else []
                R["plan"] += pc.get("WHEAT", 0) / n
                R["kept"] += rp.get("WHEAT", 0) / n
                for x in clips:
                    R["clip_what"][x.get("crop")] = R["clip_what"].get(x.get("crop"), 0) + (x.get("requested", 0) - x.get("actual", 0)) / n
                R["ours"] += (r["daily"][s][d + 1]["spend"].get("BUY_SEED:WHEAT", 0) - r["daily"][s][d]["spend"].get("BUY_SEED:WHEAT", 0)) / 10 / n
                R["dsm"] += (c["daily"][s][d + 1]["spend"].get("BUY_SEED:WHEAT", 0) - c["daily"][s][d]["spend"].get("BUY_SEED:WHEAT", 0)) / 10 / n
                R["cash_o"] += r["daily"][s][d]["money"] / n
                R["cash_d"] += c["daily"][s][d]["money"] / n
                farm = None
                for dd in r["diagnostics"][s]:
                    if int(dd.get("day", -1)) == d:
                        farm = dd.get("farm")
                R["land_o"] += len((farm or {}).get("unlocked_quadrants", [])) / n
                R["land_d"] += land_d / n
            land_d += {1000: 1, 2000: 1, 3000: 2, 4000: 1}.get(int(sp_d), 0) if sp_d else 0
    print(f"{'day':>3} | {'plan wheat':>10} | {'tiler kept':>10} | clipped (crop: units)      | {'planted DSM/ours':>16} | {'dawn cash DSM/ours':>18} | {'land DSM/ours':>13}")
    for d, R in rows.items():
        cl = ", ".join(f"{k[:4]} {v:.1f}" for k, v in R["clip_what"].items() if v >= 0.1) or "-"
        print(f"{d:3d} | {R['plan']:10.1f} | {R['kept']:10.1f} | {cl:26s} | {R['dsm']:6.1f} / {R['ours']:6.1f} | {R['cash_d']:8.0f} / {R['cash_o']:7.0f} | {R['land_d']:5.1f} / {R['land_o']:4.1f}")


if __name__ == "__main__":
    main()
