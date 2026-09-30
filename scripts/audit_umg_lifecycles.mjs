// Descriptive lifecycle audit of the 30 previously verified UMG full replays.
// Read native transitions, distinguish successful placements from market requests.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import zlib from 'node:zlib';

const root = path.resolve(import.meta.dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const hash = raw => crypto.createHash('sha256').update(raw).digest('hex');
const inc = (o, k, n = 1) => { o[k] = (o[k] || 0) + n; };
const mean = x => x.length ? x.reduce((a, b) => a + b, 0) / x.length : null;
const crops = ['MELON', 'STRAWBERRY', 'TOMATO'];
const species = ['COW', 'SHEEP', 'GOOSE'];
const identity = tile => tile?.crop ? `${tile.crop}:${tile.planted_day}` : null;
const agents = read('results/fresh/leader_segments/episode_agents.json')['56266758'];
const games = [], cohorts = [], births = [], exits = [], animalDays = [], plantChecks = [];

for (const metadata of agents) {
  const seat = metadata.agents.find(a => a.sub === 56266758).idx;
  const relative = `data/leaders_20260917/episode-${metadata.id}-replay.json`;
  if (!fs.existsSync(path.join(root, relative))) continue;
  const bytes = fs.readFileSync(path.join(root, relative));
  const raw = JSON.parse(bytes);
  const ledger = read(`results/fresh/leader_segments/segments-${metadata.id}.json`);
  assert.equal(hash(bytes), ledger.replay_sha256);
  assert.equal(raw.steps.length, 720);
  const active = new Map(), planted = {};
  for (let t = 0; t < 719; t++) {
    const day = Math.floor(t / 24), hour = t % 24;
    const pre = raw.steps[t][seat].observation;
    const post = raw.steps[t + 1][seat].observation;
    const farm = pre.farms[seat], next = post.farms[seat];
    const action = raw.steps[t + 1][seat].action || {};
    const commands = [action.farmer || [], ...(action.hands || [])];
    const positions = [farm.farmer, ...farm.hands];
    const tileCommands = new Map();
    for (let u = 0; u < Math.min(commands.length, positions.length); u++) {
      const [x, y] = positions[u];
      const index = y * 10 + x;
      if (!tileCommands.has(index)) tileCommands.set(index, []);
      tileCommands.get(index).push(commands[u]);
    }
    for (let y = 0; y < 10; y++) for (let x = 0; x < 10; x++) {
      const index = y * 10 + x, before = farm.tiles[y][x], after = next.tiles[y][x];
      const ops = (tileCommands.get(index) || []).map(c => c[0]);
      const cohort = active.get(index);
      if (cohort && identity(before) === identity(after)) {
        if (!before.watered_today && (after.watered_today || (hour === 23 && after.consecutive_unwatered === 0)) && ops.includes('WATER')) cohort.water_days.push(day);
        if (ops.includes('FERTILIZE') && before.fertilized_until_day !== after.fertilized_until_day) cohort.fertilizer_ages.push(day - before.planted_day);
        if (ops.includes('HARVEST') && before.yield_units > 0 && after.yield_units < before.yield_units) cohort.harvest_days.push(day);
      }
      if (before?.crop && identity(before) !== identity(after)) {
        assert(cohort, `missing cohort ${metadata.id} ${t} ${index}`);
        let cause = 'other';
        if (ops.includes('DIG')) cause = 'DIG';
        else if (ops.includes('HARVEST') && !after && before.crop === 'MELON') cause = 'HARVEST';
        else if (after?.kind === 'WEED') {
          cause = hour === 23 && !before.watered_today && before.consecutive_unwatered >= 1 && !ops.includes('WATER') ? 'DRY' : 'EXPIRED';
        } else if (ops.includes('HARVEST') && !after) cause = 'HARVEST';
        Object.assign(cohort, {end_day: day, end_step: t, end_age: day - before.planted_day, cause, held_yield_before_end: before.yield_units});
        if (ops.includes('HARVEST') && before.yield_units > 0) cohort.harvest_days.push(day);
        active.delete(index);
      }
      if (after?.crop && identity(before) !== identity(after)) {
        const c = {episode: metadata.id, crop: after.crop, planted_day: after.planted_day,
          tile: [x, y], water_days: [], fertilizer_ages: [], harvest_days: []};
        active.set(index, c); cohorts.push(c); inc(planted, after.crop);
        assert(ops.includes('PLANT'));
      }
      if (after?.animal && (before?.animal !== after.animal || before?.placed_day !== after.placed_day)) {
        assert(ops.includes('PLACE'));
        births.push({episode: metadata.id, day, animal: after.animal, shops: pre.town.unlocked_shops});
      }
      if (before?.animal && (before.animal !== after?.animal || before.placed_day !== after?.placed_day)) {
        exits.push({episode: metadata.id, day, animal: before.animal, age: day - before.placed_day, unfed_before: before.consecutive_unfed});
      }
      // End-of-day flags identify care/feed coverage, including hour-23 service.
      if ((hour === 23 || t === 718) && before?.animal) {
        const feedAtBoundary = hour === 23 && ops.includes('FEED') && after?.animal === before.animal && after.consecutive_unfed === 0;
        animalDays.push({episode: metadata.id, day, animal: before.animal,
          fed: !!before.fed_today || !!feedAtBoundary || (t === 718 && !!after?.fed_today),
          cared: !!before.cared_today || ops.includes('CARE'),
          shops: pre.town.unlocked_shops});
      }
    }
  }
  for (const c of active.values()) Object.assign(c, {end_day: null, cause: 'STANDING_AT_END'});
  for (const c of [...crops, 'WHEAT', 'CARROT']) {
    const expected = ledger.seats[seat].segments.reduce((n, s) => n + (s.physical[`planted:${c}`] || 0), 0);
    plantChecks.push({episode: metadata.id, crop: c, observed: planted[c] || 0, ledger: expected});
    if (crops.includes(c)) assert.equal(planted[c] || 0, expected, `plant ledger ${metadata.id} ${c}`);
  }
  games.push({episode: metadata.id, seat, sha256: ledger.replay_sha256});
}
assert.equal(games.length, 30);

const cropSummary = Object.fromEntries(crops.map(crop => {
  const rows = cohorts.filter(c => c.crop === crop), planting = {}, ending = {}, ages = {}, causes = {}, fert = {}, replacement = {};
  for (const c of rows) {
    inc(planting, c.planted_day); inc(causes, c.cause);
    for (const a of c.fertilizer_ages) inc(fert, a);
    if (c.end_day !== null) {inc(ending, c.end_day); inc(ages, `${c.cause}:${c.end_age}`);}
    const successor = cohorts.filter(q => q.episode === c.episode && q.tile[0] === c.tile[0] && q.tile[1] === c.tile[1] && q.planted_day > c.planted_day).sort((a, b) => a.planted_day - b.planted_day)[0];
    if (successor) inc(replacement, successor.crop);
  }
  return [crop, {cohorts: rows.length, planting_by_day: planting, retirement_by_day: ending, retirement_cause: causes,
    retirement_age_by_cause: ages, fertilizer_by_age: fert, next_crop_on_tile: replacement,
    mean_water_visits: mean(rows.map(c => c.water_days.length)),
    mean_harvest_visits: mean(rows.map(c => c.harvest_days.length))}];
}));
const animalSummary = Object.fromEntries(species.map(animal => {
  const rows = births.filter(b => b.animal === animal), byDay = {}, exitDay = {}, service = [];
  for (const r of rows) inc(byDay, r.day);
  for (const r of exits.filter(e => e.animal === animal)) inc(exitDay, r.day);
  for (let day = 0; day < 30; day++) {
    const a = animalDays.filter(r => r.day === day && r.animal === animal);
    service.push({day, animal_days: a.length, feed_fraction: mean(a.map(r => Number(r.fed))), care_fraction: mean(a.map(r => Number(r.cared)))});
  }
  return [animal, {placed_by_day: byDay, latest_placement: Math.max(...rows.map(r => r.day)),
    games_adding_from_day15: new Set(rows.filter(r => r.day >= 15).map(r => r.episode)).size,
    games_adding_from_day18: new Set(rows.filter(r => r.day >= 18).map(r => r.episode)).size,
    games_adding_from_day21: new Set(rows.filter(r => r.day >= 21).map(r => r.episode)).size,
    exits_by_day: exitDay, service}];
}));

// Broader check: requests in all 584 compact tapes, explicitly not execution.
const requested = Object.fromEntries(species.map(s => [s, {by_day: {}, games_from_day18: 0, games_from_day21: 0}]));
let compactCount = 0;
for (const sub of ['56266758', '56266899']) for (const file of fs.readdirSync(path.join(root, 'data/mg_tapes', sub)).filter(f => f.endsWith('.json.gz'))) {
  const tape = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root, 'data/mg_tapes', sub, file))));
  const late18 = new Set(), late21 = new Set();
  tape.actions.forEach((action, t) => {
    for (const order of action?.market || []) if (order[0] === 'BUY_ANIMAL' && requested[order[1]]) {
      const day = Math.floor(t / 24);
      inc(requested[order[1]].by_day, day, order[2] ?? 1);
      if (day >= 18) late18.add(order[1]);
      if (day >= 21) late21.add(order[1]);
    }
  });
  for (const s of late18) requested[s].games_from_day18++;
  for (const s of late21) requested[s].games_from_day21++;
  compactCount++;
}
assert.equal(compactCount, 584);
const result = {scope: 'Historical UMG tape policy: 30 full replays of 56266758; broader requests from 584 compact tapes of 56266758/56266899.',
  timing: 'Zero-based action days; births/retirements occur during the named day, not next-day snapshots.',
  validation: 'Raw SHA256 equals previous exact-replay ledger; observed successful plant totals equal verified ledger for all three long-term crops in every game. Short-crop snapshot discrepancies are listed separately.',
  limitations: ['30-game lifecycle sample is not all UMG versions.', 'Care flags describe servicing, not profitable optimality.', 'Harvest-visit counts can omit a midnight harvest if new production masks the held-yield decrease.', 'Compact market orders are requested purchases, not successful additions.'],
  crop_summary: cropSummary, animal_summary: animalSummary, compact_requests: requested, compact_games: compactCount,
  plant_checks: plantChecks, games, cohorts, animal_births: births, animal_exits: exits};
const out = path.join(root, 'results/fresh/umg_lifecycles');
fs.mkdirSync(out, {recursive: true});
fs.writeFileSync(path.join(out, 'audit.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify({crop_summary: cropSummary, animal_summary: animalSummary, compact_requests: requested}, null, 2));
