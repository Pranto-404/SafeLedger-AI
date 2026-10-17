const messages:Record<string,string> = {
  DUPLICATE_INVOICE_BLOCKED:'This invoice may be a duplicate. Review its evidence before continuing.',
  INVOICE_ALREADY_PAID:'This invoice has already been paid in the sandbox.',
  INSUFFICIENT_AVAILABLE_CASH:'There is not enough available cash after the required reserve.',
  PROPOSAL_EXPIRED:'This proposal expired. Review the invoice and prepare a new proposal.',
  AI_QUOTA_EXHAUSTED:'The free AI quota is temporarily exhausted. Cash flow and sandbox payments still work.',
  AI_NOT_CONFIGURED:'The assistant is not available yet. You can still explore the other tools.',
  AI_TIMEOUT_OR_NETWORK_FAILURE:'The assistant took too long to respond. Please try again later.',
  REQUEST_BUDGET_EXCEEDED:'Too many requests. Please wait a minute before trying again.',
  DATABASE_UNAVAILABLE:'The workspace is temporarily unavailable. Please refresh in a moment.',
  HUMAN_APPROVER_REQUIRED:'A separate approver account must review this proposal.',
};
export class ApiError extends Error {
  constructor(public code: string, public status: number, message = messages[code] || code.replaceAll('_', ' ')) { super(message); }
}
export function client(token: string, signal: AbortSignal, onUnauthorized: () => void) {
  return async function request<T>(path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST', credentials:'same-origin', headers: { ...(token?{Authorization: `Bearer ${token}`} : {}), 'X-SafeLedger-Client':'web', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.any([signal, AbortSignal.timeout(90000)]), cache: 'no-store' });
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
export const money = (minor: number) => new Intl.NumberFormat('en-BD', { style: 'currency', currency: 'BDT', currencyDisplay:'code', maximumFractionDigits: 2 }).format(minor / 100);
export function parseMinor(text: string): number {
  if (!/^\d{1,9}(\.\d{1,2})?$/.test(text)) throw new Error('Enter a nonnegative BDT amount with at most two decimal places.');
  const [whole, fraction = ''] = text.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}
