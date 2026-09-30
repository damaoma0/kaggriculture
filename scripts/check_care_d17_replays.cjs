const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1360,height:1100}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(__dirname,'../viz/tape-109740300-before-after-d17.html')).href);
  await page.locator('#viewer').waitFor({state:'visible'});
  assert.match(await page.locator('header').innerText(),/day 17 only/);
  assert.equal(await page.locator('#board button').count(),100);
  assert.equal(await page.locator('#game option').count(),2);
  await page.locator('#d17').click();
  assert.match(await page.locator('#clock').innerText(),/Day 17.*turn 409/);
  assert.match(await page.locator('#compareBody').innerText(),/CARE/);
  assert.match(await page.locator('#compareBody').innerText(),/PICKUP WHEAT 2/);
  await page.locator('#seek').fill('413');
  await page.locator('#game').selectOption('1');
  assert.match(await page.locator('#tileDetail').innerText(),/cared today: true/);
  await page.locator('#game').selectOption('0');
  assert.match(await page.locator('#tileDetail').innerText(),/cared today: false/);
  await page.locator('#end').click();
  assert.equal(await page.locator('#cash').innerText(),'87,878');
  assert.equal(await page.locator('#lead').innerText(),'-10,424');
  await page.locator('#game').selectOption('1');
  assert.equal(await page.locator('#cash').innerText(),'88,107');
  assert.equal(await page.locator('#lead').innerText(),'-10,187');
  const rows=await page.locator('#compareBody tr').allTextContents();
  assert(rows.some(x=>x==='Wool harvested9091'));
  assert(rows.some(x=>x==='Milk harvested116115'));
  await page.locator('#both').click();
  await page.evaluate(()=>{cur=719;tick();});
  assert.equal(await page.locator('#game').inputValue(),'1');
  await page.evaluate(()=>{cur=719;tick();});
  assert.equal(await page.locator('#status').innerText(),'Playback complete · After');
  for(const width of [1360,736,390,320]){
    await page.setViewportSize({width,height:1100});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }
  assert.deepEqual(errors,[]);
  console.log('Passed: day-17-only replay loads, both cash totals and care states match, back-to-back playback and responsive layout work.');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
