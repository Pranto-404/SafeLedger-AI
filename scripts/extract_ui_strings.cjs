/* Collects every phrase passed to t() or T() in the web app into api/app/ui_strings.json, the fixed list the server may translate.
   Run without arguments to update the file; with --check (used in CI) to fail when it is out of date. */
const fs=require('node:fs'),path=require('node:path');
const src=path.join(__dirname,'..','web','src'),out=path.join(__dirname,'..','api','app','ui_strings.json');
const found=new Set();
const call=/\b[tT]\(\s*(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)")/g;
const unescape=s=>s.replace(/\\(['"\\])/g,'$1').replace(/\\n/g,'\n');
for(const f of fs.readdirSync(src)){
  if(!/\.tsx?$/.test(f)||f==='localModel.ts'||f==='i18n.tsx')continue;
  const text=fs.readFileSync(path.join(src,f),'utf8');
  for(const m of text.matchAll(call)){const v=unescape(m[1]??m[2]);if(/\p{L}{2}/u.test(v)&&v.length<=400)found.add(v);}
}
const list=[...found].sort((a,b)=>a.localeCompare(b,'en'));
const body=JSON.stringify(list,null,1)+'\n';
if(process.argv.includes('--check')){
  const have=fs.existsSync(out)?fs.readFileSync(out,'utf8').replace(/\r\n/g,'\n'):'';
  if(have!==body){console.error('api/app/ui_strings.json is out of date: run node scripts/extract_ui_strings.cjs');process.exit(1);}
  console.log('ui strings up to date:',list.length);
}else{fs.writeFileSync(out,body);console.log('ui strings written:',list.length);}
