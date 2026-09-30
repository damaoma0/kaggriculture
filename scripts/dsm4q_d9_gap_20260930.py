"""Us vs the new DSM (56692773, four quadrants) on days 9-11 from an exact day-8 handover (user 2026-09-30: "investigate
discrepancy between us and new DSM during days 9-11, assuming an exact handover from day 8").

Each case is one recorded DSM-new game, our seat = DSM's seat, the opponent replays its recorded commands (exact market
credit, recorded weeds). Two official-engine games per case, every step recorded (board, units, shed, commands, cash,
prices; the frame format of scripts/b2b_replay_20260929.py):
  dsm   DSM continuing its own game (source control; must reproduce both recorded cash totals)
  ours  our seat replays DSM's recorded commands for steps 0-215 (days 0-8), the candidate plays from the day-9 dawn
Nothing of the other threads' case files is touched: recordings study/recordings_d4q9/, ids d4q9-<episode>, leader
commits results/fresh/semantic_h2h_20260929/leader_commits/d4q9-*.json, games results/fresh/dsm4q_d9_20260930/.

usage: dsm4q_d9_gap_20260930.py cases [--tapes data/leader_tapes/16732748_56692773]
       dsm4q_d9_gap_20260930.py run [--cand n18rc223d] [--prefix 216] [--workers 2] [--only ID,ID] [--limit N]
       dsm4q_d9_gap_20260930.py report [--cand n18rc223d] [--prefix 216]
       dsm4q_d9_gap_20260930.py viewer CASE_ID [--cand n18rc223d] [--prefix 216]"""
import argparse
import base64
import gzip
import hashlib
import json
import os
import statistics as st
import subprocess
import sys
import types
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
STUDY = H / "study"
OUT = ROOT / "results/fresh/dsm4q_d9_20260930"
sys.path.insert(0, str(ROOT / "scripts"))
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
TILE_KEYS = ("kind", "crop", "animal", "yield_units", "planted_day", "placed_day", "fertilized_until_day",
             "watered_today", "fed_today", "cared_today", "pending_care_bonus", "max_lifespan_step")
SEED = dict(WHEAT=10, CARROT=20, TOMATO=50, STRAWBERRY=100, MELON=80)
ANIMAL = dict(COW=400, SHEEP=500, GOOSE=300)


def cases_path():
    return OUT / "cases.json"


def build_cases(a):
    rec_dir = STUDY / "recordings_d4q9"
    rec_dir.mkdir(exist_ok=True)
    cases = []
    for src in sorted((ROOT / a.tapes).glob("*.json.gz")):
        t = json.load(gzip.open(src, "rt", encoding="utf-8"))
        seat = int(t["seat"])
        if t["names"][seat] == t["names"][1 - seat]:
            continue                                   # self-play validation game
        ep = int(t["episode"])
        rec = dict(episode=ep, seat=seat, seed=int(t["seed"]), names=t["names"], rewards=t["rewards"], opponent=None,
                   shops=[list(t["shops"][:min(8, d // 3)]) for d in range(31)], our_actions=t["actions"],
                   opp_actions=t["opp_actions"], source=f"{a.tapes}/{src.name} (DSM new, our seat = DSM)")
        dst = rec_dir / f"{ep}.json.gz"
        dst.write_bytes(gzip.compress(json.dumps(rec).encode(), mtime=0))
        cases.append(dict(id=f"d4q9-{ep}", episode=str(ep), seed=int(t["seed"]), seat=seat, file=f"recordings_d4q9/{ep}.json.gz",
                          sha256=hashlib.sha256(dst.read_bytes()).hexdigest(), opponent=t["names"][1 - seat],
                          replaced="DSM new 56692773 (exact prefix, our seat)",
                          recorded_margin=t["rewards"][seat] - t["rewards"][1 - seat], shops8=t["shops"]))
    OUT.mkdir(parents=True, exist_ok=True)
    cases_path().write_text(json.dumps(dict(note="DSM new seat swap, day-9 handover (prefix 216)", cases=cases), indent=1),
                            "utf-8")
    print(len(cases), "cases ->", cases_path())
    r = subprocess.run([sys.executable, str(ROOT / "scripts/leader_commits_20260929.py"), "--cases", str(cases_path())],
                       capture_output=True, text=True)
    print(r.stdout[-400:], r.stderr[-400:])


def job(args):
    cand, case, game, prefix = args
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    me = Path(__file__).resolve()                  # the harness audit rejects unfrozen repo modules: drop this runner
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    seat = int(case["seat"])
    tiles, lookup, frames = [], {}, []

    def tid(t):
        v = {k: t[k] for k in TILE_KEYS if k in t} if isinstance(t, dict) else t
        key = json.dumps(v, sort_keys=True, separators=(",", ":"))
        if key not in lookup:
            lookup[key] = len(tiles)
            tiles.append(v)
        return lookup[key]

    om = E._process_market

    def pm(state, env, *a, **k):
        obs = state[0].observation
        farm = obs.farms[seat]
        act = state[seat].action
        frames.append(dict(t=int(obs.step), m=[int(obs.farms[seat]["money"]), int(obs.farms[1 - seat]["money"])],
                           u=[list(farm["farmer"])] + [list(h) for h in farm["hands"]],
                           b=[tid(t) for row in farm["tiles"] for t in row],
                           sh={g: int(v) for g, v in dict(state[seat].observation.private["shed"]).items() if int(v or 0)},
                           a=deepcopy(act) if isinstance(act, dict) else None,
                           p=[int(obs.market["prices"].get(g, 0)) for g in GOODS],
                           s=list(obs.town["unlocked_shops"]), q=len(farm.get("unlocked_quadrants") or [])))
        return om(state, env, *a, **k)
    E._process_market = pm
    try:
        harness = STUDY / "candidates" / cand / "harness"
        dsm_out = OUT / "games" / f"{case['id']}.dsm.result.json"
        if game == "dsm":
            j = dict(study=str(STUDY), case=case, kind="source_control", output=str(dsm_out), candidate=cand,
                     leader_weeds=True)
        else:
            j = dict(study=str(STUDY), case=case, kind="recorded", output=str(OUT / "games" / f"{case['id']}.{cand}.p{prefix}.result.json"),
                     candidate=cand, control=str(dsm_out), leader_credit="exact",
                     leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True, prefix_steps=prefix)
        SH._worker((str(harness), j, True))
    finally:
        E._process_market = om
    res = json.loads(Path(j["output"]).read_text())
    g = dict(tiles=tiles, frames=frames, cash=res["cash"], opp_cash=res["opponent_cash"], margin=res["margin"],
             daily=res["daily"], shops=res.get("shops"), seat=seat, recorded_cash_match=res.get("recorded_cash_match"),
             errors=res.get("errors"), eligible=res.get("eligible"))
    key = "dsm" if game == "dsm" else f"{cand}.p{prefix}"
    with gzip.open(OUT / "games" / f"{case['id']}.{key}.game.json.gz", "wt", encoding="utf-8") as f:
        json.dump(g, f, separators=(",", ":"))
    return case["id"], key, res.get("margin"), res.get("recorded_cash_match"), res.get("errors")


def load_game(cid, key):
    f = OUT / "games" / f"{cid}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def run(a):
    cases = json.loads(cases_path().read_text("utf-8"))["cases"]
    if a.only:
        cases = [c for c in cases if c["id"] in a.only.split(",")]
    if a.limit:
        cases = cases[:a.limit]
    (OUT / "games").mkdir(parents=True, exist_ok=True)
    key = f"{a.cand}.p{a.prefix}"
    todo_dsm = [(a.cand, c, "dsm", a.prefix) for c in cases if not (OUT / "games" / f"{c['id']}.dsm.game.json.gz").exists()]
    with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
        for r in pool.map(job, todo_dsm):
            print("dsm", r, flush=True)
    ok = [c for c in cases if (g := load_game(c["id"], "dsm")) and g["recorded_cash_match"]]
    print(f"{len(ok)}/{len(cases)} DSM controls reproduce the recorded cash", flush=True)
    todo = [(a.cand, c, "ours", a.prefix) for c in ok if not (OUT / "games" / f"{c['id']}.{key}.game.json.gz").exists()]
    with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
        for r in pool.map(job, todo):
            print("ours", r, flush=True)


# ---------------------------------------------------------------- report
def dawn(g, d):
    """the frame at the start of day d (step 24 d)"""
    return g["frames"][min(24 * d, len(g["frames"]) - 1)]


def board_counts(g, fr):
    c = Counter()
    for i in fr["b"]:
        t = g["tiles"][i]
        if t == "LOCKED" or t is None:
            c["locked" if t == "LOCKED" else "empty"] += 1
        elif t.get("kind") == "WEED":
            c["weed"] += 1
        elif t.get("crop"):
            c[t["crop"]] += 1
        elif t.get("animal"):
            c[t["animal"]] += 1
        else:
            c["structure"] += 1
    return c


def planted_on(g, d):
    """crop tiles planted on day d that still stand at the next dawn"""
    fr = dawn(g, d + 1)
    return Counter(g["tiles"][i]["crop"] for i in fr["b"] if isinstance(g["tiles"][i], dict) and g["tiles"][i].get("crop")
                   and g["tiles"][i].get("planted_day") == d)


def day_orders(g, d):
    """the day's requested market orders and failed (no-effect) unit commands, from the frames and the daily ledger"""
    s = g["seat"]
    D, P = g["daily"][s][d + 1], g["daily"][s][d]
    spend = {k: D["spend"].get(k, 0) - P["spend"].get(k, 0) for k in D["spend"]}
    units = {k: D["sold_units"].get(k, 0) - P["sold_units"].get(k, 0) for k in D["sold_units"]}
    rev = {k: D["revenue"].get(k, 0) - P["revenue"].get(k, 0) for k in D["revenue"]}
    ph = {k: D["physical"].get(k, 0) - P["physical"].get(k, 0) for k in D["physical"]}
    hands = max((len(f["u"]) - 1 for f in g["frames"][24 * d:24 * d + 24]), default=0)
    return dict(spend=spend, units=units, rev=rev, ph=ph, hands=hands,
                seeds={c: round(spend.get(f"BUY_SEED:{c}", 0) / p, 1) for c, p in SEED.items() if spend.get(f"BUY_SEED:{c}")},
                animals={x: round(spend.get(f"BUY_ANIMAL:{x}", 0) / p, 1) for x, p in ANIMAL.items() if spend.get(f"BUY_ANIMAL:{x}")},
                land=spend.get("BUY_LAND", 0), wheat_bought=spend.get("BUY_PRODUCT:WHEAT", 0))


def report(a):
    cases = json.loads(cases_path().read_text("utf-8"))["cases"]
    key = f"{a.cand}.p{a.prefix}"
    pairs = []
    for c in cases:
        d, o = load_game(c["id"], "dsm"), load_game(c["id"], key)
        if d and o and d["recorded_cash_match"]:
            pairs.append((c, d, o))
    n = len(pairs)
    print(f"{n} paired games (DSM continuing its own game vs {key}, same world, opponent frozen)")
    if not n:
        return
    s_ = lambda g, t: g["frames"][min(24 * t, len(g["frames"]) - 1)]["m"]  # noqa: E731
    # the handover must be exact: our board / cash at the day-9 dawn = DSM's
    exact = sum(1 for c, d, o in pairs if dawn(d, 9)["b"] == dawn(o, 9)["b"] and dawn(d, 9)["m"] == dawn(o, 9)["m"])
    print(f"handover exact (day-9 dawn board and cash identical): {exact}/{n}")
    print("\ncash at dawn (ours / DSM, mean); margin = our cash - opponent cash")
    for t in (9, 10, 11, 12, 15, 20, 30):
        print(f"  day {t:2d}: cash {st.mean(s_(o, t)[0] for c, d, o in pairs):8.0f} / {st.mean(s_(d, t)[0] for c, d, o in pairs):8.0f}"
              f"   margin {st.mean(s_(o, t)[0] - s_(o, t)[1] for c, d, o in pairs):8.0f} / {st.mean(s_(d, t)[0] - s_(d, t)[1] for c, d, o in pairs):8.0f}")
    print(f"  final margin: ours {st.mean(o['margin'] for c, d, o in pairs):.0f} vs DSM {st.mean(d['margin'] for c, d, o in pairs):.0f}"
          f"  (ours - DSM {st.mean(o['margin'] - d['margin'] for c, d, o in pairs):+.0f}; better in {sum(o['margin'] > d['margin'] for c, d, o in pairs)}/{n})")
    q4 = [(next((t // 24 for t, f in enumerate(g["frames"]) if f.get("q", 0) >= 4), None)) for c, d, o in pairs for g in (o,)]
    q4d = [(next((t // 24 for t, f in enumerate(g["frames"]) if f.get("q", 0) >= 4), None)) for c, d, o in pairs for g in (d,)]
    print(f"\n4th quadrant owned from day (ours): {Counter(q4)}; DSM: {Counter(q4d)}")
    print("\nper day, mean per game: ours | DSM")
    for day in (9, 10, 11):
        od = [day_orders(o, day) for c, d, o in pairs]
        dd = [day_orders(d, day) for c, d, o in pairs]
        op = [planted_on(o, day) for c, d, o in pairs]
        dp = [planted_on(d, day) for c, d, o in pairs]
        m = lambda rows, f: st.mean(f(r) for r in rows)  # noqa: E731
        print(f" day {day}: hands {m(od, lambda r: r['hands']):.1f} | {m(dd, lambda r: r['hands']):.1f}; land ${m(od, lambda r: r['land']):.0f} | ${m(dd, lambda r: r['land']):.0f};"
              f" wheat bought ${m(od, lambda r: r['wheat_bought']):.0f} | ${m(dd, lambda r: r['wheat_bought']):.0f}")
        print("   planted (standing at next dawn): " + ", ".join(
            f"{cr} {m(op, lambda r: r.get(cr, 0)):.1f} | {m(dp, lambda r: r.get(cr, 0)):.1f}" for cr in SEED))
        print("   animals bought: " + ", ".join(f"{x} {m(od, lambda r: r['animals'].get(x, 0)):.1f} | {m(dd, lambda r: r['animals'].get(x, 0)):.1f}" for x in ANIMAL))
        print("   sold units: " + ", ".join(f"{p[:5]} {m(od, lambda r: r['units'].get(p, 0)):.1f} | {m(dd, lambda r: r['units'].get(p, 0)):.1f}" for p in GOODS
                                           if m(od, lambda r: r['units'].get(p, 0)) + m(dd, lambda r: r['units'].get(p, 0)) >= 0.5))
        print("   revenue $" + f"{m(od, lambda r: sum(r['rev'].values())):.0f} | {m(dd, lambda r: sum(r['rev'].values())):.0f}; spend $"
              f"{m(od, lambda r: sum(r['spend'].values())):.0f} | {m(dd, lambda r: sum(r['spend'].values())):.0f}; failed commands "
              f"{m(od, lambda r: r['ph'].get('no_effect', 0)):.1f} | {m(dd, lambda r: r['ph'].get('no_effect', 0)):.1f}")
        ops = sorted({k for r in od + dd for k in r["ph"] if k.startswith("op:")})
        print("   ops: " + ", ".join(f"{k[3:]} {m(od, lambda r: r['ph'].get(k, 0)):.0f} | {m(dd, lambda r: r['ph'].get(k, 0)):.0f}" for k in ops
                                     if k not in ("op:NORTH", "op:SOUTH", "op:EAST", "op:WEST")))
    print("\nboard at dawn (ours | DSM), mean tiles")
    for t in (10, 11, 12):
        bo = [board_counts(o, dawn(o, t)) for c, d, o in pairs]
        bd = [board_counts(d, dawn(d, t)) for c, d, o in pairs]
        ks = sorted({k for r in bo + bd for k in r})
        print(f"  day {t}: " + ", ".join(f"{k} {st.mean(r.get(k, 0) for r in bo):.1f} | {st.mean(r.get(k, 0) for r in bd):.1f}" for k in ks))
    print("\nper game: margin ours - DSM (final), day-12 dawn cash gap, 4th quadrant day ours/DSM, planted days 9-11 ours/DSM")
    for c, d, o in pairs:
        q_o = next((t // 24 for t, f in enumerate(o["frames"]) if f.get("q", 0) >= 4), None)
        q_d = next((t // 24 for t, f in enumerate(d["frames"]) if f.get("q", 0) >= 4), None)
        po = sum(sum(planted_on(o, x).values()) for x in (9, 10, 11))
        pd = sum(sum(planted_on(d, x).values()) for x in (9, 10, 11))
        print(f"  {c['id']} {'+'.join(x[:4] for x in c['shops8'][:3]):16s} {o['margin'] - d['margin']:+8.0f}  d12 cash {s_(o, 12)[0] - s_(d, 12)[0]:+7.0f}"
              f"  Q4 {q_o}/{q_d}  planted {po}/{pd}")


def viewer(a):
    case = [c for c in json.loads(cases_path().read_text("utf-8"))["cases"] if c["id"] == a.case_id][0]
    sys.path.insert(0, str(ROOT / "scripts"))
    import b2b_replay_20260929 as B
    games = []
    for key, lab in (("dsm", "DSM new (56692773) · its own game"), (f"{a.cand}.p{a.prefix}", f"Ours · {a.cand} · DSM's commands to step {a.prefix}")):
        g = load_game(case["id"], key)
        body = json.dumps(dict(tiles=g["tiles"], frames=g["frames"]), separators=(",", ":")).encode()
        games.append(dict(key="dsm" if key == "dsm" else "ours", label=lab, seat=g["seat"], cash=g["cash"], opp_cash=g["opp_cash"],
                          margin=g["margin"], recorded_cash_match=g["recorded_cash_match"], days=B.day_table(g),
                          packed=base64.b64encode(gzip.compress(body, mtime=0)).decode()))
    nf = OUT / f"{case['id']}.{a.cand}.p{a.prefix}.notes.json"
    notes = json.loads(nf.read_text(encoding="utf-8")) if nf.exists() else {}
    data = dict(case=case["id"], episode=case["episode"], seed=case["seed"], seat=case["seat"], cand=games[1]["label"],
                games=games, goods=GOODS, notes=notes)
    tpl = (ROOT / "scripts/fragments/b2b_replay.html").read_text(encoding="utf-8")
    dst = ROOT / f"viz/b2b_{case['id']}_{a.cand}_p{a.prefix}.html"
    dst.write_text(tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")), encoding="utf-8")
    print(dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cases", "run", "report", "viewer"])
    ap.add_argument("case_id", nargs="?")
    ap.add_argument("--tapes", default="data/leader_tapes/16732748_56692773")
    ap.add_argument("--cand", default="n18rc223d")
    ap.add_argument("--prefix", type=int, default=216)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    dict(cases=build_cases, run=run, report=report, viewer=viewer)[a.cmd](a)
