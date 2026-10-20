/* Interface-language helpers: browser-language detection, default currency, and the merge rule that keeps ready-made
   translations when the server answers with fewer strings. Synthetic text only. */
const assert=require('node:assert/strict'),vm=require('node:vm');
const esbuild=require('../web/node_modules/esbuild');
const mod={exports:{}};
vm.runInNewContext(esbuild.buildSync({entryPoints:['web/src/i18n.tsx'],bundle:true,write:false,platform:'node',format:'cjs',target:'es2022',loader:{'.tsx':'tsx'},external:['react']}).outputFiles[0].text,
  {module:mod,exports:mod.exports,require:require('node:module').createRequire(require('node:path').resolve(__dirname,'../web/package.json')),console,localStorage:{getItem(){return null},setItem(){}},navigator:{languages:['en']},document:{documentElement:{}},window:{}});
const {mergeStrings,detectLanguage,defaultCurrency,LANGUAGES}=mod.exports;
assert.equal(LANGUAGES.length,37);
const same=(a,b)=>assert.equal(JSON.stringify(a),JSON.stringify(b));
same(mergeStrings({a:'x',b:'y'},{}),{a:'x',b:'y'});               // an empty server answer erases nothing
same(mergeStrings({a:'x'},{a:'z',c:'w'}),{a:'z',c:'w'});          // newer server text wins, new keys are added
assert.equal(detectLanguage(['zh-TW']),'zh-TW');assert.equal(detectLanguage(['zh-HK']),'zh-TW');assert.equal(detectLanguage(['zh-CN']),'zh-CN');
assert.equal(detectLanguage(['tl']),'fil');assert.equal(detectLanguage(['xx','ja-JP']),'ja');assert.equal(detectLanguage(['en-GB','zh']),'en');
assert.equal(defaultCurrency('zh-CN'),'CNY');assert.equal(defaultCurrency('fr'),'BDT');
console.log('i18n helpers: 37 languages, merge rule, language detection and default currency passed');
