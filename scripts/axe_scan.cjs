/* WCAG 2.0/2.1 A and AA scan (axe-core) of the sign-in page and every workspace page at desktop and phone width.
   Run against a LOCAL app only: it creates a throwaway account.
     1. start the API (see README) and `npm run dev --prefix web`
     2. node scripts/axe_scan.cjs [http://127.0.0.1:5173]
   Needs Microsoft Edge or set SAFELEDGER_BROWSER_CHANNEL=chrome. Prints one line per view; exits 1 if any violation is found. */
const path=require('node:path');
const web=p=>require(path.resolve(__dirname,'../web/node_modules',p));
const {chromium}=web('playwright');const AxeBuilder=web('@axe-core/playwright').default;
const base=(process.argv[2]||'http://127.0.0.1:5173').replace(/\/$/,'');
const user='axe_'+Date.now().toString(36),password='Axe-'+require('node:crypto').randomBytes(9).toString('base64url')+'-9';
const tabs=['Overview','Add records','Invoices','Cash flow','Loans','Assistant','Approvals','Activity','Settings'];
(async()=>{
  const browser=await chromium.launch({channel:process.env.SAFELEDGER_BROWSER_CHANNEL||'msedge',headless:true});
  let bad=0;
  const scan=async(page,name)=>{const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();bad+=r.violations.length;console.log(r.violations.length?'FAIL':'ok  ',name,r.violations.map(v=>v.id+'x'+v.nodes.length).join(' '));};
  for(const [w,h,label] of [[1366,900,'desktop'],[390,844,'phone']]){
    const ctx=await browser.newContext({viewport:{width:w,height:h},locale:'en-US'});const page=await ctx.newPage();
    await page.goto(base);await page.waitForTimeout(2500);
    await page.mouse.wheel(0,6000);await page.waitForTimeout(1500);await page.mouse.wheel(0,-6000);await page.waitForTimeout(800);  // let scroll-in animations finish
    await scan(page,label+' sign-in');
    await page.getByPlaceholder('letters, numbers, underscore').fill(user+label[0]);await page.locator('input[type=password]').first().fill(password);
    await page.getByRole('button',{name:'Create my workspace',exact:true}).click();
    await page.getByRole('button',{name:'I saved it'}).waitFor({state:'attached',timeout:30000});await page.waitForTimeout(1500);
    for(const name of ['Skip tour','I saved it']){const b=page.getByRole('button',{name,exact:true});if(await b.count())await b.first().click().catch(()=>{});await page.waitForTimeout(500);}
    await page.getByRole('button',{name:'Try a sample business'}).click();await page.waitForTimeout(3500);
    for(const t of tabs){
      const nav=w>700?page.getByRole('navigation').getByRole('button',{name:t,exact:true}).first():page.getByRole('button',{name:t,exact:true}).last();
      await nav.click();await page.waitForTimeout(1200);
      const close=page.getByRole('button',{name:'×',exact:true});if(await close.count())await close.first().click().catch(()=>{});
      await scan(page,label+' '+t);
    }
    await ctx.close();
  }
  await browser.close();process.exit(bad?1:0);
})().catch(e=>{console.error(e);process.exit(2);});
