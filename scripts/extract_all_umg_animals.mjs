import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const [file,seatStr,subStr]=process.argv.slice(2), seat=Number(seatStr), submission=Number(subStr);
const bytes=fs.readFileSync(file), r=JSON.parse(bytes), episode=r.info.EpisodeId;
assert.equal(r.steps.length,720);
const species=['COW','SHEEP','GOOSE'], active=new Map(), animals=[], purchases=[];
const same=(a,b)=>a?.animal && a.animal===b?.animal && a.placed_day===b.placed_day;
const obs=t=>({...r.steps[t][0].observation,...r.steps[t][seat].observation,farms:r.steps[t][0].observation.farms});
function holdings(o){const n={COW:0,SHEEP:0,GOOSE:0};for(const t of o.farms[seat].tiles.flat())if(t?.animal)n[t.animal]++;for(const inv of [o.private.shed,...o.private.inventories])for(const s of species)n[s]+=inv[s]||0;return n;}
for(let t=0;t<719;t++){
 const day=Math.floor(t/24),midnight=t%24===23,before=obs(t),after=obs(t+1),pre=before.farms[seat].tiles.flat(),post=after.farms[seat].tiles.flat(),exits={};
 for(let i=0;i<100;i++){
  const b=pre[i],a=post[i];
  if(b?.animal){const c=active.get(i);assert(c&&c.animal===b.animal&&c.placed_day===b.placed_day);if(b.fed_today)c.feed_days.add(day);if(!same(b,a)){assert(midnight);assert.equal(b.consecutive_unfed,1);c.departure_day=day;active.delete(i);exits[b.animal]=(exits[b.animal]||0)+1;}}
  if(a?.animal){if(!same(b,a)){const c={episode,submission,animal:a.animal,x:i%10,y:Math.floor(i/10),placed_day:a.placed_day,feed_days:new Set(),departure_day:null};active.set(i,c);animals.push(c);}const c=active.get(i);if(midnight?a.consecutive_unfed===0:a.fed_today)c.feed_days.add(day);}
 }
 const b=holdings(before),a=holdings(after),requested={};
 for(const order of r.steps[t+1][seat].action?.market||[])if(order[0]==='BUY_ANIMAL')requested[order[1]]=(requested[order[1]]||0)+(order[2]??1);
 for(const s of species){const n=a[s]-b[s]+(exits[s]||0);assert(n>=0&&n<=(requested[s]||0));if(n)purchases.push({episode,submission,day,step:t,animal:s,units:n});}
}
for(const c of animals){c.feed_days=[...c.feed_days].sort((a,b)=>a-b);c.last_feed_day=c.feed_days.at(-1)??null;c.termination_day=c.last_feed_day===null?c.placed_day:c.last_feed_day+1;if(c.departure_day!==null&&c.last_feed_day!==null)assert.equal(c.departure_day,c.last_feed_day+2);}
const final=obs(719),unplaced={};
for(const s of species){unplaced[s]=[final.private.shed,...final.private.inventories].reduce((n,inv)=>n+(inv[s]||0),0);assert.equal(purchases.filter(p=>p.animal===s).reduce((n,p)=>n+p.units,0),animals.filter(a=>a.animal===s).length+unplaced[s]);}
const ledgerPath=path.resolve('results/fresh/leader_segments',`segments-${episode}.json`);let checks=0;
if(fs.existsSync(ledgerPath)){const ledger=JSON.parse(fs.readFileSync(ledgerPath));for(let seg=0;seg<10;seg++){assert.equal(animals.reduce((n,c)=>n+c.feed_days.filter(d=>Math.floor(d/3)===seg).length,0),ledger.seats[seat].segments[seg].physical.wheat_fed||0);checks++;}}
const out=path.resolve('results/fresh/all_umg_m1/animals');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,`${episode}.json`),JSON.stringify({episode,submission,seat,seed:r.info.seed,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),animals,purchases,unplaced,ledger_feed_checks:checks}));
