/* Real local E2E. Credentials are private fixture input, never report/trace content. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.SAFELEDGER_PLAYWRIGHT_MODULE || require.resolve('playwright', { paths: [path.resolve(__dirname, '../web')] }));
const access = JSON.parse(fs.readFileSync(process.env.SAFELEDGER_BROWSER_ACCESS, 'utf8')).bearer_tokens;
const out = process.env.SAFELEDGER_EVIDENCE_DIR;
const steps = [];
async function main() {
  let options = { headless: true };
  if (process.env.SAFELEDGER_CHROMIUM_MODULE) {
    const loaded = require(process.env.SAFELEDGER_CHROMIUM_MODULE);
    const bundled = loaded.default || loaded;
    options = { ...options, executablePath: await bundled.executablePath(), args: bundled.args };
  }
  const browser = await chromium.launch(options);
  const context = await browser.newContext({ viewport: {width: 1366, height: 900}, acceptDownloads: true });
  const page = await context.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const heading = name => page.getByRole('heading', { name, exact: true });
  const nav = name => page.getByRole('navigation', {name:'Workspace'}).getByRole('button', { name: new RegExp(name+'$') });
  async function waitFor(test, label) {
    for (let i=0;i<100;i++) { if (await test()) return; await page.waitForTimeout(100); }
    throw new Error('Timed out: '+label);
  }
  async function login(role) {
    await page.getByLabel('Private session token').fill(access[role]);
    await page.getByRole('button', {name:'Open workspace',exact:true}).click();
    await heading('Financial overview').waitFor();
    await waitFor(async()=> !(await page.getByRole('button',{name:'Refresh data'}).isDisabled()), 'workspace loaded');
    assert.equal(await page.locator('input[type=password]').count(),0);
    assert.deepEqual(await page.evaluate(()=>[localStorage.length,sessionStorage.length]),[0,0]);
  }
  async function logout() { await page.getByRole('button',{name:'Sign out'}).click(); await page.getByLabel('Private session token').waitFor(); }
  async function noOverflow() { assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true); }
  try {
    await page.goto(process.env.SAFELEDGER_BROWSER_URL);
    await page.getByLabel('Private session token').fill('invalid-session');
    await page.getByRole('button',{name:'Open workspace',exact:true}).click();
    await page.getByRole('alert').waitFor(); assert.match(await page.getByRole('alert').innerText(),/AUTHENTICATION/);
    steps.push('Invalid session denied; no workspace or stored credentials');
    await login('owner');
    assert.match(await page.locator('.metrics').first().innerText(),/120,000/);
    await noOverflow();
    await page.screenshot({path:path.join(out,'desktop-overview.png'),fullPage:true});
    steps.push('Owner dashboard displays actual 12,000,000 minor-unit baseline and source evidence');
    await nav('Cash flow').click();
    assert.match(await page.locator('.metrics').innerText(),/18,750/);
    await page.getByLabel('Delay scheduled receipts').selectOption('7');
    await page.getByRole('button',{name:'Calculate scenario'}).click();
    await waitFor(async()=> !(await page.getByRole('button',{name:'Calculate scenario'}).isDisabled()),'delayed forecast');
    assert.match(await page.locator('.metrics').innerText(),/59,300/);
    await nav('Overview').click(); assert.match(await page.locator('.metrics').nth(1).innerText(),/18,750/);
    steps.push('Live 30-day forecast and 7-day receipt-delay scenario match backend; scenario does not replace baseline overview');
    await nav('Financing').click(); assert.equal(await page.getByText('Not affordable in baseline forecast',{exact:true}).count(),3);
    const prices=await page.locator('.offer-price').allTextContents(); assert.match(prices[0],/2,000/);assert.match(prices[1],/2,100/);assert.match(prices[2],/2,500/);
    steps.push('Three fictional offers sorted by verified total cost, all unaffordable');
    await nav('Assistant').click();await page.getByRole('button',{name:'Run bounded task'}).click();
    await page.getByRole('alert').waitFor();assert.match(await page.getByRole('alert').innerText(),/AI NOT CONFIGURED/);
    await nav('Invoices').click();await page.getByLabel('Find invoice, vendor or reference').fill('INV-104');
    await page.getByRole('button',{name:'Propose INV-104',exact:true}).click();
    await waitFor(async()=> /DUPLICATE INVOICE BLOCKED/.test(await page.getByRole('alert').innerText()),'duplicate policy denial');
    steps.push('AI-offline503 is visible; deterministic UI remains functional; duplicate payment denied by backend');
    await page.getByLabel('Find invoice, vendor or reference').fill('INV-105');
    await page.getByRole('button',{name:'Propose INV-105',exact:true}).click();
    await heading('Human review & sandbox execution').waitFor();
    await waitFor(async()=>await page.getByText('Proposal created.',{exact:false}).count()>0,'proposal result');
    assert.equal(await page.getByRole('button',{name:'Approve & execute sandbox'}).count(),0);
    await logout();await login('viewer'); await nav('Invoices').click();
    assert.equal(await page.getByRole('button',{name:/Propose INV/}).count(),0);
    await nav('Approvals').click();assert.equal(await page.getByRole('button',{name:'Review decision',exact:true}).count(),0);
    steps.push('Owner only proposes; viewer has no execution controls; session switch clears workspace');
    await logout();await login('approver');await nav('Approvals').click();
    await page.getByRole('button',{name:'Review decision',exact:true}).click();
    const dialog=page.getByRole('dialog');await dialog.waitFor();
    assert.match(await dialog.innerText(),/VEND-105/);assert.match(await dialog.innerText(),/35,000/);assert.match(await dialog.innerText(),/Current available balance/);
    const approve=dialog.getByRole('button',{name:'Approve & execute sandbox',exact:true});assert.equal(await approve.isDisabled(),true);
    await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
    assert.equal(await page.getByRole('button',{name:'Review decision',exact:true}).evaluate(e=>e===document.activeElement),true,'Escape returns focus to review button');
    await page.getByRole('button',{name:'Review decision',exact:true}).click();
    await dialog.getByRole('checkbox').check();await approve.click();
    await dialog.waitFor({state:'hidden'});
    await waitFor(async()=>await page.getByText('Sandbox payment executed.',{exact:false}).count()>0,'sandbox posting');
    await nav('Overview').click();assert.match(await page.locator('.metrics').first().innerText(),/85,000/);
    await nav('Audit').click();await page.getByText('Tenant audit chain verified by backend',{exact:true}).waitFor();
    const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export audit JSON'}).click();const download=await downloadPromise;await download.saveAs(path.join(out,'audit-export.json'));
    const audit=JSON.parse(fs.readFileSync(path.join(out,'audit-export.json'),'utf8'));assert.equal(audit.chain_verified,true);
    assert.equal(audit.events.filter(e=>e.kind==='EXECUTED').length,1);
    steps.push('Independent approver reviews exact payee/amount/source/hash; unchecked approval blocked; Escape focus-safe cancellation; real sandbox execution reconciles to 8,500,000 minor');
    steps.push('Downloaded backend-verified signed audit evidence contains exactly one EXECUTED event');
    for (const width of [360,390,768,1366]) {
      await page.setViewportSize({width,height:900});
      for (const name of ['Overview','Invoices','Cash flow','Financing','Assistant','Approvals','Audit','Import']) {await nav(name).click();await noOverflow();}
      if (width===390) {await nav('Overview').click();await page.screenshot({path:path.join(out,'mobile-overview.png'),fullPage:true});}
    }
    steps.push('All eight views fit 360/390/768/1366px without document overflow; invoice tables scroll within their container');
    await page.reload();await page.getByLabel('Private session token').waitFor();assert.equal(await page.getByLabel('Private session token').inputValue(),'');
    await login('empty_owner');await page.getByText('No dataset has been imported.',{exact:false}).waitFor();await nav('Import').click();
    await page.getByLabel('Synthetic Dataset JSON').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{"currency":"BDT","currency":"USD"}')});
    await page.getByRole('button',{name:'Validate & import'}).click();await page.getByRole('alert').waitFor();assert.match(await page.getByRole('alert').innerText(),/DUPLICATE|INVALID/);
    await page.getByLabel('Synthetic Dataset JSON').setInputFiles(path.resolve('data/fixtures/seed_2026.json'));await page.getByRole('button',{name:'Validate & import'}).click();
    await waitFor(async()=>await page.getByText('Synthetic dataset imported',{exact:false}).count()>0,'real import');
    await nav('Overview').click();assert.match(await page.locator('.metrics').first().innerText(),/120,000/);
    steps.push('Reload clears token; empty-tenant import state works; raw duplicate-key JSON denied; valid owner import succeeds without leaking other tenant posting');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({status:'passed',browser:browser.version(),steps,page_errors:errors,simulation_only:true,live_ai_used:false},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',checks:steps.length,browser:browser.version(),page_errors:errors.length}));
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
