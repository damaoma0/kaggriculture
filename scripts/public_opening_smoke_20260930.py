"""Day-11 opening smoke of a public Kaggriculture agent (user 2026-09-30: "see if any of them fixes the opening problem
... One smoke run to day 11 would be enough. They must also buy 4 quadrants").

The agent plays DSM's seat from step 0 in one DSM-new world (results/fresh/semantic_h2h_20260929/study/recordings_d4q9):
forced shops, the recorded opponent with its logged weeds and exact purchase credit (the harness's leader_weeds /
leader_credit_exact); after step 263 our seat passes. Reports when each quadrant was bought, cash at each dawn, the
day-11 dawn board, and the same for DSM's own game in that world.

usage: public_opening_smoke_20260930.py AGENT_DIR EP [--steps 264]"""
import argparse
import gzip
import json
import os
import sys
import time
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
HARNESS = STUDY / "candidates/d9e68b115518441/harness"
GAMES = ROOT / "results/fresh/dsm4q_d9_20260930/games"
PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def label(t):
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    return t.get("crop") or t.get("animal") or t.get("kind")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_dir")
    ap.add_argument("ep")
    ap.add_argument("--steps", type=int, default=264)
    a = ap.parse_args()
    import semantic_h2h_20260929 as SH
    sys.path.insert(0, str(HARNESS))
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    agent_dir = Path(a.agent_dir).resolve()
    rec = json.loads(gzip.decompress((STUDY / f"recordings_d4q9/{a.ep}.json.gz").read_bytes()))
    seat, lead = int(rec["seat"]), 1 - int(rec["seat"])
    SH._leader_credit_exact(lead, json.loads((ROOT / f"results/fresh/semantic_h2h_20260929/leader_commits/d4q9-{a.ep}.json")
                                             .read_text())["steps"])
    spawns = json.loads((GAMES / f"d4q9-{a.ep}.dsm.result.spawns.json").read_text())[lead]
    sys.path.insert(0, str(agent_dir))
    cwd = os.getcwd()
    os.chdir(agent_dir)
    fn = get_last_callable((agent_dir / "main.py").read_text(encoding="utf-8"), path=str(agent_dir / "main.py"))
    os.chdir(cwd)
    env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 100000}, info={"seed": rec["seed"]})
    snaps, errors, times = {}, [], []

    def ours(obs, t):
        f = obs["farms"][seat]
        if t % 24 == 0:
            snaps[t // 24] = dict(money=f["money"], q=list(f.get("unlocked_quadrants") or []),
                                  hands=len(f.get("hands") or []), board=[label(x) for row in f["tiles"] for x in row])
        if t >= a.steps:
            return PASS
        t0 = time.perf_counter()
        try:
            r = fn(obs, env.configuration)
        except Exception:
            errors.append((t, traceback.format_exc()[-800:]))
            r = PASS
        times.append(time.perf_counter() - t0)
        return r

    def opp(obs, t):
        x = rec["opp_actions"][t] if t < len(rec["opp_actions"]) else None
        return deepcopy(x) if x else PASS
    players = [ours, opp] if seat == 0 else [opp, ours]
    TV._play(E, env, players, seat, rec["shops"], spawns, lead, lead)
    dsm = json.loads(gzip.open(GAMES / f"d4q9-{a.ep}.dsm.game.json.gz", "rt", encoding="utf-8").read())
    qd = {}
    for fr in dsm["frames"]:
        qd.setdefault(fr["q"], fr["t"])
    q_ours = {}
    for d in sorted(snaps):
        for q in snaps[d]["q"]:
            q_ours.setdefault(q, d)
    d11 = snaps.get(a.steps // 24, {})
    bd = [label(dsm["tiles"][i]) for i in dsm["frames"][min(a.steps, len(dsm["frames"]) - 1)]["b"]]
    cnt, cntd = Counter(d11.get("board", [])), Counter(bd)
    comp = sum(abs(cnt[k] - cntd[k]) for k in set(cnt) | set(cntd) if k != "LOCKED") / 2
    print(json.dumps(dict(
        agent=agent_dir.parent.name, ep=a.ep, seat=seat, errors=len(errors), first_error=errors[0] if errors else None,
        max_step_s=round(max(times), 2) if times else None, total_s=round(sum(times), 1),
        quadrants_d11=len(d11.get("q", [])), quadrant_first_seen_day=q_ours,
        dsm_quadrant_steps={k: f"day {v // 24} h{v % 24}" for k, v in qd.items()},
        cash_by_dawn={d: round(snaps[d]["money"]) for d in range(6, a.steps // 24 + 1) if d in snaps},
        dsm_cash_by_dawn={d: round(dsm["frames"][24 * d]["m"][0]) for d in range(6, a.steps // 24 + 1)},
        hands_d10=snaps.get(10, {}).get("hands"),
        board_d11={k: v for k, v in sorted(cnt.items()) if k not in ("LOCKED",)},
        dsm_board_d11={k: v for k, v in sorted(cntd.items()) if k not in ("LOCKED",)},
        composition_distance=comp)))


if __name__ == "__main__":
    main()
