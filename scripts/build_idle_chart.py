"""Chart page for scripts/panel_idle.py output: idle (wasted) unit-hours per world by hour, where in the day, distance
from the shed and idle hours per unit-day, the leader vs arms. Inline SVG, no external libraries.
usage: build_idle_chart.py <idle.json> <out.html>"""
import json
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
arms = list(d)
COL = {'DSM': 'var(--c-dsm)', arms[1] if len(arms) > 1 else 'x': 'var(--c-a)', arms[2] if len(arms) > 2 else 'y': 'var(--c-b)'}


def bars(title, sub, cats, labels, key, h=220):
    n = len(cats)
    w_ = max(560, 34 * n * len(arms) // 2 + 80)
    left, bottom, top = 44, 36, 14
    iw, ih = w_ - left - 10, h - bottom - top
    vmax = max([d[a].get(key(c), 0) for a in arms for c in cats] + [1])
    step = iw / n
    bw = step * 0.8 / len(arms)
    out = [f'<figure><figcaption><b>{title}</b><span>{sub}</span></figcaption>',
           f'<svg viewBox="0 0 {w_} {h}" role="img" aria-label="{title}">']
    for k in range(5):
        y = top + ih - ih * k / 4
        out.append(f'<line x1="{left}" x2="{left + iw}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{left - 6}" y="{y + 4:.1f}" class="ax" text-anchor="end">{vmax * k / 4:.0f}</text>')
    for i, c in enumerate(cats):
        x0 = left + i * step + step * 0.1
        for j, a in enumerate(arms):
            v = d[a].get(key(c), 0)
            bh = ih * v / vmax
            out.append(f'<rect x="{x0 + j * bw:.1f}" y="{top + ih - bh:.1f}" width="{bw - 1:.1f}" height="{bh:.1f}" '
                       f'fill="{COL.get(a, "var(--c-a)")}"><title>{a} {labels[i]}: {v:.1f}</title></rect>')
        out.append(f'<text x="{left + i * step + step / 2:.1f}" y="{h - bottom + 16}" class="ax" text-anchor="middle">{labels[i]}</text>')
    out.append('</svg></figure>')
    return '\n'.join(out)


hours = list(range(24))
tot = {a: d[a].get('total', 0) for a in arms}
legend = ''.join(f'<span class="lg"><i style="background:{COL.get(a, "var(--c-a)")}"></i>{a}: <b>{tot[a]:.1f}</b> idle unit-hours a world</span>' for a in arms)
html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wasted hand hours</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--grid:#e6e3dc;--c-dsm:#2f6f5e;--c-a:#c0553a;--c-b:#e0a33b;--card:#ffffff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16171a;--fg:#ecebe6;--muted:#a09e97;--grid:#2c2e33;--c-dsm:#5fb39b;--c-a:#e07a5f;--c-b:#f2c14e;--card:#1e2024}}}}
:root[data-theme="dark"]{{--bg:#16171a;--fg:#ecebe6;--muted:#a09e97;--grid:#2c2e33;--c-dsm:#5fb39b;--c-a:#e07a5f;--c-b:#f2c14e;--card:#1e2024}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} p{{color:var(--muted);margin:4px 0 16px}}
figure{{background:var(--card);border:1px solid var(--grid);border-radius:10px;margin:0 0 18px;padding:12px 12px 4px}}
figcaption{{display:flex;flex-direction:column;margin-bottom:6px}} figcaption span{{color:var(--muted);font-size:13px}}
svg{{width:100%;height:auto;display:block}} .grid{{stroke:var(--grid)}} .ax{{fill:var(--muted);font-size:11px}}
.lgs{{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0 18px}} .lg i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
</style></head><body><main>
<h1>Wasted hand hours</h1>
<p>Idle unit-hours (a unit that exists and is given PASS) per world, days 11-28, averaged over the 40-world DSM panel. DSM = the leader's recorded game;
KB12 = current baseline; KB54 = KB12 + collects on the pens along each hand's planned path.</p>
<div class="lgs">{legend}</div>
{bars("By hour of day", "Almost all of ours falls at hours 21-23; hour 0 is the farmer holding while the hires spawn", hours, [str(h) for h in hours], lambda h: "h%02d" % h)}
{bars("Where in the hand's day", "Before its first action / between actions / after its last action", ["before", "between", "after"], ["before first action", "between actions", "after last action"], lambda c: "where|" + c)}
{bars("Distance from the shed at the idle hour", "Steps to the nearest shed tile (6 = 6 or more)", list(range(7)), [str(i) if i < 6 else "6+" for i in range(7)], lambda c: "dist|%d" % c)}
{bars("Idle hours per hand-day", "How many hand-days (per world) have 0, 1, 2 ... idle hours", list(range(7)), [str(i) if i < 6 else "6+" for i in range(7)], lambda c: "perday|%d" % c)}
</main></body></html>'''
Path(sys.argv[2]).write_text(html, encoding='utf-8')
print('written', sys.argv[2])
