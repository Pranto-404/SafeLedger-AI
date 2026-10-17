const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const resolve=name=>require.resolve(name,{paths:[path.resolve(__dirname,'../web')]});
const {chromium}=require(process.env.SAFELEDGER_PLAYWRIGHT_MODULE||resolve('playwright'));
const {default:AxeBuilder}=require(resolve('@axe-core/playwright'));
const access=JSON.parse(fs.readFileSync(process.env.SAFELEDGER_BROWSER_ACCESS,'utf8')).bearer_tokens;
const out=process.env.SAFELEDGER_EVIDENCE_DIR,steps=[],a11y=[];
async function main(){
 let options={headless:true};
 if(process.env.SAFELEDGER_CHROMIUM_MODULE){const mod=require(process.env.SAFELEDGER_CHROMIUM_MODULE),bundled=mod.default||mod;options={...options,executablePath:await bundled.executablePath(),args:bundled.args};}
 const browser=await chromium.launch(options),context=await browser.newContext({viewport:{width:1366,height:900}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const button=name=>page.getByRole('button',{name,exact:true});
 const nav=name=>page.getByRole('navigation',{name:'Workspace'}).getByRole('button',{name:new RegExp(name+'$')});
 async function settled(){for(let i=0;i<100;i++){if(!await button('Refresh data').isDisabled())return;await page.waitForTimeout(100);}throw new Error('Workspace did not settle');}
 async function login(role){await page.getByLabel('Private session token').fill(access[role]);await button('Open workspace').click();await page.getByRole('heading',{name:'Financial overview',exact:true}).waitFor();await settled();}
 async function logout(){await button('Sign out').click();await page.getByLabel('Private session token').waitFor();}
 async function audit(){await nav('Audit').click();assert.match(await page.locator('.audit-list').innerText().catch(()=>''),/./);}
 async function scan(name){const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();a11y.push({view:name,violations:result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,failureSummary:n.failureSummary}))}))});fs.writeFileSync(path.join(out,'accessibility-results.json'),JSON.stringify({views:a11y},null,2)+'\n');}
 async function invoke(role,route,body){return page.evaluate(async({token,route,body})=>{const r=await fetch('/api'+route,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});return{status:r.status,data:await r.json()};},{token:access[role],route,body});}
 try{
  await page.goto(process.env.SAFELEDGER_BROWSER_URL);await scan('login');await login('owner');
  for(const name of ['Overview','Invoices','Cash flow','Financing','Assistant','Approvals','Audit','Import']){await nav(name).click();await scan(name);}
  // Server outage injection tests UI recovery only; financial responses are never fabricated.
  await nav('Overview').click();await page.route('**/api/dashboard',route=>route.abort('failed'));
  await button('Refresh data').click();await settled();assert.match(await page.getByRole('alert').innerText(),/Could not reach/);assert.equal(await page.getByText('BDT 120,000.00',{exact:true}).count(),0);
  await page.unroute('**/api/dashboard');await button('Refresh data').click();await settled();assert.match(await page.locator('.metrics').first().innerText(),/120,000/);
  steps.push('Network failure clears stale totals,shows retry message,and real refresh recovers');
  // Hold an old authenticated response across logout and a different tenant login.
  let release;const gate=new Promise(r=>release=r);let entered;const observed=new Promise(r=>entered=r);
  await page.route('**/api/dashboard',async route=>{entered();await gate;try{await route.continue();}catch{}});
  await button('Refresh data').click();await observed;await logout();
  await page.unroute('**/api/dashboard');await login('empty_owner');release();await page.waitForTimeout(250);
  await page.getByText('No dataset has been imported.',{exact:false}).waitFor();assert.equal(await page.getByText('BDT 120,000.00',{exact:true}).count(),0);assert.equal(await page.getByRole('heading',{name:'Financial overview',exact:true}).count(),1);
  steps.push('Logout aborts in-flight finance;new empty tenant sees no previous business totals');
  await logout();await login('approver');await nav('Approvals').click();
  const expired=page.locator('.proposal').filter({has:page.getByRole('heading',{name:/SMALL-00/})});await expired.getByRole('button',{name:'Review decision',exact:true}).click();
  let dialog=page.getByRole('dialog');await dialog.getByRole('checkbox').check();await dialog.getByRole('button',{name:'Approve & execute sandbox',exact:true}).click();
  await dialog.getByRole('alert').waitFor();assert.match(await dialog.getByRole('alert').innerText(),/PROPOSAL EXPIRED/);assert.equal((await invoke('viewer','/dashboard')).data.balance_minor,12000000);await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  steps.push('Genuinely signed expired proposal denied in actual API;modal shows failure;no balance change');
  const proposed=await invoke('owner','/proposals',{invoice_id:'INV-105'});assert.equal(proposed.status,201);
  const proposal=proposed.data;await button('Refresh data').click();await settled();
  await page.locator('.proposal').filter({has:page.getByRole('heading',{name:/INV-105/})}).getByRole('button',{name:'Review decision',exact:true}).click();dialog=page.getByRole('dialog');
  await scan('approval-dialog');await dialog.getByRole('checkbox').check();
  await page.route('**/api/proposals/*/approve',route=>{const body=route.request().postDataJSON();return route.continue({postData:JSON.stringify({...body,proposal_hash:'0'.repeat(64)})});});
  await dialog.getByRole('button',{name:'Approve & execute sandbox',exact:true}).click();await dialog.getByRole('alert').waitFor();assert.match(await dialog.getByRole('alert').innerText(),/APPROVAL HASH MISMATCH/);
  assert.equal((await invoke('viewer','/dashboard')).data.balance_minor,12000000);await page.unroute('**/api/proposals/*/approve');
  // Tab focus stays in the native modal in both directions.
  for(let i=0;i<10;i++){await page.keyboard.press('Tab');assert.equal(await dialog.evaluate(e=>e.contains(document.activeElement)),true,'Keyboard focus remains within approval modal');}
  for(let i=0;i<10;i++){await page.keyboard.press('Shift+Tab');assert.equal(await dialog.evaluate(e=>e.contains(document.activeElement)),true,'Keyboard focus remains within approval modal');}
  await dialog.getByRole('button',{name:'Reject proposal',exact:true}).click();await dialog.waitFor({state:'hidden'});
  const rejected=await invoke('approver',`/proposals/${proposal.proposal_id}/approve`,{proposal_hash:proposal.action_hash,decision:'approve'});assert.equal(rejected.status,409);assert.equal((await invoke('viewer','/dashboard')).data.balance_minor,12000000);
  steps.push('Tampered approval hash rejected server-side;modal traps Tab/Shift+Tab;human rejection final and cannot be replayed as approval');
  // UI removal isn't the permission boundary: exercise direct browser fetch as a viewer/other business.
  assert.equal((await invoke('viewer','/proposals',{invoice_id:'INV-105'})).status,403);
  assert.equal((await invoke('empty_owner',`/proposals/${proposal.proposal_id}`)).status,404);
  assert.equal((await invoke('empty_owner',`/audit/${proposal.proposal_id}`)).status,404);
  const log=(await invoke('viewer','/audit')).data;assert.equal(log.chain_verified,true);assert.equal(log.events.filter(e=>e.kind==='EXECUTED').length,0);
  steps.push('Direct browser role/tenant bypass attempts denied and signed audit proves zero executions');
  await logout();await login('memo_owner');await nav('Invoices').click();await page.getByLabel('Find invoice, vendor or reference').fill('INV-105');await page.getByText('Untrusted memo',{exact:true}).click();
  assert.match(await page.locator('tbody').innerText(),/<img src=x onerror/);assert.equal(await page.locator('tbody img,tbody script').count(),0);assert.equal(await page.evaluate(()=>window.memoExecuted),undefined);
  assert.equal((await invoke('memo_viewer','/audit')).data.events.filter(e=>e.kind==='EXECUTED').length,0);
  steps.push('Actual stored HTML/prompt-injection memo is escaped inert text;no script,no execution');
  // Browser session expiry: real invalid bearer token,not a mocked401 response.
  await page.route('**/api/dashboard',route=>route.continue({headers:{...route.request().headers(),authorization:'Bearer invalid-expired-session'}}));
  await button('Refresh data').click();await page.getByLabel('Private session token').waitFor();await page.unroute('**/api/dashboard');assert.equal(await page.getByLabel('Private session token').inputValue(),'');
  assert.deepEqual(await page.evaluate(()=>[localStorage.length,sessionStorage.length]),[0,0]);
  steps.push('Real server401 clears active workspace/token;no persistent credentials');
  fs.writeFileSync(path.join(out,'accessibility-results.json'),JSON.stringify({tool:'axe-core/playwright',scope:'WCAG2A/AA and2.1A/AA automated subset;not conformance certification',views:a11y},null,2)+'\n');
  const violationCount=a11y.reduce((n,r)=>n+r.violations.length,0);assert.equal(violationCount,0,'Automated accessibility violations;see accessibility-results.json');
  assert.deepEqual(errors,[]);steps.push('Automated axe scans of login,eightviews,approvaldialog report zero WCAG2/2.1A/AA violations');
  fs.writeFileSync(path.join(out,'qa-results.json'),JSON.stringify({status:'passed',browser:browser.version(),steps,page_errors:errors,accessibility_scans:a11y.length,violation_count:violationCount,live_ai_used:false,financial_denials_from_real_api:true,network_abort_injected:true},null,2)+'\n');console.log(JSON.stringify({status:'passed',scenarios:steps.length,accessibility_scans:a11y.length,page_errors:errors.length}));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
