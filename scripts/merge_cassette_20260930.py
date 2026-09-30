"""Season cassette merged from DSM-only and pooled leader figures (user 2026-09-30: integrate the other leaders' count
figures; per-kind rule from the bias check): a row is DSM's own when DSM has the day's shop-type mix, else the pooled
row (fallback); from day `from_day` on, the animal and strawberry end counts come from the pooled row when it exists
(Victor / DECEM / M&M&P&Q match DSM there within +-1 / +-1-3), while tomatoes, melons, carrots, wheat plantings, hands and
land stay DSM's (the leaders' tomatoes and wheat are systematically different).

usage: merge_cassette_20260930.py DSM.json POOLED.json OUT.json [--from-day 12]"""
import argparse
import json
from pathlib import Path

POOLED_KINDS = ("COW", "SHEEP", "GOOSE", "STRAWBERRY")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dsm")
    ap.add_argument("pooled")
    ap.add_argument("out")
    ap.add_argument("--from-day", type=int, default=12)
    a = ap.parse_args()
    d, p = json.loads(Path(a.dsm).read_text()), json.loads(Path(a.pooled).read_text())
    table, stats = {}, {"dsm": 0, "fallback": 0, "pooled_kinds": 0}
    for day in sorted(set(d["table"]) | set(p["table"]), key=int):
        rows = {}
        dr, pr = d["table"].get(day, {}), p["table"].get(day, {})
        for mix in set(dr) | set(pr):
            if mix in dr:
                row = json.loads(json.dumps(dr[mix]))
                stats["dsm"] += 1
                if int(day) >= a.from_day and mix in pr:
                    for k in POOLED_KINDS:
                        if k in pr[mix]["end_counts"]:
                            row["end_counts"][k] = pr[mix]["end_counts"][k]
                    row["pooled_kinds"] = list(POOLED_KINDS)
                    stats["pooled_kinds"] += 1
            else:
                row = json.loads(json.dumps(pr[mix]))
                row["fallback_pooled"] = True
                stats["fallback"] += 1
            rows[mix] = row
        table[day] = rows
    out = dict(source=f"merge of {a.dsm} (DSM) and {a.pooled} (pooled)", submission=d.get("submission"),
               games=dict(dsm=d["games"], pooled=p["games"]), held_out=d.get("held_out"), days=d["days"],
               shop_types=d.get("shop_types"), rule=f"DSM rows; pooled fallback; from day {a.from_day} "
               f"{'/'.join(POOLED_KINDS)} from pooled", table=table)
    Path(a.out).write_text(json.dumps(out), encoding="utf-8")
    print(a.out, stats)


if __name__ == "__main__":
    main()
