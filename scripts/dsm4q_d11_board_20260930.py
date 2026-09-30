"""Our board vs the new DSM's at the day-11 dawn (step 264) after an exact day-8 handover (user 2026-09-30: "You hand off
at day 11 and what we only care is your board then"). Reads the paired games of scripts/dsm4q_d9_gap_20260930.py
(results/fresh/dsm4q_d9_20260930/games/<case>.dsm.game.json.gz and <case>.<cand>.p<prefix>.game.json.gz: every step's
board). Only the board counts: tile by tile (same coordinates) and by kind, with crop ages and animal counts.

usage: dsm4q_d11_board_20260930.py [--cand n18rc223d] [--prefix 216] [--step 264] [--detail CASE_ID]"""
import argparse
import gzip
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/dsm4q_d9_20260930"


def load(cid, key):
    f = OUT / "games" / f"{cid}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def label(t):
    """a tile's kind: crop / animal name, EMPTY, WEED, LOCKED, or STRUCTURE (an empty coop / pasture)"""
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    if t.get("kind") == "WEED":
        return "WEED"
    return t.get("crop") or t.get("animal") or ("STRUCTURE:" + t.get("kind", "?"))


def board(g, step):
    fr = g["frames"][min(step, len(g["frames"]) - 1)]
    return [g["tiles"][i] for i in fr["b"]], fr


def quadrant(i):
    x, y = i % 10, i // 10
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default="n18rc223d")
    ap.add_argument("--prefix", type=int, default=216)
    ap.add_argument("--step", type=int, default=264)
    ap.add_argument("--detail", default="")
    a = ap.parse_args()
    key = f"{a.cand}.p{a.prefix}"
    cases = json.loads((OUT / "cases.json").read_text("utf-8"))["cases"]
    rows, inexact = [], []
    for c in cases:
        d, o = load(c["id"], "dsm"), load(c["id"], key)
        if not (d and o and d.get("recorded_cash_match")):
            continue
        bd, fd = board(d, a.step)
        bo, fo = board(o, a.step)
        h0d, hd = board(d, a.prefix)
        h0o, ho = board(o, a.prefix)
        # the handover must be exact; the forced opponent weeds shift our farm's weed draws, so a midnight weed can differ
        nd = sum(1 for x, y in zip(h0d, h0o) if label(x) != label(y))
        if nd or hd["m"][0] != ho["m"][0]:
            inexact.append((c["id"], nd))
            continue
        ld, lo = [label(t) for t in bd], [label(t) for t in bo]
        diff = [i for i in range(100) if ld[i] != lo[i]]
        same_kind_diff_age = [i for i in range(100) if ld[i] == lo[i] and isinstance(bd[i], dict) and isinstance(bo[i], dict)
                              and bd[i].get("crop") and bd[i].get("planted_day") != bo[i].get("planted_day")]
        rows.append(dict(c=c, ld=ld, lo=lo, bd=bd, bo=bo, diff=diff, age=same_kind_diff_age, qd=fd.get("q"), qo=fo.get("q"),
                         cd=fd["m"][0], co=fo["m"][0], shd=fd.get("sh", {}), sho=fo.get("sh", {})))
    n = len(rows)
    print(f"{n} paired games with an exact handover at step {a.prefix}; boards compared at step {a.step} "
          f"(day {a.step // 24} hour {a.step % 24}); excluded (handover board not identical): {inexact}")
    if not n:
        return
    kinds = sorted({k for r in rows for k in r["ld"] + r["lo"]})
    print("\ntiles by kind, mean per game: ours | DSM | ours - DSM")
    for k in kinds:
        mo, md = st.mean(r["lo"].count(k) for r in rows), st.mean(r["ld"].count(k) for r in rows)
        if mo or md:
            print(f"  {k:22s} {mo:6.1f} | {md:6.1f} | {mo - md:+6.1f}")
    print(f"\nquadrants owned: ours {Counter(r['qo'] for r in rows)}; DSM {Counter(r['qd'] for r in rows)}")
    print(f"tiles that differ in kind (same coordinates): mean {st.mean(len(r['diff']) for r in rows):.1f}, "
          f"median {st.median(len(r['diff']) for r in rows)}, min {min(len(r['diff']) for r in rows)}, max {max(len(r['diff']) for r in rows)}")
    print(f"  of which in DSM's 4th quadrant (locked for us): {st.mean(sum(1 for i in r['diff'] if r['lo'][i] == 'LOCKED') for r in rows):.1f}; "
          f"on land both own: {st.mean(sum(1 for i in r['diff'] if r['lo'][i] != 'LOCKED' and r['ld'][i] != 'LOCKED') for r in rows):.1f}")
    print(f"  same crop but a different planting day: {st.mean(len(r['age']) for r in rows):.1f}")
    pair = Counter()
    for r in rows:
        for i in r["diff"]:
            pair[(r["ld"][i], r["lo"][i])] += 1
    print("\nmost common tile differences (DSM has -> we have), per game:")
    for (x, y), v in pair.most_common(16):
        print(f"  {x:14s} -> {y:14s} {v / n:5.2f}")
    print("\ncrop ages at the dawn (planted day), mean tiles per game: ours | DSM")
    for crop in ("WHEAT", "TOMATO", "STRAWBERRY", "MELON", "CARROT"):
        for side in ("lo", "ld"):
            pass
        ao = Counter(t.get("planted_day") for r in rows for t in r["bo"] if isinstance(t, dict) and t.get("crop") == crop)
        ad = Counter(t.get("planted_day") for r in rows for t in r["bd"] if isinstance(t, dict) and t.get("crop") == crop)
        days = sorted(set(ao) | set(ad))
        if days:
            print(f"  {crop:10s} " + " ".join(f"d{x}:{ao.get(x, 0) / n:.1f}|{ad.get(x, 0) / n:.1f}" for x in days if x is not None and x >= 4))
    print(f"\ncash at the dawn (not part of the board): ours {st.mean(r['co'] for r in rows):.0f}, DSM {st.mean(r['cd'] for r in rows):.0f}")
    sk = sorted({k for r in rows for k in list(r['sho']) + list(r['shd'])})
    print("shed at the dawn, mean: " + ", ".join(f"{k} {st.mean(r['sho'].get(k, 0) for r in rows):.1f}|{st.mean(r['shd'].get(k, 0) for r in rows):.1f}" for k in sk))
    print("\nper game: tiles differing (total / on shared land), our quadrants vs DSM's, kind counts ours-DSM")
    for r in sorted(rows, key=lambda r: -len(r["diff"])):
        cnt = Counter(r["lo"]) - Counter(r["ld"]), Counter(r["ld"]) - Counter(r["lo"])
        print(f"  {r['c']['id']} {'+'.join(x[:4] for x in r['c']['shops8'][:3]):16s} diff {len(r['diff']):3d} / "
              f"{sum(1 for i in r['diff'] if r['lo'][i] != 'LOCKED' and r['ld'][i] != 'LOCKED'):3d}  Q {r['qo']}/{r['qd']}  "
              f"ours+: {dict(cnt[0])}  DSM+: {dict(cnt[1])}")
    if a.detail:
        r = next(r for r in rows if r["c"]["id"] == a.detail)
        ab = {"WHEAT": "Wh", "TOMATO": "To", "STRAWBERRY": "St", "MELON": "Me", "CARROT": "Ca", "COW": "co", "SHEEP": "sh",
              "GOOSE": "go", "EMPTY": "..", "WEED": "ww", "LOCKED": "##"}
        for name, lab_ in (("DSM", r["ld"]), ("ours", r["lo"])):
            print(f"\n{name} board at step {a.step} (rows y=0..9):")
            for y in range(10):
                print("   " + " ".join(ab.get(lab_[y * 10 + x], lab_[y * 10 + x][:2]) for x in range(10)))


if __name__ == "__main__":
    main()
