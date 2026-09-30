const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/xyygl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  try{
    const page=await browser.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js',route=>route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.resolve(__dirname,'../results/fresh/tile_transition_timing/d3-7.9.0.min.js'),'utf8')}));
    const html=fs.readFileSync(process.argv[2],'utf8');
    await page.setContent('<style>:root{--foreground:#e8ede9;--muted-foreground:#abb5ae;--muted:#25342b;--border:#44544a;--viz-series-1:#82caa7}body{background:#111a15;font:14px system-ui;padding:16px}.text-small{font-size:12px}h2,h3{font-weight:500}</style>'+html);
    await page.waitForSelector('rect.cell');
    for(const width of [1024,736,320]){
      await page.setViewportSize({width,height:900});await page.waitForTimeout(100);
      const check=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,cells:document.querySelectorAll('rect.cell').length,svgs:document.querySelectorAll('.timing-chart').length,cutoff:[...document.querySelectorAll('svg text')].some(el=>{const a=el.getBoundingClientRect(),b=el.closest('svg').getBoundingClientRect();return a.left<b.left-1||a.right>b.right+1;})}));
      assert.equal(check.overflow,false);assert.equal(check.cutoff,false);assert.equal(check.cells,540);assert.equal(check.svgs,2);console.log(JSON.stringify({width,...check}));
    }
    assert.match(await page.locator('rect.cell').first().getAttribute('data-tooltip'),/DSM.*day 0/);
    assert.deepEqual(errors,[]);
    await page.setViewportSize({width:1024,height:650});await page.waitForTimeout(100);
    await page.screenshot({path:path.resolve(__dirname,'../viz/tile-transition-timing-preview.png'),fullPage:true});
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
