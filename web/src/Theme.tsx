import {createContext,useContext,useLayoutEffect,useState,type ReactNode} from 'react';
type Theme='light'|'dark';
const ThemeContext=createContext<{theme:Theme;toggle:()=>void}>({theme:'light',toggle:()=>{}});
export function ThemeProvider({children}:{children:ReactNode}){
 const [theme,setTheme]=useState<Theme>(()=>{try{return localStorage.getItem('safeledger-theme')==='dark'?'dark':'light';}catch{return 'light';}});
 useLayoutEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('safeledger-theme',theme);}catch{/* Theme preference is optional. */}},[theme]);
 return <ThemeContext.Provider value={{theme,toggle:()=>setTheme(v=>v==='light'?'dark':'light')}}>{children}</ThemeContext.Provider>;
}
export function ThemeButton(){const {theme,toggle}=useContext(ThemeContext);return <button type="button" className="secondary theme-toggle" onClick={toggle} aria-label={theme==='light'?'Switch to dark theme':'Switch to light theme'} aria-pressed={theme==='dark'}><span aria-hidden="true">{theme==='light'?'☾':'☀'}</span><span>{theme==='light'?'Dark':'Light'}</span></button>;}
