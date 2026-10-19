/* Real browser screencast. Capture starts only after login and stops before account changes. */
const fs=require('node:fs'),fsp=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const {chromium}=require(require.resolve('playwright',{paths:[path.resolve(__dirname,'../web')]}));
const tokens=JSON.parse(fs.readFileSync(process.env.SAFELEDGER_BROWSER_ACCESS,'utf8')).bearer_tokens;
const out=process.env.SAFELEDGER_EVIDENCE_DIR;
const destination=process.env.SAFELEDGER_DEMO_OUTPUT;
if(!destination||!path.isAbsolute(destination))throw new Error('Set an absolute private demo output path.');
async function main(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'safeledger-video-private-'));const frames=[],captions=[];let offset=0,start=0,pending=[],browser;
 try{
  const options={headless:true};if(process.env.SAFELEDGER_CHROMIUM_EXECUTABLE)options.executablePath=process.env.SAFELEDGER_CHROMIUM_EXECUTABLE;
  browser=await chromium.launch(options);const context=await browser.newContext({viewport:{width:1366,height:900}});const page=await context.newPage();const cdp=await context.newCDPSession(page);
  const button=name=>page.getByRole('button',{name,exact:true});const nav=name=>page.getByRole('navigation',{name:'Workspace'}).getByRole('button',{name:new RegExp(name+'$')});
  async function settled(){for(let i=0;i<100;i++){if(!await button('Refresh data').isDisabled())return;await page.waitForTimeout(100);}throw new Error('Workspace loading timeout');}
  async function login(role){await page.getByLabel('Private session token').fill(tokens[role]);await button('Open workspace').click();await page.getByRole('heading',{name:'Financial overview',exact:true}).waitFor();await settled();}
  cdp.on('Page.screencastFrame',event=>{const frame={file:path.join(temp,`${String(frames.length).padStart(6,'0')}.jpg`),time:offset+(Date.now()-start)/1000};frames.push(frame);pending.push(fsp.writeFile(frame.file,Buffer.from(event.data,'base64')));void cdp.send('Page.screencastFrameAck',{sessionId:event.sessionId});});
  async function record(){assert.equal(await page.getByLabel('Private session token').count(),0);start=Date.now();await cdp.send('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1366,maxHeight:900,everyNthFrame:1});}
  async function pause(){await cdp.send('Page.stopScreencast');offset+=(Date.now()-start)/1000;await Promise.all(pending);pending=[];}
  async function scene(text,action,seconds=7){const from=offset+(Date.now()-start)/1000;await action();await page.waitForTimeout(seconds*1000);captions.push({start:from,end:offset+(Date.now()-start)/1000,text});}
  await page.goto(process.env.SAFELEDGER_BROWSER_URL);await login('owner');await record();
  await scene('Capzoryx Copilot:actual local prototype. Synthetic BDT data and sandbox only. No real money moves.',async()=>{},7);
  await scene('Cleared balance:BDT 120,000. The backend preserves source IDs and uses exact integer minor units.',async()=>{assert.match(await page.locator('.metrics').first().innerText(),/120,000/);await page.getByText('Source evidence · 3 records',{exact:true}).click();},8);
  await scene('Deterministic 30-day outlook:BDT -18,750. Upcoming obligations reveal a reserve shortage.',async()=>{await nav('Cash flow').click();assert.match(await page.locator('.metrics').innerText(),/18,750/);},8);
  await scene('What-if:delay scheduled receipts by 7 days. The lowest projected balance falls to BDT -59,300.',async()=>{await page.getByLabel('Delay scheduled receipts').selectOption('7');await button('Calculate scenario').click();await settled();assert.match(await page.locator('.metrics').innerText(),/59,300/);},8);
  await scene('Fictional financing only. Total costs rank BDT 2,000 /2,100 /2,500. All fail baseline affordability.',async()=>{await nav('Financing').click();assert.equal(await page.getByText('Not affordable in baseline forecast',{exact:true}).count(),3);},8);
  await scene('Real LLM is not configured at this checkpoint. AI unavailability does not stop deterministic finance.',async()=>{await nav('Assistant').click();await button('Run bounded task').click();await page.getByRole('alert').waitFor();assert.match(await page.getByRole('alert').innerText(),/AI NOT CONFIGURED/);},8);
  await scene('Duplicate invoice risk:the actual backend rejects INV-104 before it can create a payment proposal.',async()=>{await nav('Invoices').click();await page.getByLabel('Find invoice, vendor or reference').fill('INV-104');await button('Review payment for INV-104').click();await page.getByRole('alert').waitFor();assert.match(await page.getByRole('alert').innerText(),/DUPLICATE INVOICE BLOCKED/);},8);
  await scene('INV-105:BDT 35,000. The owner creates a signed pending proposal. Creating it moves no funds.',async()=>{await page.getByLabel('Find invoice, vendor or reference').fill('INV-105');await button('Review payment for INV-105').click();await page.getByRole('heading',{name:'Human review & sandbox execution',exact:true}).waitFor();await settled();},9);
  await pause();await button('Sign out').click();await login('approver');await nav('Approvals').click();await record();
  await scene('A separate authenticated approver session reviews the payee,amount,source and immutable action hash.',async()=>{await button('Review decision').click();await page.getByRole('dialog').waitFor();await page.getByRole('dialog').getByText('Action hash and dataset fingerprint',{exact:true}).click();},9);
  await scene('Explicit confirmation enables approval. The backend rechecks permission,expiry,policy and funds before posting.',async()=>{const d=page.getByRole('dialog');assert.equal(await d.getByRole('button',{name:'Approve & execute sandbox',exact:true}).isDisabled(),true);await d.getByRole('checkbox').check();},7);
  await scene('One sandbox posting completes. Available cash reconciles from BDT 120,000 to BDT 85,000.',async()=>{await page.getByRole('dialog').getByRole('button',{name:'Approve & execute sandbox',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await settled();await nav('Overview').click();assert.match(await page.locator('.metrics').first().innerText(),/85,000/);},8);
  await scene('The backend verifies the audit chain. Proposal,approval and execution remain linked to one trace.',async()=>{await nav('Audit').click();await page.getByText('Tenant audit chain verified by backend',{exact:true}).waitFor();},9);
  await scene('Open release gates:live-model evaluation,public durable hosting and independent review. Repository contains actual test evidence.',async()=>{},8);
  await pause();await browser.close();browser=null;
  const concat=[];for(let i=0;i<frames.length;i++){concat.push(`file '${frames[i].file}'`);concat.push('duration '+Math.max(.02,(frames[i+1]?.time??offset)-frames[i].time).toFixed(3));}concat.push(`file '${frames.at(-1).file}'`);fs.writeFileSync(path.join(temp,'frames.txt'),concat.join('\n')+'\n');
  function timestamp(seconds){const ms=Math.round(seconds*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`;}
  const srt=captions.map((c,i)=>`${i+1}\n${timestamp(c.start)} --> ${timestamp(c.end)}\n${c.text.replace(/,(?=[A-Za-z])/g,', ')}\n`).join('\n');fs.writeFileSync(path.join(temp,'captions.srt'),srt);
  fs.mkdirSync(path.dirname(destination),{recursive:true});assert.equal(fs.existsSync(destination),false,'Do not overwrite a previous demo');
  const encode=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',path.join(temp,'frames.txt'),'-vf',`subtitles=${temp}/captions.srt:force_style='FontName=DejaVu Sans,FontSize=10,PrimaryColour=&HFFFFFF,OutlineColour=&H00363E16,BorderStyle=3,Outline=2,Alignment=8,MarginV=12'`,'-r','25','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',destination],{encoding:'utf8'});if(encode.status!==0)throw new Error('Video encode failed:'+encode.stderr);
  const probe=spawnSync('ffprobe',['-v','error','-show_entries','format=duration,size','-of','json',destination],{encoding:'utf8'});const info=JSON.parse(probe.stdout).format;assert.ok(Number(info.duration)<300);
  fs.writeFileSync(path.join(out,'demo-recording.json'),JSON.stringify({status:'passed',method:'Actual Chromium Page.startScreencast frames,paused during login/session switch,English captions burned into real-timeline recording',simulation_only:true,live_ai_used:false,narration_audio:false,scenes:captions.length,frames:frames.length,duration_seconds:Number(info.duration),size_bytes:Number(info.size),credentials_captured:false,output_filename:path.basename(destination)},null,2)+'\n');
  fs.writeFileSync(path.join(out,'demo-captions.srt'),srt);console.log(JSON.stringify({status:'passed',scenes:captions.length,duration_seconds:Number(info.duration),credentials_captured:false}));
 }finally{if(browser)await browser.close();fs.rmSync(temp,{recursive:true,force:true});}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
