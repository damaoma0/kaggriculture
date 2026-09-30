"""Board picture of the time-based path partition for one DSM game-day (scripts/path_partition_20260930.py), next to
DSM's actual unit tracks that day. Left: each worker's path from the shed through its tiles, with its jobs (mandatory
solid, non-mandatory half, slack outline, cut crossed). Right: DSM's units hour by hour and the ops they did.

usage: path_partition_viz_20260930.py EP DAY [--out viz/path_partition_EP_dDAY.html]"""
import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import path_partition_20260930 as PP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ABBR = {"WHEAT": "Wh", "CARROT": "Ca", "TOMATO": "To", "STRAWBERRY": "St", "MELON": "Me", "COW": "cow", "SHEEP": "shp",
        "GOOSE": "gs", "WEED": "weed", "COOP": "coop", "PASTURE": "pas"}


def tile_label(t):
    if t is None:
        return ""
    if t == "LOCKED":
        return "##"
    if t.get("crop"):
        return ABBR.get(t["crop"], t["crop"][:2])
    if t.get("animal"):
        return ABBR.get(t["animal"], t["animal"][:3])
    return ABBR.get(t.get("kind"), t.get("kind", "?")[:3].lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("day", type=int)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    CR, AN = PP._engine_tables()
    games = json.loads(gzip.open(PP.CACHE, "rt", encoding="utf-8").read())
    D = games[a.ep]["days"][str(a.day)]
    jobs, useless = PP.day_jobs(D["dawn"], D["dusk"], a.day, D["prices"], CR, AN, D.get("shed"))
    legs, first = PP.bringback_legs(D)
    done_bb = {}
    for L in legs.values():
        for k in L["ops"]:
            done_bb[k] = done_bb.get(k, 0) + 1
    bb_jobs = []
    for j in list(jobs):
        key_ = [(j.tile, o) for o in j.op.split("+")]
        if any(done_bb.get(k_, 0) > 0 for k_ in key_):
            for k_ in key_:
                if done_bb.get(k_, 0) > 0:
                    done_bb[k_] -= 1
            jobs.remove(j)
            bb_jobs.append(j)
    tjobs = {}
    for j in jobs:
        tjobs.setdefault(j.tile, []).append(j)
    units = max(len(s["pos"]) for s in D["steps"])
    T_dsm = [24 - first.get(u, 1) - ((legs[u]["end"] - legs[u]["start"] + 1) if u in legs else 0) for u in range(units)]
    plans = PP.partition(tjobs, units, T_dsm)
    moves = sum(1 for s in D["steps"] for c in s["cmd"] if c and c[0] in PP.MOVES)
    ours = []
    for k, q in enumerate(plans):
        ours.append(dict(T=q["T"], time=q["time"], walk=q["walk"], all=q["all_time"], seq=[list(t) for t in q["seq"]],
                         start=list(PP.near_shed(q["seq"][0])) if q["seq"] else None,
                         group=[list(t) for t in q["group"]],
                         jobs=[dict(t=list(j.tile), op=j.op, c=j.cls, h=j.hours, v=round(j.value, 1), cut=j not in q["keep"])
                               for t in q["group"] for j in tjobs.get(t, [])]))
    tracks = []
    for u in range(units):
        pts, ops = [], []
        for h, stp in enumerate(D["steps"]):
            if u < len(stp["pos"]):
                pts.append([h] + list(stp["pos"][u]))
                c = stp["cmd"][u] if u < len(stp["cmd"]) else None
                if c and c[0] not in PP.MOVES and c[0] != "PASS":
                    ops.append([h] + list(stp["pos"][u]) + [c[0] + ((" " + str(c[1])) if len(c) > 1 else "")])
        tracks.append(dict(pts=pts, ops=ops, bb=(legs[u]["end"] if u in legs else None)))
    data = dict(ep=a.ep, day=a.day, dawn=[tile_label(t) for t in D["dawn"]], units=units, dsm_moves=moves,
                ours=ours, tracks=tracks, bb_jobs=[dict(t=list(j.tile), op=j.op, c=j.cls) for j in bb_jobs],
                useless=dict(useless),
                totals=dict(M=sum(j.hours for j in jobs if j.cls == "M"), N=sum(j.hours for j in jobs if j.cls == "N"),
                            S=sum(j.hours for j in jobs if j.cls == "S")))
    out = Path(a.out) if a.out else ROOT / f"viz/path_partition_{a.ep}_d{a.day}.html"
    out.write_text(HTML.replace("__DATA__", json.dumps(data)), encoding="utf-8")
    print("->", out)


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Path partition vs DSM</title>
<style>
:root{--bg:#fbfaf7;--fg:#1f2328;--mut:#6b7280;--grid:#d9d6cf;--tile:#ffffff;--shed:#efe7d6;--card:#ffffff;--line:#e5e2db}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e6e6;--mut:#9aa1ab;--grid:#34373d;--tile:#1d2024;--shed:#3a3326;--card:#1b1e22;--line:#2c3036}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e6e6;--mut:#9aa1ab;--grid:#34373d;--tile:#1d2024;--shed:#3a3326;--card:#1b1e22;--line:#2c3036}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 2px} .sub{color:var(--mut);margin:0 0 12px}
.boards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.card h2{font-size:15px;margin:0 0 6px} .kpi{color:var(--mut);font-size:13px;margin-bottom:8px}
svg{width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:10px} th,td{padding:4px 6px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left} tr.sel{outline:2px solid currentColor} tr{cursor:pointer}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.legend{color:var(--mut);font-size:12.5px;margin-top:8px} #tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);
border-radius:8px;padding:6px 8px;font-size:12px;max-width:280px;display:none;box-shadow:0 2px 8px rgba(0,0,0,.15)}
</style></head><body><main>
<h1>Time-based paths vs DSM</h1>
<p class="sub" id="sub"></p>
<div class="boards">
 <div class="card"><h2>Time-based partition (offline, DSM's crew size)</h2><div class="kpi" id="k1"></div><svg id="b1" viewBox="0 0 400 400"></svg>
  <div class="legend">Line: worker path from its shed tile. Dots: mandatory (solid), non-mandatory (ring + dot), slack (ring); crossed = cut to fit the day.</div></div>
 <div class="card"><h2>DSM's actual day</h2><div class="kpi" id="k2"></div><svg id="b2" viewBox="0 0 400 400"></svg>
  <div class="legend">Line: unit track over the day (first bring-back leg dashed). Dots: tiles where it worked.</div></div>
</div>
<div class="card" style="margin-top:16px"><h2>Workers</h2><table id="tbl"></table></div>
<div id="tip"></div>
</main>
<script>
const D = __DATA__;
const C = 40, PAL = ["#e6194b","#3cb44b","#4363d8","#f58231","#911eb4","#46a0a0","#d6336c","#7a9e1a","#b8860b","#1f77b4","#8c564b","#2ca02c","#9467bd","#17becf","#bcbd22"];
const col = k => PAL[k % PAL.length];
document.getElementById("sub").textContent = `World ${D.ep}, day ${D.day}: jobs mandatory ${D.totals.M} h, non-mandatory ${D.totals.N} h, slack ${D.totals.S} h (useless jobs filtered: ${Object.entries(D.useless).map(([k,v])=>k+" "+v).join(", ")||"none"})`;
const walk = D.ours.reduce((a,q)=>a+q.walk,0);
document.getElementById("k1").textContent = `${D.ours.length} workers, ${walk} tiles walked, cut: ${D.ours.reduce((a,q)=>a+q.jobs.filter(j=>j.cut&&j.c==="N").length,0)} non-mandatory, ${D.ours.reduce((a,q)=>a+q.jobs.filter(j=>j.cut&&j.c==="S").length,0)} slack jobs`;
document.getElementById("k2").textContent = `${D.units} units, ${D.dsm_moves} tiles walked (bring-back legs included)`;
const owner = {}; D.ours.forEach((q,k)=>q.group.forEach(t=>owner[t[0]+","+t[1]]=k));
const tip = document.getElementById("tip");
function board(svg, tint){
  let s = "";
  for (let y=0;y<10;y++) for (let x=0;x<10;x++){
    const i=y*10+x, shed=(x==4||x==5)&&(y==4||y==5), k=owner[x+","+y];
    const fill = tint && k!==undefined ? col(k)+"22" : (shed?"var(--shed)":"var(--tile)");
    s += `<rect x="${x*C}" y="${y*C}" width="${C}" height="${C}" fill="${fill}" stroke="var(--grid)" data-t="${x},${y}"/>`;
    s += `<text x="${x*C+3}" y="${y*C+11}" font-size="9" fill="var(--mut)">${D.dawn[i]}</text>`;
  }
  svg.innerHTML = s;
}
const cx = t => t[0]*C+C/2, cy = t => t[1]*C+C/2;
function drawOurs(sel){
  const svg=document.getElementById("b1"); board(svg,true);
  let s="";
  D.ours.forEach((q,k)=>{
    if(!q.seq.length) return;
    const op = sel===null||sel===k ? 1 : .15;
    const seq=[q.start].concat(q.seq), steps=[seq[0]];
    for(let n=1;n<seq.length;n++){ const a=seq[n-1], b=seq[n]; if(a[0]!==b[0]&&a[1]!==b[1]) steps.push([b[0],a[1]]); steps.push(b); }
    const pts=steps.map(t=>`${cx(t)+((k%5)-2)*1.5},${cy(t)+((k%3)-1)*1.5}`).join(" ");
    s+=`<polyline points="${pts}" fill="none" stroke="${col(k)}" stroke-width="3" stroke-linejoin="round" opacity="${op}"/>`;
    const per={}; q.jobs.forEach(j=>{const key=j.t[0]+","+j.t[1]; (per[key]=per[key]||[]).push(j);});
    Object.entries(per).forEach(([key,js])=>{
      const [x,y]=key.split(",").map(Number);
      js.forEach((j,n)=>{
        const px=x*C+8+ (n%4)*8, py=y*C+C-8-Math.floor(n/4)*8, c=col(k);
        const f = j.c==="M"?c:"none";
        s+=`<circle cx="${px}" cy="${py}" r="3" fill="${f}" stroke="${c}" stroke-width="1.3" opacity="${op}"/>`;
        if(j.c==="N") s+=`<circle cx="${px}" cy="${py}" r="1.2" fill="${c}" opacity="${op}"/>`;
        if(j.cut) s+=`<path d="M${px-3.5},${py-3.5}L${px+3.5},${py+3.5}M${px+3.5},${py-3.5}L${px-3.5},${py+3.5}" stroke="var(--fg)" stroke-width="1" opacity="${op}"/>`;
      });
    });
  });
  svg.insertAdjacentHTML("beforeend",s);
  hover(svg,true);
}
function drawDsm(sel){
  const svg=document.getElementById("b2"); board(svg,false);
  let s="";
  D.tracks.forEach((tr,k)=>{
    const op = sel===null||sel===k ? 1 : .15;
    const j = (a)=>a.map(p=>`${p[1]*C+C/2+((k%5)-2)*2},${p[2]*C+C/2+((k%3)-1)*2}`).join(" ");
    if(tr.bb!==null){
      const a=tr.pts.filter(p=>p[0]<=tr.bb), b=tr.pts.filter(p=>p[0]>=tr.bb);
      s+=`<polyline points="${j(a)}" fill="none" stroke="${col(k)}" stroke-width="2" stroke-dasharray="4 3" opacity="${op}"/>`;
      s+=`<polyline points="${j(b)}" fill="none" stroke="${col(k)}" stroke-width="2" opacity="${op}"/>`;
    } else s+=`<polyline points="${j(tr.pts)}" fill="none" stroke="${col(k)}" stroke-width="2" opacity="${op}"/>`;
    tr.ops.forEach(o=>{ s+=`<circle cx="${o[1]*C+C/2+((k%5)-2)*2}" cy="${o[2]*C+C/2+((k%3)-1)*2}" r="2.6" fill="${col(k)}" opacity="${op}"/>`; });
  });
  svg.insertAdjacentHTML("beforeend",s);
  hover(svg,false);
}
function hover(svg, ours){
  svg.querySelectorAll("rect").forEach(r=>{
    r.addEventListener("mousemove",e=>{
      const [x,y]=r.dataset.t.split(",").map(Number); let lines=[`(${x},${y}) ${D.dawn[y*10+x]||"empty"}`];
      if(ours){ D.ours.forEach((q,k)=>q.jobs.filter(j=>j.t[0]==x&&j.t[1]==y).forEach(j=>lines.push(`w${k}: ${j.op} ${j.c} ${j.h}h $${j.v}${j.cut?" (cut)":""}`)));
        D.bb_jobs.filter(j=>j.t[0]==x&&j.t[1]==y).forEach(j=>lines.push(`bring-back leg: ${j.op} ${j.c}`)); }
      else D.tracks.forEach((tr,k)=>tr.ops.filter(o=>o[1]==x&&o[2]==y).forEach(o=>lines.push(`u${k} h${o[0]}: ${o[3]}`)));
      tip.innerHTML=lines.join("<br>"); tip.style.display="block"; tip.style.left=(e.clientX+12)+"px"; tip.style.top=(e.clientY+12)+"px";
    });
    r.addEventListener("mouseleave",()=>tip.style.display="none");
  });
}
let sel=null;
function table(){
  const t=document.getElementById("tbl");
  let h=`<tr><th>worker</th><th>budget h</th><th>planned h</th><th>all work h</th><th>walk</th><th>M</th><th>N</th><th>S kept</th><th>cut</th></tr>`;
  D.ours.forEach((q,k)=>{
    const sum=c=>q.jobs.filter(j=>j.c===c&&!j.cut).reduce((a,j)=>a+j.h,0);
    h+=`<tr data-k="${k}" class="${sel===k?"sel":""}"><td><span class="sw" style="background:${col(k)}"></span>w${k}</td><td>${q.T}</td><td>${q.time}</td><td>${q.all}</td><td>${q.walk}</td><td>${sum("M")}</td><td>${sum("N")}</td><td>${sum("S")}</td><td>${q.jobs.filter(j=>j.cut).map(j=>j.op[0]+j.op.slice(1).toLowerCase()+"("+j.t+")").join(" ")}</td></tr>`;
  });
  t.innerHTML=h;
  t.querySelectorAll("tr[data-k]").forEach(r=>r.addEventListener("click",()=>{const k=+r.dataset.k; sel = sel===k?null:k; drawOurs(sel); drawDsm(null); table();}));
}
drawOurs(null); drawDsm(null); table();
</script></body></html>
"""

if __name__ == "__main__":
    main()
