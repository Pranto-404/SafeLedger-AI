import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import {ThemeProvider} from './Theme';
import './style.css';
createRoot(document.getElementById('root')!).render(<StrictMode><ThemeProvider><App /></ThemeProvider></StrictMode>);
