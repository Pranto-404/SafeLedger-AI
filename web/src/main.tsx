import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import {ThemeProvider} from './Theme';
import {I18nProvider} from './i18n';
import './style.css';
createRoot(document.getElementById('root')!).render(<StrictMode><ThemeProvider><I18nProvider><App /></I18nProvider></ThemeProvider></StrictMode>);

// The logo screen is plain HTML that paints before any script runs. Once the app is on screen it slides away.
const splash=document.getElementById('splash');
if(splash){
  const leave=()=>{splash.classList.add('leave');window.setTimeout(()=>splash.remove(),700);};
  window.setTimeout(leave,Math.max(80,600-performance.now()));
}
