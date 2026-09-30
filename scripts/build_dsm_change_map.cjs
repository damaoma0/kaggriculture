// node scripts/build_dsm_change_map.cjs <absolute output HTML path>
const fs=require('node:fs');
const path=require('node:path');
const zlib=require('node:zlib');
const root=path.resolve(__dirname,'..');
const target=process.argv[2];
if(!target||!path.isAbsolute(target))throw Error('Supply an absolute output path.');
const html=fs.readFileSync(path.join(root,'viz/dsm-tapes.html'),'utf8');
const data=JSON.parse(html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const tiles=Array.from({length:100},(_,i)=>({x:i%10,y:Math.floor(i/10),counts:[],used:0,pairs:{}}));
let stable=0,productive=0;
for(const meta of data.games){
  const game=meta.packed?{...meta,...JSON.parse(zlib.gunzipSync(Buffer.from(meta.packed,'base64')).toString())}:meta;
  if(game.frames.length!==720)throw Error(`Incomplete game ${game.id}`);
  for(let i=0;i<100;i++){
    let previous=null,count=0,used=false;
    for(const frame of game.frames){
      const tile=game.tiles[frame.farms[game.seat].board[i]];
      const kind=tile&&typeof tile==='object'?(tile.crop||tile.animal):null;
      if(!kind)continue;
      used=true;
      if(previous&&previous!==kind){count++;const pair=previous+' → '+kind;tiles[i].pairs[pair]=(tiles[i].pairs[pair]||0)+1;}
      previous=kind;
    }
    tiles[i].counts.push(count);tiles[i].used+=Number(used);
    if(used){productive++;if(!count)stable++;}
  }
}
const n=data.games.length;
for(const t of tiles){t.total=t.counts.reduce((a,b)=>a+b,0);t.mean=t.used?t.total/n:null;}
const max=Math.max(...tiles.map(t=>t.mean||0));
const result={n,submission:data.submission,episodeIds:data.games.map(g=>g.id),denominator:'All loaded games per coordinate; never-productive coordinates marked missing',productiveTileGames:productive,stableTileGames:stable,totalChanges:tiles.reduce((s,t)=>s+t.total,0),tiles};
const outDir=path.join(root,'results/fresh/dsm_visualizer');
fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,'tile_change_map.json'),JSON.stringify(result,null,2));
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
let cells='<span></span>'+Array.from({length:10},(_,x)=>'<span class="axis">'+x+'</span>').join('');
for(let y=0;y<10;y++){
  cells+='<span class="axis">'+y+'</span>';
  for(const t of tiles.slice(y*10,y*10+10)){
    const pairs=Object.entries(t.pairs).sort((a,b)=>b[1]-a[1]).map(([k,v])=>k.toLowerCase()+': '+v).join('; ');
    const tip=t.used?`Tile (${t.x}, ${t.y}): ${t.mean.toFixed(2)} changes/game; ${t.total} changes across ${n} games; productive in ${t.used}/${n}. Range ${Math.min(...t.counts)}–${Math.max(...t.counts)}. ${pairs||'No production type changes.'}`:`Tile (${t.x}, ${t.y}): never productive in any sampled game.`;
    const fill=t.used?`color-mix(in srgb,var(--viz-series-1) ${8+54*t.mean/Math.max(1,max)}%,transparent)`:'var(--muted)';
    cells+=`<span class="mark" style="background:${fill}" data-tooltip="${escape(tip)}" aria-label="${escape(tip)}">${t.used?t.mean.toFixed(1):'—'}</span>`;
  }
}
const template=fs.readFileSync(path.join(root,'scripts/fragments/dsm_tile_changes.html'),'utf8');
fs.writeFileSync(target,template.replace('__CELLS__',cells).replace('12 tapes',`${n} tapes`).replace('3.1 changes/game',`${max.toFixed(1)} changes/game`));
console.log(JSON.stringify({games:n,productiveTileGames:productive,stableTileGames:stable,stablePercent:100*stable/productive,totalChanges:result.totalChanges,max,output:target}));
