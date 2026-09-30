"""Back-to-back replay: our agent vs DSM (current, submission 56619023) in the same world (user 2026-09-29: "give me
honest gap between us and DSM current. Explain what happened and when using a tape replay back-to-back").

Two official-engine games of one dsm3q case (dsmseat_cases.json), both in DSM's seat against the opponent's recorded
commands, recorded shops and weeds, exact market credit for the opponent:
  dsm   DSM continuing its own recorded game (the source control; reproduces the recorded cash)
  ours  the candidate from day 0 (no prefix); the DSM tape router runs WITHOUT this episode's own tape (MGT_EXCLUDE)
Every step records our seat's board (interned tiles), units, shed, the step's commands, both cash totals and the
quotes; the day tables come from each game's own result (daily money / production / sales / spend / tile-hours).

usage: b2b_replay_20260929.py CASE_ID [--cand n18rc8] [--prefix 264] [--label TEXT] [--out FILE] [--rerun]
  each game is cached (<case>.dsm.game.json.gz, <case>.<cand>.p<prefix>.game.json.gz); later calls only rebuild the
  viewer, e.g. after editing <case>.<cand>.p<prefix>.notes.json ({"lede", "method", "events": [{day, hour, title, text}]})
  -> results/fresh/semantic_h2h_20260929/b2b/<case>.<game>.json(.gz) and the viewer (template
     scripts/fragments/b2b_replay.html)"""
import base64
import gzip
import json
import os
import sys
import types
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
OUT = H / "b2b"
sys.path.insert(0, str(ROOT / "scripts"))
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
TILE_KEYS = ("kind", "crop", "animal", "yield_units", "planted_day", "placed_day", "fertilized_until_day",
             "watered_today", "fed_today", "cared_today", "pending_care_bonus", "max_lifespan_step")


def job(args):
    cand, case, game = args[:3]
    prefix = int(args[3]) if len(args) > 3 else 0
    if game == "ours" and not prefix:
        os.environ["MGT_EXCLUDE"] = str(case["episode"])   # leave this world's own DSM tape out of the router
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    me = Path(__file__).resolve()                  # the harness audit rejects unfrozen repo modules: drop this runner
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    seat = int(case["seat"])
    tiles, lookup, frames = [], {}, []

    def tid(t):
        if not isinstance(t, dict):
            key = json.dumps(t)
            v = t
        else:
            v = {k: t[k] for k in TILE_KEYS if k in t}
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
                           s=list(obs.town["unlocked_shops"])))
        return om(state, env, *a, **k)
    E._process_market = pm
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        harness = H / "study/candidates" / cand / "harness"
        ctl = H / "local_dsmseat/_controls" / f"{case['id']}.json"
        if game == "dsm":
            j = dict(study=str(H / "study"), case=case, kind="source_control", output=str(OUT / f"{case['id']}.dsm.result.json"),
                     candidate=cand, leader_weeds=True)
        else:
            j = dict(study=str(H / "study"), case=case, kind="recorded",
                     output=str(OUT / f"{case['id']}.{cand}.p{prefix}.result.json"),
                     candidate=cand, control=str(ctl), leader_credit="exact",
                     leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True)
            if prefix:                             # action-exact: our seat replays DSM's recorded commands until this step
                j["prefix_steps"] = prefix
        row = SH._worker((str(harness), j, True))
    finally:
        E._process_market = om
    res = json.loads(Path(j["output"]).read_text())
    return game, dict(tiles=tiles, frames=frames, cash=res["cash"], opp_cash=res["opponent_cash"], margin=res["margin"],
                      daily=res["daily"], shops=res.get("shops"), seat=seat, recorded_cash_match=res.get("recorded_cash_match"))


def day_table(g):
    """per day d (end of day d): cumulative money / revenue / units / spend / tile-days for our seat and the opponent"""
    s = g["seat"]
    out = []
    for d in range(30):
        D, O = g["daily"][s][d + 1], g["daily"][1 - s][d + 1]
        P = g["daily"][s][d]
        th = {k: (D["tile_hours"].get(k, 0) - P["tile_hours"].get(k, 0)) / 24 for k in set(D["tile_hours"]) | set(P["tile_hours"])}
        out.append(dict(d=d, money=D["money"], opp=O["money"], rev={k: round(v) for k, v in D["revenue"].items()},
                        units={k: v for k, v in D["sold_units"].items()},
                        prod={k.split(":")[1]: v for k, v in D["physical"].items() if k.startswith("produced:")},
                        spend={k: round(v) for k, v in D["spend"].items()},
                        opp_rev={k: round(v) for k, v in O["revenue"].items()},
                        ops={k[3:]: v for k, v in D["physical"].items() if k.startswith("op:")},
                        tiles={k: round(v, 2) for k, v in th.items()}))
    return out


def load_or_run(case, cand, prefix):
    """one game, cached: <case>.dsm.game.json.gz (DSM's own) or <case>.<cand>.p<prefix>.game.json.gz (ours)"""
    key = "dsm" if cand is None else f"{cand}.p{prefix}"
    f = OUT / f"{case['id']}.{key}.game.json.gz"
    if f.exists():
        return json.loads(gzip.open(f, "rt", encoding="utf-8").read())
    return None


def save(case, cand, prefix, g):
    key = "dsm" if cand is None else f"{cand}.p{prefix}"
    with gzip.open(OUT / f"{case['id']}.{key}.game.json.gz", "wt", encoding="utf-8") as f:
        json.dump(g, f, separators=(",", ":"))


def main():
    a = sys.argv
    cid = a[1]
    cand = a[a.index("--cand") + 1] if "--cand" in a else "n18rc8"
    prefix = int(a[a.index("--prefix") + 1]) if "--prefix" in a else 0
    label = a[a.index("--label") + 1] if "--label" in a else (f"Ours · {cand}" + (f" · DSM's commands to step {prefix}" if prefix else " from day 0"))
    case = [c for c in json.loads((H / "dsmseat_cases.json").read_text())["cases"] if c["id"] == cid][0]
    old = OUT / f"{cid}.{cand}.games.json.gz"   # first version cached both games in one file
    if old.exists() and not prefix and load_or_run(case, cand, 0) is None:
        both = json.loads(gzip.open(old, "rt", encoding="utf-8").read())
        save(case, None, 0, both["dsm"])
        save(case, cand, 0, both["ours"])
    got = {"dsm": None if "--rerun" in a else load_or_run(case, None, 0),
           "ours": None if "--rerun" in a else load_or_run(case, cand, prefix)}
    todo = [k for k, v in got.items() if v is None]
    if todo:
        with ProcessPoolExecutor(max_workers=len(todo), max_tasks_per_child=1) as pool:
            for k, g in pool.map(job, [(cand, case, k, prefix) for k in todo]):
                got[k] = g
                save(case, None if k == "dsm" else cand, prefix, g)
    games = []
    for key, lab in (("dsm", "DSM (current) · its own game"), ("ours", label)):
        g = got[key]
        assert len(g["frames"]) >= 719, (key, len(g["frames"]))
        body = json.dumps(dict(tiles=g["tiles"], frames=g["frames"]), separators=(",", ":")).encode()
        games.append(dict(key=key, label=lab, seat=g["seat"], cash=g["cash"], opp_cash=g["opp_cash"], margin=g["margin"],
                          recorded_cash_match=g["recorded_cash_match"], days=day_table(g),
                          packed=base64.b64encode(gzip.compress(body, mtime=0)).decode()))
    tag = f"{cand}.p{prefix}"
    nf = OUT / f"{cid}.{tag}.notes.json"
    notes = json.loads(nf.read_text(encoding="utf-8")) if nf.exists() else {}
    data = dict(case=cid, episode=case["episode"], seed=case["seed"], seat=case["seat"], cand=label, games=games,
                goods=GOODS, notes=notes)
    tpl = (ROOT / "scripts/fragments/b2b_replay.html").read_text(encoding="utf-8")
    dst = ROOT / (a[a.index("--out") + 1] if "--out" in a else f"viz/b2b_{cid}_{cand}_p{prefix}.html")
    dst.write_text(tpl.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")), encoding="utf-8")
    print(cid, {g["key"]: (g["cash"], g["opp_cash"], g["margin"]) for g in games}, "->", dst)


if __name__ == "__main__":
    main()
