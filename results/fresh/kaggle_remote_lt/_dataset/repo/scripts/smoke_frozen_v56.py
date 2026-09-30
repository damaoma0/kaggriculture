"""Eight-game development smoke check: unchanged mgt_m1 versus frozen public v56."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_production_modules as B  # noqa: E402

OUT = ROOT / "results" / "fresh" / "tape_gap_plans" / "v56_baseline_smoke"
V56 = ROOT / "data" / "router_refresh_20260922" / "v56" / "main.py"
SEEDS = (93021000, 93021001, 93021002, 93021003)


def worker(job):
    # Set the opponent in the worker because Windows workers use spawn.
    B.OPPONENTS["v56"] = V56
    return B.run(job)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    own_loaded_hash = sha256((ROOT / 'agents/mgt_m1.py').read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    v56_loaded_hash = sha256(V56.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    jobs = [("mgt_m1", seed, seat, "v56", str(OUT)) for seed in SEEDS for seat in (0, 1)]
    rows = []
    with ProcessPoolExecutor(max_workers=2, max_tasks_per_child=1) as pool:
        futures = [pool.submit(worker, job) for job in jobs]
        for future in as_completed(futures):
            row = future.result()
            assert row['sha256'] == own_loaded_hash and row['opponent_sha256'] == v56_loaded_hash
            assert row["statuses"] == ["DONE", "DONE"], row
            assert row["actions"] == 719, row
            ledger = row["ledger"]
            assert row["cash"] == 3000 + sum(ledger["revenue"].values()) - sum(ledger["spend"].values()), row
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("seed", "seat", "cash", "opponent_cash", "margin", "action_sha256")}), flush=True)
    rows.sort(key=lambda r: (r["seed"], r["seat"]))
    margins = [r["margin"] for r in rows]
    shop_types = {}
    for r in rows:
        shops = r["shops"]
        # The first revealed shop is the first element at the first 3-day reveal.
        shop_types[str(r["seed"])] = shops[0] if shops else None
    summary = {
        "design": "Development smoke only; unchanged mgt_m1 versus frozen public v56, natural RNG, both seats, 4 seeds. Sealed 93022000 block untouched.",
        "games": len(rows), "seeds": list(SEEDS), "workers": 2,
        "win_tie_loss": {"wins": sum(m > 0 for m in margins), "ties": sum(m == 0 for m in margins), "losses": sum(m < 0 for m in margins)},
        "mean_margin": sum(margins) / len(margins),
        "mean_cash": sum(r["cash"] for r in rows) / len(rows),
        "mean_opponent_cash": sum(r["opponent_cash"] for r in rows) / len(rows),
        "shop_types_by_seed": shop_types,
        "status_check": "all eight rows DONE/DONE with 719 actions and reconciled own cash ledger",
        "hashes": {
            "mgt_m1": sha256((ROOT / "agents" / "mgt_m1.py").read_bytes()).hexdigest(),
            "v56": sha256(V56.read_bytes()).hexdigest(),
            "mgt_m1_loaded_text": own_loaded_hash,
            "v56_loaded_text": v56_loaded_hash,
        },
        "hash_note": "Frozen hashes use file bytes; legacy per-game sha256 hashes UTF-8 source after Python newline normalization. Both are checked.",
        "rows": rows,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("games", "win_tie_loss", "mean_margin", "shop_types_by_seed", "hashes")}, indent=2))


if __name__ == "__main__":
    main()
