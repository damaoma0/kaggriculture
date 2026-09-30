"""agents/mgt_dsm_c.py -> agents/mgt_dsm_ch.py: opening hire guard for the DSM tape router (days 0 .. hire_keep_until-1).
User 2026-09-29: "we should make sure the opening has minimal knock-on effect. Why would anything happening before day 3
different? Not even a shop was revealed?"

Measured (9 current-DSM worlds, full games, own tape left out; results/fresh/semantic_h2h_20260929/local_dsmfull): before
day 3 the router plays its default tape (episode 114348368) - DSM's fixed opening, command for command, except the
build-time "equilibrium feed purchase" (her turn-0/1 wheat round trip replaced by one net buy). DSM's own agent adapts to
its coins; the tape cannot. In 6 of 9 worlds we end day 0 with 0-1 coins (DSM 1-9), the tape's day-1 hour-0 hires (1+1+2
coins) mostly fail (units 2 vs DSM's 4 on day 1; DSM re-hires at hour 2 right after selling fertilizer, the tape - tuned
to a richer world - has no such hire), two sheep go unfed / uncared on day 1, their care bank is one short and each gives
5 wool instead of 6 on day 6 (16 vs 18 in exactly those 6 worlds; 7-8 coins at day end in the other 3 -> 18).

  hire_keep  from hire_keep_hour on each opening day, BUY_SEED orders that would leave less cash than tomorrow's hour-0
             tape hires cost (sum of fib(k), k < n) are held (v2: feed wheat, animals and land are never held - v1 held
             them too: random seeds vs MGT, 17 wool on day 6 in 8 of 24 games (unfed sheep), no 3rd quadrant by day 8)
  rehire     on opening days from hour 1, while we have fewer hands than the tape commands this step, HIRE orders are
             placed right after this step's SELLs (the sale proceeds pay for them), as many as the cash covers

v3 (user: "the guard should only work for a few days"): the hold only on day 0 (it funds the day-1 hour-0 hires), the
re-hire only on day 1; days 2-5 replay the tape untouched.

usage: make_dsm_router_hirekeep_20260929.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_dsm_c.py"
DST = ROOT / "agents/mgt_dsm_ch.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "terminal_liquidation": True,
    # tunables''', '''    "terminal_liquidation": True,
    "hire_keep": False,        # opening guard (2026-09-29): keep tomorrow's hour-0 hire money on opening days
    "rehire": False,           # opening guard (2026-09-29): missing tape hands re-hired after the step's sales
    "hire_keep_until": 1,      # days the purchase hold covers (v3: day 0 only - it funds the day-1 hour-0 hires)
    "rehire_until": 2,         # days the re-hire covers (v3: day 1 only)
    "hire_keep_hour": 12,      # from this hour of each opening day purchases keep tomorrow's hire money
    # tunables''')
    s = sub(s, '''            if cfg["budget_guard"]:
                self._budget_guard(action, view, route, step)''', '''            if cfg["budget_guard"]:
                self._budget_guard(action, view, route, step)
            if cfg.get("hire_keep") or cfg.get("rehire"):
                self._hire_guard(action, view, route, step)''')
    s = sub(s, '''    # ---- layer: room_guard ----------------------------------------------------''', '''    # ---- opening hire guard (2026-09-29) -------------------------------------------
    def _hire_guard(self, action, view, route, step):
        cfg = self.cfg
        day, hour = divmod(step, 24)
        if day >= max(int(cfg.get("hire_keep_until", 1)), int(cfg.get("rehire_until", 2))):
            return
        tape = self.routes[route]
        market = action.setdefault("market", [])
        cash = view.money
        for o in market:
            if o and o[0] == "SELL" and len(o) > 1:
                cash += max(0, _int(o[2]) if len(o) > 2 else 1) * view.prices.get(o[1], 0)
        hired = view.hires_today
        n_hire = sum(1 for o in market if o and o[0] == "HIRE")
        for k in range(n_hire):
            cash -= _fib(hired + k)
        hired += n_hire
        if (cfg.get("rehire") and day < int(cfg.get("rehire_until", 2)) and hour >= 1 and step < len(tape)
                and isinstance(tape[step], dict)):
            want = len(tape[step].get("hands") or [])
            have = len(view.positions) - 1
            missing = want - have - n_hire
            added = 0
            while missing > 0 and cash >= _fib(hired):
                pos = max([i + 1 for i, o in enumerate(market) if o and o[0] == "SELL"] or [0])
                if len(market) >= cfg["max_orders"]:
                    drop = next((i for i in range(len(market) - 1, -1, -1) if market[i] and market[i][0] not in ("HIRE", "SELL")), None)
                    if drop is None:
                        break
                    del market[drop]
                    pos = min(pos, len(market))
                market.insert(pos, ["HIRE"])
                cash -= _fib(hired)
                hired += 1
                missing -= 1
                added += 1
            if added:
                self.diagnostics["opening_rehire"] = self.diagnostics.get("opening_rehire", 0) + added
        if cfg.get("hire_keep") and day < int(cfg.get("hire_keep_until", 1)) and hour >= int(cfg.get("hire_keep_hour", 12)):
            nxt = (day + 1) * 24
            n_next = 0
            if nxt < len(tape) and isinstance(tape[nxt], dict):
                n_next = sum(1 for o in (tape[nxt].get("market") or []) if o and o[0] == "HIRE")
            reserve = sum(_fib(k) for k in range(n_next))
            kept = []
            for o in market:
                cost = 0
                if o and o[0] == "BUY_SEED" and len(o) > 1:
                    cost = SEED_PRICE.get(o[1], 0) * max(1, _int(o[2]) if len(o) > 2 else 1)
                elif o and o[0] in ("BUY_ANIMAL", "BUY_PRODUCT", "BUY_LAND"):
                    held_ = False                  # never held: feed wheat, the herd and land (random-seed check:
                    # holding them left sheep unfed - 17 wool on day 6 in 8 of 24 games - and no 3rd quadrant by day 8)
                    if o[0] == "BUY_ANIMAL" and len(o) > 1:
                        cash -= ANIMAL_COST.get(o[1], 0) * max(1, _int(o[2]) if len(o) > 2 else 1)
                    elif o[0] == "BUY_PRODUCT" and len(o) > 1:
                        cash -= (view.prices.get(o[1], 0) + 1) * max(1, _int(o[2]) if len(o) > 2 else 1)
                    kept.append(o)
                    continue
                if cost and cash - cost < reserve:
                    self.diagnostics["opening_hire_keep_held"] = self.diagnostics.get("opening_hire_keep_held", 0) + 1
                    continue
                cash -= cost
                kept.append(o)
            action["market"] = kept

    # ---- layer: room_guard ----------------------------------------------------''')
    s = sub(s, "'terminal_liquidation': True}}", "'terminal_liquidation': True, 'hire_keep': True, 'rehire': True}}")
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()
