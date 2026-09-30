const fs = require('fs');
const assert = require('assert');
const {chromium} = require('C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless:true, channel:'msedge'});
  const page = await browser.newPage({viewport:{width:736,height:1000}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('file:///C:/Users/xyygl/Documents/kaggriculture/results/fresh/production_continuation/shop_changes_preview.html');
  const f = page.frameLocator('iframe');
  await f.locator('#usc-overview button').first().waitFor();
  assert.equal(await f.locator('#usc-overview button').count(),76);
  const initial = await f.locator('#usc-selection').innerText();
  assert(initial.includes('+14…+24'));
  assert(initial.includes('median +17'));
  await f.locator('[data-key="YARN_STORE|24|WOOL"]').click();
  assert((await f.locator('#usc-selection').innerText()).includes('Yarn Store · day 24 · Wool'));
  await f.locator('summary').click();
  assert.equal(await f.locator('#usc-pairs tr').count(),4);
  assert.equal(await f.locator('#usc-products tr').count(),9);
  const checks = [];
  for (const width of [736,360]) {
    await page.setViewportSize({width,height:1000});
    await page.waitForTimeout(150);
    const overflow = await f.locator('#umg-shop-change-view').evaluate(() => document.documentElement.scrollWidth > innerWidth);
    assert(!overflow);
    checks.push({width,overflow});
  }
  await f.locator('#umg-shop-change-view').evaluate(() => window.dispatchEvent(new CustomEvent('openai:set_globals',{detail:{globals:{widgetState:{modelContent:{shop:'FARMERS_MARKET',day:18,product:'STRAWBERRY'}}}}})));
  assert((await f.locator('#usc-selection').innerText()).includes('+14…+24'));
  await f.locator('summary').click();
  await page.setViewportSize({width:736,height:1050});
  await page.screenshot({path:'results/fresh/production_continuation/shop_changes_check.png'});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({initial,checks,buttons:76,errors}));
  await browser.close();
})().catch(e => {console.error(e);process.exit(1);});
