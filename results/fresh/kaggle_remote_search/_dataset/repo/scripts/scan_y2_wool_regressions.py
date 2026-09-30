"""How many of the 180 ladder-panel worlds show the y2 wool-regression pattern: yarn_service
fired (overlay counter > 0) but y2 sold fewer WOOL units than mgt_lib584 (mgt_m1) in the same
world. Reads the saved per-world results under results/fresh/ladder_panel/mgt_y2/ and
results/fresh/ladder_panel/mgt_lib584/ (fields: sold, revenue, overlay) -- no engine run needed.

Usage: .venv/Scripts/python.exe scripts/scan_y2_wool_regressions.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Y2 = ROOT / 'results/fresh/ladder_panel/mgt_y2'
BASE = ROOT / 'results/fresh/ladder_panel/mgt_lib584'


def main():
    rows = []
    for p in sorted(Y2.glob('*.json')):
        bp = BASE / p.name
        if not bp.exists():
            continue
        y2 = json.loads(p.read_text(encoding='utf-8'))
        b = json.loads(bp.read_text(encoding='utf-8'))
        yarn = int((y2.get('overlay') or {}).get('yarn_service', 0) or 0)
        wool_y2 = int((y2.get('sold') or {}).get('WOOL', 0) or 0)
        wool_b = int((b.get('sold') or {}).get('WOOL', 0) or 0)
        rev_y2 = float((y2.get('revenue') or {}).get('WOOL', 0) or 0)
        rev_b = float((b.get('revenue') or {}).get('WOOL', 0) or 0)
        rows.append(dict(episode=p.stem, yarn_service=yarn, wool_y2=wool_y2, wool_base=wool_b,
                          wool_delta=wool_y2 - wool_b, rev_delta=rev_y2 - rev_b,
                          margin_y2=y2.get('margin'), margin_base=b.get('margin'),
                          margin_delta=(y2.get('margin') or 0) - (b.get('margin') or 0),
                          ops_harvest_y2=int((y2.get('overlay') or {}).get('ops_harvest', 0) or 0),
                          ops_harvest_base=int((b.get('overlay') or {}).get('ops_harvest', 0) or 0)))
    total = len(rows)
    fired = [r for r in rows if r['yarn_service'] > 0]
    affected = [r for r in fired if r['wool_delta'] < 0]
    worse_margin = [r for r in fired if r['margin_delta'] < 0]
    print(f'{total} worlds with both results')
    print(f'{len(fired)} worlds where yarn_service fired (overlay counter > 0)')
    print(f'{len(affected)} of those sold FEWER wool units with y2 than mgt_lib584 (the anomaly pattern)')
    print(f'  wool_delta sum over affected: {sum(r["wool_delta"] for r in affected)}, '
          f'rev_delta sum: {sum(r["rev_delta"] for r in affected):.0f}')
    print(f'{len(worse_margin)} of the yarn_service worlds have a WORSE margin_delta than mgt_lib584')
    print(f'  margin_delta sum over fired: {sum(r["margin_delta"] for r in fired):.0f}; '
          f'mean {sum(r["margin_delta"] for r in fired) / max(1, len(fired)):.0f}')
    not_fired = [r for r in rows if r['yarn_service'] == 0]
    print(f'{len(not_fired)} worlds where yarn_service never fired (should be identical/near-identical to mgt_lib584)')
    nonzero_diff_when_off = [r for r in not_fired if r['wool_delta'] != 0 or abs(r['margin_delta']) > 1]
    print(f'  of those, {len(nonzero_diff_when_off)} still show a nonzero wool_delta or margin_delta > 1 (unrelated noise/other diffs)')
    affected.sort(key=lambda r: r['wool_delta'])
    out = dict(total=total, fired=len(fired), affected=len(affected), worse_margin=len(worse_margin),
               not_fired=len(not_fired), rows=rows)
    out_path = ROOT / 'results/fresh/newphase_20260923/y2_anomaly/wool_regression_scan.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f'\nworst 10 by wool_delta:')
    for r in affected[:10]:
        print(f"  {r['episode']}: wool {r['wool_base']}->{r['wool_y2']} ({r['wool_delta']:+d}), "
              f"rev {r['rev_delta']:+.0f}, margin_delta {r['margin_delta']:+.0f}, yarn_service={r['yarn_service']}, "
              f"ops_harvest {r['ops_harvest_base']}->{r['ops_harvest_y2']}")
    print(f'\nwritten to {out_path}')


if __name__ == '__main__':
    main()
