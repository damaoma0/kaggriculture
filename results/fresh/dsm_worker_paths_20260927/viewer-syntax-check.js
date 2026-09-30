
  (() => {
    const root=document.getElementById('dsm-worker-traces');
    const data=JSON.parse(document.getElementById('dsm-worker-trace-data').textContent);
    const q=s=>root.querySelector(s);
    const controls={world:q('[data-control="world"]'),day:q('[data-control="day"]'),worker:q('[data-control="worker"]'),hour:q('#dsm-trace-hour')};
    const view={map:q('[data-view="map"]'),budget:q('[data-view="budget"]'),hour:q('[data-view="hour"]'),strip:q('[data-view="strip"]'),detail:q('[data-view="detail"]')};
    const moves=new Set(['NORTH','SOUTH','EAST','WEST']);
    const animals=new Set(['GOOSE','COW','SHEEP']);
    const colors={work:'var(--viz-series-1)',move:'var(--viz-series-2)',shed:'var(--viz-series-3)',idle:'var(--muted-foreground)'};
    const names={WH:'wheat',CA:'carrot',TO:'tomato',ST:'strawberry',ME:'melon',GO:'goose',CO:'cow',SH:'sheep',WE:'weed',CP:'coop',PA:'pasture','--':'empty',XX:'locked'};
    const compact={WHEAT:'WH',CARROT:'CA',TOMATO:'TO',STRAWBERRY:'ST',MELON:'ME',GOOSE:'GO',COW:'CO',SHEEP:'SH',WEED:'WE',COOP:'CP',PASTURE:'PA',EMPTY:'--',LOCKED:'XX','empty':'--','locked':'XX'};
    let world,day,worker;
    function label(v){ return compact[v]||v||'--'; }
    function options(el,rows,preferred){el.replaceChildren(...rows.map(([value,text])=>{const o=document.createElement('option');o.value=String(value);o.textContent=text;return o;}));if([...el.options].some(o=>o.value===String(preferred)))el.value=String(preferred);}
    function isShed(x,y){return (x===4||x===5)&&(y===4||y===5);}
    function category(e){const c=e[3]||['PASS'],op=c[0];return moves.has(op)?'move':op==='PASS'?'idle':(op==='PICKUP'||op==='DROP'||(op==='PLACE'&&isShed(e[1],e[2])&&!animals.has(c[1])))?'shed':'work';}
    function setWorld(preferredDay=17,preferredWorker=1){world=data.worlds.find(w=>String(w.episode)===controls.world.value);options(controls.day,world.days.map(d=>[d.day,String(d.day)]),preferredDay);setDay(preferredWorker);}
    function setDay(preferredWorker=controls.worker.value){day=world.days.find(d=>String(d.day)===controls.day.value);options(controls.worker,day.workers.map(w=>[w.unit,w.unit===0?'Farmer':`Hand ${w.unit}`]),preferredWorker);setWorker();}
    function setWorker(){worker=day.workers.find(w=>String(w.unit)===controls.worker.value);controls.hour.min=worker.events[0][0];controls.hour.max=worker.events[worker.events.length-1][0];controls.hour.value=Math.max(Number(controls.hour.min),Math.min(Number(controls.hour.value),Number(controls.hour.max)));draw();}
    function save(){if(window.openai&&window.openai.setWidgetState)window.openai.setWidgetState({modelContent:{episode:world.episode,day:day.day,unit:worker.unit,hour:Number(controls.hour.value)},privateContent:null}).catch(()=>{});}
    function escape(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
    function draw(){
      const hour=Number(controls.hour.value),events=worker.events,sel=events.find(e=>e[0]===hour)||events[events.length-1],shown=events.filter(e=>e[0]<=hour);
      const counts={work:0,move:0,shed:0,idle:0};events.forEach(e=>counts[category(e)]++);
      view.budget.innerHTML=Object.entries(counts).map(([k,v])=>`<span><i class="trace-swatch" style="background:${colors[k]}"></i>${v} ${k==='move'?'walking':k==='shed'?'shed exchange':k} h</span>`).join('');
      view.hour.textContent=String(hour);
      view.strip.replaceChildren(...events.map(e=>{const s=document.createElement('span');s.style.background=colors[category(e)];s.style.opacity=e[0]<=hour?'1':'0.2';s.setAttribute('data-tooltip',`h${e[0]} · ${(e[3]||['PASS']).join(' ')}`);return s;}));
      const delta=sel[5]||{},changes=Object.entries(delta).filter(([,v])=>v).map(([k,v])=>`${k.toLowerCase()} ${v>0?'+':''}${v}`);
      const effect=sel[7]===0&&sel[3][0]!=='PASS'?' · no effect':'';
      view.detail.textContent=`h${sel[0]} · (${sel[1]}, ${sel[2]}) ${names[label(sel[4])]||String(sel[4]).toLowerCase()} · ${sel[3].join(' ')}${changes.length?' · '+changes.join(', '):''}${effect}`;
      const width=Math.max(280,view.map.getBoundingClientRect().width),pad=23,cell=(width-pad-7)/10,height=cell*10+pad+5;
      const cx=x=>pad+(x+0.5)*cell,cy=y=>pad+(y+0.5)*cell;
      let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Recorded route for world ${world.episode}, day ${day.day}, ${worker.unit===0?'farmer':'hand '+worker.unit}, through hour ${hour}"><title>Exact recorded DSM worker route</title><desc>The background is the morning farm. A thin line shows the full day's movement; the colored line shows movement through the selected hour. Circles count work actions at a tile.</desc>`;
      for(let y=0;y<10;y++)for(let x=0;x<10;x++){
        const raw=day.board[y*10+x],v=label(raw),locked=v==='XX';
        svg+=`<rect x="${pad+x*cell}" y="${pad+y*cell}" width="${cell}" height="${cell}" fill="${locked?'var(--muted)':'none'}" stroke="var(--border)" stroke-width="0.6"/>`;
        if(v!=='--'&&v!=='XX')svg+=`<text x="${pad+x*cell+2}" y="${pad+y*cell+12}" fill="var(--muted-foreground)" font-size="11">${escape(v)}</text>`;
        if(isShed(x,y))svg+=`<text x="${pad+(x+1)*cell-3}" y="${pad+(y+1)*cell-3}" text-anchor="end" fill="var(--foreground)" font-size="11">S</text>`;
      }
      for(let i=0;i<10;i++)svg+=`<text x="${cx(i)}" y="15" text-anchor="middle" fill="var(--foreground)" font-size="12">${i}</text><text x="12" y="${cy(i)+4}" text-anchor="middle" fill="var(--foreground)" font-size="12">${i}</text>`;
      function points(es){if(!es.length)return '';let ps=[[es[0][1],es[0][2]]];es.forEach(e=>{const p=e[6]||[e[1],e[2]],last=ps[ps.length-1];if(p[0]!==last[0]||p[1]!==last[1])ps.push(p);});return ps.map(p=>`${cx(p[0])},${cy(p[1])}`).join(' ');}
      svg+=`<polyline points="${points(events)}" fill="none" stroke="var(--border)" stroke-width="2"/><polyline points="${points(shown)}" fill="none" stroke="var(--viz-series-2)" stroke-width="2.5" stroke-linejoin="round"/>`;
      const visits=new Map();shown.filter(e=>category(e)==='work').forEach(e=>{const key=e[1]+','+e[2];visits.set(key,(visits.get(key)||0)+1);});
      for(const [key,n] of visits){const [x,y]=key.split(',').map(Number),r=Math.min(11,cell*0.32);svg+=`<circle cx="${cx(x)}" cy="${cy(y)}" r="${r}" fill="var(--background)"/><circle cx="${cx(x)}" cy="${cy(y)}" r="${r}" fill="var(--viz-series-1)" fill-opacity="0.17"/><text x="${cx(x)}" y="${cy(y)+4}" text-anchor="middle" fill="var(--foreground)" font-size="12">${n}</text>`;}
      const start=events[0],p=sel[6]||[sel[1],sel[2]];
      svg+=`<rect x="${cx(start[1])-4}" y="${cy(start[2])-4}" width="8" height="8" fill="var(--foreground)"/><circle cx="${cx(p[0])}" cy="${cy(p[1])}" r="${Math.min(14,cell*.43)}" fill="none" stroke="var(--viz-series-2)" stroke-width="2.5"/>`;
      svg+='</svg>';view.map.innerHTML=svg;
    }
    controls.world.addEventListener('change',()=>{setWorld(Number(controls.day.value),Number(controls.worker.value));save();});
    controls.day.addEventListener('change',()=>{setDay();save();});
    controls.worker.addEventListener('change',()=>{setWorker();save();});
    controls.hour.addEventListener('input',draw);controls.hour.addEventListener('change',save);
    const saved=window.openai?.widgetState?.modelContent||{};
    options(controls.world,data.worlds.map(w=>[w.episode,String(w.episode)]),saved.episode||112604454);
    if(Number.isFinite(saved.hour))controls.hour.value=saved.hour;
    setWorld(saved.day??16,saved.unit??5);
    window.addEventListener('openai:set_globals',e=>{const s=e.detail?.globals?.widgetState?.modelContent;if(!s)return;if([...controls.world.options].some(o=>o.value===String(s.episode))){controls.world.value=String(s.episode);controls.hour.value=s.hour??23;setWorld(s.day,s.unit);}});
    new ResizeObserver(()=>draw()).observe(view.map);
  })();
  