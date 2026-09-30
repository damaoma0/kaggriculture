// Successful purchase-date distributions from conservation of animal holdings.
// Reconcile each three-day species total against exact-engine transaction spend.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const root = path.resolve(import.meta.dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const source = read('results/fresh/umg_lifecycles/audit.json');
const species = ['COW', 'SHEEP', 'GOOSE'];
const costs = {COW: 400, SHEEP: 500, GOOSE: 300};
const purchased = [], checks = [], unplaced = {}, finalLive = {};
const sum = (a, fn) => a.reduce((n, x) => n + fn(x), 0);
const inc = (o, k, n = 1) => {o[k] = (o[k] || 0) + n;};
function holdings(obs, seat) {
  const result = Object.fromEntries(species.map(s => [s, 0]));
  for (const tile of obs.farms[seat].tiles.flat()) if (tile?.animal) result[tile.animal]++;
  for (const stock of [obs.private.shed, ...obs.private.inventories]) for (const s of species) result[s] += stock[s] || 0;
  return result;
}
for (const game of source.games) {
  const bytes = fs.readFileSync(path.join(root, `data/leaders_20260917/episode-${game.episode}-replay.json`));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), game.sha256);
  const r = JSON.parse(bytes), seat = game.seat;
  const ledger = read(`results/fresh/leader_segments/segments-${game.episode}.json`);
  const totals = Array.from({length: 10}, () => ({}));
  for (let t = 0; t < 719; t++) {
    const day = Math.floor(t / 24), before = r.steps[t][seat].observation, after = r.steps[t+1][seat].observation;
    const b = holdings(before, seat), a = holdings(after, seat), escape = {}, requested = {};
    const tiles0 = before.farms[seat].tiles.flat(), tiles1 = after.farms[seat].tiles.flat();
    tiles0.forEach((tile, i) => {
      if (tile?.animal && (tile.animal !== tiles1[i]?.animal || tile.placed_day !== tiles1[i]?.placed_day)) inc(escape, tile.animal);
    });
    for (const order of r.steps[t+1][seat].action?.market || []) if (order[0] === 'BUY_ANIMAL') inc(requested, order[1], order[2] ?? 1);
    for (const animal of species) {
      const n = a[animal] - b[animal] + (escape[animal] || 0);
      assert(n >= 0 && n <= (requested[animal] || 0), `unexplained holding change ${game.episode} ${t} ${animal}`);
      if (n) {purchased.push({episode: game.episode, day, step: t, animal, units: n}); inc(totals[Math.floor(day/3)], animal, n);}
    }
  }
  for (let segment = 0; segment < 10; segment++) for (const animal of species) {
    const inferred = totals[segment][animal] || 0;
    const measured = (ledger.seats[seat].segments[segment].ledger.spend[`BUY_ANIMAL:${animal}`] || 0) / costs[animal];
    assert.equal(inferred, measured, `purchase ledger ${game.episode} ${segment} ${animal}`);
    checks.push({episode: game.episode, segment, animal, units: measured});
  }
  const final = r.steps[719][seat].observation;
  for (const animal of species) {
    inc(finalLive, animal, final.farms[seat].tiles.flat().filter(t => t?.animal === animal).length);
    inc(unplaced, animal, sum([final.private.shed, ...final.private.inventories], s => s[animal] || 0));
  }
}
const summary = {};
for (const animal of species) {
  const buys = purchased.filter(p => p.animal === animal), placements = source.animal_births.filter(p => p.animal === animal), exits = source.animal_exits.filter(p => p.animal === animal);
  const units = sum(buys, p => p.units), count = placements.length;
  assert.equal(units, count + unplaced[animal]);
  assert.equal(count, exits.length + finalLive[animal]);
  const daily = Array.from({length: 30}, (_, day) => ({day,
    purchased: sum(buys.filter(p => p.day === day), p => p.units),
    placed: placements.filter(p => p.day === day).length,
    departed: exits.filter(p => p.day === day).length,
    games_purchasing: new Set(buys.filter(p => p.day === day).map(p => p.episode)).size,
    games_with_departure: new Set(exits.filter(p => p.day === day).map(p => p.episode)).size}));
  const bins = Array.from({length: 10}, (_, k) => {const selected=daily.slice(k*3,k*3+3);return {days:[k*3,k*3+2], purchased:sum(selected,p=>p.purchased), placed:sum(selected,p=>p.placed), departed:sum(selected,p=>p.departed)};});
  const dates = buys.flatMap(p => Array(p.units).fill(p.day)).sort((a,b)=>a-b);
  summary[animal] = {purchased: units, placed: count, departed: exits.length, still_alive: finalLive[animal], unplaced: unplaced[animal],
    median_purchase_day: (dates[Math.floor((dates.length-1)/2)]+dates[Math.floor(dates.length/2)])/2,
    fraction_bought_by_day11: sum(buys.filter(p=>p.day<=11),p=>p.units)/units,
    fraction_bought_from_day18: sum(buys.filter(p=>p.day>=18),p=>p.units)/units,
    fraction_still_alive: finalLive[animal]/count, daily, bins};
}
const result = {games: source.games.length, scope:source.scope,
  purchase_definition:'Successful units: change in total animals across live farm, shed and worker inventories plus departures; each three-day species count reconciles to exact-engine transaction spending.',
  departure_definition:'Animal disappears after its second consecutive missed feed. Day is the day ending at that refresh, not the next day when absence is first visible. Intentional retirement and accidental loss are not separable from dates alone.',
  validation:{segment_species_checks:checks.length,all_passed:true,placed_equals_departed_plus_surviving:true,purchased_equals_placed_plus_unplaced:true},
  summary, purchases:purchased};
const out=path.join(root,'results/fresh/umg_lifecycles/animal_date_distributions.json');
fs.writeFileSync(out,JSON.stringify(result,null,2));
const fmt=(n,total)=>`${n} (${(100*n/total).toFixed(1)}%)`;
let md='# UMG animal purchase and departure dates\n\n30 verified full replays of submission 56266758. Zero-based days. Percentages are pooled animal counts, not fractions of games.\n\n## Successful purchases\n\n';
md+='| Days | Cows | Sheep | Geese |\n|---|---:|---:|---:|\n';
for(let i=0;i<10;i++)md+=`| ${i*3}–${i*3+2} | ${species.map(s=>fmt(summary[s].bins[i].purchased,summary[s].purchased)).join(' | ')} |\n`;
md+=`| Total purchased | ${species.map(s=>summary[s].purchased).join(' | ')} |\n\n## Departures and survival\n\nPercentages below use all successfully placed animals as the denominator, including those that survive the season. A departure happens at the end of the labeled day after two missed feeds; not every departure is necessarily deliberate retirement.\n\n| Days | Cows | Sheep | Geese |\n|---|---:|---:|---:|\n`;
for(let i=0;i<10;i++)md+=`| ${i*3}–${i*3+2} | ${species.map(s=>fmt(summary[s].bins[i].departed,summary[s].placed)).join(' | ')} |\n`;
md+=`| Still alive at game end | ${species.map(s=>fmt(summary[s].still_alive,summary[s].placed)).join(' | ')} |\n| Total placed | ${species.map(s=>summary[s].placed).join(' | ')} |\n\n## Exact daily counts\n\n| Day | Cows bought | Sheep bought | Geese bought | Cows departed | Sheep departed | Geese departed |\n|---|---:|---:|---:|---:|---:|---:|\n`;
for(let d=0;d<30;d++)md+=`| ${d} | ${species.map(s=>summary[s].daily[d].purchased).join(' | ')} | ${species.map(s=>summary[s].daily[d].departed).join(' | ')} |\n`;
md+='\n## Validation\n\nAll 900 game × three-day-period × species purchase counts reconcile to the previous exact-engine spending ledgers. Live animals, stored animals and carried animals are included to distinguish purchases from placements. Every species reconciles purchased = placed + unplaced, and placed = departed + surviving. Full daily counts, game incidence and successful purchase events are in `results/fresh/umg_lifecycles/animal_date_distributions.json`. Reproduce with `node scripts/report_umg_animal_dates.mjs`.\n';
fs.writeFileSync(path.join(root,'docs/umg_animal_date_distributions.md'),md);
console.log(md);
