export class ApiError extends Error {
  constructor(public code: string, public status: number, message = code.replaceAll('_', ' ')) { super(message); }
}
export function client(token: string, signal: AbortSignal, onUnauthorized: () => void) {
  return async function request<T>(path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.any([signal, AbortSignal.timeout(60000)]), cache: 'no-store' });
    } catch (error) {
      if (signal.aborted) throw error;
      throw new ApiError('CONNECTION_FAILED', 0, 'Could not reach the server. Check the connection and retry. A timed-out action may have completed; refresh before retrying.');
    }
    const data = await response.json().catch(() => null);
    // An old session must not sign out a newly mounted workspace after cancellation.
    signal.throwIfAborted();
    if (!response.ok) {
      if (response.status === 401) onUnauthorized();
      const fields = data?.error?.fields as {field: string; message: string}[] | undefined;
      throw new ApiError(data?.error?.code || 'SERVER_ERROR', response.status, fields ? fields.map(x => `${x.field}: ${x.message}`).join('; ') : undefined);
    }
    if (!data || data.simulation_only !== true) throw new ApiError('INVALID_SERVER_RESPONSE', 502);
    return data as T;
  };
}
// Display only. All balances, costs and projections come from backend integer calculations.
export const money = (minor: number) => new Intl.NumberFormat('en-BD', { style: 'currency', currency: 'BDT', maximumFractionDigits: 2 }).format(minor / 100);
export function parseMinor(text: string): number {
  if (!/^\d{1,9}(\.\d{1,2})?$/.test(text)) throw new Error('Enter a nonnegative BDT amount with at most two decimal places.');
  const [whole, fraction = ''] = text.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}
