"""Randomized property checks for the financing engine: no crashes, exact conservation, stable ordering."""
from datetime import date, timedelta
import random
import pytest
from pydantic import ValidationError
from api.app.services.finance import Dataset
from api.app.services.financing import FinancingMatchRequest, LenderQuote, match_financing, repayment_schedule, effective_annual_rate_bps

AS_OF = date(2026, 10, 19)


def dataset(rng):
    events = [dict(source_record_id='e%d' % i, event_id='e%d' % i, direction=rng.choice(['inflow', 'outflow']), status='scheduled',
                   effective_on=(AS_OF + timedelta(days=rng.randint(1, 120))).isoformat(), amount_minor=rng.randint(1, 5 * 10**8), currency='BDT', invoice_id=None) for i in range(rng.randint(0, 12))]
    return Dataset.model_validate(dict(opening_source_id='open', opening_on='2026-10-01', as_of=AS_OF.isoformat(), opening_balance_minor=rng.randint(0, 10**9), currency='BDT', invoices=[], events=events))


def random_quote(rng, n):
    repayment = rng.choice(['single_payment', 'equal_installments'])
    installments = 1 if repayment == 'single_payment' else rng.randint(1, 60)
    term = installments * rng.randint(1, 30) if repayment == 'equal_installments' else rng.randint(1, 1825)
    term = min(term, 1825) // installments * installments or installments
    principal = rng.choice([1, 2, 99, 100, 101, 12345, 10**6, rng.randint(1, 10**12)])
    return dict(quote_id='q%d' % n, lender_name='Lender %d' % n, product_type=rng.choice(['term_loan', 'working_capital_line', 'invoice_financing', 'equipment_loan', 'other']),
                currency='BDT', principal_minor=principal, upfront_fee_minor=rng.randint(0, principal - 1) if principal > 1 and rng.random() < 0.5 else 0,
                rate_type=rng.choice(['flat_per_term', 'annual_reducing']), rate_bps=rng.choice([0, 1, 50, 250, 900, 1350, 3600, 9999, 20000, rng.randint(0, 20000)]),
                repayment=repayment, installments=installments, term_days=term, quote_source='fuzz source', quoted_on=(AS_OF - timedelta(days=rng.randint(0, 60))).isoformat())


def test_random_quotes_never_crash_and_conserve_money():
    rng = random.Random(20261020)
    accepted = rejected = 0
    for round_number in range(120):
        ds = dataset(rng)
        quotes = [random_quote(rng, n) for n in range(rng.randint(1, 10))]
        try:
            request = FinancingMatchRequest.model_validate(dict(as_of=AS_OF.isoformat(), quotes=quotes))
        except ValidationError:
            rejected += 1
            continue
        reserve = rng.choice([0, 0, 10**6, rng.randint(0, 10**9)])
        try:
            result = match_financing(ds, reserve, request)
        except ValueError:
            rejected += 1  # terms that cannot amortize are refused, never half-computed
            continue
        accepted += 1
        assert result['funding_need_minor'] >= 0
        order = [x['quote_id'] for x in result['quotes']]
        assert sorted(order) == sorted(q['quote_id'] for q in quotes)
        fits = [x for x in result['quotes'] if x['status'] == 'FITS_CASH_FLOW']
        assert result['quotes'][:len(fits)] == fits  # fitting offers always rank first
        assert result['best_match_quote_id'] == (fits[0]['quote_id'] if fits else None)
        assert [x['total_cost_minor'] for x in fits] == sorted(x['total_cost_minor'] for x in fits)
        for row in result['quotes']:
            schedule = row['schedule']
            assert len(schedule) == row['installments'] and all(s['payment_minor'] > 0 for s in schedule[:-1])
            paid = sum(s['payment_minor'] for s in schedule); interest = sum(s['interest_minor'] for s in schedule)
            assert paid == row['total_repayment_minor'] == row['principal_minor'] + row['interest_minor'] and interest == row['interest_minor']
            assert row['total_cost_minor'] == row['interest_minor'] + row['upfront_fee_minor']
            assert row['net_proceeds_minor'] == row['principal_minor'] - row['upfront_fee_minor'] > 0
            assert row['effective_annual_rate_bps'] >= 0
            assert [s['date'] for s in schedule] == sorted(s['date'] for s in schedule)
            if row['status'] == 'FITS_CASH_FLOW':
                assert row['lowest_balance_with_financing_minor'] >= reserve and row['first_reserve_breach_on'] is None
            if row['status'] == 'REPAYMENT_BREACHES_RESERVE':
                assert row['first_reserve_breach_on'] is not None
        shuffled = quotes[:]; rng.shuffle(shuffled)
        again = match_financing(ds, reserve, FinancingMatchRequest.model_validate(dict(as_of=AS_OF.isoformat(), quotes=shuffled)))
        assert again['quotes'] == result['quotes']
    assert accepted >= 25 and rejected > 0, (accepted, rejected)


@pytest.mark.parametrize('principal,rate,term,installments', [(10**12, 20000, 1825, 1), (10**12, 20000, 1800, 60), (1, 0, 1, 1), (2, 20000, 60, 60), (100, 1, 360, 12), (10**12, 1, 1800, 60)])
def test_extreme_terms_are_exact_or_cleanly_rejected(principal, rate, term, installments):
    for rate_type in ('flat_per_term', 'annual_reducing'):
        try:
            quote = LenderQuote.model_validate(dict(quote_id='x', lender_name='x', product_type='other', currency='BDT', principal_minor=principal, upfront_fee_minor=0, rate_type=rate_type,
                                                rate_bps=rate, repayment='single_payment' if installments == 1 else 'equal_installments', installments=installments, term_days=term, quote_source='extreme', quoted_on='2026-10-19'))
            schedule = repayment_schedule(quote)
        except (ValueError, ValidationError):
            continue
        assert sum(a - i for _, a, i in schedule) == principal
        assert effective_annual_rate_bps(principal, schedule) >= 0
