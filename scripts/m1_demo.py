"""Reproduce M1 financial analysis with SQLite staging; no LLM or payment execution."""
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.app.contracts import ScenarioRequest
from api.app.services.finance import FinancingRequest, compare_financing, project_cashflow, snapshot
from api.app.services.intake import parse_json
from api.app.services.storage import create_schema, load_dataset, store_dataset

root=Path(__file__).resolve().parents[1]
fixtures=root/'data/fixtures'
with tempfile.TemporaryDirectory(prefix='safeledger-m1-') as directory:
    with sqlite3.connect(Path(directory)/'demo.sqlite3') as db:
        create_schema(db)
        ds=parse_json((fixtures/'seed_2026.json').read_bytes())
        imported=store_dataset(db,'synthetic-demo-business',ds)
        ds=load_dataset(db,'synthetic-demo-business')
        expected=json.loads((fixtures/'expected_results.json').read_text())
        summary=snapshot(ds)
        scenarios={}
        for horizon in (7,30):
            scenarios[str(horizon)]=project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=horizon,reserve_minor=1000000))
            assert scenarios[str(horizon)]['closing_balance_minor']==expected[f'forecast_{horizon}_closing_minor']
        assert summary['balance_minor']==expected['balance_minor']
        delayed=project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=30,reserve_minor=1000000,delay_inflows_days=7))
        assert delayed['minimum_balance_minor']==expected['delayed_30_minimum_minor']
        capacity=max(0,scenarios['30']['closing_balance_minor']-1000000)
        comparison=compare_financing(FinancingRequest(principal_minor=5000000,repayment_capacity_minor=capacity,capacity_source_ids=scenarios['30']['source_ids'],offers=json.loads((fixtures/'fictional_offers.json').read_text())))
        assert [x['offer_id'] for x in comparison['offers']]==expected['ranked_offers']
        assert [x['total_cost_minor'] for x in comparison['offers']]==expected['total_cost_minor']
        result={'simulation_only':True,'milestone':'M1','ai_used':False,'payments_executed':0,'import':imported,'snapshot':summary,'cashflow':scenarios,'delayed_30':delayed,'financing':comparison}
        print(json.dumps(result,indent=2))
