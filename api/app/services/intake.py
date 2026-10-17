"""Bounded local import parsing; never sends memo text to an instruction channel."""
import csv
import io
import json
from pydantic import ValidationError
from api.app.contracts import CashEventInput, InvoiceInput
from api.app.services.finance import validated

MAX_BYTES = 1024 * 1024


class IntakeError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Input rejected; inspect field/line errors")


def parse_json(content: bytes):
    if len(content) > MAX_BYTES:
        raise IntakeError([{"field": "file", "message": "File exceeds 1 MiB limit"}])
    try:
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON object key")
                result[key] = value
            return result
        raw = json.loads(content.decode("utf-8-sig"), object_pairs_hook=unique_keys)
        return validated(raw)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ValidationError):
            errors = [{"field": ".".join(map(str, x["loc"])), "message": x["msg"]} for x in exc.errors()]
        else:
            errors = [{"field": "file", "message": "Invalid UTF-8 JSON or duplicate object keys"}]
        raise IntakeError(errors) from None


def parse_csv(content: bytes, kind: str):
    if kind not in {"invoices", "events"}:
        raise ValueError("Unsupported CSV kind")
    if len(content) > MAX_BYTES:
        raise IntakeError([{"line": 1, "field": "file", "message": "File exceeds 1 MiB limit"}])
    model = InvoiceInput if kind == "invoices" else CashEventInput
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError:
        raise IntakeError([{"line": 1, "field": "file", "message": "Expected UTF-8 CSV"}]) from None
    if "\x00" in text:
        raise IntakeError([{"line": 1, "field": "file", "message": "Binary/NUL data is not CSV"}])
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    fields = model.model_fields
    required = {name for name, info in fields.items() if info.is_required()}
    errors, records = [], []
    try:
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not required.issubset(headers) or set(headers) - set(fields):
            raise IntakeError([{"line": 1, "field": "header", "message": "Use unique schema headers; required: " + ", ".join(sorted(required))}])
        for index, row in enumerate(reader, 1):
            if index > (1000 if kind == "invoices" else 2000):
                raise IntakeError([{"line": reader.line_num, "field": "file", "message": "Too many rows"}])
            line = reader.line_num
            if None in row or any(value is None for value in row.values()):
                errors.append({"line": line, "field": "row", "message": "Column count differs from header"})
                continue
            if len(row["amount_minor"]) > 13 or not row["amount_minor"].isascii() or not row["amount_minor"].isdigit():
                errors.append({"line": line, "field": "amount_minor", "message": "Use integer minor units (e.g. 3500000); no decimals or formulas"})
                continue
            row["amount_minor"] = int(row["amount_minor"])
            if kind == "events" and row.get("invoice_id") == "":
                row["invoice_id"] = None
            try:
                records.append(model.model_validate(row))
            except ValidationError as exc:
                errors.extend({"line": line, "field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors())
    except csv.Error:
        raise IntakeError([{"line": reader.line_num, "field": "file", "message": "Malformed CSV quoting/structure"}]) from None
    if errors:
        raise IntakeError(errors)
    return records


def safe_csv_cell(value):
    """For future CSV exports: stop spreadsheet formulas incl. whitespace prefixes."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
