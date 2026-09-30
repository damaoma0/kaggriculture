"""Replay one forced late tape switch and compare it with the no-switch control.

The target recording is withheld from the router until the chosen day.  Then
the router is forced onto that recording in the *same* world, with the same
recorded shop path and a live opponent.  The control keeps the target hidden.
This is a transition diagnostic with hindsight, not a deployable policy.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mgt_loo  # noqa: E402
from mgt_dead import classify  # noqa: E402

OUT = ROOT / "results" / "fresh" / "tape_switch_probe_20260923"


def target_path(episode: str) -> Path:
    for submission in ("56266758", "56266899"):
        path = ROOT / "data" / "mg_tapes" / submission / f"{episode}.json.gz"
        if path.exists():
            return path
    raise FileNotFoundError(episode)


def diagnostic_run(path: Path, arm: str, own_seat: int) -> tuple[dict, dict]:
    """Capture invalid commands and live assets before running the official engine."""
    record = {"failed_commands": [], "day_start": []}
    original_play = mgt_loo.TV._play

    def observed_play(engine, env, players, record_seat, *args, **kwargs):
        original_agent = players[own_seat]

        def observed_agent(obs, step):
            action = original_agent(obs, step)
            farm = obs["farms"][own_seat]
            if step % 24 == 0:
                assets = Counter()
                board = []
                for y, row in enumerate(farm["tiles"]):
                    for x, tile in enumerate(row):
                        if isinstance(tile, dict):
                            item = tile.get("animal") or tile.get("crop")
                            if item:
                                assets[item] += 1
                                board.append([x, y, item, tile.get("planted_day"), tile.get("yield_units"), tile.get("pending_care_bonus")])
                record["day_start"].append({"day": step // 24, "cash": farm["money"], "assets": dict(assets), "board": board})
            if step >= 16 * 24:
                units = [farm["farmer"]] + list(farm["hands"])
                commands = [action.get("farmer")] + list(action.get("hands") or [])
                private = obs.get("private") or {}
                shed = private.get("shed") or {}
                seeds = private.get("seeds") or {}
                inventories = private.get("inventories") or []
                for unit_index, (unit, command) in enumerate(zip(units, commands)):
                    if not command:
                        continue
                    x, y = int(unit[0]), int(unit[1])
                    tile = farm["tiles"][y][x]
                    inventory = inventories[unit_index] if unit_index < len(inventories) else {}
                    failure = classify(command, (x, y), tile, inventory, shed, seeds)
                    if failure:
                        record["failed_commands"].append({"step": step, "day": step // 24,
                            "unit": unit_index, "position": [x, y], "command": command,
                            "tile": tile, "failure": failure})
            return action

        wrapped = list(players)
        wrapped[own_seat] = observed_agent
        return original_play(engine, env, wrapped, record_seat, *args, **kwargs)

    mgt_loo.TV._play = observed_play
    try:
        result = mgt_loo.run(("mgtape_vs_mgt_m1o", "mgt_m1o", arm, str(path)))
    finally:
        mgt_loo.TV._play = original_play
    return result, record


def run(episode: str, day: int) -> dict:
    path = target_path(episode)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        target = json.load(stream)
    own_seat = 1 - int(target["seat"])
    mgt_loo.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    control, control_trace = diagnostic_run(path, "mg_vs", own_seat)
    switch, switch_trace = diagnostic_run(path, f"mg_late{day}", own_seat)
    switched_history = switch.get("rival_history") or []
    control_history = control.get("rival_history") or []
    chosen_before = next((h[1] for h in reversed(switched_history) if h[0] < day), None)
    own_margin_switch = -switch["margin"]
    own_margin_control = -control["margin"]
    result = {
        "episode": int(episode),
        "switch_day": day,
        "target_tape": int(episode),
        "tape_before_switch": chosen_before,
        "shops": switch["shops"],
        "own_margin_control": own_margin_control,
        "own_margin_switch": own_margin_switch,
        "own_margin_delta": own_margin_switch - own_margin_control,
        "own_cash_delta": switch["rival_final"] - control["rival_final"],
        "opponent_cash_delta": switch["final"] - control["final"],
        "control_history": control_history,
        "switch_history": switched_history,
        "control_router_report": control.get("rival_report"),
        "switch_router_report": switch.get("rival_report"),
        "control_overlay_report": control.get("rival_sheep"),
        "switch_overlay_report": switch.get("rival_sheep"),
        "control_cash_daily": control.get("cash_daily"),
        "switch_cash_daily": switch.get("cash_daily"),
        "control_trace": control_trace,
        "switch_trace": switch_trace,
        "source_control": str(OUT / f"mgtape_vs_mgt_m1o-mg_vs-{episode}.json"),
        "source_switch": str(OUT / f"mgtape_vs_mgt_m1o-mg_late{day}-{episode}.json"),
    }
    out = OUT / f"probe-{episode}-d{day}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    episode = sys.argv[1] if len(sys.argv) > 1 else "109534325"
    day = int(sys.argv[2]) if len(sys.argv) > 2 else 18
    result = run(episode, day)
    print(json.dumps({key: result[key] for key in (
        "episode", "switch_day", "target_tape", "tape_before_switch",
        "own_margin_control", "own_margin_switch", "own_margin_delta",
        "own_cash_delta", "opponent_cash_delta", "source_switch",
    )}, indent=2))


if __name__ == "__main__":
    main()
