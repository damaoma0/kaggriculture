"""Day-12 side-by-side viewer: leader's recorded game vs our agent, same world (thread day12_viz, 2026-09-25).

Two comparisons, both in the SAME 12 lead_g1 worlds (recorded seed, forced shop schedule, opponent = the tape's
recorded opp_actions):
  t0           leader (data/leader_tapes) vs T from step 0 (results/fresh/upkeep_20260925/ttape) -- day 12 only.
  exact_start  leader vs an exact-opening hybrid: leader's own recorded actions through step 263 (day 0-10), then
               results/fresh/day12_viz/xdyn_streams/<ep>.json from step 264 (day-11 morning) -- day 11 AND day 12.
               Only built when that directory exists (a separate thread produces it); the day-11 morning boards
               (step 264, pre-action) must reproduce the leader's own state exactly -- checked per game.

Replays both sides through scripts/upkeep_engine.py (light in-process engine, no kaggle_environments import), NOT
by running our agent. Captures full tile/unit/inventory/shed/cash state for every hour needed, plus per-day running
counters computed by hooking the engine's own _apply_unit_action / _commit_unit (same technique as lead_g1.py).

usage: build_day12_side_by_side.py [--games team:ep,...]
Writes results/fresh/day12_viz/day12_data.json (raw, uncompressed) and viz/day12_leader_vs_T.html (embedded,
gzip+base64). Prints a verification table (final-cash reproduction + day-12 counter spot-check vs xopen ledgers).
"""
import base64
import gzip
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lead_g1                      # noqa: E402  (GAMES, TEAM)
import upkeep_engine as UE          # noqa: E402

TTAPE_DIR = ROOT / 'results/fresh/upkeep_20260925/ttape'
XOPEN_DIR = ROOT / 'results/fresh/xopen_20260925/g1'
XDYN_DIR = ROOT / 'results/fresh/day12_viz/xdyn_streams'
OUT_DIR = ROOT / 'results/fresh/day12_viz'
OUT_HTML = ROOT / 'viz/day12_leader_vs_T.html'
DAY11_START, DAY12_START, DAY12_END, DAY13_MORNING = 264, 288, 311, 312
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
MEM_MIN_GB = 0.8


def free_gb():
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        return None


def check_memory(tag):
    g = free_gb()
    if g is not None:
        print(f'  [mem] {g:.2f} GB free ({tag})', flush=True)
        if g < MEM_MIN_GB:
            raise SystemExit(f'ABORT: free memory {g:.2f} GB < {MEM_MIN_GB} GB threshold at {tag}')
    return g


# ---------------------------------------------------------------- engine hooks (per-day counters) ----------
def new_day_counters():
    return dict(eff={}, harv={}, plant={}, sold={}, rev={}, bought={}, spend={}, idle=0)


def install_hooks(E):
    """Wrap _apply_unit_action / _commit_unit once; ctx['rec'] selects which farm/day-counter dict is 'ours'
    for the currently running replay (None = pass through untouched, e.g. opponent-side calls)."""
    orig_apply = E._apply_unit_action
    orig_commit = E._commit_unit
    ctx = {'rec': None}

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        rec = ctx['rec']
        if rec is None or farm is not rec['farm']:
            return orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        op = action[0] if isinstance(action, list) and action else None
        if op in (None, 'PASS'):
            return orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        pos0 = E._farmer_position(farm, idx)
        tile0 = deepcopy(farm['tiles'][pos0[1]][pos0[0]]) if pos0 is not None else None
        inv0 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        shed0 = dict(private['shed'])
        r = orig_apply(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        if op in MOVES:
            return r
        pos1 = E._farmer_position(farm, idx)
        tile1 = deepcopy(farm['tiles'][pos1[1]][pos1[0]]) if pos1 is not None else None
        inv1 = dict(private['inventories'][idx]) if idx < len(private['inventories']) else {}
        if (pos0 != pos1) or (tile0 != tile1) or (inv0 != inv1) or (shed0 != private['shed']):
            d = rec['day']
            d['eff'][op] = d['eff'].get(op, 0) + 1
            if op == 'HARVEST':
                for k, v in inv1.items():
                    dv = v - inv0.get(k, 0)
                    if dv > 0:
                        d['harv'][k] = d['harv'].get(k, 0) + dv
            elif op == 'PLANT' and isinstance(action, list) and len(action) > 1:
                d['plant'][action[1]] = d['plant'].get(action[1], 0) + 1
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = orig_commit(op, item, price, farm, private, market, shed_capacity)
        rec = ctx['rec']
        if rec is not None and r and farm is rec['farm']:
            d = rec['day']
            if op == 'SELL':
                d['sold'][item] = d['sold'].get(item, 0) + 1
                d['rev'][item] = d['rev'].get(item, 0) + price
            else:
                key = f'{op}:{item}'
                d['bought'][key] = d['bought'].get(key, 0) + 1
                d['spend'][key] = d['spend'].get(key, 0) + price
        return r

    E._apply_unit_action = apply_hook
    E._commit_unit = commit_hook
    return ctx


# ---------------------------------------------------------------- tile dedup + frame capture ----------------
def tile_id(tile, lookup, table):
    key = json.dumps(tile, sort_keys=True, separators=(',', ':'))
    i = lookup.get(key)
    if i is None:
        i = len(table)
        lookup[key] = i
        table.append(deepcopy(tile))
    return i


def build_frame(w, seat, action, day_counters, lookup, table):
    farm = w.farms[seat]
    private = w.private(seat)
    board = [tile_id(t, lookup, table) for row in farm['tiles'] for t in row]
    units = [list(farm['farmer'])] + [list(h) for h in farm['hands']]
    inv = [dict(private['inventories'][i]) if i < len(private['inventories']) else {} for i in range(len(units))]
    return dict(step=w.t, cash=round(float(farm['money']), 2), units=units, inv=inv,
                shed=dict(private['shed']), action=deepcopy(action) if action else None,
                board=board, counters=deepcopy(day_counters))


def run_side(seed, shops, seat, provider, lo, hi, run_to, lookup, table, ctx):
    """Step an engine World from 0..run_to-1 (matching upkeep_engine.replay_check's `while w.t < N` convention:
    run_to=719 replays the full season). Captures a pre-action frame for every step in [lo, hi], plus one extra
    post-action frame at hi+1 (the 'next morning' result, action=None)."""
    w = UE.World(seed, shops)
    rec = {'farm': w.farms[seat], 'day': new_day_counters()}
    ctx['rec'] = rec
    frames = []
    try:
        for t in range(0, run_to):
            if t % 24 == 0:
                rec['day'] = new_day_counters()
            own_a, opp_a = provider(t)
            if lo <= t <= hi:
                frames.append(build_frame(w, seat, own_a, rec['day'], lookup, table))
            farm = w.farms[seat]
            n_units = 1 + len(farm['hands'])
            ops = [(own_a.get('farmer') or ['PASS'])[0] if own_a else 'PASS']
            for h in (own_a.get('hands') or []) if own_a else []:
                ops.append(h[0] if isinstance(h, list) and h else 'PASS')
            while len(ops) < n_units:
                ops.append('PASS')
            rec['day']['idle'] += sum(1 for o in ops[:n_units] if o in (None, 'PASS'))
            acts = [None, None]
            acts[seat], acts[1 - seat] = own_a, opp_a
            w.step(acts)
            if t == hi:
                frames.append(build_frame(w, seat, None, rec['day'], lookup, table))
        final_seat = float(w.farms[seat]['money'])
        final_opp = float(w.farms[1 - seat]['money'])
    finally:
        ctx['rec'] = None
    return frames, final_seat, final_opp


# ---------------------------------------------------------------- xdyn (exact-start) loader ------------------
def load_xdyn(ep):
    p = XDYN_DIR / f'{ep}.json'
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding='utf-8'))
    actions, offset = (raw.get('actions'), raw.get('start_step', raw.get('offset'))) if isinstance(raw, dict) else (raw, None)
    if not actions:
        return None
    candidates = [offset] if offset is not None else [0 if len(actions) >= DAY13_MORNING else DAY11_START]
    if offset is None and 0 not in candidates:
        candidates.append(0)
    return dict(actions=actions, candidates=candidates)


def xdyn_action_at(xdyn, offset, t):
    idx = t - offset
    a = xdyn['actions'][idx] if 0 <= idx < len(xdyn['actions']) else None
    return deepcopy(a) if isinstance(a, dict) and a else deepcopy(UE.PASS)


# ---------------------------------------------------------------- per-game orchestration ---------------------
def spot_check(computed, ledger_days, day=12):
    ld = ledger_days[day]
    out = {}
    for key in ('eff', 'harv', 'plant', 'sold', 'rev'):
        out[key] = dict(ours=computed.get(key, {}), ledger=ld.get(key, {}), match=computed.get(key, {}) == ld.get(key, {}))
    return out


def process_game(game, ctx):
    team_id, ep_s = game.split(':')
    ep = int(ep_s)
    leader_tape = UE.load_tape(team_id, ep)
    seat, seed, shops = leader_tape['seat'], leader_tape['seed'], leader_tape['shops']
    ttape = json.load(gzip.open(TTAPE_DIR / f'{ep}.json.gz', 'rt', encoding='utf-8'))
    assert ttape['seat'] == seat and ttape['seed'] == seed, f'{game}: T tape seat/seed mismatch'

    lookup, table = {}, []

    def leader_provider(t):
        return UE.tape_action(leader_tape['actions'], t), UE.tape_action(leader_tape['opp_actions'], t)

    def t_provider(t):
        return UE.tape_action(ttape['actions'], t), UE.tape_action(leader_tape['opp_actions'], t)

    leader_frames, leader_final, leader_opp_final = run_side(seed, shops, seat, leader_provider, DAY11_START, DAY12_END, 719, lookup, table, ctx)
    t_frames, t_final, t_opp_final = run_side(seed, shops, seat, t_provider, DAY12_START, DAY12_END, 719, lookup, table, ctx)

    leader_ledger = json.loads((XOPEN_DIR / 'LEADER' / f'{ep}.json').read_text(encoding='utf-8'))
    t_ledger = json.loads((XOPEN_DIR / 'T' / f'{ep}.json').read_text(encoding='utf-8'))
    leader_d12_counters = leader_frames[DAY13_MORNING - DAY11_START]['counters']   # post-day12, pre-reset
    t_d12_counters = t_frames[DAY13_MORNING - DAY12_START]['counters']

    verify = dict(
        leader_cash_ok=round(leader_final) == round(leader_tape['rewards'][seat]),
        leader_cash=leader_final, leader_target=leader_tape['rewards'][seat],
        leader_opp_cash_ok=round(leader_opp_final) == round(leader_tape['rewards'][1 - seat]),
        t_cash_ok=round(t_final) == round(ttape['final']),
        t_cash=t_final, t_target=ttape['final'],
        t_opp_cash_ok=round(t_opp_final) == round(ttape['opp_final']),
        spot_leader=spot_check(leader_d12_counters, leader_ledger['days']),
        spot_t=spot_check(t_d12_counters, t_ledger['days']),
    )

    result = dict(episode=ep, team=lead_g1.TEAM.get(team_id, team_id), seat=seat,
                  leader=dict(frames=leader_frames, final=leader_final, target=leader_tape['rewards'][seat]),
                  t=dict(frames=t_frames, final=t_final, target=ttape['final']),
                  x=dict(available=False), verify=verify)

    xdyn = load_xdyn(ep)
    if xdyn is not None:
        handoff_ok, x_frames, x_final, used_offset = False, None, None, None
        for offset in xdyn['candidates']:
            def x_provider(t, _off=offset):
                if t < DAY11_START:
                    return UE.tape_action(leader_tape['actions'], t), UE.tape_action(leader_tape['opp_actions'], t)
                return xdyn_action_at(xdyn, _off, t), UE.tape_action(leader_tape['opp_actions'], t)
            frames, final_seat, final_opp = run_side(seed, shops, seat, x_provider, DAY11_START, DAY12_END, DAY13_MORNING, lookup, table, ctx)
            f0 = frames[0]
            ok = (f0['board'] == leader_frames[0]['board'] and f0['units'] == leader_frames[0]['units'] and
                  f0['inv'] == leader_frames[0]['inv'] and f0['shed'] == leader_frames[0]['shed'] and
                  abs(f0['cash'] - leader_frames[0]['cash']) < 0.01)
            if ok:
                handoff_ok, x_frames, x_final, x_opp_final, used_offset = True, frames, final_seat, final_opp, offset
                break
        if x_frames is None:
            x_frames, x_final, x_opp_final, used_offset = frames, final_seat, final_opp, xdyn['candidates'][-1]
        result['x'] = dict(available=True, frames=x_frames, final_at_d12end=x_final, opp_final_at_d12end=x_opp_final,
                            handoff_ok=handoff_ok, offset_used=used_offset)

    result['tiles'] = table
    return result


def main():
    argv = sys.argv[1:]
    games = lead_g1.GAMES
    if '--games' in argv:
        sel = argv[argv.index('--games') + 1].split(',')
        games = [g for g in lead_g1.GAMES if any(g.endswith(s) or g == s for s in sel)] or sel

    check_memory('start')
    E = UE.engine()
    ctx = install_hooks(E)

    results = []
    t0 = time.time()
    for i, game in enumerate(games):
        check_memory(f'before {game}')
        r = process_game(game, ctx)
        results.append(r)
        print(f'  {game}: leader {r["verify"]["leader_cash_ok"]} T {r["verify"]["t_cash_ok"]} '
              f'x_available={r["x"]["available"]}' + (f" handoff_ok={r['x'].get('handoff_ok')}" if r['x']['available'] else ''),
              flush=True)
    print(f'engine wall: {time.time() - t0:.1f}s', flush=True)
    check_memory('after replays')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'day12_data.json').write_text(json.dumps(results, separators=(',', ':')), encoding='utf-8')

    print_verify_table(results)
    write_html(results)
    check_memory('after html write')


def print_verify_table(results):
    lines = ['', '| game (team) | leader cash | ok | T cash | ok | spot-check (leader/T eff,harv,plant,sold,rev) | x avail | handoff ok |',
             '|---|---:|---|---:|---|---|---|---|']
    for r in results:
        v = r['verify']
        sl = all(v['spot_leader'][k]['match'] for k in v['spot_leader'])
        st = all(v['spot_t'][k]['match'] for k in v['spot_t'])
        lines.append(f"| {r['episode']} ({r['team']}) | {v['leader_cash']:.0f} ({v['leader_target']:.0f}) | "
                      f"{'OK' if v['leader_cash_ok'] else 'MISMATCH'} | {v['t_cash']:.0f} ({v['t_target']:.0f}) | "
                      f"{'OK' if v['t_cash_ok'] else 'MISMATCH'} | {'OK/OK' if sl and st else f'{sl}/{st}'} | "
                      f"{r['x']['available']} | {r['x'].get('handoff_ok', '-')} |")
    table = '\n'.join(lines)
    print(table)
    (OUT_DIR / 'verify_table.md').write_text(table, encoding='utf-8')
    # print any spot-check mismatch in full, for diagnosis
    for r in results:
        for side, key in (('leader', 'spot_leader'), ('T', 'spot_t')):
            sc = r['verify'][key]
            for field, d in sc.items():
                if not d['match']:
                    print(f"  MISMATCH {r['episode']} {side} {field}: ours={d['ours']} ledger={d['ledger']}")


# ---------------------------------------------------------------- HTML export ---------------------------------
def write_html(results):
    payload = dict(built=time.strftime('%Y-%m-%d %H:%M'), games=results)
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    compressed = gzip.compress(body, mtime=0)
    b64 = base64.b64encode(compressed).decode('ascii')
    html = HTML_TEMPLATE.replace('__DATA_B64__', b64)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding='utf-8')
    print(f'wrote {OUT_HTML} ({OUT_HTML.stat().st_size / 1e6:.2f} MB), payload raw {len(body) / 1e6:.2f} MB, '
          f'gzip {len(compressed) / 1e6:.2f} MB, {len(results)} games')


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kaggriculture · Day 12 · leader vs our agent</title>
<style>
:root{color-scheme:dark;--bg:#101713;--panel:#19231d;--line:#34463a;--text:#ecf2e9;--muted:#afbcaf;--accent:#b7e88e;--diff:#ffce54}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}
header,main,footer{max-width:1400px;margin:auto;padding:20px 28px}
h1{font-size:26px;letter-spacing:-.6px;margin:0}h2{font-size:16px;margin:0 0 10px}
p{margin:6px 0}.eyebrow{color:var(--accent);font-size:12px;letter-spacing:1.5px;text-transform:uppercase}
.muted,small{color:var(--muted)}button,select,input{font:inherit}
button,select{color:var(--text);background:#233127;border:1px solid var(--line);border-radius:7px;padding:7px 10px}
button{cursor:pointer}button:hover{border-color:var(--accent)}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.primary{background:var(--accent);color:#162210;border:0;font-weight:600}
select{max-width:100%}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.transport{margin:0 0 16px;background:var(--panel);padding:14px 16px;border:1px solid var(--line);border-radius:12px}
#clock{margin-left:auto;font-variant-numeric:tabular-nums}
#seek{width:100%;accent-color:var(--accent);margin:13px 0 3px}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.panel{background:var(--panel);border:1px solid var(--line);padding:16px;border-radius:12px;min-width:0}
.panelhead{display:flex;justify-content:space-between;gap:8px;align-items:baseline;margin-bottom:10px}
.panelhead h2{margin:0}
.board{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:3px}
.tile{aspect-ratio:1;border:1px solid transparent;padding:0;border-radius:4px;position:relative;
  font-size:clamp(10px,1.25vw,15px);background:#27372b;overflow:visible}
.tile.selected{outline:2px solid #f7f7e6;outline-offset:1px}
.tile.diff{box-shadow:inset 0 0 0 2px var(--diff)}
.tile.locked{background:#111a15;color:#607267}
.tile .units{position:absolute;inset:1px auto auto 1px;display:flex;flex-direction:column;gap:1px;align-items:flex-start}
.tile .unit{background:#07160dee;color:#fff;border-radius:3px;font-size:8.5px;padding:0 2px;line-height:1.3;white-space:nowrap}
.tile .unit.key{background:var(--diff);color:#172010}
.tile .age{position:absolute;right:1px;bottom:0;font-size:8px;color:#cfe;background:#07160dcc;border-radius:2px;padding:0 1px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:10px 0}
.stat{background:#1f2b22;border-radius:8px;padding:6px 7px}
.stat strong{display:block;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}
.stat span{font-size:10.5px;color:var(--muted)}
.breakdown{font-size:12px;display:grid;gap:3px;margin:8px 0}
.breakdown strong{color:var(--accent);font-weight:600;margin-right:4px}
.detail{border-top:1px solid var(--line);margin-top:10px;padding-top:9px;font-size:12px}
.detail div{margin:2px 0}
#legend{display:flex;gap:6px 10px;flex-wrap:wrap;font-size:11.5px;margin:10px 0}
.chip{padding:2px 6px;border-radius:4px;background:#2b3a2e;font-size:11.5px}
#verify{font-size:12.5px;color:var(--accent);margin:6px 0}
#error{color:#ffb4a4}
footer{color:var(--muted);font-size:12px;padding-bottom:32px}
button:disabled,select:disabled{opacity:.45;cursor:default}
#worldbar{margin-bottom:10px}
.tag{font-size:11px;background:#233127;border-radius:4px;padding:1px 6px;color:var(--muted)}
@media(max-width:900px){.layout{grid-template-columns:1fr}header,main,footer{padding:14px}}
</style></head><body>
<header>
<div class="eyebrow">Kaggriculture · day 12 side-by-side</div>
<h1>Leader's recorded game vs our agent</h1>
<p class="muted">Same seed, forced shop schedule and recorded opponent, replayed exactly through the official engine. Both boards show <strong>our own farm</strong> under two different action policies &mdash; the opponent is identical in both.</p>
<p id="error" role="alert"></p>
</header>
<main id="viewer" hidden>
<section class="transport" aria-label="Replay controls">
<div class="row" id="worldbar">
<label>World <select id="world"></select></label>
<label>Comparison <select id="mode"><option value="t0">T from step 0 (day 12)</option><option value="exact" id="modeX">Exact start (day 11-12)</option></select></label>
<span id="verify"></span>
</div>
<div class="row">
<button id="play" class="primary">&#9654; Play</button>
<button id="prev" aria-label="Previous hour">&minus; Hour</button>
<button id="next" aria-label="Next hour">+ Hour</button>
<label>Speed <select id="speed"><option value="700">Slow</option><option value="220" selected>Normal</option><option value="80">Fast</option></select></label>
<strong id="clock"></strong>
</div>
<div id="status" class="muted" aria-live="polite"></div>
<input id="seek" type="range" min="0" max="48" value="0" aria-label="Replay hour">
</section>
<div class="layout">
<section class="panel">
<div class="panelhead"><h2 id="titleL">Leader (recorded)</h2><span class="tag">cash <strong id="cashL"></strong></span></div>
<div id="boardL" class="board" aria-label="Leader farm board"></div>
<div class="stats" id="statsL"></div>
<div class="breakdown" id="breakdownL"></div>
<div class="detail">
<div><strong>Carried:</strong> <span id="carriedL"></span></div>
<div><strong>Shed:</strong> <span id="shedL"></span></div>
<div><strong>Market orders this hour:</strong></div>
<div id="ordersL" style="white-space:pre-wrap;font:11.5px/1.5 ui-monospace,monospace"></div>
<div><strong>Selected tile:</strong> <span id="tiledetailL"></span></div>
</div>
</section>
<section class="panel">
<div class="panelhead"><h2 id="titleR">T</h2><span class="tag">cash <strong id="cashR"></strong></span></div>
<div id="boardR" class="board" aria-label="Other side farm board"></div>
<div class="stats" id="statsR"></div>
<div class="breakdown" id="breakdownR"></div>
<div class="detail">
<div><strong>Carried:</strong> <span id="carriedR"></span></div>
<div><strong>Shed:</strong> <span id="shedR"></span></div>
<div><strong>Market orders this hour:</strong></div>
<div id="ordersR" style="white-space:pre-wrap;font:11.5px/1.5 ui-monospace,monospace"></div>
<div><strong>Selected tile:</strong> <span id="tiledetailR"></span></div>
</div>
</section>
</div>
<section class="panel" style="margin-top:18px">
<h2>Legend</h2>
<div id="legend"></div>
<p class="muted">Unit badge: <strong>F</strong> = farmer, otherwise hand index; after the colon, that hour's action (&uarr;&darr;&rarr;&larr; move, P plant, W water, H harvest, Fd feed, C care, Fz fertilize, Cf collect fertilizer, D dig, Pk pickup, Dr drop, Pl place, Bc/Bp build coop/pasture). A gold outline on a tile means the two boards disagree there this hour. Click any tile to inspect it below both boards.</p>
</section>
</main>
<footer id="provenance">Built by scripts/build_day12_side_by_side.py &middot; replayed through scripts/upkeep_engine.py (official kaggriculture 1.32.7 engine, loaded by path). Space: play/pause. Arrow keys: one hour; Shift+arrow: one day.</footer>
<script id="data" type="application/octet-stream">__DATA_B64__</script>
<script>
'use strict';
const $=id=>document.getElementById(id);
const TYPES={WHEAT:['🌾','#665526'],CARROT:['🥕','#744827'],TOMATO:['🍅','#73362f'],STRAWBERRY:['🍓','#713748'],MELON:['🍉','#335b37'],GOOSE:['🦢','#46545c'],COW:['🐄','#3d5264'],SHEEP:['🐑','#596050'],WEED:['×','#534c36'],PASTURE:['🌿','#35483b'],COOP:['🏠','#35483b']};
const ACTS={NORTH:'↑',SOUTH:'↓',EAST:'→',WEST:'←',PLANT:'P',WATER:'W',HARVEST:'H',FEED:'Fd',CARE:'C',FERTILIZE:'Fz',COLLECT_FERTILIZER:'Cf',DIG:'D',BUILD_COOP:'Bc',BUILD_PASTURE:'Bp',PICKUP:'Pk',DROP:'Dr',PLACE:'Pl',PASS:'·'};
const fmt=n=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:0});
const nice=s=>String(s).toLowerCase().replaceAll('_',' ');
const sumv=o=>Object.values(o||{}).reduce((a,b)=>a+b,0);

let DATA=null, games=[], gi=0, mode='t0', cur=0, timer=null, selected=44;

function leftFrames(){const g=games[gi];return mode==='exact'?g.leader.frames:g.leader.frames.slice(g.leader.frames.length-g.t.frames.length);}
function rightFrames(){const g=games[gi];return mode==='exact'?(g.x.frames||[]):g.t.frames;}

function stop(){clearInterval(timer);timer=null;$('play').textContent='▶ Play';}
function tick(){const LF=leftFrames();if(cur<LF.length-1){cur++;render();}else{stop();}}
function jump(t){stop();const LF=leftFrames();cur=Math.max(0,Math.min(LF.length-1,t));render();}

function drawBoard(elId,g,mine,other){
  const el=$(elId);
  const positions={};
  mine.units.forEach((p,u)=>{const k=p[1]*10+p[0];(positions[k]=positions[k]||[]).push(u);});
  const day=Math.floor(mine.step/24);
  for(let i=0;i<100;i++){
    const b=el.children[i];
    const tile=g.tiles[mine.board[i]];
    const isObj=tile&&typeof tile==='object';
    const kind=isObj?(tile.crop||tile.animal||tile.kind):tile;
    const style=TYPES[kind];
    const diff=mine.board[i]!==other.board[i];
    b.className='tile'+(tile==='LOCKED'?' locked':'')+(selected===i?' selected':'')+(diff?' diff':'');
    b.style.background=style?style[1]:'';
    const label=style?style[0]+(isObj&&tile.yield_units?tile.yield_units:''):'';
    let age='';
    if(isObj){
      if(tile.kind==='PLANT'&&typeof tile.planted_day==='number')age='d'+(day-tile.planted_day);
      else if(tile.animal&&typeof tile.placed_day==='number')age='d'+(day-tile.placed_day);
    }
    b.replaceChildren(document.createTextNode(label));
    if(age){const a=document.createElement('span');a.className='age';a.textContent=age;b.append(a);}
    const us=positions[i];
    if(us){
      const wrap=document.createElement('span');wrap.className='units';
      us.forEach(u=>{
        const act=u===0?(mine.action&&mine.action.farmer):((mine.action&&mine.action.hands)||[])[u-1];
        const op=Array.isArray(act)&&act.length?act[0]:'PASS';
        const tag=document.createElement('span');tag.className='unit'+(u===0?' key':'');
        tag.textContent=(u===0?'F':u)+(ACTS[op]?':'+ACTS[op]:'');
        wrap.append(tag);
      });
      b.append(wrap);
    }
    b.title=`(${i%10}, ${Math.floor(i/10)})`+(isObj?' '+Object.entries(tile).map(([k,v])=>`${k}=${v}`).join(' '):tile?' '+tile:' empty');
  }
}

function fillDetail(tag,g,frame){
  const tile=g.tiles[frame.board[selected]];
  $('tiledetail'+tag).textContent=tile==null?'Empty':typeof tile==='string'?tile:Object.entries(tile).map(([k,v])=>`${nice(k)}: ${v}`).join(' · ');
}

function fillSide(tag,g,frame,title){
  $('title'+tag).textContent=title;
  $('cash'+tag).textContent=fmt(frame.cash);
  const c=frame.counters||{eff:{},harv:{},plant:{},sold:{},rev:{},idle:0};
  const rows=[
    ['Hands',frame.units.length-1],
    ['Waters',c.eff.WATER||0],['Fertilizes',c.eff.FERTILIZE||0],['Feeds',c.eff.FEED||0],
    ['Cares',c.eff.CARE||0],['Collects',c.eff.COLLECT_FERTILIZER||0],
    ['Idle unit-steps',c.idle||0],['Units harvested',sumv(c.harv)],['Revenue today',fmt(sumv(c.rev))],
  ];
  $('stats'+tag).replaceChildren(...rows.map(([k,v])=>{const d=document.createElement('div');d.className='stat';d.innerHTML=`<strong>${v}</strong><span>${k}</span>`;return d;}));
  const lists=[['Harvested',c.harv],['Planted',c.plant],['Sold',c.sold],['Revenue',c.rev]];
  $('breakdown'+tag).replaceChildren(...lists.map(([label,obj])=>{
    const div=document.createElement('div');
    const entries=Object.entries(obj||{});
    div.innerHTML=`<strong>${label}:</strong> `+(entries.length?entries.map(([k,v])=>`${nice(k)} ${fmt(v)}`).join(', '):'—');
    return div;
  }));
  const tot={};(frame.inv||[]).forEach(u=>Object.entries(u||{}).forEach(([k,v])=>{tot[k]=(tot[k]||0)+v;}));
  const te=Object.entries(tot);
  $('carried'+tag).textContent=te.length?te.map(([k,v])=>`${nice(k)} ${v}`).join(', '):'none';
  const se=Object.entries(frame.shed||{});
  $('shed'+tag).textContent=se.length?se.map(([k,v])=>`${nice(k)} ${v}`).join(', '):'empty';
  const a=frame.action;
  $('orders'+tag).textContent=a?((a.market||[]).map(o=>o.join(' ')).join('\n')||'No market orders this hour'):'End of captured range (no pending action)';
  fillDetail(tag,g,frame);
}

function renderVerify(g){
  const v=g.verify;
  const parts=[
    `Leader cash reproduced: ${fmt(v.leader_cash)} vs recorded ${fmt(v.leader_target)} (${v.leader_cash_ok?'OK':'MISMATCH'})`,
    `T cash reproduced: ${fmt(v.t_cash)} vs recorded ${fmt(v.t_target)} (${v.t_cash_ok?'OK':'MISMATCH'})`,
  ];
  if(g.x&&g.x.available)parts.push(`Day-11 handoff boards identical: ${g.x.handoff_ok?'OK':'MISMATCH'}`);
  $('verify').textContent=parts.join(' · ');
}

function render(){
  if(!DATA)return;
  const g=games[gi];
  const LF=leftFrames(), RF=rightFrames();
  if(!RF.length){$('status').textContent='This comparison is not available for this world yet.';return;}
  cur=Math.max(0,Math.min(LF.length-1,cur));
  const lf=LF[cur], rf=RF[Math.min(cur,RF.length-1)];
  $('seek').max=LF.length-1;$('seek').value=cur;
  const day=Math.floor(lf.step/24),hour=lf.step%24;
  $('clock').textContent=`Day ${day} · ${String(hour).padStart(2,'0')}:00 · step ${lf.step}`;
  $('status').textContent=(timer?'Playing':'Paused')+' · '+(mode==='exact'?'Exact start · day 11-12':'T from step 0 · day 12')+' · hour '+(cur+1)+' / '+LF.length;
  drawBoard('boardL',g,lf,rf);
  drawBoard('boardR',g,rf,lf);
  fillSide('L',g,lf,'Leader (recorded)');
  fillSide('R',g,rf,mode==='exact'?'Our agent · exact start from day 11':'T · from step 0');
  renderVerify(g);
}

function selectWorld(idx){
  gi=idx;const g=games[gi];$('world').value=String(g.episode);
  const hasX=!!(g.x&&g.x.available);
  $('modeX').disabled=!hasX;
  if(mode==='exact'&&!hasX)mode='t0';
  $('mode').value=mode;
  cur=0;stop();render();
}

async function boot(){
  try{
    const raw=$('data').textContent.trim();
    const bytes=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    DATA=JSON.parse(await new Response(stream).text());
    games=DATA.games;
    games.forEach(g=>{const o=document.createElement('option');o.value=String(g.episode);o.textContent=`${g.team} · ${g.episode}`;$('world').append(o);});
    for(let i=0;i<100;i++)for(const side of ['boardL','boardR']){const b=document.createElement('button');b.type='button';b.className='tile';b.onclick=(j=>()=>{selected=j;render();})(i);$(side).append(b);}
    Object.entries(TYPES).forEach(([name,[icon]])=>{const e=document.createElement('span');e.className='chip';e.textContent=icon+' '+nice(name);$('legend').append(e);});
    const diffchip=document.createElement('span');diffchip.className='chip';diffchip.style.boxShadow='inset 0 0 0 2px var(--diff)';diffchip.textContent='boards differ here';$('legend').append(diffchip);
    $('viewer').hidden=false;
    $('error').textContent='';
    selectWorld(0);
  }catch(e){
    $('error').textContent='Unable to load the embedded data. Open this file in a current Chrome, Edge or Firefox.';
    console.error(e);
  }
}

$('play').onclick=()=>{if(timer){stop();render();return;}timer=setInterval(tick,+$('speed').value);$('play').textContent='Ⅱ Pause';};
$('seek').oninput=()=>jump(+$('seek').value);
$('prev').onclick=()=>jump(cur-1);
$('next').onclick=()=>jump(cur+1);
$('speed').onchange=()=>{if(timer){stop();$('play').click();}};
$('world').onchange=()=>selectWorld(games.findIndex(g=>String(g.episode)===$('world').value));
$('mode').onchange=()=>{mode=$('mode').value;cur=0;stop();render();};
document.addEventListener('keydown',e=>{
  if(!DATA||['INPUT','SELECT','BUTTON','TEXTAREA'].includes(e.target.tagName))return;
  if(e.code==='Space'){e.preventDefault();$('play').click();}
  if(['ArrowLeft','ArrowRight'].includes(e.code)){e.preventDefault();jump(cur+(e.code==='ArrowRight'?1:-1)*(e.shiftKey?24:1));}
});
boot();
</script>
</body></html>
"""


if __name__ == '__main__':
    main()
