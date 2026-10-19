/* Exact reporting conversion; never changes source amounts or calls an FX service. */
const assert=require('node:assert/strict');
const esbuild=require('../web/node_modules/esbuild');
const vm=require('node:vm');
const built=esbuild.buildSync({entryPoints:['web/src/currencyView.ts'],bundle:true,write:false,platform:'node',format:'cjs',target:'es2022'}).outputFiles[0].text;
const items=new Map();const sandbox={module:{exports:{}},exports:{},Intl,AbortSignal,Error,localStorage:{getItem:k=>items.get(k)||null}};sandbox.exports=sandbox.module.exports;vm.runInNewContext(built,sandbox);
const {convertMinor,formatConverted,parseRate,readCurrencyView}=sandbox.module.exports;
const cases=[
 [10000,'USD','BDT','120',1200000n], [12345,'USD','JPY','150',18518n],
 [-12345,'USD','JPY','150',-18518n], [1,'JPY','KWD','0.002',2n],
 [12345,'KWD','USD','3.25',4012n], [1,'CLF','USD','45.123456789012',0n],
 [10000,'USD','CLF','0.02345',23450n], [1,'USD','JPY','0.5',0n],
 [1,'USD','KWD','0.05',1n],[-1,'USD','KWD','0.05',-1n],
 [9007199254740991,'USD','BDT','999999999.999999999999',9007199254740990999990993n],
];
for(const [amount,base,target,rate,wanted] of cases)assert.equal(convertMinor(amount,base,target,rate),wanted);
assert.match(formatConverted(-1n,'USD'),/-/);assert.match(formatConverted(-1n,'USD'),/0\.01/);
assert.match(formatConverted(900719925474099101n,'USD'),/9,007,199,254,740,991\.01/);
for(const rate of ['0','-1','NaN','Infinity','1e3','1,000',' 1','1.','1000000000','0.0000000000001'])assert.throws(()=>parseRate(rate));
assert.throws(()=>convertMinor(1.5,'USD','BDT','1'));assert.throws(()=>convertMinor(1,'XXX','BDT','1'));
const valid={base:'USD',currency:'BDT',rate:'120',updatedAt:'2026-10-19T00:00:00Z'};
items.set('a',JSON.stringify(valid));assert.equal(readCurrencyView('a').rate,'120');assert.equal(readCurrencyView('b'),null);
for(const bad of ['{bad',JSON.stringify({...valid,rate:'0'}),JSON.stringify({...valid,base:'XXX'}),JSON.stringify({...valid,updatedAt:'bad'})]){items.set('a',bad);assert.equal(readCurrencyView('a'),null);}
console.log('Reporting currencies: exact precision, negative rounding, large values, invalid rates, persistence validation and workspace isolation passed.');
