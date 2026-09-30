"""v18k -> v18l: sd_tier_srun_all (default off) - on a strawberry harvest day bring in EVERY ripe strawberry with
dedicated runs. User 2026-09-29: "when we spot the need of a bringback run, make dedicated effort into it first";
"we should encourage bring in all strawberry that is ripe instead of harvesting partially".

Debug (n18rc55, lead-dsm-114377700): the opponent gate opens on days 16 / 18 / 20 (its ripe 34 / 36 / 10), we hold 20 /
22 / 24 ripe units on 10-12 tiles, but sd_tier_sclu builds 1-2 runs covering ~5 tiles: clusters need every pair of
tiles within r (our ripe tiles are spread: 1-2 tile clusters), and the loop STOPS at the first cluster that fails its
check. The other tiles go to the ordinary routes, picked at hours 14-23, dumped, sold the next day into the crash
(@51 vs the leader's same-day lots @140 -> @77).

sd_tier_srun_all 1 (inside _tier_sclu, after its gates - sd_tier_sclu_opp_min / _pmin / _day_min): every ripe strawberry
tile (a HARVEST in today's jobs) is given to a dedicated run. Free early hands (hour-0/1 hires, not the farmer, not on a
dawn trip) in turn take a nearest-first chain from their spawn: a tile joins while the run still DELIVERs by
sd_tier_sclu_by with no lateness / supply failure (a tile that does not fit is skipped, not a reason to stop); the run
takes the tiles' HARVEST / WATER (and FERTILIZE with shed fertilizer, sd_tier_sclu_fert), DELIVERs at the nearest shed
tile (sold on arrival) and then works a normal post segment. Up to sd_tier_sclu_max runs.

usage: patch_exec_srun_all_20260929.py  (writes agents/mgt_lead_kb115lt2_v18l.py from v18k)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18k.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18l.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_sclu_opp_min": None,''', '''    "sd_tier_srun_harvest_only": 0,  # 1: the all-ripe runs only HARVEST (n18rc56: water + fertilize + the shed fertilizer
    # pickup made a 2-tile run ~12 hours; the leader's runs ~2 tiles each, ~6 hands, picked by hour 8)
    "sd_tier_srun_all": 0,  # 1 (user 2026-09-29: bring in every ripe strawberry on a harvest day): the dedicated strawberry
    # runs (sd_tier_sclu, after its gates) cover ALL ripe strawberry tiles - nearest-first chains per free early hand,
    # each delivering by sd_tier_sclu_by (tiles that do not fit are skipped, not a stop)
    "sd_tier_sclu_opp_min": None,''')
    old = '''    EXTRA = ("WATER", "CARE", "FEED", "COLLECT_FERTILIZER", "HARVEST", "PLACE_HARVEST")
    out = {}
    rec_ = st["_sclu_day"] = {"clusters": [], "cand": len(cand), "cand_units": sum(cand.values()), "ready": ready_, "favail": favail}'''
    new = '''    EXTRA = ("WATER", "CARE", "FEED", "COLLECT_FERTILIZER", "HARVEST", "PLACE_HARVEST")
    out = {}
    rec_ = st["_sclu_day"] = {"clusters": [], "cand": len(cand), "cand_units": sum(cand.values()), "ready": ready_, "favail": favail}
    if int(CFG.get("sd_tier_srun_all", 0) or 0):   # every ripe strawberry tile goes to a dedicated run (user)
        left_ = dict(cand)
        for fu in sorted(free, key=lambda f: (f[2], min([D[f[1][1] * 10 + f[1][0]][m] for m in left_] or [99]))):
            if not left_ or len(out) >= int(CFG["sd_tier_sclu_max"]):
                break
            u, p0, t0 = fu
            pi = p0[1] * 10 + p0[0]
            seg = {"p0": pi, "t0": t0, "stops": []}
            chain, taken = [], {}

            def run_stops(seq, taken=taken):
                sh_ = min(_TIER_SHED_I, key=lambda q: D[seq[-1]][q])
                out_ = [{"tile": b, "ops": sorted([dict(o, m=True, tier=1) for o in taken[b]], key=lambda o: o["rank"]),
                         "rel": rec[b]["rel"] if b in rec else 0} for b in seq]
                return out_ + [{"tile": sh_, "ops": [_tier_op(["DELIVER", "STRAWBERRY"], True, 0.0, 1)], "rel": 0, "turn": True,
                                "sell_now": True}]

            def fits(seq):
                seg["fpick"] = sum(1 for b in seq for o in taken[b] if o["c"][0] == "FERTILIZE")
                ev_ = _tier_eval(seg, run_stops(seq), want_hours=True)
                dh_ = max(h for (b_, c_, h) in ev_[4] if c_[0] == "DELIVER")
                return ev_[1] == 0 and ev_[3] == 0 and dh_ <= by, ev_, dh_
            pos_ = pi
            tried = set()
            while True:
                nxt = [m for m in sorted(left_, key=lambda q: (D[pos_][q], q)) if m not in tried]
                if not nxt:
                    break
                b = nxt[0]
                tried.add(b)
                hon_ = int(CFG.get("sd_tier_srun_harvest_only", 0) or 0)   # the run only harvests (routes keep water / fertilize)
                taken[b] = [o for o in rec[b]["ops"] if o["c"][0] in (("HARVEST", "PLACE_HARVEST") if hon_ else ("HARVEST", "PLACE_HARVEST", "WATER"))]
                fz_ = [o for o in rec[b]["ops"] if o["c"][0] == "FERTILIZE"] if (_fert_useful(_tile(tiles, b), day) and not hon_) else []
                nf_ = sum(1 for x in chain for o in taken[x] if o["c"][0] == "FERTILIZE")
                if int(CFG["sd_tier_sclu_fert"]) and fz_ and nf_ + len(fz_) <= favail:
                    taken[b] += fz_
                ok_, ev, dh = fits(chain + [b])
                if ok_:
                    chain.append(b)
                    pos_ = b
                else:
                    taken.pop(b, None)
            if not chain:
                continue
            ok_, ev, dh = fits(chain)
            for b in chain:
                ids = set(id(o) for o in taken[b])
                rec[b]["ops"] = [o for o in rec[b]["ops"] if id(o) not in ids]
                if not rec[b]["ops"]:
                    rec.pop(b)
                left_.pop(b, None)
            fp_ = sum(1 for b in chain for o in taken[b] if o["c"][0] == "FERTILIZE")
            favail -= fp_
            out[u] = {"stops": run_stops(chain), "p0": pi, "t0": t0, "drop": dh, "_value": sum(cand[m] for m in chain), "fpick": fp_,
                      "hh": {b_: h for (b_, c_, h) in ev[4] if c_[0] == "HARVEST"}}
            rec_["clusters"].append({"u": u, "tiles": list(chain), "units": sum(cand[m] for m in chain), "drop": dh, "fpick": fp_,
                                     "all": True})
        rec_["left"] = len(left_)
        return out'''
    s = sub(s, old, new)
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
