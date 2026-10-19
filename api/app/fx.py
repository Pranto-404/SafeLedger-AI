"""Live exchange rates from free public sources, cached in memory. Display conversion only; ledgers stay in their own currency."""
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import httpx
from fastapi import APIRouter, Depends, Query
from api.app import security as sec
from api.app.currencies import CURRENCIES
from api.app.routes import db_connection, principal

router = APIRouter(prefix='/api')
TTL_SECONDS = 3600
STALE_SECONDS = 86400
SOURCES = (
    ('Exchange Rate API', 'https://open.er-api.com/v6/latest/USD'),
    ('Currency API', 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json'),
)
_cache = {'at': 0.0, 'rates': {}, 'source': None, 'as_of': None}
_lock = threading.Lock()


def fetch_json(url):
    with httpx.Client(timeout=8, trust_env=False, follow_redirects=False) as client:
        response = client.get(url, headers={'Accept': 'application/json'})
        response.raise_for_status()
        if len(response.content) > 600_000:raise ValueError('Rate table too large')
        return response.json()


def _clean(table):
    rates = {}
    for code, value in table.items():
        code = str(code).upper()
        if len(code) != 3 or not code.isalpha():continue
        try:rate = Decimal(str(value))
        except InvalidOperation:continue
        if rate.is_finite() and Decimal('1e-9') < rate < Decimal('1e12'):rates[code] = rate
    return rates


def _parse(name, body):
    if name == 'Exchange Rate API':
        if body.get('result') != 'success':raise ValueError('Source reported failure')
        stamp = body.get('time_last_update_unix')
        as_of = datetime.fromtimestamp(stamp, timezone.utc).isoformat() if isinstance(stamp, (int, float)) else None
        return _clean(body['rates']), as_of
    return _clean(body['usd']), (str(body.get('date')) + 'T00:00:00+00:00') if body.get('date') else None


def load_rates():
    """Return (rates per 1 USD, source, as_of, stale). Falls back to the other source, then to a recent cache."""
    now = time.time()
    with _lock:
        if _cache['rates'] and now - _cache['at'] < TTL_SECONDS:
            return _cache['rates'], _cache['source'], _cache['as_of'], False
        for name, url in SOURCES:
            try:
                rates, as_of = _parse(name, fetch_json(url))
                if len(rates) >= 50 and 'USD' not in rates:rates['USD'] = Decimal(1)
                if len(rates) >= 50:
                    _cache.update(at=now, rates=rates, source=name, as_of=as_of)
                    return rates, name, as_of, False
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                continue
        if _cache['rates'] and now - _cache['at'] < STALE_SECONDS:
            return _cache['rates'], _cache['source'], _cache['as_of'], True
    sec.fail(503, 'FX_UNAVAILABLE')


def pair_rate(rates, source_code, target_code):
    if source_code not in rates or target_code not in rates:sec.fail(404, 'FX_PAIR_UNAVAILABLE')
    with localcontext() as ctx:
        ctx.prec = 40
        value = rates[target_code] / rates[source_code]
    quantized = value.quantize(Decimal('1e-12'), rounding=ROUND_HALF_EVEN)
    if quantized <= 0 or quantized >= Decimal('1e9'):sec.fail(422, 'FX_RATE_OUT_OF_RANGE')
    return format(quantized, 'f')


@router.get('/fx/rate')
def rate(source: str = Query(alias='from', pattern='^[A-Z]{3}$'), target: str = Query(alias='to', pattern='^[A-Z]{3}$'), actor=Depends(principal), db=Depends(db_connection)):
    if source not in CURRENCIES or target not in CURRENCIES:sec.fail(422, 'UNSUPPORTED_CURRENCY')
    sec.budget(db, 'fx:' + actor.user_id, 40)
    rates, name, as_of, stale = load_rates()
    return dict(source_currency=source, target_currency=target, rate=pair_rate(rates, source, target), provider=name, as_of=as_of, stale=stale, simulation_only=True)
