import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from api.app.main import app
from api.app.contracts import InvoiceInput, ApprovalRequest, ProposalRequest, AgentToolCall

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SAFELEDGER_DB", str(tmp_path / "demo.sqlite3"))
    monkeypatch.setenv("SAFELEDGER_BUILD_COMMIT", "test-build")
    with TestClient(app) as c:
        yield c

def invoice(**overrides):
    return dict(source_record_id="row-1", invoice_id="INV-105", vendor_id="V-1", invoice_number="A-105", issued_on="2026-10-01", due_on="2026-10-20", amount_minor=3500000, currency="BDT", **overrides)

def test_health_is_explicit_about_simulation_and_ai(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["simulation_only"] is True
    assert r.json()["ai_status"] == "not_configured"
    assert r.json()["build_commit"] == "test-build"
    assert r.headers["cache-control"] == "no-store"

def test_sqlite_readiness(client):
    assert client.get("/api/ready").json() == {"status":"ready", "database":"sqlite", "schema_version":1}

def test_database_failure_is_redacted(client, monkeypatch):
    monkeypatch.setenv("SAFELEDGER_DB", "/nonexistent/private/database.sqlite3")
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert "private" not in r.text

@pytest.mark.parametrize("route,expected", [("/api/proposals",401), ("/api/invoices/import",401), ("/api/proposals/forged/execute",404)])
def test_financial_mutations_require_auth_and_direct_execute_is_absent(client, route, expected):
    assert client.post(route, json={"role":"owner", "amount_minor":1}).status_code == expected

@pytest.mark.parametrize("amount", [-1, 0, 1.2, "3500000", True, 10**12+1])
def test_reject_non_integer_or_unsafe_money(amount):
    row = invoice(); row["amount_minor"] = amount
    with pytest.raises(ValidationError): InvoiceInput.model_validate(row)

def test_valid_invoice_preserves_source_and_exact_amount():
    parsed = InvoiceInput.model_validate(invoice())
    assert parsed.amount_minor == 3500000
    assert parsed.source_record_id == "row-1"

@pytest.mark.parametrize("field,value", [("currency","USD"), ("due_on","2026-09-01"), ("business_id","other-tenant"), ("role","approver")])
def test_reject_currency_dates_and_client_authority(field, value):
    row = invoice(); row[field] = value
    with pytest.raises(ValidationError): InvoiceInput.model_validate(row)

def test_proposal_cannot_select_amount_or_payee():
    with pytest.raises(ValidationError):
        ProposalRequest.model_validate({"invoice_id":"INV-105", "amount_minor":1})

@pytest.mark.parametrize("tool", ["approve_proposal", "execute_sandbox_payment", "run_sql", "reveal_secrets"])
def test_agent_envelope_excludes_privileged_tools(tool):
    with pytest.raises(ValidationError): AgentToolCall(tool=tool, arguments={})

def test_approval_hash_contract():
    with pytest.raises(ValidationError): ApprovalRequest(proposal_hash="forged", decision="approve")
