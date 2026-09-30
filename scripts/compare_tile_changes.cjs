// Compare observed production-type switches using full hourly states for both leaders.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
function blank(name,submission,startDay){return {name,submission,startDay,endDay:29,episodeIds:[],productive:0,stable:0,tiles:Array.from({length:100},(_,i)=>({x:i%10,y:Math.floor(i/10),used:0,counts:[],pairs:{}}))};}
function kind(tile){return tile&&typeof tile==='object'?(tile.crop||tile.animal||null):null;}
function accumulate(group,eid,boards){
  assert.equal(boards.length,720);assert(!group.episodeIds.includes(eid));group.episodeIds.push(eid);
  for(let i=0;i<100;i++){
    let previous=null,count=0,used=false;
    for(let t=group.startDay*24;t<boards.length;t++){
      const current=boards[t][i];if(!current)continue;used=true;
      if(previous&&previous!==current){count++;const pair=previous+' → '+current;group.tiles[i].pairs[pair]=(group.tiles[i].pairs[pair]||0)+1;}
      previous=current;
    }
    group.tiles[i].used+=Number(used);group.tiles[i].counts.push(count);
    if(used){group.productive++;if(!count)group.stable++;}
  }
}
const groups=[blank('DSM',56444344,12),blank('UMG',56266758,12),blank('DSM',56444344,0),blank('UMG',56266758,0)];
const h=fs.readFileSync(path.join(ROOT,'viz/dsm-tapes.html'),'utf8');
const dsm=JSON.parse(h.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
for(const meta of dsm.games){
  const g={...meta,...JSON.parse(zlib.gunzipSync(Buffer.from(meta.packed,'base64')).toString())};
  const boards=g.frames.map(f=>f.farms[g.seat].board.map(id=>kind(g.tiles[id])));
  accumulate(groups[0],g.id,boards);accumulate(groups[2],g.id,boards);
}
const umg=['results/fresh/cumulative_planning/dataset_train.json','results/fresh/cumulative_planning/dataset_test.json'].flatMap(p=>read(p).games).filter(g=>+g.submission===56266758);
assert.equal(umg.length,105);
const dirs=['results/fresh/cumulative_planning/raw_replays','data/leaders_20260917','data/leaders_20260919'];
const sources=[];
for(const [index,meta] of umg.entries()){
  const file=dirs.map(d=>path.join(ROOT,d,`episode-${meta.episode}-replay.json`)).find(p=>fs.existsSync(p));
  assert(file,`Missing full replay ${meta.episode}`);
  const g=JSON.parse(fs.readFileSync(file,'utf8'));
  assert.equal(g.info.EpisodeId,meta.episode);assert.equal(g.info.TeamNames[meta.seat],'Unknown Mother-Goose');
  const boards=g.steps.map(step=>step[0].observation.farms[meta.seat].tiles.flat().map(kind));
  accumulate(groups[1],meta.episode,boards);accumulate(groups[3],meta.episode,boards);
  sources.push({episode:meta.episode,seat:meta.seat,path:path.relative(ROOT,file)});
  if((index+1)%20===0)console.log(`Read ${index+1}/${umg.length} UMG hourly replays`);
}
for(const group of groups){
  group.n=group.episodeIds.length;
  for(const t of group.tiles){t.total=t.counts.reduce((a,b)=>a+b,0);t.mean=t.used?t.total/group.n:null;}
  group.totalChanges=group.tiles.reduce((sum,t)=>sum+t.total,0);group.stablePercent=100*group.stable/group.productive;
}
// Full-season DSM totals must reproduce the earlier complete-library audit.
assert.equal(groups[2].totalChanges,9595);assert.equal(groups[2].stable,2349);
// Regression checks for interval boundaries, gaps, and same-type replanting.
const testBoards=Array.from({length:720},()=>Array(100).fill(null));
testBoards[287][0]='WHEAT';testBoards[288][0]='CARROT';testBoards[300][0]='CARROT';testBoards[400][0]='TOMATO';
const test=blank('test',0,12);accumulate(test,1,testBoards);assert.equal(test.tiles[0].counts[0],1);
const output={method:'Hourly recorded crop/animal identities. Start at day 12 hour 0 (frame 288) for late windows; the first observed productive type within each window is its baseline. Ignore empty, locked, weeds, empty structures, and same-type replanting. Map means divide by all games in that leader sample; never-productive coordinates are missing. Stable percentages exclude never-productive tile/game pairs.',groups,umgSources:sources};
const out=path.join(ROOT,'results/fresh/dsm_visualizer/leader_tile_change_comparison.json');
fs.writeFileSync(out,JSON.stringify(output,null,2));
console.log(JSON.stringify(groups.map(({name,startDay,n,productive,stable,stablePercent,totalChanges})=>({name,startDay,n,productive,stable,stablePercent,totalChanges})),null,2));
