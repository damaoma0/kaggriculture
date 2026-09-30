// Last successful feeding day per individual animal, including season survivors.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
const root = path.resolve(import.meta.dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const source = read('results/fresh/umg_lifecycles/audit.json');
const species = ['COW', 'SHEEP', 'GOOSE'];
const animals = [], checks = [];
const same = (a, b) => a?.animal && a.animal === b?.animal && a.placed_day === b.placed_day;
for (const game of source.games) {
  const bytes = fs.readFileSync(path.join(root, `data/leaders_20260917/episode-${game.episode}-replay.json`));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), game.sha256);
  const raw = JSON.parse(bytes), active = new Map(), local = [];
  for (let t = 0; t < 719; t++) {
    const day = Math.floor(t / 24), midnight = t % 24 === 23;
    const pre = raw.steps[t][game.seat].observation.farms[game.seat].tiles.flat();
    const post = raw.steps[t+1][game.seat].observation.farms[game.seat].tiles.flat();
    for (let i = 0; i < pre.length; i++) {
      const b = pre[i], a = post[i];
      if (b?.animal) {
        const cohort = active.get(i);
        assert(cohort && cohort.animal === b.animal && cohort.placed_day === b.placed_day);
        if (b.fed_today) cohort.feed_days.add(day);
        if (!same(b, a)) {
          assert.equal(b.consecutive_unfed, 1);
          assert.equal(midnight, true);
          cohort.departure_day = day;
          active.delete(i);
        }
      }
      if (a?.animal) {
        if (!same(b, a)) {
          const cohort = {episode: game.episode, animal: a.animal, tile: [i%10, Math.floor(i/10)],
            placed_day: a.placed_day, feed_days: new Set(), departure_day: null};
          active.set(i, cohort); local.push(cohort);
        }
        const cohort = active.get(i);
        // Midnight resets fed_today. A zero consecutive-unfed counter after
        // refresh proves this animal was fed during the day that just ended.
        if (midnight ? a.consecutive_unfed === 0 : a.fed_today) cohort.feed_days.add(day);
      }
    }
  }
  const ledger = read(`results/fresh/leader_segments/segments-${game.episode}.json`);
  for (let segment = 0; segment < 10; segment++) {
    const found = local.reduce((n, c) => n + [...c.feed_days].filter(d => Math.floor(d/3) === segment).length, 0);
    const expected = ledger.seats[game.seat].segments[segment].physical.wheat_fed || 0;
    assert.equal(found, expected, `successful feed ledger ${game.episode} segment ${segment}`);
    checks.push({episode: game.episode, segment, successful_feeds: found});
  }
  for (const c of local) {
    c.feed_days = [...c.feed_days].sort((a,b)=>a-b);
    c.last_feed_day = c.feed_days.length ? c.feed_days.at(-1) : null;
    c.first_day_without_further_feed = c.last_feed_day === null ? c.placed_day : c.last_feed_day + 1;
    if (c.departure_day !== null && c.last_feed_day !== null) assert.equal(c.departure_day, c.last_feed_day+2);
    animals.push(c);
  }
}
const summary = {};
for (const s of species) {
  const rows = animals.filter(a=>a.animal===s), counts = Array(30).fill(0);
  for (const a of rows) if (a.last_feed_day !== null) counts[a.last_feed_day]++;
  assert.equal(rows.length, source.animal_births.filter(a=>a.animal===s).length);
  const dates = rows.filter(a=>a.last_feed_day!==null).map(a=>a.last_feed_day).sort((a,b)=>a-b);
  summary[s] = {animals: rows.length, never_fed: rows.filter(a=>a.last_feed_day===null).length,
    last_feed_by_day:counts, median_last_feed_day:(dates[Math.floor((dates.length-1)/2)]+dates[Math.floor(dates.length/2)])/2,
    final_feed_days_27_28:counts[27]+counts[28], last_feed_by_day_among_survivors:Array.from({length:30},(_,d)=>rows.filter(a=>a.departure_day===null&&a.last_feed_day===d).length)};
}
const result = {scope:source.scope, games:source.games.length,
  definition:'Last successful feed day per placed animal, including season survivors. Termination starts the following day. This is an observed final feed, not inferred deliberate intent; a skipped day followed by feeding is not termination.',
  validation:{all_300_game_segment_feed_totals_match_exact_engine_wheat_consumption:true,all_departures_with_prior_feeding_occur_two_days_after_last_feed:true},
  summary, checks, animals};
fs.writeFileSync(path.join(root,'results/fresh/umg_lifecycles/feed_termination.json'),JSON.stringify(result,null,2));
let md='# UMG feed termination dates\n\n30 verified full replays of submission 56266758. Zero-based days. Each animal contributes once, including animals still alive at season end. Percentages count animals, not games.\n\nThe last-feed date is its final successful wheat feeding. Maintenance termination begins the following day; isolated skipped days followed by more feeding do not count. These dates do not establish intent for individual early losses.\n\n| Last successful feed day | Cows (228) | Sheep (192) | Geese (116) |\n|---|---:|---:|---:|\n';
for(let d=0;d<30;d++)if(species.some(s=>summary[s].last_feed_by_day[d]))md+=`| ${d} | ${species.map(s=>`${summary[s].last_feed_by_day[d]} (${(100*summary[s].last_feed_by_day[d]/summary[s].animals).toFixed(1)}%)`).join(' | ')} |\n`;
md+=`| Never fed | ${species.map(s=>summary[s].never_fed).join(' | ')} |\n\nAll 300 game × three-day-period feed totals reconcile to successful wheat consumption in the previous exact-engine audit. Midnight feed resets are handled through the post-refresh consecutive-unfed counter. Every animal departure with prior feeding occurs two days after its last feed.\n\nReproduce: \`node scripts/report_umg_feed_termination.mjs\`. Individual histories and daily distributions: \`results/fresh/umg_lifecycles/feed_termination.json\`.\n`;
fs.writeFileSync(path.join(root,'docs/umg_feed_termination.md'),md);
console.log(md);
