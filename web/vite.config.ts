import { defineConfig, loadEnv } from 'vite';
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'SAFELEDGER_DEV_');
  return { server: { proxy: { '/api': env.SAFELEDGER_DEV_API_URL || 'http://127.0.0.1:8000' } } };
});
