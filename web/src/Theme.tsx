import {Icon} from './Icon';
import {createContext,useContext,useLayoutEffect,useState,type ReactNode} from 'react';
import {t} from './i18n';
type Theme='light'|'dark';
const ThemeContext=createContext<{theme:Theme;toggle:()=>void}>({theme:'light',toggle:()=>{}});
export function ThemeProvider({children}:{children:ReactNode}){
 const [theme,setTheme]=useState<Theme>(()=>{try{return localStorage.getItem('safeledger-theme')==='dark'?'dark':'light';}catch{return 'light';}});
 useLayoutEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('safeledger-theme',theme);}catch{/* Theme preference is optional. */}},[theme]);
 return <ThemeContext.Provider value={{theme,toggle:()=>setTheme(v=>v==='light'?'dark':'light')}}>{children}</ThemeContext.Provider>;
}
export function ThemeButton(){const {theme,toggle}=useContext(ThemeContext);return <button type="button" className="secondary theme-toggle" onClick={toggle} aria-label={theme==='light'?t('Switch to dark theme'):t('Switch to light theme')} aria-pressed={theme==='dark'}><span aria-hidden="true"><Icon name={theme==='light'?'moon':'sun'}/></span><span>{theme==='light'?'Dark':t('Light')}</span></button>;}
