import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import {ThemeProvider} from './Theme';
import {I18nProvider} from './i18n';
import './style.css';
createRoot(document.getElementById('root')!).render(<StrictMode><ThemeProvider><I18nProvider><App /></I18nProvider></ThemeProvider></StrictMode>);
