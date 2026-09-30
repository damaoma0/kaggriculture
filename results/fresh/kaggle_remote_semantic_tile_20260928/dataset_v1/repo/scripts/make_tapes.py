"""Turn downloaded ladder replays into local tape agents that replay an opponent's recorded actions.

Usage: python scripts/make_tapes.py [--me "Yiyang Xu"] [--out agents/tapes]

For every replay in data/replays/ that includes our team, the *other* seat's action stream is
written to agents/tapes/<opponent>_<episode>.py. A tape agent is exact only for open-loop
opponents (the meta tapes), which most of them are; closed-loop opponents are frozen at what
they did in that one game.
"""
import argparse
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE = '''"""Tape agent reconstructed from ladder episode {episode}: {name} (seat {seat}). Auto-generated."""
import json, zlib, base64
_ACTIONS = json.loads(zlib.decompress(base64.b64decode(
{blob}
)).decode())


def agent(obs):
    step = int(obs.get("step", 0))
    if step < len(_ACTIONS) and _ACTIONS[step]:
        a = _ACTIONS[step]
        hands = obs["farms"][int(obs.get("player", 0))].get("hands") or []
        h = list(a.get("hands") or [])
        h = (h + [["PASS"]] * len(hands))[:len(hands)]
        return {{"farmer": a.get("farmer") or ["PASS"], "hands": h, "market": a.get("market") or []}}
    return {{"farmer": ["PASS"], "hands": [], "market": []}}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--me", default="Yiyang Xu")
    ap.add_argument("--out", default="agents/tapes")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for f in sorted(glob.glob(str(ROOT / "data" / "replays" / "episode-*-replay.json"))):
        j = json.load(open(f, encoding="utf-8"))
        names = j.get("info", {}).get("TeamNames") or []
        if names.count(args.me) != 1:
            continue
        op = 1 - names.index(args.me)
        episode = re.search(r"episode-(\d+)", f).group(1)
        actions = [(s[op].get("action") or {}) for s in j["steps"]]
        # steps[0] is the initial state; action at index i was taken at step i-1 in obs terms
        actions = actions[1:] + [{}]
        blob = __import__("base64").b64encode(__import__("zlib").compress(json.dumps(actions).encode())).decode()
        blob_lines = ",\n".join('    "%s"' % blob[i:i + 100] for i in range(0, len(blob), 100))
        blob_py = "b''.join([\n" + ",\n".join('    b"%s"' % blob[i:i + 100] for i in range(0, len(blob), 100)) + "\n])"
        safe = re.sub(r"[^A-Za-z0-9]+", "_", names[op]).strip("_")[:24] or "opp"
        path = out / f"{safe}_{episode}.py"
        path.write_text(TEMPLATE.format(episode=episode, name=names[op].encode("ascii", "replace").decode(),
                                        seat=op, blob=blob_py), encoding="utf-8")
        made.append((path.name, op))
    for name, seat in made:
        print(name, "seat", seat)
    print(len(made), "tapes written to", out)


if __name__ == "__main__":
    main()
