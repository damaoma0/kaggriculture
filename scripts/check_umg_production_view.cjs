const fs=require('fs');
const {chromium}=require('C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const html=fs.readFileSync('C:/Users/xyygl/.codex/visualizations/2026/09/15/01a0a5c7-18b1-7141-a48f-45f175aa1a3c/umg-production-plans.html','utf8');
 const browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent(html);await page.locator('#umg-game').selectOption('1');await page.locator('#umg-day').fill('24');await page.locator('#umg-board button').nth(45).click();
 for(const width of [736,360]){await page.setViewportSize({width,height:1000});await page.waitForTimeout(100);console.log(JSON.stringify({width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),tiles:await page.locator('#umg-board button').count(),meta:await page.locator('#umg-tile').textContent()}));}
 if(errors.length)throw Error(errors.join('\n'));console.log('Interactions and script execution passed');await browser.close();
})();
