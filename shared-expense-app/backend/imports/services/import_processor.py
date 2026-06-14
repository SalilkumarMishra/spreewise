"""
Import Processor
================
Orchestrates the full import pipeline:
  1. Parse CSV rows
  2. Detect anomalies
  3. Pause if REVIEW_REQUIRED anomalies exist
  4. Create Expense or Settlement via service layers (never bypass)
  5. Trigger balance recalculation on completion

Critical rule: NEVER directly manipulate balances. NEVER bypass service layers.
"""
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from imports.models import ImportJob, ImportRow, ImportAnomaly
from imports.services.csv_parser import parse_csv
from imports.services.anomaly_detector import (
    detect_anomalies, POLICY_REJECT, POLICY_REVIEW_REQUIRED
)
from imports.services.report_service import generate_report
from expenses.services.expense_service import create_expense
from settlements.services.settlement_service import create_settlement
from balance_engine.services.balance_service import recalculate_group_balances

User = get_user_model()

def process_import_job(import_job, csv_content, group, importer_user):
    """
    Full import pipeline for a single ImportJob.

    Args:
        import_job    : ImportJob instance (already created)
        csv_content   : raw bytes or str of the CSV file
        group         : Group instance
        importer_user : User who triggered the import
    """
    import_job.status = "processing"
    import_job.save(update_fields=["status"])

    # ── Step 1: Parse CSV ────────────────────────────────────────────────
    rows, file_errors = parse_csv(csv_content)

    if file_errors:
        import_job.status = "failed"
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=["status", "completed_at"])
        return import_job

    # ── Step 2: Create ImportRow & detect anomalies ─────────────────────
    any_review_required = False

    for row_data in rows:
        import_row = ImportRow.objects.create(
            import_job=import_job,
            row_number=row_data["row_number"],
            raw_data=row_data["raw_data"],
            parsed_data=row_data.get("partial_parsed"),
            processing_status="pending",
        )

        anomalies = detect_anomalies(
            import_job=import_job,
            import_row=import_row,
            parsed=row_data["parsed"],
            partial_parsed=row_data.get("partial_parsed"),
            parse_errors=row_data["parse_errors"],
            group=group,
        )

        has_reject = any(a.detected_action == POLICY_REJECT for a in anomalies)
        has_review = any(a.detected_action == POLICY_REVIEW_REQUIRED for a in anomalies)

        if has_reject:
            import_row.processing_status = "failed"
        elif has_review:
            import_row.processing_status = "review_required"
            any_review_required = True
        elif row_data["parsed"] is None:
            import_row.processing_status = "failed"

        import_row.save(update_fields=["processing_status"])

    # ── Step 3: Pause if review is needed ──────────────────────────────
    if any_review_required:
        import_job.status = "review_required"
        import_job.save(update_fields=["status"])
        generate_report(import_job)
        return import_job

    # ── Step 4: Process valid rows ──────────────────────────────────────
    _process_valid_rows(import_job, group, importer_user)
    return import_job


def resume_import_after_decisions(import_job, group, importer_user):
    """
    Called after user has made decisions on all REVIEW_REQUIRED anomalies.
    Processes approved rows and finalizes the job.
    """
    _process_valid_rows(import_job, group, importer_user)


def _process_valid_rows(import_job, group, importer_user):
    """Process all rows that are pending (no blocking anomalies or approved)."""
    rows_to_process = import_job.rows.filter(processing_status="pending")

    for import_row in rows_to_process:
        parsed = import_row.parsed_data
        if not parsed:
            import_row.processing_status = "failed"
            import_row.save(update_fields=["processing_status"])
            continue

        try:
            _create_record_from_row(import_row, parsed, import_job, group, importer_user)
            import_row.processing_status = "imported"
        except Exception as e:
            import_row.processing_status = "failed"
            # Log the error into parsed_data for traceability
            if import_row.parsed_data:
                import_row.parsed_data["import_error"] = str(e)
        import_row.save(update_fields=["processing_status", "parsed_data"])

    # ── Step 5: Finalize job ─────────────────────────────────────────────
    remaining_review = import_job.rows.filter(processing_status="review_required").count()
    if remaining_review > 0:
        import_job.status = "review_required"
    else:
        import_job.status = "completed"
        import_job.completed_at = timezone.now()
    import_job.save(update_fields=["status", "completed_at"])

    generate_report(import_job)

    # ── Step 6: Trigger balance recalculation ────────────────────────────
    if import_job.status == "completed":
        try:
            recalculate_group_balances(group)
        except Exception:
            pass  # Balance recalculation failure does not abort import completion


@transaction.atomic
def _create_record_from_row(import_row, parsed, import_job, group, importer_user):
    """
    Create an Expense or Settlement via service layers.
    Never bypass service layers. Never directly manipulate balances.
    """
    from datetime import date as date_cls
    import datetime

    # Resolve date (may be stored as string in JSONField)
    expense_date = parsed.get("date")
    if isinstance(expense_date, str):
        expense_date = date_cls.fromisoformat(expense_date)

    amount = parsed.get("amount")
    if isinstance(amount, str):
        from decimal import Decimal
        amount = Decimal(amount)

    payer = User.objects.get(username=parsed["payer"])
    participant_usernames = parsed.get("participants", [])
    participant_users = list(User.objects.filter(username__in=participant_usernames))
    split_type = parsed.get("split_type", "equal")
    description = parsed.get("description", "")
    currency = parsed.get("currency", "INR")
    category = parsed.get("category", "general")

    # Detect if this is a settlement row
    is_settlement = parsed.get("is_possible_settlement", False)

    # Check if REVIEW_REQUIRED anomaly was approved to be treated as settlement
    review_decision = ImportAnomaly.objects.filter(
        import_row=import_row,
        anomaly_type="settlement_logged_as_expense",
    ).first()

    if review_decision and review_decision.user_decision == "approve":
        is_settlement = True

    if is_settlement and len(participant_users) >= 1:
        receiver = participant_users[0]
        settlement = create_settlement(
            group=group,
            payer=payer,
            receiver=receiver,
            amount=amount,
            currency=currency,
            payment_date=expense_date,
            creator=importer_user,
            notes=description,
            source="csv_import",
            settlement_category="imported",
        )
        settlement.import_job = import_job
        settlement.save(update_fields=["import_job"])
    else:
        if not participant_users:
            participant_users = [payer]

        expense = create_expense(
            group=group,
            title=description,
            amount=amount,
            currency=currency,
            expense_date=expense_date,
            paid_by=payer,
            split_type=split_type,
            creator=importer_user,
            participant_users=participant_users,
            notes=parsed.get("notes", ""),
            source="csv_import",
            expense_category=category if category in [
                "food", "rent", "utilities", "travel", "groceries",
                "entertainment", "settlement", "refund", "general"
            ] else "general",
        )
        expense.import_job = import_job
        expense.save(update_fields=["import_job"])
