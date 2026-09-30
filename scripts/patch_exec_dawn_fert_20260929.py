"""v18p -> v18q: sd_tier_dawn_fert [d0, d1] (default off) - the dawn cash trip brings the pens' fertilizer home.

User 2026-09-29: "Can we hardcode the fertilizer bringback? ... DSM probably always do the run"; "cash now is worth more
than cash future before day 11". Verified (9 current-DSM worlds): DSM sells each day's collected fertilizer the same day
on days 1-9 (day 6: 8.4 collected / 9.2 sold @86, day 7: 14.9 / 11.3 @82) and fertilizes nothing before day 10; in the 3
hour-by-hour worlds it collects 71 of its 117 day-6..8 fertilizer before hour 9 and places 15 in the shed at hours 3-5.
With the day-0/1 hire guard (n18rc105) days 6-7 differ from DSM only in fertilizer revenue (794 / 223 on day 6, 931 /
612 on day 7) and day-6 purchases are 473 lower. Our dawn trip (sd_tier_dawn_cash, days 6-10) takes only the pen's
HARVEST and its shed DELIVER places the largest carried pile; the pen's COLLECT_FERTILIZER stays with the day routes,
which carry it to the midnight dump.

sd_tier_dawn_fert [d0, d1]: on those days a dawn leg also collects the fertilizer of its pen and of pens next to it (one
step off the pen, added in order while the leg still delivers by sd_tier_dawn_by), and its shed stop places the fertilizer
too (DELIVER FERTILIZER). Use with FERTILIZER off sd_books_sell on those days so the delivery is sold at once.

usage: patch_exec_dawn_fert_20260929.py  (writes agents/mgt_lead_kb115lt2_v18q.py from v18p)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18p.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18q.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_eve_feed_buy": None,''', '''    "sd_tier_dawn_fert": None,  # [d0, d1]: the dawn leg also collects its pen's (and adjacent pens') fertilizer and places it
    # at the shed (DSM sells each day's fertilizer the same day on days 1-9; ours rode to the midnight dump)
    "sd_eve_feed_buy": None,''')
    old = '''        ev = _tier_eval({"p0": pi, "t0": t0, "stops": []}, stops, want_hours=True)
        drop = max(h for (b_, c_, h) in ev[4] if c_[0] in ("DELIVER", "PLACE_HARVEST"))
        out[u] = {"stops": stops, "p0": pi, "t0": t0, "end": ev[0], "tile": stops[-1]["tile"], "drop": drop,
                  "pen": take[0][0], "units": sum(y for _, _, y in take), "prod": prods[0],'''
    new = '''        ev = _tier_eval({"p0": pi, "t0": t0, "stops": []}, stops, want_hours=True)
        drop = max(h for (b_, c_, h) in ev[4] if c_[0] in ("DELIVER", "PLACE_HARVEST"))
        df_ = CFG.get("sd_tier_dawn_fert")
        if df_ and int(df_[0]) <= int(day) <= int(df_[1]):
            # the dawn leg brings the fertilizer home: its pens' collects, then pens one step off them while the drop
            # stays within 2 hours of the plain leg and by sd_tier_dawn_cash_by (DSM places it at hours 3-5)
            lim_ = min(drop + 2, max(drop, int(CFG.get("sd_tier_dawn_cash_by", 8))))
            taken_ti_ = [ti for ti, _, _ in take]
            near_ = sorted((j for j in rec if j not in taken_ti_ and _animal(_tile(tiles, j))
                            and min(D[j][ti] for ti in taken_ti_) == 1), key=lambda j: (min(D[j][ti] for ti in taken_ti_), j))
            got_ = []
            for j in taken_ti_ + near_:
                cf_ = [o for o in rec.get(j, {}).get("ops", []) if o["c"][0] == "COLLECT_FERTILIZER"]
                if not cf_ or not _tile(tiles, j).get("fertilizer_available"):
                    continue
                tr_ = [dict(x) for x in stops]
                k_ = next((i_ for i_, x in enumerate(tr_) if x["tile"] == j), None)
                if k_ is not None:
                    tr_[k_] = dict(tr_[k_], ops=sorted(tr_[k_]["ops"] + [dict(cf_[0], m=True, tier=1)], key=lambda o: o["rank"]))
                else:
                    pos_ = len(tr_) - 1 if tr_[-1].get("turn") else len(tr_)
                    tr_ = tr_[:pos_] + [{"tile": j, "ops": [dict(cf_[0], m=True, tier=1)], "rel": rec[j]["rel"]}] + tr_[pos_:]
                last_ = tr_[-1]
                if not any(o["c"] == ["DELIVER", "FERTILIZER"] for o in last_["ops"]):
                    if last_.get("turn") or last_["tile"] in _TIER_SHED_I:
                        tr_[-1] = dict(last_, ops=sorted(last_["ops"] + [_tier_op(["DELIVER", "FERTILIZER"], True, 0.0, 1)],
                                                         key=lambda o: o["rank"]))
                    else:
                        continue
                ev_ = _tier_eval({"p0": pi, "t0": t0, "stops": []}, tr_, want_hours=True)
                hs_ = [h for (b_, c_, h) in ev_[4] if c_[0] in ("DELIVER", "PLACE_HARVEST")]
                if not hs_ or ev_[1] > 0 or ev_[3] > 0 or max(hs_) > lim_:
                    continue
                stops, ev, drop = tr_, ev_, max(hs_)
                got_.append((j, id(cf_[0])))
            for j, oid in got_:
                rec[j]["ops"] = [o for o in rec[j]["ops"] if id(o) != oid]
            st["tier_dawn_fert"] = st.get("tier_dawn_fert", 0) + len(got_)
        out[u] = {"stops": stops, "p0": pi, "t0": t0, "end": ev[0], "tile": stops[-1]["tile"], "drop": drop,
                  "pen": take[0][0], "units": sum(y for _, _, y in take), "prod": prods[0],'''
    s = sub(s, old, new)
    s = sub(s, '''        for ti, hv, _ in take:
            ids = set(id(o) for o in hv)
            rec[ti]["ops"] = [o for o in rec[ti]["ops"] if id(o) not in ids]
            if not rec[ti]["ops"]:
                rec.pop(ti)
        out[u]["svc"] = _tier_dawn_svc(rec, [ti for ti, _, _ in take])''', '''        for ti, hv, _ in take:
            ids = set(id(o) for o in hv)
            rec[ti]["ops"] = [o for o in rec[ti]["ops"] if id(o) not in ids]
            if not rec[ti]["ops"]:
                rec.pop(ti)
        for j in [j for j, r_ in rec.items() if not r_["ops"]]:
            rec.pop(j)                             # sd_tier_dawn_fert: a neighbour pen whose only op was the collect
        out[u]["svc"] = _tier_dawn_svc(rec, [ti for ti, _, _ in take])''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
