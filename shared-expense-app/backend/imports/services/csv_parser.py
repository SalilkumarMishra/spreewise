"""
CSV Parser
==========
Reads a CSV file, validates columns, normalizes data, and returns
structured row objects ready for anomaly detection and import processing.

Never crashes the import pipeline due to a single bad row.
"""
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = {"date", "description", "payer", "amount", "currency", "participants", "split_type"}

SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}

SETTLEMENT_KEYWORDS = {
    "paid back", "reimbursement", "reimburse", "payback", "pay back",
    "settled", "settlement", "transfer", "repaid", "repay",
}

def normalize_header(header):
    """Lowercase and strip all headers for flexible CSV format support."""
    return header.strip().lower().replace(" ", "_")

def detect_settlement_from_description(description):
    """Heuristically detect if a row is a settlement disguised as an expense."""
    desc_lower = (description or "").lower()
    return any(kw in desc_lower for kw in SETTLEMENT_KEYWORDS)

def parse_date(date_str):
    """Try multiple date formats and return a date object or None."""
    if not date_str:
        return None, "Missing date"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date(), None
        except ValueError:
            continue
    return None, f"Unrecognised date format: '{date_str}'"

def parse_amount(amount_str):
    """Parse an amount string to Decimal or return None with error message."""
    if not amount_str:
        return None, "Missing amount"
    try:
        cleaned = amount_str.strip().replace(",", "").lstrip("₹$€£")
        return Decimal(cleaned), None
    except InvalidOperation:
        return None, f"Invalid amount: '{amount_str}'"

def parse_participants(participants_str):
    """Parse a comma-separated list of participant usernames."""
    if not participants_str:
        return []
    return [p.strip() for p in participants_str.split(",") if p.strip()]

def parse_splits_data(splits_str, split_type):
    """
    Parse optional splits data in 'user:value,user:value' format.
    Used for percentage, shares, or exact split types.
    """
    if not splits_str or split_type == "equal":
        return [], None
    try:
        splits = []
        for item in splits_str.split(","):
            user, value = item.strip().split(":")
            splits.append({"username": user.strip(), "value": value.strip()})
        return splits, None
    except Exception:
        return [], f"Invalid splits format: '{splits_str}'"

def parse_csv(file_content):
    """
    Parse CSV content (bytes or string) into a list of structured row dicts.
    
    Returns:
        rows: list of dicts with keys:
            - row_number
            - raw_data (original row dict)
            - parsed (dict with typed fields, or None on complete failure)
            - parse_errors (list of error strings)
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(file_content))
    
    # Normalize headers
    if reader.fieldnames is None:
        return [], ["CSV file has no headers or is empty."]

    normalized_fieldnames = [normalize_header(f) for f in reader.fieldnames]
    
    missing_required = REQUIRED_COLUMNS - set(normalized_fieldnames)
    if missing_required:
        return [], [f"Missing required columns: {', '.join(sorted(missing_required))}"]

    rows = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is headers
        # Normalize keys
        row = {normalize_header(k): v for k, v in raw_row.items() if k}
        parse_errors = []

        # Parse date
        parsed_date, date_err = parse_date(row.get("date", ""))
        if date_err:
            parse_errors.append(date_err)

        # Parse amount
        parsed_amount, amount_err = parse_amount(row.get("amount", ""))
        if amount_err:
            parse_errors.append(amount_err)

        # Normalize currency
        currency = (row.get("currency", "INR") or "INR").strip().upper()

        # Parse participants
        participants = parse_participants(row.get("participants", ""))

        # Detect split type
        split_type = (row.get("split_type", "equal") or "equal").strip().lower()

        # Parse splits data (optional column)
        splits_data, splits_err = parse_splits_data(row.get("splits_data", ""), split_type)
        if splits_err:
            parse_errors.append(splits_err)

        # Detect if settlement
        description = row.get("description", "").strip()
        is_possible_settlement = detect_settlement_from_description(description)

        parsed = {
            "date": parsed_date,
            "description": description,
            "payer": (row.get("payer", "") or "").strip(),
            "amount": parsed_amount,
            "currency": currency,
            "participants": participants,
            "split_type": split_type,
            "splits_data": splits_data,
            "notes": row.get("notes", ""),
            "category": (row.get("category", "general") or "general").strip().lower(),
            "is_possible_settlement": is_possible_settlement,
        }

        # JSON-safe version for storage in JSONField (date -> str, Decimal -> str)
        def to_json_safe(obj):
            if obj is None:
                return None
            from decimal import Decimal as D
            import datetime
            if isinstance(obj, datetime.date):
                return obj.isoformat()
            if isinstance(obj, D):
                return str(obj)
            return obj

        json_safe_parsed = {k: to_json_safe(v) for k, v in parsed.items()}

        rows.append({
            "row_number": i,
            "raw_data": dict(raw_row),
            "parsed": parsed if not parse_errors else None,
            "partial_parsed": json_safe_parsed,  # JSON-safe for storage in JSONField
            "parse_errors": parse_errors,
        })

    return rows, []
