"""Where our live submission loses on the ladder (user 2026-09-30: "inspect some latest games of our latest published
version against ladder opponents" / "Where we lost"). The compact ladder games (scripts/ladder_panel_fetch.py ->
data/ladder_panel/<sub>/) are replayed exactly through the frozen harness (source control: both recorded command streams,
both cash totals must match the live result) to get per-day, per-product ledgers for both sides; the report compares
the losses with the wins. Does not touch ladder_cases.json (the shared validation panel): recordings go to
study/recordings_live_<sub>/ and cases/outputs to results/fresh/ladder_live_20260930/<sub>/.

usage: ladder_live_losses_20260930.py run --sub 56676484 [--workers 1]
       ladder_live_losses_20260930.py report --sub 56676484 [--last N]"""
import argparse
import gzip
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
H = ROOT / "results/fresh/semantic_h2h_20260929"
STUDY = H / "study"
OUT = ROOT / "results/fresh/ladder_live_20260930"
PRODUCTS = ["WHEAT", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "MILK", "WOOL", "EGG", "FERTILIZER"]


def build_cases(sub):
    rec_dir = STUDY / f"recordings_live_{sub}"
    rec_dir.mkdir(exist_ok=True)
    cases = []
    for p in sorted((ROOT / "data/ladder_panel" / sub).glob("*.json.gz")):
        try:                                       # the fetch may still be writing this one; the next run picks it up
            x = json.load(gzip.open(p, "rt", encoding="utf-8"))
        except (OSError, EOFError, ValueError):
            continue
        rec = dict(episode=x["episode"], seat=int(x["seat"]), seed=int(x["seed"]), names=x["names"], rewards=x["rewards"],
                   opponent=x.get("opponent"), shops=x["shops"], our_actions=x["our_actions"], opp_actions=x["opp_actions"],
                   source=p.relative_to(ROOT).as_posix())
        dst = rec_dir / p.name
        if not dst.exists():
            dst.write_bytes(gzip.compress(json.dumps(rec).encode(), mtime=0))
        opp = x.get("opponent") or {}
        seat = int(x["seat"])
        cases.append(dict(id=f"lad-{x['episode']}", episode=str(x["episode"]), created=x.get("created"), seed=int(x["seed"]),
                          seat=seat, file=f"recordings_live_{sub}/{p.name}",
                          sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),
                          opponent=opp.get("team") or x["names"][1 - seat], opponent_submission=opp.get("submission"),
                          replaced=f"our live submission {sub}", live_margin=x["rewards"][seat] - x["rewards"][1 - seat]))
    return cases


def run(a):
    import semantic_h2h_20260929 as SH
    out = OUT / a.sub
    out.mkdir(parents=True, exist_ok=True)
    cases = build_cases(a.sub)
    (out / "cases.json").write_text(json.dumps(dict(note=f"ladder games of {a.sub}", cases=cases), indent=1), "utf-8")
    harness = STUDY / "candidates/n18/harness"
    jobs = [dict(study=str(STUDY), case=c, kind="source_control", output=str(out / f"{c['id']}.json"), candidate="n18",
                 leader_weeds=True) for c in cases if not (out / f"{c['id']}.json").exists()]
    print(f"{len(cases)} games, {len(jobs)} to replay", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
        for r in pool.map(SH._worker, [(str(harness), j, True) for j in jobs]):
            print(r.get("case", {}).get("id"), "cash match", r.get("recorded_cash_match"), "margin", r.get("margin"),
                  flush=True)


def _spend_group(k):
    if k.startswith("BUY_SEED"):
        return "seeds"
    if k.startswith("BUY_ANIMAL"):
        return "animals"
    if k == "BUY_PRODUCT:WHEAT":
        return "wheat_bought"
    if k == "BUY_PRODUCT:FERTILIZER":
        return "fert_bought"
    return {"HIRE": "hires", "BUY_LAND": "land"}.get(k, k)


def load(sub):
    out = OUT / sub
    cases = json.loads((out / "cases.json").read_text("utf-8"))["cases"]
    games = []
    for c in cases:
        f = out / f"{c['id']}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text("utf-8"))
        s = int(c["seat"])
        d = r["daily"]
        g = dict(case=c, ok=bool(r.get("completed") and r.get("recorded_cash_match")), cash=r["cash"],
                 opp_cash=r["opponent_cash"], margin=r["margin"],
                 day_margin=[d[s][t]["money"] - d[1 - s][t]["money"] for t in range(len(d[s]))])
        for side, i in (("us", s), ("them", 1 - s)):
            e = d[i][-1]
            g[side] = dict(rev=e["revenue"], units=e["sold_units"], spend={}, tile_hours=e["tile_hours"],
                           produced={k[9:]: v for k, v in e["physical"].items() if k.startswith("produced:")},
                           commands=e["physical"].get("commands", 0))
            for k, v in e["spend"].items():
                g[side]["spend"][_spend_group(k)] = g[side]["spend"].get(_spend_group(k), 0) + v
            g[side]["spend_raw"] = e["spend"]
        games.append(g)
    return games


# product P&L = its revenue minus its own inputs (seeds, animals, bought-back product), so a wheat trader's purchases and
# resales net out; hires and land are overhead. Sum of all lines + 3000 = final cash (ledgers reconcile exactly).
INPUTS = {"WHEAT": ["BUY_SEED:WHEAT", "BUY_PRODUCT:WHEAT"], "STRAWBERRY": ["BUY_SEED:STRAWBERRY"],
          "MELON": ["BUY_SEED:MELON"], "TOMATO": ["BUY_SEED:TOMATO"], "CARROT": ["BUY_SEED:CARROT"],
          "MILK": ["BUY_ANIMAL:COW"], "WOOL": ["BUY_ANIMAL:SHEEP"], "EGG": ["BUY_ANIMAL:GOOSE"],
          "FERTILIZER": ["BUY_PRODUCT:FERTILIZER"]}
LINES = PRODUCTS + ["hires", "land"]


def pnl(side):
    out = {p: side["rev"].get(p, 0) - sum(side["spend_raw"].get(k, 0) for k in INPUTS[p]) for p in PRODUCTS}
    out["hires"] = -side["spend_raw"].get("HIRE", 0)
    out["land"] = -side["spend_raw"].get("BUY_LAND", 0)
    return out


def report(a):
    games = sorted(load(a.sub), key=lambda g: g["case"].get("created") or "")
    if a.last:
        games = games[-a.last:]
    bad = [g for g in games if not g["ok"]]
    games = [g for g in games if g["ok"]]
    for g in games:
        pu, pt = pnl(g["us"]), pnl(g["them"])
        g["pnl"] = {k: pu[k] - pt[k] for k in LINES}
        assert abs(sum(g["pnl"].values()) - g["margin"]) < 1, g["case"]["id"]
    loss = [g for g in games if g["margin"] < 0]
    win = [g for g in games if g["margin"] > 0]
    print(f"{a.sub}: {len(games)} exact replays ({len(bad)} not reproduced), {len(win)} W / {len(loss)} L")

    def mean(xs):
        xs = list(xs)
        return sum(xs) / len(xs) if xs else 0.0

    print("\nmargin by line, mean per game (us - them; product = revenue - its seeds / animals / bought-back units)")
    print(f"{'line':12s} {'losses':>8s} {'wins':>8s} {'L - W':>8s}   losses: volume / price effect")
    for k in LINES:
        lo, wi = mean(g["pnl"][k] for g in loss), mean(g["pnl"][k] for g in win)
        vp = ""
        if k in PRODUCTS:                          # revenue gap = (units ours - theirs) x their price + our units x price gap
            vol = mean((g["us"]["units"].get(k, 0) - g["them"]["units"].get(k, 0))
                       * g["them"]["rev"].get(k, 0) / max(g["them"]["units"].get(k, 0), 1) for g in loss)
            pri = mean(g["us"]["units"].get(k, 0) * (g["us"]["rev"].get(k, 0) / max(g["us"]["units"].get(k, 0), 1)
                       - g["them"]["rev"].get(k, 0) / max(g["them"]["units"].get(k, 0), 1)) for g in loss)
            vp = f"   {vol:8.0f} / {pri:8.0f}"
        print(f"{k:12s} {lo:8.0f} {wi:8.0f} {lo - wi:8.0f}{vp}")
    print(f"{'MARGIN':12s} {mean(g['margin'] for g in loss):8.0f} {mean(g['margin'] for g in win):8.0f}")
    print(f"{'our cash':12s} {mean(g['cash'] for g in loss):8.0f} {mean(g['cash'] for g in win):8.0f}")
    print(f"{'their cash':12s} {mean(g['opp_cash'] for g in loss):8.0f} {mean(g['opp_cash'] for g in win):8.0f}")

    print("\nunits sold / average price, per game: losses us / them | wins us / them")
    for p in PRODUCTS:
        row = []
        for gs in (loss, win):
            n = max(len(gs), 1)
            uu, ut = sum(g["us"]["units"].get(p, 0) for g in gs), sum(g["them"]["units"].get(p, 0) for g in gs)
            ru, rt = sum(g["us"]["rev"].get(p, 0) for g in gs), sum(g["them"]["rev"].get(p, 0) for g in gs)
            row.append(f"{uu / n:5.0f} @{ru / max(uu, 1):5.1f} / {ut / n:5.0f} @{rt / max(ut, 1):5.1f}")
        print(f"  {p:10s} " + " | ".join(row))

    print("\nmargin by day (cash difference), mean: losses / wins")
    for t in (3, 6, 9, 11, 12, 15, 18, 21, 24, 27, 30):
        print(f"  day {t:2d}: {mean(g['day_margin'][t] for g in loss):8.0f} / {mean(g['day_margin'][t] for g in win):8.0f}")

    print("\nlosses (oldest first): margin, cash, day-11/18/24 cash margin, the three worst and two best lines")
    for g in loss:
        c = g["case"]
        top = sorted(((v, k) for k, v in g["pnl"].items()), key=lambda x: x[0])
        print(f"  {c['episode']} s{c['seat']} {c['opponent'][:26]:26s} {c['opponent_submission']} {g['margin']:7.0f}"
              f"  {g['cash']:6.0f} v {g['opp_cash']:6.0f}  d11 {g['day_margin'][11]:6.0f} d18 {g['day_margin'][18]:6.0f}"
              f" d24 {g['day_margin'][24]:6.0f} | " + ", ".join(f"{k} {v:+.0f}" for v, k in top[:3])
              + " | " + ", ".join(f"{k} {v:+.0f}" for v, k in top[-2:]))
    if a.json:
        Path(a.json).write_text(json.dumps([dict(case=g["case"], margin=g["margin"], cash=g["cash"], opp_cash=g["opp_cash"],
                                                 pnl=g["pnl"], day_margin=g["day_margin"], us=g["us"], them=g["them"])
                                            for g in games]), "utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--sub", default="56676484")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    run(a) if a.cmd == "run" else report(a)
