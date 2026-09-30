"""KB115LT2 on DSM's recorded plan (tile-exact via the TilePlanView interface, DSM's opening replayed for days 0-10 exactly
as the season harness does, DSM's recorded shops forced) in DSM's seat of a recorded DSM world - against the LIVE
packaged mgt_v9lite (the semantic-strategy study's opponent package) instead of DSM's recorded opponent actions.
Official time rules for both players (1 s a step + 60 s overage); each player's per-step times and the engine's remaining
bank are saved. Game loop: the study's frozen tape_vs_bench._play (both farms' daily ledgers, forced shops).

--arm TAPE replays DSM's own recorded actions (open loop) in its seat instead of an agent.
usage: kb_vs_v9_20260929.py --games team:ep,... --arm KB115LT2|TAPE --out DIR [--workers 4] [--spec SPEC.json] [--no-timeout]
out: DIR/<ep>.json per game, DIR/summary.json"""
import argparse
import copy
import gzip
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_strategy_20260928"
HARNESS = STUDY / "candidates/strategy_v8_kb115lt2_readiness/harness"


def _game(args):
    game, arm, spec_path, out, no_timeout = args
    for p in (str(ROOT / "scripts"), str(HARNESS)):
        if p not in sys.path:
            sys.path.insert(0, p)
    for f in list(STUDY.rglob("*.gz.raw")):        # bundle KGR_GZ_RAW payloads (hash-checked opponent files)
        try:
            f.rename(str(f)[:-4])
        except OSError:
            pass
    row = dict(game=game, arm=arm, completed=False, errors=[])
    timings = [[], []]
    try:
        import importlib.util
        import sector_run as SR
        import run_arms as RA
        import xfix_run as X
        import lead_g1
        import tape_vs_bench as TV
        spec = importlib.util.spec_from_file_location("frozen_gate", HARNESS / "semantic_strategy_gate_20260928.py")
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        from kaggle_environments import make
        from kaggle_environments.envs.kaggriculture import kaggriculture as E
        SR.setup()
        RA.register(json.loads((ROOT / spec_path).read_text(encoding="utf-8")))
        team, ep = game.split(":")
        tape = X.tape_of(game)
        sem = json.load(gzip.open(lead_g1.SEM / team / f"{ep}.json.gz", "rt", encoding="utf-8"))
        seat, seed = int(tape["seat"]), tape["seed"]
        shops_by_day = [list(tape["shops"][:min(8, d // 3)]) for d in range(31)]
        mod = None
        if arm == "TAPE":                          # DSM's own recorded actions, open loop, all 719 steps
            pass
        else:
            path, cfg = SR.ARMS[arm]
            mod = X.load_module(path, "kbv9_" + arm)
            h = X.Handoff(mod, dict(X.BASE, **cfg), tape, hand=X.D, stop=None)
            h.configure(sem)
        protocol = json.loads((STUDY / "protocol.json").read_text())
        G.verify_files(STUDY / "opponent/pkg", protocol["opponent"]["files"])
        fn, fn_cfg, _ = G.load_entry(STUDY / protocol["opponent"]["entry"], STUDY / "opponent/pkg")
        # --no-timeout: research mode (as the season panels, lead_ledger's KAGG_NO_TIMEOUT); the packaged V9-lite sizes its
        # search by fixed per-reveal caps and the remaining bank, which then stays at 60 s (its caps bind in official games)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 100000 if no_timeout else 1},
                   info={"seed": seed})

        def player(index):
            def act(obs, step):
                tick = time.perf_counter()
                try:
                    if index == seat:
                        if mod is None:
                            acts = tape["actions"]
                            a_ = acts[step] if step < len(acts) and isinstance(acts[step], dict) else None
                            return copy.deepcopy(a_) if a_ else {"farmer": ["PASS"], "hands": [], "market": []}
                        return h.agent(obs, env.configuration)
                    return fn(obs, env.configuration) if fn_cfg else fn(obs)
                except Exception:
                    row["errors"].append(dict(seat=index, step=step, tb=traceback.format_exc()[-1500:]))
                    raise
                finally:
                    timings[index].append(time.perf_counter() - tick)
            return act
        res = TV._play(E, env, [player(0), player(1)], seat, shops_by_day, None, None, 1 - seat)
        final = res["final"]
        daily = res["daily"]
        row.update(completed=True, seat=seat, seed=seed, cash=final[seat], opponent_cash=final[1 - seat],
                   margin=final[seat] - final[1 - seat], daily=daily,
                   money_by_day={str(d): [daily[seat][d]["money"], daily[1 - seat][d]["money"]] for d in range(len(daily[seat]))},
                   engine=dict(statuses=[s.status for s in env.state],
                               remaining_overage=[s.observation.get("remainingOverageTime") for s in env.state]),
                   tp_leak=dict(getattr(mod, "_TP_LEAK", {}) or {}))
    except Exception:
        row["error"] = traceback.format_exc()[-3000:]
    row["timings_sum"] = [round(sum(t), 1) for t in timings]
    row["overage_used"] = [round(sum(max(0.0, x - 1.0) for x in t), 1) for t in timings]
    row["calls_over_1s"] = [sum(1 for x in t if x > 1.0) for t in timings]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / f"{game.split(':')[1]}.json").write_text(json.dumps(row, default=str))
    return {k: row.get(k) for k in ("game", "completed", "seat", "cash", "opponent_cash", "margin", "overage_used", "error")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True)
    ap.add_argument("--arm", default="KB115LT2")
    ap.add_argument("--spec", default="results/fresh/threads_20260928/animal/spec.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-timeout", action="store_true")
    a = ap.parse_args()
    games = a.games.split(",")
    out = str((ROOT / a.out).resolve())
    from concurrent.futures import ProcessPoolExecutor, as_completed
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
        futs = [pool.submit(_game, (g, a.arm, a.spec, out, a.no_timeout)) for g in games]
        for fu in as_completed(futs):
            try:
                r = fu.result()
            except Exception as exc:
                r = dict(error=repr(exc))
            rows.append(r)
            print(json.dumps(r, default=str)[:600], flush=True)
    (Path(out) / "summary.json").write_text(json.dumps(rows, indent=1, default=str))
    ok = [r for r in rows if r.get("completed")]
    print(f"{len(ok)}/{len(rows)} completed; wins {sum(r['margin'] > 0 for r in ok)}; mean margin "
          f"{sum(r['margin'] for r in ok) / max(1, len(ok)):+.0f}", flush=True)


if __name__ == "__main__":
    main()
