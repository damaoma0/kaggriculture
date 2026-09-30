"""v18q -> v18r: sd_dig_after_harvest (default 0) - a live ongoing plant the plan replaces today is harvested, THEN dug.

User 2026-09-29 ("could we discuss wheat first?"): wheat lost 82 tile-days a world vs current DSM (9 3Q worlds), 42 of
them on days 19-26. Finished strawberries: DSM digs 16.7 a world right after the 4th (last) harvest and replants the
same hour (gap 0.07 day, next crop wheat 11 / carrot 6); ours are never dug alive - 21 a world turn into weeds (the
engine makes an ongoing plant a weed at the start of the day after its last production), sit 1.3 days, replant gap 0.89
day (14 weed tile-days a world vs DSM 3). The tiler frees a strawberry at release age 17 (tomato 12), the day it is
already a weed; release age 16 (tomato 11) = the last production's harvest day.

In the tier path a planting on a tile whose live ongoing plant the plan removes today gets pre-ops: with the plant's
HARVEST already in the tile's ops, DIG (rank 0 - it sorts BEFORE the HARVEST, rank 6, and would destroy the last
production); a ripe plant without a planned harvest, DIG alone. sd_dig_after_harvest 1 = the sd_exact_site behaviour
for these tiles only: HARVEST + DIG for a ripe plant, DIG ranked 6.7 (after HARVEST / PLACE_HARVEST, before PLANT 7),
and the replaced plant's WATER / FERTILIZE dropped. Use with policy / tiles release_age STRAWBERRY 16 (TOMATO 11).

usage: patch_exec_dig_harvest_20260929.py  (writes agents/mgt_lead_kb115lt2_v18r.py from v18q)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18q.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18r.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_dawn_fert": None,''', '''    "sd_dig_after_harvest": 0,  # 1: a live ongoing plant replaced today is harvested first, then dug (DIG after HARVEST)
    "sd_tier_dawn_fert": None,''')
    s = sub(s, '''                elif CFG["sd_exact_site"] and ripe_ and c_.get("ongoing"):
                    pre = [["HARVEST"], ["DIG"]]     # sd_exact_site: take the units, then dig''',
            '''                elif (CFG["sd_exact_site"] or CFG.get("sd_dig_after_harvest")) and ripe_ and c_.get("ongoing"):
                    pre = [["HARVEST"], ["DIG"]]     # sd_exact_site / sd_dig_after_harvest: take the units, then dig''')
    s = sub(s, '''                if CFG["sd_exact_site"] and t.get("crop") != (job[1] if job[0] == "PLANT" else None):
                    r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("WATER", "FERTILIZE")]   # the plant is replaced''',
            '''                if ((CFG["sd_exact_site"] or (CFG.get("sd_dig_after_harvest") and c_.get("ongoing")))
                        and t.get("crop") != (job[1] if job[0] == "PLANT" else None)):
                    r_["ops"] = [o for o in r_["ops"] if o["c"][0] not in ("WATER", "FERTILIZE")]   # the plant is replaced''')
    s = sub(s, '''            new = [_tier_op(o, True, 0.0, 2) for o in pre]
            if CFG["sd_exact_site"]:
                for o in new:''', '''            new = [_tier_op(o, True, 0.0, 2) for o in pre]
            if CFG["sd_exact_site"] or (CFG.get("sd_dig_after_harvest") and _is_plant(t)):
                for o in new:''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
