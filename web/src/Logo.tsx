/** The Capzoryx Copilot mark: a "C" with a rising line inside. */
export function Logo({size=36}:{size?:number}){
  return <svg className="logo-mark" width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" focusable="false"><defs><linearGradient id="cz-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#0f7a63"/><stop offset="1" stopColor="#132a4a"/></linearGradient></defs><rect width="40" height="40" rx="11" fill="url(#cz-grad)"/><path d="M27.5 13.2A9.6 9.6 0 1 0 27.5 26.8" fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round"/><path className="logo-rise" d="M16.5 24.5l4-4.2 3 2.4 6-7.4" fill="none" stroke="#8cebd0" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
export function Brand(){return <div className="brand"><Logo/><span className="brand-name">Capzoryx <b>Copilot</b></span></div>;}
