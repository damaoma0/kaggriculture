"""v18v -> v18w: sd_fert_force_tiles (default None) - when a list of tile indices (10*y + x), sd_fert_force applies only to
those tiles (the entry sets it every morning).

User 2026-09-29 ("I think you should not force carrot fertilization at day1? We do it only if we expect this as a 2day
cycle"): n18rc185d forced every age-1 carrot (41 fertilizes) and took the day's fertilizer from the age-2 wheat (49 -> 30),
so wheat waited to age 4 (39 -> 61). The entry's fert_force_plan hook lists the age-1 carrots whose tile the morning
plan uses again tomorrow (a planting or a structure at age 2): only those are fertilized at age 1.

usage: patch_exec_fert_force_tiles_20260929.py  (writes agents/mgt_lead_kb115lt2_v18w.py from v18v)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18v.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18w.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_fert_force": None,''', '''    "sd_fert_force_tiles": None,  # list of tile indices (10*y + x): sd_fert_force only on these (set each morning by the entry)
    "sd_fert_force": None,''')
    s = sub(s, '''            if ffo_ is not None and du <= 0 and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1]):''',
            '''            if (ffo_ is not None and du <= 0 and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1])
                    and (CFG.get("sd_fert_force_tiles") is None or 10 * y + x in CFG["sd_fert_force_tiles"])):''')
    s = sub(s, '''        if (ffo_ is not None and g <= 0 and int(t.get("fertilized_until_day", -1) or -1) < day
                and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1])):''',
            '''        if (ffo_ is not None and g <= 0 and int(t.get("fertilized_until_day", -1) or -1) < day
                and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1])
                and (CFG.get("sd_fert_force_tiles") is None or idx in CFG["sd_fert_force_tiles"])):''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
