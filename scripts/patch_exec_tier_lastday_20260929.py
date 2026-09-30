"""v18s -> v18t: sd_tier_lastday (default 0) - the tier plan also runs on the last day (day 29), with the final-day delivery.

User 2026-09-29: "some harvests are not done after the end of day 29. If we don't harvest it we should not plant it. Or
maybe we should harvest it early." Measured (b2b recordings, 9 current-DSM 3Q worlds, n18rc127): one-time crops ripe at
the day-29 dawn 14.3 a world, 11.3 harvested, 3.0 left with 7.9 units (DSM 16.1 / 15.2 / 0.9); same hands (9.2 a world),
but DSM harvests 34 times with 21 idle hand-hours and we 28 with 11. Reward = money only, so a crop left on its tile is
worth 0 (seeds 108 a world vs DSM 27). Day 29 was run by the old hourly dispatcher: _tier_pre skips day >= last_day.

sd_tier_lastday 1: _tier_pre plans day 29 too; after the tier override, on the last day every unit carrying sellable
goods walks to the shed and drops them once (22 - hour) <= its distance + 1 (the dispatcher's own final-day rule - the
game ends before the midnight dump, so anything still carried is lost).

usage: patch_exec_tier_lastday_20260929.py  (writes agents/mgt_lead_kb115lt2_v18t.py from v18s)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18s.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18t.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_land_virtual": None,''', '''    "sd_tier_lastday": 0,     # 1: the tier plan also runs on day 29; carried goods go to the shed by hour 22 (no midnight dump)
    "sd_land_virtual": None,''')
    s = sub(s, '''    if hour != 0 or len(pos) != 1 or day >= last_day or (S.get("tier") or {}).get("day") == day:
        return''', '''    if (hour != 0 or len(pos) != 1 or day >= last_day + (1 if CFG.get("sd_tier_lastday") else 0)
            or (S.get("tier") or {}).get("day") == day):
        return''')
    s = sub(s, '''            _tier_override(S, obs, step, day, hour, tiles, pos, invs, actions, seeds, shed)
        except Exception as exc:''', '''            _tier_override(S, obs, step, day, hour, tiles, pos, invs, actions, seeds, shed)
            if CFG.get("sd_tier_lastday") and day >= last_day:   # final day: nothing reaches a midnight dump
                for u_ in range(min(len(pos), len(actions))):
                    inv_ = invs[u_] if u_ < len(invs) else {}
                    if sum(v_ for k_, v_ in inv_.items() if k_ in PRODUCTS):
                        p_ = tuple(pos[u_])
                        s_ = _near_shed(p_)
                        if (22 - hour) <= _dist(p_, s_) + 1:
                            actions[u_] = ["DROP"] if p_ == s_ else _step_toward(p_, s_)
                            S["log"]["tier_lastday_deliver"] += 1
        except Exception as exc:''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
