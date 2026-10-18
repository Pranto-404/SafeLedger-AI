/* Currency arithmetic checks; no browser or external data. */
const assert=require('node:assert/strict');
const esbuild=require('../web/node_modules/esbuild');
const vm=require('node:vm');
const built=esbuild.buildSync({entryPoints:['web/src/api.ts'],bundle:true,write:false,platform:'node',format:'cjs',target:'es2022'}).outputFiles[0].text;
const sandbox={module:{exports:{}},exports:{},Intl,AbortSignal,Error};sandbox.exports=sandbox.module.exports;vm.runInNewContext(built,sandbox);
const {parseMinor,money,currencyDigits}=sandbox.module.exports;
for(const [code,input,expected,digits] of [['JPY','12345',12345,0],['USD','123.45',12345,2],['KWD','12.345',12345,3],['CLF','1.2345',12345,4]]){
 assert.equal(parseMinor(input,code),expected);assert.equal(currencyDigits(code),digits);
 assert(money(expected,code).includes(code));assert.equal(parseMinor('0',code),0);
 assert.throws(()=>parseMinor(code==='JPY'?input+'.1':input+'1',code));
}

for(const bad of ['1e3','-1','NaN','Infinity','1,000',' 1','1.','1.001','10000000001'])assert.throws(()=>parseMinor(bad,'USD'));
assert.equal(parseMinor('10000000000','USD'),1000000000000);
assert.equal(parseMinor('0.001','KWD'),1);
assert.equal(parseMinor('0.0001','CLF'),1);
console.log('Currency parsing and formatting: 4 precision classes and limits passed');
