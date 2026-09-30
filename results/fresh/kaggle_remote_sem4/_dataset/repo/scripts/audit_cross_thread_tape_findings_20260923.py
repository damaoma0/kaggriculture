"""Read-only audit of completed panels; writes only a new synthesis artifact.

No simulations, policy changes, or additional qualification games are performed.
"""
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIDE = ROOT / "results/fresh/value_tape_wide_20260923_01a0"
FRESH = ROOT / "results/fresh/records_refresh_20260923"
OUT = ROOT / "results/fresh/tape_cross_thread_20260923_01a0"
SOURCES = {}


def read(path):
    data = path.read_bytes()
    SOURCES[path.relative_to(ROOT).as_posix()] = sha256(data).hexdigest()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def funnel(pairs):
    counts = Counter()
    days = {day: Counter() for day in (12, 15, 18)}
    for pair in pairs:
        for day in days:
            decision = read(WIDE / f"decisions/{pair['spec']['id']}-d{day}.json")
            counts["decisions"] += 1
            rows = decision["candidates"][1:]
            assert not decision["timed_out"]
            for row in rows:
                if row.get("early_rejection"):
                    reason = "cohort_loss_at_next_reveal"
                elif row.get("protection_failures"):
                    reason = "other_protection_failure"
                elif row["admitted"]:
                    reason = "admitted"
                elif not row.get("expanded"):
                    reason = "not_expanded_after_one_scenario"
                elif not row.get("fully_evaluated"):
                    assert len(row["predictions"]) == 4 and row["risk_score"] <= 0
                    reason = "nonpositive_four_scenario_risk_score"
                else:
                    reason = "failed_final_eight_scenario_gate"
                counts["alternatives"] += 1
                counts[reason] += 1
                days[day][reason] += 1
            counts["selected_decisions"] += decision["selected"] is not None
    return dict(counts=counts, by_day=days, games=len(pairs))


def main():
    pairs = [read(p) for p in sorted((WIDE / "pairs").glob("*.json"))]
    live = [p for p in pairs if p["spec"]["kind"] == "live"]
    anchored = [p for p in pairs if p["spec"].get("anchored")]
    clean_replay = [p for p in pairs if p["spec"]["kind"] == "replay"
                    and not p["spec"].get("anchored")
                    and not p["baseline_divergence"]["material_command_break"]
                    and not p["candidate_divergence"]["material_command_break"]]
    assert (len(pairs), len(live), len(anchored), len(clean_replay)) == (106, 64, 10, 21)
    fresh_design = read(FRESH / "fix_design.json")
    replay_ids = {p["spec"]["episode"] for p in pairs if p["spec"]["kind"] == "replay"}
    overlap = dict(
        v9_game_overlap=sorted(replay_ids & set(fresh_design["v9_sample"])),
        fresh_m1_record_overlap=sorted(replay_ids & set(fresh_design["all_new_m1"])),
        note="Keep the different sampling designs separate; do not pool headline means.",
    )

    case = "anchor-112109339"
    arm = read(WIDE / f"arms/{case}-baseline.json")
    recording = read(WIDE / "recordings/112109339.json.gz")
    assert arm["ledger_verified"] and arm["control_exact"]
    own, rival = arm["economics"]
    revenue_gap = {p: own["revenue"].get(p, 0) - rival["revenue"].get(p, 0)
                   for p in sorted(set(own["revenue"]) | set(rival["revenue"]))}
    spending_contribution = {p: rival["spend"].get(p, 0) - own["spend"].get(p, 0)
                            for p in sorted(set(own["spend"]) | set(rival["spend"]))}
    assert sum(revenue_gap.values()) + sum(spending_contribution.values()) == arm["margin"]
    daily = []
    for checkpoint in recording["observations"]:
        if checkpoint["step"] % 24 or checkpoint["step"] // 24 not in (6, 9, 12, 15, 18, 21, 24, 29):
            continue
        obs = checkpoint["seats"][0]
        farms = []
        for farm in obs["farms"]:
            counts = Counter()
            for row in farm["tiles"]:
                for tile in row:
                    if isinstance(tile, dict):
                        for field in ("crop", "animal"):
                            if tile.get(field):
                                counts[tile[field]] += 1
            farms.append(dict(cash=farm["money"], cohorts=counts))
        daily.append(dict(day=obs["day"], shops=obs["town"]["unlocked_shops"], farms=farms))
    decisions = []
    for day in (12, 15, 18):
        d = read(WIDE / f"decisions/{case}-d{day}.json")
        decisions.append(dict(day=day, selected=d["selected"], candidates=[
            {k: c.get(k) for k in ("route", "episode", "hamming", "distance",
                "mean_margin", "risk_score", "cash_deltas", "margin_deltas",
                "early_rejection", "protection_failures", "expanded", "fully_evaluated")}
            for c in d["candidates"]]))
    wool = []
    for seat in (0, 1):
        private = recording["observations"][-1]["seats"][seat]["private"]
        economy = arm["economics"][seat]
        wool.append(dict(
            harvested=arm["physical"][seat].get("produced:WOOL", 0),
            sold=economy["units"].get("WOOL", 0),
            revenue=economy["revenue"].get("WOOL", 0),
            average_sale_price=economy["revenue"]["WOOL"] / economy["units"]["WOOL"],
            held_at_finish=sum(inv.get("WOOL", 0) for inv in private["inventories"])
                           + private["shed"].get("WOOL", 0)))
    result = dict(
        protocol="Post-hoc read-only synthesis; no new game evidence or changed policy.",
        overlap=overlap,
        funnels={"live": funnel(live), "exact_native_recordings": funnel(anchored),
                 "other_recordings_without_major_command_failure": funnel(clean_replay)},
        snorlax=dict(episode=112109339, margin=arm["margin"], revenue_gap=revenue_gap,
                     spending_contribution=spending_contribution, wool=wool,
                     daily=daily, decisions=decisions),
        source_sha256=SOURCES,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("snorlax", "source_sha256")}, indent=2))
    print(json.dumps({k: v for k, v in result["snorlax"].items() if k != "decisions"}, indent=2))


if __name__ == "__main__":
    main()
