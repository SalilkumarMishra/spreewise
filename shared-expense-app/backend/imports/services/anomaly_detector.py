"""
Anomaly Detector
================
Evaluates each parsed row against a set of rules. When a rule fires,
it creates an ImportAnomaly with a policy:

  - AUTO_FIX       : Engine handles it automatically (e.g. currency upper-case)
  - REVIEW_REQUIRED: Human must approve / reject before row is processed
  - REJECT         : Row is immediately failed, no import

Rules (A–L):
  A. Duplicate Expense
  B. Duplicate Settlement
  C. Negative Amount
  D. Zero Amount
  E. Unknown User
  F. Invalid Date
  G. Unsupported Currency
  H. Missing Required Fields
  I. User Not Active On Date
  J. Settlement Logged As Expense
  K. Currency Conversion Required
  L. Split Validation Failure
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from expenses.models import Expense
from settlements.models import Settlement
from imports.models import ImportAnomaly
from imports.services.csv_parser import SUPPORTED_CURRENCIES

User = get_user_model()

POLICY_AUTO_FIX        = "AUTO_FIX"
POLICY_REVIEW_REQUIRED = "REVIEW_REQUIRED"
POLICY_REJECT          = "REJECT"

def _create_anomaly(import_job, import_row, anomaly_type, category, severity, description, policy):
    return ImportAnomaly.objects.create(
        import_job=import_job,
        import_row=import_row,
        anomaly_type=anomaly_type,
        anomaly_category=category,
        severity=severity,
        description=description,
        detected_action=policy,
    )

def detect_anomalies(import_job, import_row, parsed, partial_parsed, parse_errors, group):
    """
    Run all anomaly rules against one row.
    Returns list of ImportAnomaly instances created.
    """
    anomalies = []

    # ── H. Missing Required Fields ─────────────────────────────────────────
    if parse_errors:
        # Check if any of the parse errors are date-related
        date_errors = [e for e in parse_errors if "date" in e.lower() or "format" in e.lower()]
        other_errors = [e for e in parse_errors if e not in date_errors]

        if date_errors:
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="invalid_date",
                category="date",
                severity="high",
                description=f"Invalid date: {'; '.join(date_errors)}",
                policy=POLICY_REJECT,
            )
            anomalies.append(a)

        if other_errors:
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="missing_required_fields",
                category="validation",
                severity="high",
                description=f"Parse errors: {'; '.join(other_errors)}",
                policy=POLICY_REJECT,
            )
            anomalies.append(a)

        # If parsed is None (critical parse errors), skip further checks
        if parsed is None and not partial_parsed:
            return anomalies

    p = parsed or partial_parsed

    # ── F. Invalid Date ──────────────────────────────────────────────────
    if p.get("date") is None:
        # Only add if not already added from parse_errors above
        if not any(a.anomaly_type == "invalid_date" for a in anomalies):
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="invalid_date",
                category="date",
                severity="high",
                description="Row has an invalid or missing date and cannot be processed.",
                policy=POLICY_REJECT,
            )
            anomalies.append(a)
        return anomalies  # Subsequent checks need a valid date

    # ── C. Negative Amount ──────────────────────────────────────────────
    amount = p.get("amount")
    if amount is not None:
        try:
            from decimal import Decimal as D
            amount = D(str(amount))
        except Exception:
            amount = None
    if amount is not None and amount < 0:
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="negative_amount",
            category="validation",
            severity="medium",
            description=f"Amount is negative: {amount}. Financial amounts must be positive (e.g. refund).",
            policy=POLICY_REVIEW_REQUIRED,
        )
        anomalies.append(a)

    # ── D. Zero Amount ──────────────────────────────────────────────────
    if amount is not None and amount == Decimal("0.00"):
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="zero_amount",
            category="validation",
            severity="high",
            description="Amount is zero. This row likely represents a placeholder or error.",
            policy=POLICY_REJECT,
        )
        anomalies.append(a)

    # ── G. Unsupported Currency / K. Currency Conversion Required ───────
    currency = p.get("currency", "INR")
    if currency not in SUPPORTED_CURRENCIES:
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="unsupported_currency",
            category="currency",
            severity="high",
            description=f"Currency '{currency}' is not supported. Supported: {SUPPORTED_CURRENCIES}",
            policy=POLICY_REJECT,
        )
        anomalies.append(a)
    elif currency != (group.currency or "INR").upper():
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="currency_conversion_required",
            category="currency",
            severity="medium",
            description=f"Row currency '{currency}' differs from group currency '{group.currency}'. Manual conversion review required.",
            policy=POLICY_REVIEW_REQUIRED,
        )
        anomalies.append(a)

    # ── E. Unknown User (payer) ──────────────────────────────────────────
    payer_username = p.get("payer", "")
    payer_user = None
    resolved_user_id = p.get("resolved_user_id")
    if resolved_user_id:
        try:
            payer_user = User.objects.get(id=resolved_user_id)
        except User.DoesNotExist:
            pass

    if not payer_user:
        if payer_username:
            try:
                payer_user = User.objects.get(username=payer_username)
            except User.DoesNotExist:
                a = _create_anomaly(
                    import_job, import_row,
                    anomaly_type="unknown_user",
                    category="unknown_user",
                    severity="medium",
                    description=f"Payer '{payer_username}' does not exist in the system.",
                    policy=POLICY_REVIEW_REQUIRED,
                )
                anomalies.append(a)
        else:
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="missing_payer",
                category="validation",
                severity="high",
                description="Payer field is empty. Cannot process row without a payer.",
                policy=POLICY_REVIEW_REQUIRED,
            )
            anomalies.append(a)

    # ── E. Unknown User (participants) ───────────────────────────────────
    unknown_participants = []
    for username in p.get("participants", []):
        if not User.objects.filter(username=username).exists():
            unknown_participants.append(username)
    if unknown_participants:
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="unknown_participant",
            category="unknown_user",
            severity="high",
            description=f"Unknown participants: {', '.join(unknown_participants)}",
            policy=POLICY_REVIEW_REQUIRED,
        )
        anomalies.append(a)

    # ── I. User Not Active On Date ────────────────────────────────────────
    expense_date = p.get("date")
    if payer_user and expense_date:
        if not group.is_user_member_on_date(payer_user, expense_date):
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="payer_not_active_on_date",
                category="membership",
                severity="high",
                description=f"Payer '{payer_username}' was not an active member of '{group.name}' on {expense_date}.",
                policy=POLICY_REJECT,
            )
            anomalies.append(a)

        # Check each participant
        for username in p.get("participants", []):
            try:
                participant = User.objects.get(username=username)
                if not group.is_user_member_on_date(participant, expense_date):
                    a = _create_anomaly(
                        import_job, import_row,
                        anomaly_type="participant_not_active_on_date",
                        category="membership",
                        severity="high",
                        description=f"Participant '{username}' was not an active member of '{group.name}' on {expense_date}.",
                        policy=POLICY_REJECT,
                    )
                    anomalies.append(a)
            except User.DoesNotExist:
                pass  # Already caught above

    # ── J. Settlement Logged As Expense ──────────────────────────────────
    if p.get("is_possible_settlement"):
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="settlement_logged_as_expense",
            category="settlement",
            severity="high",
            description=f"Row description '{p.get('description')}' suggests this may be a settlement/reimbursement, not a shared expense.",
            policy=POLICY_REVIEW_REQUIRED,
        )
        anomalies.append(a)

    # ── A. Duplicate Expense ─────────────────────────────────────────────
    if (p.get("date") and amount and payer_user and
            not p.get("is_possible_settlement")):
        duplicate_qs = Expense.objects.filter(
            group=group,
            expense_date=p["date"],
            amount=amount,
            paid_by=payer_user,
            title=p.get("description", ""),
            is_archived=False,
        )
        if duplicate_qs.exists():
            a = _create_anomaly(
                import_job, import_row,
                anomaly_type="duplicate_expense",
                category="duplicate",
                severity="high",
                description=f"A matching expense ('{p.get('description')}', {amount}, {p['date']}) already exists for this group.",
                policy=POLICY_REVIEW_REQUIRED,
            )
            anomalies.append(a)

    # ── B. Duplicate Settlement ──────────────────────────────────────────
    if (p.get("is_possible_settlement") and p.get("date") and amount and payer_user):
        participants = p.get("participants", [])
        if participants:
            try:
                receiver = User.objects.get(username=participants[0])
                dup_settlement = Settlement.objects.filter(
                    group=group,
                    payment_date=p["date"],
                    amount=amount,
                    payer=payer_user,
                    receiver=receiver,
                    is_archived=False,
                )
                if dup_settlement.exists():
                    a = _create_anomaly(
                        import_job, import_row,
                        anomaly_type="duplicate_settlement",
                        category="duplicate",
                        severity="high",
                        description=f"A matching settlement ({payer_username} -> {participants[0]}, {amount}, {p['date']}) already exists.",
                        policy=POLICY_REVIEW_REQUIRED,
                    )
                    anomalies.append(a)
            except User.DoesNotExist:
                pass

    # ── L. Split Validation Failure ──────────────────────────────────────
    split_type = p.get("split_type", "equal")
    splits_data = p.get("splits_data", [])
    participants = p.get("participants", [])
    if split_type != "equal" and not splits_data:
        a = _create_anomaly(
            import_job, import_row,
            anomaly_type="split_validation_failure",
            category="split",
            severity="high",
            description=f"split_type is '{split_type}' but no splits_data provided.",
            policy=POLICY_REJECT,
        )
        anomalies.append(a)
    elif split_type == "percentage" and splits_data:
        try:
            total_pct = sum(Decimal(s["value"]) for s in splits_data)
            if abs(total_pct - Decimal("100")) > Decimal("0.01"):
                a = _create_anomaly(
                    import_job, import_row,
                    anomaly_type="split_validation_failure",
                    category="split",
                    severity="critical",
                    description=f"Invalid percentage split: total percentages sum to {total_pct}% instead of 100%.",
                    policy=POLICY_REJECT,
                )
                anomalies.append(a)
        except Exception:
            pass
    elif split_type == "exact" and splits_data and amount is not None:
        try:
            total_exact = sum(Decimal(s["value"]) for s in splits_data)
            if abs(total_exact - amount) > Decimal("0.01"):
                a = _create_anomaly(
                    import_job, import_row,
                    anomaly_type="split_validation_failure",
                    category="split",
                    severity="high",
                    description=f"Invalid exact split: splits sum to {total_exact} instead of the total amount {amount}.",
                    policy=POLICY_REJECT,
                )
                anomalies.append(a)
        except Exception:
            pass

    # ── M. Date Ambiguity ────────────────────────────────────────────────
    raw_date = import_row.raw_data.get("date", "") if import_row and import_row.raw_data else ""
    if raw_date:
        import re
        match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-]\d{4}\b', raw_date)
        if match:
            val1 = int(match.group(1))
            val2 = int(match.group(2))
            if 1 <= val1 <= 12 and 1 <= val2 <= 12 and val1 != val2:
                a = _create_anomaly(
                    import_job, import_row,
                    anomaly_type="date_ambiguity",
                    category="date",
                    severity="high",
                    description=f"Date '{raw_date}' is ambiguous (could be {val1} month / {val2} day or vice versa).",
                    policy=POLICY_REVIEW_REQUIRED,
                )
                anomalies.append(a)

    return anomalies
