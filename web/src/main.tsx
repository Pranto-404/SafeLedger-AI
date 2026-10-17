import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
type Health = {status: string; milestone: string; ai_status: string; simulation_only: boolean};
function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true); setError(''); setHealth(null);
    try {
      const response = await fetch('/api/health', {signal: AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('Backend unavailable. Start the API and retry.');
      const data: unknown = await response.json();
      if (!data || typeof data !== 'object' || !('status' in data) || data.status !== 'ok' || !('milestone' in data) || typeof data.milestone !== 'string' || !('ai_status' in data) || typeof data.ai_status !== 'string' || !('simulation_only' in data) || data.simulation_only !== true) throw new Error('Unexpected API response.');
      setHealth(data as Health);
    } catch (err) { setError(err instanceof Error ? err.message : 'Connection failed. Retry shortly.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  return <main>
    <p className="banner">Simulated environment · No real money moves</p>
    <header><span className="mark" aria-hidden="true">S</span><div><p className="eyebrow">TOPIC E · SME FINANCE COPILOT</p><h1>SafeLedger AI</h1></div></header>
    <section aria-labelledby="foundation"><p className="eyebrow">ENGINEERING CHECKPOINT</p><h2 id="foundation">A verifiable foundation.</h2><p>Every financial action will connect evidence, deterministic calculations, security policy and a separate human approval.</p>
      <div className="status" role="status" aria-live="polite">{loading ? 'Checking backend…' : health ? `Backend connected · ${health.milestone} · AI ${health.ai_status.replaceAll('_', ' ')}` : 'Backend disconnected'}</div>
      {error && <p role="alert" className="error">{error}</p>}
      <button onClick={() => void refresh()} disabled={loading}>{loading ? 'Checking…' : 'Check connection'}</button>
    </section>
    <section aria-labelledby="scope"><h2 id="scope">Current build scope</h2><p>Financial APIs and human-approved sandbox execution are verified. The bounded AI adapter is available; live provider configuration and the connected financial dashboard are still pending.</p><ol><li>Evidence and exact financial calculations</li><li>Policy checks and independent human approval</li><li>Idempotent sandbox posting and audit replay</li></ol></section>
    <footer>Competition prototype · Synthetic data only · Registration unconfirmed</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
