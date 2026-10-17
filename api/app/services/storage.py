"""Atomic staging storage, internal only until M2 authentication is implemented."""
import json
import sqlite3
from api.app.services.finance import fingerprint, validated


def create_schema(connection):
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS financial_datasets (
      business_id TEXT PRIMARY KEY, dataset_sha256 TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS source_records (
      business_id TEXT NOT NULL REFERENCES financial_datasets(business_id),
      source_record_id TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL,
      record_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
      PRIMARY KEY (business_id, source_record_id), UNIQUE (business_id, kind, record_id));
    """)


def store_dataset(connection, business_id: str, raw, *, before_write=None, after_write=None):
    if not isinstance(business_id, str) or not business_id or len(business_id) > 80:
        raise ValueError("Trusted internal business ID is required")
    if connection.in_transaction:
        raise ValueError("Import requires its own transaction")
    ds = validated(raw)  # All validation before first write; no partial malformed batches.
    checksum = fingerprint(ds)
    connection.execute("BEGIN IMMEDIATE")
    with connection:
        if before_write is not None:
            before_write()
        connection.execute("INSERT INTO financial_datasets VALUES (?,?,?)", (business_id, checksum, ds.model_dump_json()))
        records = [("invoice", x.invoice_id, x) for x in ds.invoices] + [("event", x.event_id, x) for x in ds.events]
        for kind, record_id, record in records:
            connection.execute("INSERT INTO source_records VALUES (?,?,?,?,?,?)", (business_id, record.source_record_id, kind, record_id, fingerprint(record), record.model_dump_json()))
        if after_write is not None:
            after_write(ds, checksum)
    return {"dataset_sha256": checksum, "invoice_count": len(ds.invoices), "event_count": len(ds.events)}


def load_dataset(connection, business_id: str):
    # Internal caller supplies authenticated tenant in M2; this is NOT an auth control.
    row = connection.execute("SELECT dataset_sha256,payload FROM financial_datasets WHERE business_id=?", (business_id,)).fetchone()
    if row is None:
        raise KeyError("Dataset not found")
    ds = validated(json.loads(row[1]))
    if fingerprint(ds) != row[0]:
        raise ValueError("Dataset checksum mismatch")
    expected = {(x.source_record_id, kind, record_id): (fingerprint(x), x.model_dump(mode="json"))
                for kind, record_id, x in [("invoice", x.invoice_id, x) for x in ds.invoices] + [("event", x.event_id, x) for x in ds.events]}
    stored = connection.execute("SELECT source_record_id,kind,record_id,record_sha256,payload FROM source_records WHERE business_id=?", (business_id,)).fetchall()
    if len(stored) != len(expected):
        raise ValueError("Source record integrity mismatch")
    for source_id, kind, record_id, checksum, payload in stored:
        try:
            record = (checksum, json.loads(payload))
        except ValueError:
            raise ValueError("Source record integrity mismatch") from None
        if expected.get((source_id, kind, record_id)) != record:
            raise ValueError("Source record integrity mismatch")
    return ds
