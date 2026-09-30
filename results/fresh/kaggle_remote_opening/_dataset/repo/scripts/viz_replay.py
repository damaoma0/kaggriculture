"""Build a self-contained HTML visualizer for a Kaggriculture replay.

Usage:
    python scripts/viz_replay.py data/replays/episode-106870999-replay.json [--me "Yiyang Xu"] [--out viz/x.html]
    python scripts/viz_replay.py local_replay.json --names A,B     # env.toJSON() output

The page (viz/<name>.html) plays the game step by step (play/pause, step, jump to day:hour),
shows both farms, price and market-volume trends with every executed sale/buy marked, the daily
hand cost, money, and each player's shed. The opponent's shed and unit inventories are not in the
replay: they are reconstructed forward from public information (their actions, their tiles'
yield changes, market prices) using the engine's rules. The same reconstruction is run for our
own side and compared with our real private shed, and the page reports the mismatch, so the
inference can be trusted or not at a glance.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
ANIMALS = {"GOOSE": ("COOP", "EGG", 300), "COW": ("PASTURE", "MILK", 400), "SHEEP": ("PASTURE", "WOOL", 500)}
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
SHOPS = {
    "BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"], "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
LAND_PRICES = [1000, 2000, 4000]
SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}
SHED_CAP = 100
CROP_CODE = {"WHEAT": "w", "CARROT": "c", "TOMATO": "t", "STRAWBERRY": "s", "MELON": "m"}
ANIMAL_CODE = {"GOOSE": "G", "COW": "C", "SHEEP": "S"}


def fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def tile_code(t):
    """Compact per-tile code: kind, yield, flags. '.' empty, 'L' locked, 'x' weed."""
    if t is None:
        return "."
    if t == "LOCKED":
        return "L"
    if t.get("kind") == "WEED":
        return "x"
    if t.get("kind") == "PLANT":
        c = CROP_CODE.get(t["crop"], "?")
        flag = "W" if t.get("watered_today") else "-"
        fz = "F" if t.get("fertilized_until_day", -1) >= 0 else "-"
        return f"{c}{t.get('yield_units', 0)}{flag}{fz}{t.get('consecutive_unwatered', 0)}"
    if "animal" in t:
        a = ANIMAL_CODE[t["animal"]]
        return f"{a}{t.get('yield_units', 0)}{'F' if t.get('fed_today') else '-'}{'C' if t.get('cared_today') else '-'}{'z' if t.get('fertilizer_available') else '-'}"
    return "P" if t.get("kind") == "PASTURE" else "K"


def load_replay(path, me_name, names_arg):
    j = json.load(open(path, encoding="utf-8"))
    steps = j["steps"]
    names = (j.get("info") or {}).get("TeamNames") or []
    if names_arg:
        names = names_arg.split(",")
    if not names:
        names = ["Player 0", "Player 1"]
    me = 0
    if me_name and me_name in names:
        me = names.index(me_name)
    return steps, names, me


def reconstruct(steps, pl):
    """Forward-simulate player pl's shed, seeds and unit inventories from public data + actions.

    Returns per-step lists: shed (dict), executed sells (dict product->units), executed buys
    (dict), unit inventories (list of dicts), hire cost paid this step.
    Engine order per step: unit actions -> market -> town drain -> decay -> (end of day: refresh,
    inventories dumped into the shed, hands vanish)."""
    n = len(steps)
    shed = {}
    seeds = {}
    invs = [{}]          # [farmer, hands...] inventories at the start of the step
    out = []
    for i in range(n - 1):
        obs = steps[i][pl]["observation"]
        act = steps[i + 1][pl].get("action") or {}
        farm = obs["farms"][pl]
        farm_next = steps[i + 1][pl]["observation"]["farms"][pl]
        prices = obs["market"]["prices"]
        step = i
        day, hour = step // 24, step % 24
        money = farm["money"]
        positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        while len(invs) < len(positions):
            invs.append({})
        invs = invs[:len(positions)]
        units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
        units = (units + [["PASS"]] * len(positions))[:len(positions)]
        tiles = farm["tiles"]
        tiles_next = farm_next["tiles"]
        # --- unit actions
        plant_demand = {}
        for a in units:
            if a and a[0] == "PLANT" and len(a) > 1:
                plant_demand[a[1]] = plant_demand.get(a[1], 0) + 1
        blocked = {c for c, k in plant_demand.items() if k > seeds.get(c, 0)}
        for k, (a, (x, y)) in enumerate(zip(units, positions)):
            if not a:
                continue
            op = a[0]
            inv = invs[k]
            t = tiles[y][x]
            at_shed = (x, y) in SHED_TILES
            if op == "HARVEST":
                if isinstance(t, dict) and t.get("yield_units", 0) > 0:
                    tn = tiles_next[y][x]
                    if t.get("kind") == "PLANT":
                        # one-time crop: tile becomes empty; ongoing: yield reset to 0
                        if tn is None or (isinstance(tn, dict) and tn.get("kind") == "PLANT" and tn.get("yield_units", 0) < t["yield_units"]):
                            got = t["yield_units"] if tn is None else t["yield_units"] - tn.get("yield_units", 0)
                            if got > 0:
                                inv[t["crop"]] = inv.get(t["crop"], 0) + got
                    elif "animal" in t:
                        tn_y = tn.get("yield_units", 0) if isinstance(tn, dict) else 0
                        got = t["yield_units"] - tn_y
                        if got > 0:
                            prod = ANIMALS[t["animal"]][1]
                            inv[prod] = inv.get(prod, 0) + got
            elif op == "COLLECT_FERTILIZER":
                if isinstance(t, dict) and "animal" in t and t.get("fertilizer_available"):
                    inv["FERTILIZER"] = inv.get("FERTILIZER", 0) + 1
            elif op == "FEED":
                if isinstance(t, dict) and "animal" in t and not t.get("fed_today") and inv.get("WHEAT", 0) > 0:
                    tn = tiles_next[y][x]
                    if isinstance(tn, dict) and tn.get("fed_today"):
                        inv["WHEAT"] -= 1
            elif op == "FERTILIZE":
                if isinstance(t, dict) and t.get("kind") == "PLANT" and inv.get("FERTILIZER", 0) > 0:
                    tn = tiles_next[y][x]
                    if isinstance(tn, dict) and tn.get("fertilized_until_day", -1) > t.get("fertilized_until_day", -1):
                        inv["FERTILIZER"] -= 1
            elif op == "PLANT" and len(a) > 1:
                c = a[1]
                if c not in blocked and t is None and seeds.get(c, 0) > 0:
                    tn = tiles_next[y][x]
                    if isinstance(tn, dict) and tn.get("kind") == "PLANT":
                        seeds[c] -= 1
            elif op == "PICKUP" and len(a) > 1 and at_shed:
                item = a[1]
                q = int(a[2]) if len(a) > 2 else 1
                q = min(q, shed.get(item, 0))
                if q > 0:
                    shed[item] -= q
                    inv[item] = inv.get(item, 0) + q
            elif op == "DROP" and at_shed:
                for item, q in list(inv.items()):
                    room = max(0, SHED_CAP - sum(shed.values()))
                    take = min(q, room)
                    if take > 0:
                        shed[item] = shed.get(item, 0) + take
                inv.clear()
            elif op == "PLACE" and len(a) > 1:
                item = a[1]
                if item in ANIMALS and isinstance(t, dict) and t.get("kind") == ANIMALS[item][0] and "animal" not in t:
                    tn = tiles_next[y][x]
                    if isinstance(tn, dict) and tn.get("animal") == item and inv.get(item, 0) > 0:
                        inv[item] -= 1
                elif at_shed:
                    q = int(a[2]) if len(a) > 2 else 1
                    q = min(q, inv.get(item, 0), max(0, SHED_CAP - sum(shed.values())))
                    if q > 0:
                        inv[item] -= q
                        shed[item] = shed.get(item, 0) + q
        for inv in invs:
            for k2 in [k2 for k2, v in inv.items() if v <= 0]:
                del inv[k2]
        # --- market (approximate: sequential, sells limited by shed, buys by money)
        sold, bought = {}, {}
        hire_cost = 0
        hires = farm["hires_today"]
        for o in act.get("market") or []:
            if not o:
                continue
            op = o[0]
            if op == "SELL" and len(o) > 2 and o[1] in PRODUCTS:
                q = min(int(o[2]), shed.get(o[1], 0))
                if q > 0:
                    shed[o[1]] -= q
                    sold[o[1]] = sold.get(o[1], 0) + q
                    money += q * prices[o[1]]
            elif op == "BUY_PRODUCT" and len(o) > 2 and o[1] in ("WHEAT", "FERTILIZER"):
                q = int(o[2])
                p = prices[o[1]]
                q = min(q, int(money // max(1, p)), max(0, SHED_CAP - sum(shed.values())))
                if q > 0:
                    shed[o[1]] = shed.get(o[1], 0) + q
                    bought[o[1]] = bought.get(o[1], 0) + q
                    money -= q * p
            elif op == "BUY_ANIMAL" and len(o) > 2 and o[1] in ANIMALS:
                cost = ANIMALS[o[1]][2]
                q = min(int(o[2]), int(money // cost), max(0, SHED_CAP - sum(shed.values())))
                if q > 0:
                    shed[o[1]] = shed.get(o[1], 0) + q
                    bought[o[1]] = bought.get(o[1], 0) + q
                    money -= q * cost
            elif op == "BUY_SEED" and len(o) > 2 and o[1] in SEED_COST:
                q = min(int(o[2]), int(money // SEED_COST[o[1]]))
                if q > 0:
                    seeds[o[1]] = seeds.get(o[1], 0) + q
                    money -= q * SEED_COST[o[1]]
            elif op == "HIRE":
                c = fib(hires)
                if money >= c:
                    money -= c
                    hire_cost += c
                    hires += 1
            elif op == "BUY_LAND":
                k = len(farm["unlocked_quadrants"]) - 1
                if k < 3 and money >= LAND_PRICES[k]:
                    money -= LAND_PRICES[k]
        # --- end of day (inside the hour-23 step): inventories dumped into the shed, hands vanish
        if hour == 23:
            for inv in invs:
                for item, q in list(inv.items()):
                    room = max(0, SHED_CAP - sum(shed.values()))
                    take = min(q, room)
                    if take > 0:
                        shed[item] = shed.get(item, 0) + take
            invs = [{}]
        out.append({"shed": dict(shed), "seeds": dict(seeds), "invs": [dict(v) for v in invs],
                    "sold": sold, "bought": bought, "hire_cost": hire_cost})
    out.append(out[-1] if out else {"shed": {}, "seeds": {}, "invs": [{}], "sold": {}, "bought": {}, "hire_cost": 0})
    return out


def build(steps, names, me):
    n = len(steps)
    recon = [reconstruct(steps, 0), reconstruct(steps, 1)]
    # accuracy of the reconstruction on our own side (private shed is known)
    mism, total = 0, 0
    for i in range(n - 1):
        real = steps[i + 1][me]["observation"].get("private", {}).get("shed") or {}
        est = recon[me][i]["shed"]
        for p in PRODUCTS + list(ANIMALS):
            d = abs(real.get(p, 0) - est.get(p, 0))
            mism += d
            total += real.get(p, 0)
    accuracy = 1 - mism / max(1, total + mism)
    data = {"names": names, "me": me, "n": n, "products": PRODUCTS, "accuracy": round(accuracy, 4),
            "steps": []}
    for i in range(n):
        obs = steps[i][0]["observation"]
        farms = obs["farms"]
        row = {
            "p": [obs["market"]["prices"][p] for p in PRODUCTS],
            "v": [obs["market"]["inventory"][p] for p in PRODUCTS],
            "m": [round(f["money"]) for f in farms],
            "h": [len(f["hands"]) for f in farms],
            "q": [len(f["unlocked_quadrants"]) for f in farms],
            "shops": obs["town"]["unlocked_shops"],
            "tiles": ["".join(tile_code(t) + "|" for row_ in f["tiles"] for t in row_) for f in farms],
            "units": [[list(f["farmer"])] + [list(h) for h in f["hands"]] for f in farms],
            "r": [],
        }
        for pl in (0, 1):
            r = recon[pl][i]
            true_shed = steps[i][pl]["observation"].get("private", {}).get("shed") if pl == me else None
            act = steps[i + 1][pl].get("action") if i + 1 < n else None
            row["r"].append({"shed": r["shed"], "true": true_shed, "seeds": r["seeds"], "invs": r["invs"],
                             "sold": r["sold"], "bought": r["bought"], "hc": r["hire_cost"],
                             "orders": (act or {}).get("market") or [],
                             "acts": [(act or {}).get("farmer") or ["PASS"]] + list((act or {}).get("hands") or [])})
        data["steps"].append(row)
    return data


HTML = r'''<!doctype html>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
:root{--bg:#111;--fg:#e8e8e8;--dim:#9a9a9a;--panel:#1b1b1b;--line:#333;--me:#4fc3f7;--op:#ffb74d}
body{margin:0;font:13px/1.35 system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:10px;align-items:center;padding:8px 12px;background:var(--panel);border-bottom:1px solid var(--line);flex-wrap:wrap;position:sticky;top:0;z-index:5}
button{background:#2a2a2a;color:var(--fg);border:1px solid #444;border-radius:4px;padding:4px 9px;cursor:pointer}
button:hover{background:#383838}
input[type=range]{width:420px}
input[type=text]{width:70px;background:#222;color:var(--fg);border:1px solid #444;border-radius:4px;padding:3px 6px}
.k{color:var(--dim)} .me{color:var(--me)} .op{color:var(--op)}
main{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}
section{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px;min-width:0}
section h3{margin:0 0 6px;font-size:13px;font-weight:600;color:var(--dim)}
.wide{grid-column:1/3}
canvas{width:100%;height:auto;display:block;background:#161616;border-radius:4px}
.farms{display:flex;gap:14px;flex-wrap:wrap}
.farm{flex:1;min-width:300px}
.grid{display:grid;grid-template-columns:repeat(10,1fr);gap:2px;aspect-ratio:1}
.cell{position:relative;display:flex;align-items:center;justify-content:center;font-size:11px;border-radius:3px;background:#262626;color:#ddd;user-select:none}
.cell.L{background:#141414;color:#333}.cell.x{background:#3b2f1f;color:#c9a}.cell.w{background:#5c4d1a}.cell.c{background:#6b3a12}.cell.t{background:#7a2323}.cell.s{background:#7a2050}.cell.m{background:#1f5f3a}
.cell.G{background:#4a4a7a}.cell.C{background:#3f5f7f}.cell.S{background:#6a6a6a}.cell.P,.cell.K{background:#2f3a2f;color:#8a8}
.cell .u{position:absolute;right:1px;top:0;font-size:9px;color:#fff;background:rgba(0,0,0,.55);border-radius:2px;padding:0 2px}
.cell .dry{position:absolute;left:1px;bottom:0;width:4px;height:4px;border-radius:2px;background:#ff5252}
.cell .fz{position:absolute;left:1px;top:1px;width:4px;height:4px;border-radius:2px;background:#b388ff}
table{border-collapse:collapse;width:100%}td,th{padding:2px 6px;text-align:right;border-bottom:1px solid #2a2a2a}th{color:var(--dim);font-weight:500}td:first-child,th:first-child{text-align:left}
.legend{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0}.legend span{cursor:pointer;padding:1px 6px;border-radius:3px;border:1px solid #444}.legend span.off{opacity:.35}
.small{font-size:11px;color:var(--dim)}
.grid{max-width:340px}
@media (max-width:900px){main{grid-template-columns:1fr}.wide{grid-column:1}input[type=range]{width:200px}}
.orders{font-family:ui-monospace,Consolas,monospace;font-size:11px;white-space:pre-wrap;max-height:120px;overflow:auto}
</style>
<header>
  <button id="play">▶ Play</button>
  <button id="b24">⏮ -day</button><button id="b1">◀ -1</button><button id="f1">+1 ▶</button><button id="f24">+day ⏭</button>
  <input type="range" id="slider" min="0" max="719" value="0">
  <span>jump <input type="text" id="jump" placeholder="d:h or step"> <button id="go">Go</button></span>
  <span>speed <select id="speed"><option value="250">slow</option><option value="80" selected>normal</option><option value="20">fast</option></select></span>
  <b id="clock"></b>
  <span class="small" id="acc"></span>
</header>
<main>
  <section class="wide">
    <div class="farms">
      <div class="farm"><h3 id="t0"></h3><div class="grid" id="g0"></div></div>
      <div class="farm"><h3 id="t1"></h3><div class="grid" id="g1"></div></div>
    </div>
    <div class="small" id="shops"></div>
  </section>
  <section><h3>Sheds and inventories at this step (opponent side reconstructed)</h3><div id="sheds"></div></section>
  <section><h3>Market orders this step</h3><div class="orders" id="orders"></div></section>
  <section class="wide"><h3>Prices (lines) with executed sales ● and buys ▲ — click legend to toggle products</h3>
    <div class="legend" id="lg"></div><canvas id="cp" width="1400" height="300"></canvas></section>
  <section class="wide"><h3>Market volume (inventory relative to 10,000)</h3><canvas id="cv" width="1400" height="220"></canvas></section>
  <section><h3>Money</h3><canvas id="cm" width="700" height="200"></canvas></section>
  <section><h3>Hands hired (bars) and daily hand cost (lines)</h3><canvas id="ch" width="700" height="200"></canvas></section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const N = D.n, P = D.products, ME = D.me, OP = 1 - ME;
const COLORS = {WHEAT:'#e0c060',CARROT:'#ff8a3d',TOMATO:'#ff5555',STRAWBERRY:'#ff4fa3',MELON:'#4dd67a',EGG:'#f5f5c0',MILK:'#bde0ff',WOOL:'#d0d0d0',FERTILIZER:'#b388ff'};
const on = Object.fromEntries(P.map(p=>[p,true]));
let cur = 0, timer = null;
const $ = id => document.getElementById(id);
$('acc').textContent = 'reconstruction check on own shed: ' + (D.accuracy*100).toFixed(1) + '% of units match';
$('t0').innerHTML = `<span class="${ME===0?'me':'op'}">${D.names[0]}${ME===0?' (me)':''}</span>`;
$('t1').innerHTML = `<span class="${ME===1?'me':'op'}">${D.names[1]}${ME===1?' (me)':''}</span>`;
for (const g of ['g0','g1']) for (let i=0;i<100;i++){const c=document.createElement('div');c.className='cell';c.title='';$(g).appendChild(c);}
const lg = $('lg'); P.forEach(p=>{const s=document.createElement('span');s.textContent=p;s.style.borderColor=COLORS[p];s.style.color=COLORS[p];s.onclick=()=>{on[p]=!on[p];s.classList.toggle('off');drawAll();};lg.appendChild(s);});

function fmtStep(s){return `day ${Math.floor(s/24)} hour ${s%24}  (step ${s})`;}
function renderFarm(idx){
  const st = D.steps[cur], codes = st.tiles[idx].split('|'), cells = $('g'+idx).children;
  const units = st.units[idx]; const at = {}; units.forEach((u,k)=>{const key=u[0]+','+u[1]; at[key]=(at[key]||'')+(k===0?'F':k);});
  for (let i=0;i<100;i++){
    const x=i%10,y=Math.floor(i/10), code=codes[i]||'.', c=cells[i];
    c.className='cell '+code[0]; c.innerHTML='';
    let label='', tip='('+x+','+y+') ';
    if (code==='.'){tip+='empty';} else if (code==='L'){tip+='locked';} else if (code==='x'){label='✕';tip+='weed';}
    else if ('wctsm'.includes(code[0])){label=code[0].toUpperCase()+code[1];tip+={w:'wheat',c:'carrot',t:'tomato',s:'strawberry',m:'melon'}[code[0]]+' yield '+code[1]+(code[2]==='W'?', watered':', NOT watered')+(code[3]==='F'?', fertilized':'')+', unwatered streak '+code[4];
      if (code[2]!=='W'){const d=document.createElement('i');d.className='dry';c.appendChild(d);} if (code[3]==='F'){const f=document.createElement('i');f.className='fz';c.appendChild(f);}}
    else if ('GCS'.includes(code[0])){label=code[0]+code[1];tip+={G:'goose',C:'cow',S:'sheep'}[code[0]]+' holds '+code[1]+(code[2]==='F'?', fed':', NOT fed')+(code[3]==='C'?', cared':'')+(code[4]==='z'?', fertilizer ready':'');}
    else if (code[0]==='P'){label='▭';tip+='empty pasture';} else if (code[0]==='K'){label='▭';tip+='empty coop';}
    const t=document.createElement('span');t.textContent=label;c.appendChild(t);
    if (at[x+','+y]){const u=document.createElement('b');u.className='u';u.textContent=at[x+','+y];c.appendChild(u);tip+=' | units: '+at[x+','+y];}
    c.title=tip;
  }
}
function fmtBag(b){const ks=Object.keys(b||{}).filter(k=>b[k]>0);return ks.length?ks.map(k=>k.toLowerCase()+' '+b[k]).join(', '):'—';}
function renderSide(){
  const st = D.steps[cur];
  let html='<table><tr><th></th><th class="'+(ME===0?'me':'op')+'">'+D.names[0]+'</th><th class="'+(ME===1?'me':'op')+'">'+D.names[1]+'</th></tr>';
  const r0=st.r[0], r1=st.r[1];
  html+='<tr><td>money</td><td>'+st.m[0]+'</td><td>'+st.m[1]+'</td></tr>';
  html+='<tr><td>hands / quadrants</td><td>'+st.h[0]+' / '+st.q[0]+'</td><td>'+st.h[1]+' / '+st.q[1]+'</td></tr>';
  html+='<tr><td>shed (reconstructed)</td><td style="text-align:left">'+fmtBag(r0.shed)+'</td><td style="text-align:left">'+fmtBag(r1.shed)+'</td></tr>';
  const tr = st.r[ME].true; if (tr) html+='<tr><td>shed (true, mine)</td><td style="text-align:left" colspan=2>'+fmtBag(tr)+'</td></tr>';
  html+='<tr><td>seeds</td><td style="text-align:left">'+fmtBag(r0.seeds)+'</td><td style="text-align:left">'+fmtBag(r1.seeds)+'</td></tr>';
  html+='<tr><td>carried by units</td><td style="text-align:left">'+r0.invs.map((v,i)=>(i===0?'F:':i+':')+fmtBag(v)).filter(s=>!s.endsWith('—')).join('; ')+'</td><td style="text-align:left">'+r1.invs.map((v,i)=>(i===0?'F:':i+':')+fmtBag(v)).filter(s=>!s.endsWith('—')).join('; ')+'</td></tr>';
  html+='<tr><td>sold this step</td><td style="text-align:left">'+fmtBag(r0.sold)+'</td><td style="text-align:left">'+fmtBag(r1.sold)+'</td></tr>';
  html+='<tr><td>bought this step</td><td style="text-align:left">'+fmtBag(r0.bought)+'</td><td style="text-align:left">'+fmtBag(r1.bought)+'</td></tr>';
  html+='</table>';
  $('sheds').innerHTML=html;
  const fmtO=o=>o.join(' ');
  $('orders').textContent = D.names[0]+': '+(r0.orders.length?r0.orders.map(fmtO).join(' | '):'—')+'\n  units: '+r0.acts.map(a=>a.join(' ')).join(', ')+'\n'+D.names[1]+': '+(r1.orders.length?r1.orders.map(fmtO).join(' | '):'—')+'\n  units: '+r1.acts.map(a=>a.join(' ')).join(', ');
  $('shops').textContent='shops unlocked: '+(st.shops.length?st.shops.join(', '):'none');
}
// ---------- charts
function axes(ctx,W,H,pad,ymin,ymax,yfmt){
  ctx.strokeStyle='#333';ctx.fillStyle='#888';ctx.font='11px system-ui';ctx.lineWidth=1;
  for(let d=0;d<=30;d+=5){const x=pad.l+(d*24)/(N-1)*(W-pad.l-pad.r);ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,H-pad.b);ctx.stroke();ctx.fillText('d'+d,x+2,H-pad.b+12);}
  for(let k=0;k<=4;k++){const v=ymin+(ymax-ymin)*k/4,y=H-pad.b-(v-ymin)/(ymax-ymin)*(H-pad.t-pad.b);ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(W-pad.r,y);ctx.stroke();ctx.fillText(yfmt(v),2,y-2);}
}
function cursor(ctx,W,H,pad){const x=pad.l+cur/(N-1)*(W-pad.l-pad.r);ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,H-pad.b);ctx.stroke();}
function lineChart(canvas, series, markers, yfmt, ymin0){
  const ctx=canvas.getContext('2d'),W=canvas.width,H=canvas.height,pad={l:44,r:10,t:8,b:18};
  ctx.clearRect(0,0,W,H);
  let ymin=ymin0===undefined?Infinity:ymin0,ymax=-Infinity;
  for(const s of series){if(!s.on)continue;for(const v of s.y){if(v<ymin)ymin=v;if(v>ymax)ymax=v;}}
  if(!isFinite(ymin)){ymin=0;ymax=1;} if(ymax===ymin)ymax=ymin+1;
  axes(ctx,W,H,pad,ymin,ymax,yfmt);
  const X=i=>pad.l+i/(N-1)*(W-pad.l-pad.r), Y=v=>H-pad.b-(v-ymin)/(ymax-ymin)*(H-pad.t-pad.b);
  for(const s of series){if(!s.on)continue;ctx.strokeStyle=s.color;ctx.lineWidth=s.width||1.3;ctx.beginPath();s.y.forEach((v,i)=>{i?ctx.lineTo(X(i),Y(v)):ctx.moveTo(X(i),Y(v));});ctx.stroke();}
  for(const m of markers){if(!m.on)continue;const x=X(m.i),y=Y(m.v),r=Math.min(9,2+Math.sqrt(m.q));ctx.fillStyle=m.color;ctx.strokeStyle=m.stroke;ctx.lineWidth=1.2;ctx.beginPath();
    if(m.kind==='sell'){ctx.arc(x,y,r,0,Math.PI*2);} else {ctx.moveTo(x,y-r);ctx.lineTo(x+r,y+r);ctx.lineTo(x-r,y+r);ctx.closePath();}
    ctx.fill();ctx.stroke();}
  cursor(ctx,W,H,pad);
}
function barLineChart(canvas){
  const ctx=canvas.getContext('2d'),W=canvas.width,H=canvas.height,pad={l:44,r:10,t:8,b:18};
  ctx.clearRect(0,0,W,H);
  const cost=[[],[]],hands=[[],[]];
  for(let d=0;d<30;d++){for(const pl of[0,1]){let c=0,h=0;for(let s=d*24;s<Math.min(N,d*24+24);s++){c+=D.steps[s].r[pl].hc;h=Math.max(h,D.steps[s].h[pl]);}cost[pl].push(c);hands[pl].push(h);}}
  const cmax=Math.max(1,...cost[0],...cost[1]);
  axes(ctx,W,H,pad,0,cmax,v=>Math.round(v)+'');
  const X=d=>pad.l+(d*24+12)/(N-1)*(W-pad.l-pad.r), Y=v=>H-pad.b-v/cmax*(H-pad.t-pad.b), Yh=h=>H-pad.b-h/14*(H-pad.t-pad.b);
  const bw=(W-pad.l-pad.r)/30/2-2;
  for(let d=0;d<30;d++){for(const pl of[0,1]){ctx.fillStyle=pl===ME?'rgba(79,195,247,.35)':'rgba(255,183,77,.35)';const x=X(d)+(pl===0?-bw:0);ctx.fillRect(x,Yh(hands[pl][d]),bw,H-pad.b-Yh(hands[pl][d]));}}
  for(const pl of[0,1]){ctx.strokeStyle=pl===ME?'#4fc3f7':'#ffb74d';ctx.lineWidth=1.6;ctx.beginPath();cost[pl].forEach((v,d)=>{d?ctx.lineTo(X(d),Y(v)):ctx.moveTo(X(d),Y(v));});ctx.stroke();}
  ctx.fillStyle='#888';ctx.fillText('bars: hands (0-14 scale), lines: coins/day',pad.l+4,pad.t+10);
  cursor(ctx,W,H,pad);
}
let priceSeries=[],priceMarkers=[],volSeries=[],moneySeries=[];
function prep(){
  priceSeries=P.map((p,k)=>({color:COLORS[p],y:D.steps.map(s=>s.p[k]),on:true,p}));
  volSeries=P.map((p,k)=>({color:COLORS[p],y:D.steps.map(s=>s.v[k]-10000),on:true,p}));
  priceMarkers=[];
  D.steps.forEach((s,i)=>{for(const pl of[0,1]){const r=s.r[pl];for(const p in r.sold){const k=P.indexOf(p);if(k<0)continue;priceMarkers.push({i,v:s.p[k],q:r.sold[p],kind:'sell',color:pl===ME?'rgba(79,195,247,.85)':'rgba(255,183,77,.85)',stroke:COLORS[p],p});}
    for(const p in r.bought){const k=P.indexOf(p);if(k<0)continue;priceMarkers.push({i,v:s.p[k],q:r.bought[p],kind:'buy',color:pl===ME?'rgba(79,195,247,.85)':'rgba(255,183,77,.85)',stroke:COLORS[p],p});}}});
  moneySeries=[{color:ME===0?'#4fc3f7':'#ffb74d',y:D.steps.map(s=>s.m[0]),on:true,width:1.8},{color:ME===1?'#4fc3f7':'#ffb74d',y:D.steps.map(s=>s.m[1]),on:true,width:1.8}];
}
function drawAll(){
  priceSeries.forEach(s=>s.on=on[s.p]);volSeries.forEach(s=>s.on=on[s.p]);priceMarkers.forEach(m=>m.on=on[m.p]);
  lineChart($('cp'),priceSeries,priceMarkers,v=>Math.round(v)+'',0);
  lineChart($('cv'),volSeries,[],v=>(v>0?'+':'')+Math.round(v));
  lineChart($('cm'),moneySeries,[],v=>Math.round(v/1000)+'k',0);
  barLineChart($('ch'));
}
function render(){cur=Math.max(0,Math.min(N-1,cur));$('slider').value=cur;$('clock').textContent=fmtStep(cur);renderFarm(0);renderFarm(1);renderSide();drawAll();}
function setStep(s){cur=s;render();}
$('slider').oninput=e=>setStep(+e.target.value);
$('b1').onclick=()=>setStep(cur-1);$('f1').onclick=()=>setStep(cur+1);$('b24').onclick=()=>setStep(cur-24);$('f24').onclick=()=>setStep(cur+24);
$('go').onclick=()=>{const v=$('jump').value.trim();const m=v.match(/^(\d+)\s*[:dD]\s*(\d+)$/);if(m)setStep(+m[1]*24+ +m[2]);else if(/^\d+$/.test(v))setStep(+v);};
$('jump').onkeydown=e=>{if(e.key==='Enter')$('go').onclick();};
function play(){if(timer){clearInterval(timer);timer=null;$('play').textContent='▶ Play';return;}$('play').textContent='⏸ Pause';timer=setInterval(()=>{if(cur>=N-1){play();return;}setStep(cur+1);},+$('speed').value);}
$('play').onclick=play;$('speed').onchange=()=>{if(timer){play();play();}};
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;if(e.key===' '){e.preventDefault();play();}else if(e.key==='ArrowRight')setStep(cur+(e.shiftKey?24:1));else if(e.key==='ArrowLeft')setStep(cur-(e.shiftKey?24:1));});
for(const id of['cp','cv','cm','ch']){$(id).addEventListener('click',e=>{const c=$(id),r=c.getBoundingClientRect(),x=(e.clientX-r.left)*c.width/r.width,pad={l:44,r:10};setStep(Math.round((x-pad.l)/(c.width-pad.l-pad.r)*(N-1)));});}
prep();render();
</script>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--me", default="Yiyang Xu")
    ap.add_argument("--names", default=None, help="comma-separated names for local replays")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    steps, names, me = load_replay(args.replay, args.me, args.names)
    data = build(steps, names, me)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", Path(args.replay).stem)
    out = Path(args.out) if args.out else ROOT / "viz" / f"{stem}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    safe_names = [n.encode("ascii", "replace").decode() for n in names]
    title = f"Kaggriculture replay: {safe_names[0]} vs {safe_names[1]}"
    html = HTML.replace("__TITLE__", title).replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB); reconstruction check on own shed: {data['accuracy']*100:.1f}% of units match")


if __name__ == "__main__":
    main()
