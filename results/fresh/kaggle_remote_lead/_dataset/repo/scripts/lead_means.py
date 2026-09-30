"""mean ratio over 12 games and over the 11 without the collapsed-opponent game 112708229; day-1 animals."""
import json, sys
from collections import Counter
from pathlib import Path
for tag in sys.argv[1:]:
    rows = [json.load(open(f)) for f in sorted(Path(f'results/fresh/lead_agent_20260924/{tag}').glob('1*.json'))]
    rs = [r['ratio'] for r in rows]
    r11 = [r['ratio'] for r in rows if r['episode'] != 112708229]
    an1 = sum(sum(1 for i in range(0, 200, 2) if r['days'][1]['board'][i:i + 2] in ('sh', 'co') and r['days'][1]['board'][i:i+2] != 'pa') for r in rows) / len(rows)
    died = sum(sum(v for d in r['days'] for k, v in d['died'].items() if k.startswith('unw')) for r in rows) / len(rows)
    steps = sum(sum(sum(d['cmds'].values()) for d in r['days']) + sum(v for k, v in r['agent_log'].items() if k.startswith('pass')) for r in rows) / len(rows)
    pick = sum(sum(d['cmds'].get('PICKUP', 0) for d in r['days']) for r in rows) / len(rows)
    c9 = sum(r['days'][9]['cash'] / max(1, r['days'][9]['target_cash']) for r in rows) / len(rows)
    c12 = sum(r['days'][12]['cash'] / max(1, r['days'][12]['target_cash']) for r in rows) / len(rows)
    print(f"{tag:8s} n={len(rows)} mean12 {sum(rs)/len(rs):.3f} mean11 {sum(r11)/max(1,len(r11)):.3f} | d1 sh+co {an1:.1f} "
          f"plants died {died:.1f} unit-steps {steps:.0f} pickups {pick:.0f} cash/leader d9 {c9:.2f} d12 {c12:.2f}")
