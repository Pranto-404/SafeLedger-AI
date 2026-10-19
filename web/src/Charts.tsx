import {useId} from 'react';
import {useCurrency} from './Currency';
import type {Forecast} from './types';
export function CashChart({forecast}:{forecast:Forecast}){
 const {money,digits}=useCurrency();const id=useId().replaceAll(':','');
 const values=forecast.days.map(d=>d.projected_balance_minor);const min=Math.min(0,...values);const max=Math.max(10**digits,...values);const y=(v:number)=>170-(v-min)/(max-min)*140;
 const points=values.map((v,i)=>`${100+i/Math.max(1,values.length-1)*560},${y(v)}`).join(' ');
 const dates=[0,Math.floor(values.length/2),values.length-1].filter((v,i,a)=>v>=0&&a.indexOf(v)===i);
 return <figure className="cash-chart"><svg viewBox="0 0 690 215" role="img" aria-label="Projected cash balance from your saved records. The Cash flow page contains exact daily figures."><defs><linearGradient id={'area-'+id} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity=".22"/><stop offset="100%" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>{[0,.5,1].map(t=><g key={t}><line x1="100" x2="660" y1={30+t*140} y2={30+t*140} className="chart-grid"/><text x="87" y={34+t*140} textAnchor="end">{money(Math.round(max-t*(max-min)))}</text></g>)}{values.length>0&&<><polygon points={`100,185 ${points} 660,185`} fill={`url(#area-${id})`}/><polyline points={points} fill="none" stroke="currentColor" strokeWidth="3"/><circle cx="660" cy={y(values[values.length-1])} r="4" fill="currentColor"/></>}{dates.map(i=><text key={i} x={100+i/Math.max(1,values.length-1)*560} y="205" textAnchor={i===0?'start':i===values.length-1?'end':'middle'}>{forecast.days[i]?.date}</text>)}</svg><figcaption>Projected from recorded activity · no AI estimate</figcaption></figure>;
}
