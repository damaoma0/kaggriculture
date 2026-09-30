// Full hourly audit of production changes, replacement times and preceding vacancies.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),OUT=path.join(ROOT,'results/fresh/tile_transition_timing');
fs.mkdirSync(OUT,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const kind=t=>t&&typeof t==='object'?(t.crop||t.animal||null):null;
const birth=t=>t&&typeof t==='object'?(t.planted_day??t.placed_day??null):null;
function commandsAt(frame,i){
  if(!frame)return [];
  const commands=[frame.action?.farmer||['PASS'],...(frame.action?.hands||[])];
  return frame.units.flatMap(([x,y],u)=>y*10+x===i?[{worker:u,command:commands[u]||['PASS']}]:[]);
}
function extract(meta,frames){
  assert.equal(frames.length,720);const events=[],replants=[],histories=[],initials=[],exits=[];
  let reveals=[],priorShopCount=0;
  for(let t=0;t<frames.length;t++)if(frames[t].shops.length>priorShopCount){reveals.push({step:t,shop:frames[t].shops.at(-1)});priorShopCount=frames[t].shops.length;}
  for(let i=0;i<100;i++){
    let last=null,lastStep=null,lastTile=null,cohortStart=null,typeStart=null,vacancy=null;const sequence=[];
    for(let t=0;t<frames.length;t++){
      const tile=frames[t].board[i],type=kind(tile);
      if(!type){
        if(last&&vacancy===null)vacancy={observedStep:t,actionStep:t-1,commands:commandsAt(frames[t-1],i),nextState:tile};
        continue;
      }
      const newCohort=last===null||type!==last||lastStep!==t-1||birth(tile)!==birth(lastTile);
      if(newCohort){
        const step=t-1,decision=frames[Math.max(0,step)],recent=rev=>reveals.filter(r=>r.step<=rev).at(-1),reveal=recent(step);
        const item={leader:meta.leader,submission:meta.submission,episode:meta.episode,seat:meta.seat,x:i%10,y:Math.floor(i/10),
          from:last,to:type,observedStep:t,actionStep:step,day:Math.floor(step/24),hour:step%24,
          previousLastProductiveStep:lastStep,previousCohortObservedStep:cohortStart,previousTypeObservedStep:typeStart,
          previousBirthDay:birth(lastTile),previousAgeDays:lastTile?Math.floor(lastStep/24)-birth(lastTile):null,
          releaseObservedStep:last===null?null:(vacancy?.observedStep??t),releaseActionStep:last===null?null:(vacancy?.actionStep??step),
          emptyHours:last===null?null:t-lastStep-1,
          releaseCommands:last===null?[]:(vacancy?.commands??commandsAt(frames[Math.max(0,t-1)],i)),
          establishmentCommands:commandsAt(decision,i),previousTile:lastTile,newTile:tile,
          visibleShops:decision.shops,latestShop:reveal?.shop??null,hoursSinceShopReveal:reveal?step-reveal.step:null,
          prices:decision.prices,cash:decision.money};
        if(last===null)initials.push(item);else if(type===last)replants.push(item);else events.push(item);
        if(type!==last){typeStart=t;sequence.push({type,observedStep:t,actionStep:step});}
        cohortStart=t;
      }
      last=type;lastStep=t;lastTile=tile;vacancy=null;
    }
    if(last){histories.push({episode:meta.episode,x:i%10,y:Math.floor(i/10),sequence});if(lastStep<719)exits.push({episode:meta.episode,x:i%10,y:Math.floor(i/10),type:last,lastProductiveStep:lastStep,releaseObservedStep:vacancy.observedStep,releaseCommands:vacancy.commands});}
  }
  return {events,replants,histories,initials,exits,meta};
}
function quantile(xs,p){if(!xs.length)return null;const a=[...xs].sort((a,b)=>a-b),k=(a.length-1)*p,l=Math.floor(k);return a[l]+(a[Math.ceil(k)]-a[l])*(k-l);}
const stats=xs=>({p10:quantile(xs,.1),p25:quantile(xs,.25),median:quantile(xs,.5),p75:quantile(xs,.75),p90:quantile(xs,.9),min:xs.length?Math.min(...xs):null,max:xs.length?Math.max(...xs):null});
function summarize(leader,runs){
  const events=runs.flatMap(r=>r.events),replants=runs.flatMap(r=>r.replants),histories=runs.flatMap(r=>r.histories);
  const pair=(from,to)=>from+' → '+to;
  const groups={};for(const e of events)(groups[pair(e.from,e.to)]??=[]).push(e);
  const pairRows=Object.entries(groups).map(([transition,list])=>{
    const byDay=Array(30).fill(0),byHour=Array(24).fill(0),releaseOps={};for(const e of list){byDay[e.day]++;byHour[e.hour]++;const ops=[...new Set(e.releaseCommands.map(c=>c.command[0]))].sort().join('+')||'NO_UNIT_COMMAND';releaseOps[ops]=(releaseOps[ops]||0)+1;}
    return {transition,n:list.length,games:new Set(list.map(e=>e.episode)).size,perGame:list.length/runs.length,
      afterDay12:list.filter(e=>e.actionStep>=288).length,byDay,byHour,actionTime:stats(list.map(e=>e.actionStep)),
      ageDays:stats(list.filter(e=>e.previousAgeDays!==null).map(e=>e.previousAgeDays)),emptyHours:stats(list.map(e=>e.emptyHours)),
      fractionAtMost1EmptyHour:list.filter(e=>e.emptyHours<=1).length/list.length,
      establishConfirmed:list.filter(e=>e.establishmentCommands.some(c=>(c.command[0]==='PLANT'||c.command[0]==='PLACE')&&c.command[1]===e.to)).length,
      releaseOps};
  }).sort((a,b)=>b.n-a.n);
  const daily=Array.from({length:30},(_,day)=>({day,total:0,replants:0,pairs:{}}));for(const e of events){daily[e.day].total++;daily[e.day].pairs[pair(e.from,e.to)]=(daily[e.day].pairs[pair(e.from,e.to)]||0)+1;}for(const e of replants)daily[e.day].replants++;
  const tiles=Array.from({length:100},(_,i)=>{const list=events.filter(e=>e.y*10+e.x===i),hs=histories.filter(h=>h.y*10+h.x===i),paths={};for(const h of hs){const k=h.sequence.map(s=>s.type).join(' → ');paths[k]=(paths[k]||0)+1;}return {x:i%10,y:Math.floor(i/10),productiveGames:hs.length,changedGames:new Set(list.map(e=>e.episode)).size,
    firstChangeTime:stats(hs.filter(h=>h.sequence.length>1).map(h=>h.sequence[1].actionStep)),
    paths:Object.entries(paths).sort((a,b)=>b[1]-a[1]),events:list.map(e=>({episode:e.episode,from:e.from,to:e.to,actionStep:e.actionStep,emptyHours:e.emptyHours}))};});
  return {leader,n:runs.length,submission:runs[0].meta.submission,events:events.length,sameTypeReplants:replants.length,
    afterDay12:events.filter(e=>e.actionStep>=288).length,previousMapComparable:events.filter(e=>e.previousLastProductiveStep>=288).length,
    emptyHours:stats(events.map(e=>e.emptyHours)),fractionAtMost1EmptyHour:events.filter(e=>e.emptyHours<=1).length/events.length,
    fractionAtMost3EmptyHours:events.filter(e=>e.emptyHours<=3).length/events.length,
    establishConfirmed:events.filter(e=>e.establishmentCommands.some(c=>(c.command[0]==='PLANT'||c.command[0]==='PLACE')&&c.command[1]===e.to)).length,
    pairRows,daily,tiles,episodes:runs.map(r=>r.meta),retirementsWithoutReplacement:runs.reduce((s,r)=>s+r.exits.length,0)};
}

// Synthetic gap, replant, direct replacement, and day-12-boundary checks.
const synthetic=Array.from({length:720},()=>({board:Array(100).fill(null),units:[],action:{},shops:[],prices:{},money:0}));
synthetic[287].board[0]={crop:'WHEAT',planted_day:10};synthetic[289].board[0]={crop:'CARROT',planted_day:12};synthetic[291].board[0]={crop:'CARROT',planted_day:12};synthetic[292].board[0]={crop:'TOMATO',planted_day:12};
const check=extract({leader:'test',episode:1},synthetic);assert.equal(check.events.length,2);assert.equal(check.replants.length,1);assert.equal(check.events[0].actionStep,288);assert.equal(check.events[0].emptyHours,1);assert.equal(check.events[1].emptyHours,0);

const all={DSM:[],UMG:[]};
const h=fs.readFileSync(path.join(ROOT,'viz/dsm-tapes.html'),'utf8'),dsm=JSON.parse(h.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
for(const meta of dsm.games){
  const g={...meta,...JSON.parse(zlib.gunzipSync(Buffer.from(meta.packed,'base64')).toString())};
  const frames=g.frames.map(f=>({board:f.farms[g.seat].board.map(id=>g.tiles[id]),units:f.farms[g.seat].units,action:f.farms[g.seat].action,shops:f.shops,prices:f.prices,money:f.farms[g.seat].money}));
  all.DSM.push(extract({leader:'DSM',episode:g.id,submission:g.submission,seat:g.seat},frames));
}
console.log('DSM extracted: '+all.DSM.length+' games');
const manifest=read('results/fresh/dsm_visualizer/leader_tile_change_comparison.json');
for(const [index,meta] of manifest.umgSources.entries()){
  const g=read(meta.path);assert.equal(g.info.EpisodeId,meta.episode);assert.equal(g.info.TeamNames[meta.seat],'Unknown Mother-Goose');
  const frames=g.steps.map((st,t)=>{const o=st[0].observation,f=o.farms[meta.seat];return {board:f.tiles.flat(),units:[f.farmer,...f.hands],action:g.steps[t+1]?.[meta.seat]?.action,shops:o.town.unlocked_shops,prices:o.market.prices,money:f.money};});
  all.UMG.push(extract({leader:'UMG',episode:meta.episode,submission:56266758,seat:meta.seat},frames));
  if((index+1)%25===0)console.log('UMG extracted: '+(index+1)+' games');
}
const summary={method:{time:'Action issued at step t-1; changed type first observed in frame t. Day/hour are zero-based. Empty hours count nonproductive observations strictly between old and new types.',switch:'A difference between successive nonempty crop/animal types. Initial establishment, same-type replanting and unreplaced retirements are separate.',afterDay12:'Actions issued at step >= 288; source identity can carry across day 12. The earlier map reset source identity at frame 288; previousMapComparable reproduces that convention.',scope:'108 DSM games (56444344) and 105 historical UMG games (56266758); observational, not matched worlds or causal demand-response estimates.'},leaders:[]};
for(const leader of ['DSM','UMG']){
  const result=summarize(leader,all[leader]);summary.leaders.push(result);
  assert.equal(result.events,leader==='DSM'?9595:7867);assert.equal(result.previousMapComparable,leader==='DSM'?7176:5777);
  fs.writeFileSync(path.join(OUT,leader.toLowerCase()+'-events.json'),JSON.stringify(all[leader]));
  console.log(JSON.stringify({leader,games:result.n,switches:result.events,replants:result.sameTypeReplants,afterDay12:result.afterDay12,previousMapComparable:result.previousMapComparable,emptyHours:result.emptyHours,fastFraction:result.fractionAtMost3EmptyHours,confirmed:result.establishConfirmed}));
}
fs.writeFileSync(path.join(OUT,'summary.json'),JSON.stringify(summary,null,2));
console.log('Saved event ledgers and summary to '+OUT);
