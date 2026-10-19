/* Prompts about the website itself must be answered on the device, with no network and no model. Synthetic text only. */
const assert=require('node:assert/strict'),vm=require('node:vm');
const esbuild=require('../web/node_modules/esbuild');
const mod={exports:{}};
vm.runInNewContext(esbuild.buildSync({entryPoints:['web/src/localAssistant.ts'],bundle:true,write:false,platform:'node',format:'cjs',target:'es2022'}).outputFiles[0].text,{module:mod,exports:mod.exports,TextEncoder,TextDecoder,console});
const {localAnswer}=mod.exports;
const ctx={snapshot:null,forecast:null,week:null,invoices:[],events:[]};
const cases=[
 ['hey how does this website work','how_it_works'],['How does this app work?','how_it_works'],['how do I use this website','how_it_works'],['explain this site to me','how_it_works'],
 ['ei website kivabe kaj kore','how_it_works'],['এই ওয়েবসাইট কীভাবে কাজ করে','how_it_works'],
 ['what is Capzoryx Copilot','about_product'],['who made this website','about_product'],['tell me about capzoryx','about_product'],
 ['can I scan a bill with my camera','scan_bill'],['how do I upload a photo of an invoice','scan_bill'],['বিলের ছবি দিয়ে কীভাবে যোগ করব','scan_bill'],
 ['can I add a payment by chat','chat_add_record'],['can I just tell you what I paid','chat_add_record'],
 ['how do I turn on 2fa','two_factor'],['set up two step sign in','two_factor'],
 ['how do I change my password','recovery'],['I forgot my password','recovery'],['পাসওয়ার্ড বদলাব কীভাবে','recovery'],
 ['how do I change my name','profile'],['add a profile photo','profile'],
 ['how do I clear my data','clear_data'],['can I undo clearing data','clear_data'],
 ['how do I share my workspace','invite'],['how do I download a pdf report','export'],
];
let wrong=0;
for(const [q,intent] of cases){
  const r=localAnswer(q,ctx,'');
  if(!r.handled||r.intent!==intent){wrong++;console.error('WRONG',JSON.stringify(q),'->',r.intent,r.handled);}
  assert.ok(!/SafeLedger|Gemini|OpenAI|Google/i.test(r.text),'answers must not name providers or the old brand: '+q);
}
const bn=localAnswer('এই ওয়েবসাইট কীভাবে কাজ করে',ctx,'');assert.match(bn.text,/[ঀ-৿]/);
const en=localAnswer('how does this website work',ctx,'');assert.match(en.text,/Capzoryx Copilot/);assert.match(en.text,/never sends bank transfers/);
// Off-topic prompts must still be refused locally.
for(const q of ['what is the weather in dhaka','write me a poem','who won the world cup']){const r=localAnswer(q,ctx,'');assert.equal(r.intent,'out_of_domain',q);}
assert.equal(wrong,0,wrong+' site-guide prompts were not handled');
console.log('site guide:',cases.length,'prompts answered on the device; off-topic still refused');
