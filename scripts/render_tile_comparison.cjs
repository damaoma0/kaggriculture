const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),target=process.argv[2];
if(!target||!path.isAbsolute(target))throw Error('Pass an absolute destination path');
const {groups}=JSON.parse(fs.readFileSync(path.join(root,'results/fresh/dsm_visualizer/leader_tile_change_comparison.json')));
const max=Math.max(...groups.flatMap(g=>g.tiles.map(t=>t.mean||0)));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
let html=fs.readFileSync(path.join(root,'scripts/fragments/leader_tile_comparison.html'),'utf8').replace('__MAX__',max.toFixed(1));
for(const [i,g] of groups.entries()){
  let cells='<span></span>'+Array.from({length:10},(_,x)=>'<span class="axis">'+x+'</span>').join('');
  for(let y=0;y<10;y++){
    cells+='<span class="axis">'+y+'</span>';
    for(const t of g.tiles.slice(y*10,y*10+10)){
      const pairs=Object.entries(t.pairs).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([k,v])=>k.toLowerCase()+': '+v).join('; ');
      const tip=t.used?`${g.name}, days ${g.startDay}–29, tile (${t.x}, ${t.y}): ${t.mean.toFixed(2)} changes/game; ${t.total} changes across ${g.n} games; productive in ${t.used}/${g.n}. ${pairs||'No type changes.'}`:`Tile (${t.x}, ${t.y}): never productive in this window.`;
      const fill=t.used?`color-mix(in srgb,var(--viz-series-1) ${8+54*t.mean/max}%,transparent)`:'var(--muted)';
      cells+=`<span class="mark" style="background:${fill}" data-tooltip="${esc(tip)}" aria-label="${esc(tip)}">${t.used?t.mean.toFixed(1):'—'}</span>`;
    }
  }
  html=html.replace(`__MAP${i}__`,cells).replace(`__META${i}__`,`${g.n} games · ${g.stablePercent.toFixed(1)}% of productive tiles unchanged`);
}
if(/__(MAP|META|MAX)/.test(html))throw Error('Unfilled template');
fs.writeFileSync(target,html);
console.log(JSON.stringify({target,bytes:Buffer.byteLength(html),max,cells:(html.match(/class="mark"/g)||[]).length}));
