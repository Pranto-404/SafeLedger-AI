import {currencies} from './currencies';
const messages:Record<string,string> = {
  WORKSPACE_CURRENCY_LOCKED:'This workspace already has records. Create another workspace for a different currency.',
  IMPORT_CURRENCY_MISMATCH:'The import currency must match your workspace. Change the empty workspace currency first.',
  AI_PROVIDER_REJECTED:'The AI provider rejected the request. Check its model and credentials, or use the private helper.',
  DUPLICATE_INVOICE_BLOCKED:'This invoice may be a duplicate. Review its evidence before continuing.',
  INVOICE_ALREADY_PAID:'This invoice has already been recorded as paid.',
  INSUFFICIENT_AVAILABLE_CASH:'There is not enough available cash after the required reserve.',
  PROPOSAL_EXPIRED:'This proposal expired. Review the invoice and prepare a new proposal.',
  AI_QUOTA_EXHAUSTED:'The free AI quota is temporarily exhausted. Cash flow and payment recording still work.',
  AI_NOT_CONFIGURED:'The assistant is not available yet. You can still explore the other tools.',
  AI_TIMEOUT_OR_NETWORK_FAILURE:'The assistant took too long to respond. Please try again later.',
  REQUEST_BUDGET_EXCEEDED:'Too many requests. Please wait a minute before trying again.',
  DATABASE_UNAVAILABLE:'The workspace is temporarily unavailable. Please refresh in a moment.',
  HUMAN_APPROVER_REQUIRED:'A separate approver account must review this proposal.',
  QUOTE_CURRENCY_MISMATCH:'Quotes must use the workspace record currency.',
  QUOTE_DATE_AFTER_SNAPSHOT:'The quote date cannot be later than your records snapshot date.',
  QUOTE_TERMS_INVALID:'These quote terms cannot be repaid as entered. Check the rate, term and installments.',
  OWNER_OR_APPROVER_REQUIRED:'Only the owner or approver can run financing analysis.',
  SNAPSHOT_DATE_CHANGED_REFRESH_REQUIRED:'Your records changed. Refresh data and try again.',
};
export class ApiError extends Error {
  constructor(public code: string, public status: number, message = messages[code] || code.replaceAll('_', ' '), public providerStatus?:number) { super(message); }
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
      throw new ApiError(data?.error?.code || 'SERVER_ERROR', response.status, fields ? fields.map(x => `${x.field}: ${x.message}`).join('; ') : undefined,typeof data?.provider_http_status==='number'?data.provider_http_status:undefined);
    }
    if (!data || data.simulation_only !== true) throw new ApiError('INVALID_SERVER_RESPONSE', 502);
    return data as T;
  };
}
// Display only. All balances, costs and projections come from backend integer calculations.
export const currencyDigits = (currency:string) => currencies.find(c=>c.code===currency)?.digits ?? 2;
export const money = (minor:number,currency='BDT') => new Intl.NumberFormat(undefined,{style:'currency',currency,currencyDisplay:'code',minimumFractionDigits:currencyDigits(currency),maximumFractionDigits:currencyDigits(currency)}).format(minor / 10**currencyDigits(currency));
export function parseMinor(text:string,currency='BDT'):number {
  const digits=currencyDigits(currency);
  if(!new RegExp('^\\d{1,13}'+(digits?'(\\.\\d{1,'+digits+'})?':'')+'$').test(text))throw new Error(`Enter a nonnegative ${currency} amount with at most ${digits} decimal places.`);
  const [whole,fraction='']=text.split('.');
  const result=BigInt(whole)*10n**BigInt(digits)+BigInt(fraction.padEnd(digits,'0')||'0');
  if(result>1000000000000n)throw new Error('Amount exceeds the supported limit.');
  return Number(result);
}

const friendly: Record<string,string> = {
  INVALID_USERNAME_OR_PASSWORD: 'That username and password do not match. Please try again.',
  USERNAME_UNAVAILABLE: 'That username is already in use. Try another one.',
  REQUEST_BUDGET_EXCEEDED: 'A few too many requests. Please wait a minute and try again.',
  INVITATION_INVALID_OR_EXPIRED: 'This invitation has expired or was already used. Ask the workspace owner for a new one.',
  INVALID_RECOVERY_DETAILS:'The username and recovery code do not match. Check your saved code.',
  ALREADY_A_WORKSPACE_MEMBER: 'You already belong to that workspace. Select it from the workspace list.',
};
export async function accountRequest<T>(path:string, body?:unknown, signal?:AbortSignal):Promise<T> {
  const r = await fetch('/api'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-SafeLedger-Client':'web'},body:body===undefined?undefined:JSON.stringify(body),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(90000)]):AbortSignal.timeout(90000)});
  const data=await r.json().catch(()=>null);
  if(!r.ok) throw new Error(friendly[data?.error?.code] || (r.status===422?'Check your username and use a password of at least 8 characters.':data?.error?.code?.replaceAll('_',' ') || 'The server is unavailable. Please try again.'));
  if(data?.simulation_only!==true)throw new Error('Unexpected server response. Please try again.');
  return data as T;
}
