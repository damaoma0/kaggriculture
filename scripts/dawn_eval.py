"""One-world summary of arms (dawn thread): money at the end (own / rival / margin, vs a reference arm), deaths, unfinished
planned WATER / FEED / CARE / HARVEST ops (the hour-23 executor log), tier errors / bank stop, and the planned vs executed
dawn legs (sd_tier_dawn: tier_days units' "dawn" = [pen, units, drop hour]; executed = the unit's HARVEST on the pen and
its DELIVER / PLACE_HARVEST by the planned drop hour + 2).
usage: dawn_eval.py <ep> <REF> <ARM>[,<ARM>...]"""
import json
import sys
from collections import Counter
from pathlib import Path

M = Path(__file__).resolve().parents[1] / 'results/fresh/sector_20260925/multi'
ep, ref, arms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')


def load(a):
    return json.loads((M / a / f'{ep}.json').read_text(encoding='utf-8'))


r0 = load(ref)
o0, v0 = r0['money']['30']
print(f'{"arm":10s} {"own":>8s} {"rival":>8s} {"margin":>8s} {"d_own":>7s} {"d_riv":>7s} {"d_marg":>7s}  deaths | unfinished W/F/C/H | dawn legs planned/done units | err')
for a in [ref] + arms:
    r = load(a)
    o, v = r['money']['30']
    died = Counter()
    for dd in (r.get('died') or {}).values():
        died.update(dd or {})
    unf = Counter()
    legs = done = units = 0
    for day, t in (r.get('tier_days') or {}).items():
        for u, items in (t.get('unfinished') or {}).items():
            for it in items:
                for o_ in (it[1] if isinstance(it[1], list) else []):
                    unf[o_[0] if isinstance(o_, list) else o_] += 1
        ex = t.get('exec') or {}
        for un in t.get('units') or []:
            if 'dawn' not in un:
                continue
            pen, n, drop = un['dawn']
            legs += 1
            units += n
            dn = (ex.get(str(un['u'])) or {}).get('done') or []
            h_ok = any(x[1] == pen and x[2] == 'HARVEST' for x in dn)
            d_ok = any(x[2] in ('DELIVER', 'PLACE_HARVEST') and x[0] <= drop + 2 for x in dn)
            done += h_ok and d_ok
    te = r.get('tier_err') or {}
    err = f"errors {te.get('errors')} {'BANK STOP' if 'bank' in str(te.get('last_error', '')).lower() else ''}{str(te.get('last_error', ''))[:60]}"
    print(f'{a:10s} {o:8.0f} {v:8.0f} {o - v:8.0f} {o - o0:7.0f} {v - v0:7.0f} {(o - v) - (o0 - v0):7.0f}  '
          f'{dict(died)} | {unf["WATER"]}/{unf["FEED"]}/{unf["CARE"]}/{unf["HARVEST"]} | {legs}/{done} {units} | {err}')
