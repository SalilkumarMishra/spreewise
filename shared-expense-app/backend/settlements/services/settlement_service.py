import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from settlements.models import Settlement, SettlementSnapshot

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_settlement(group, payer, receiver, amount, payment_date):
    """
    Validate business rules for a settlement.
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Settlement amount must be greater than 0.")

    if payer.id == receiver.id:
        raise ValidationError("Payer and receiver cannot be the same person.")

    if group.is_archived:
        raise ValidationError(f"Group '{group.name}' is archived. Cannot add settlements.")

    if not group.is_user_member_on_date(payer, payment_date):
        raise ValidationError(
            f"Payer '{payer.username}' was not an active member of "
            f"'{group.name}' on {payment_date}."
        )

    if not group.is_user_member_on_date(receiver, payment_date):
        raise ValidationError(
            f"Receiver '{receiver.username}' was not an active member of "
            f"'{group.name}' on {payment_date}."
        )

# ---------------------------------------------------------------------------
# Snapshot Builder
# ---------------------------------------------------------------------------

def _build_snapshot_payload(settlement, version):
    return {
        "version": version,
        "reference_id": settlement.reference_id,
        "settlement": {
            "id": settlement.id,
            "group_id": settlement.group_id,
            "payer_id": settlement.payer_id,
            "receiver_id": settlement.receiver_id,
            "amount": str(settlement.amount),
            "currency": settlement.currency,
            "original_amount": str(settlement.original_amount),
            "original_currency": settlement.original_currency,
            "payment_date": str(settlement.payment_date),
            "notes": settlement.notes,
            "settlement_category": settlement.settlement_category,
            "source": settlement.source,
            "status": settlement.status,
        }
    }

# ---------------------------------------------------------------------------
# Reference ID Generator
# ---------------------------------------------------------------------------

def generate_reference_id():
    """Generate a unique reference ID for a settlement like SET-2026-000001"""
    year = timezone.now().year
    # For a real system we might use a sequence or UUID. Using a short UUID for simplicity while meeting uniqueness.
    short_uuid = str(uuid.uuid4().hex)[:6].upper()
    # If we need exact sequential like SET-2026-000001, we would query max ID. For now:
    last_settlement = Settlement.objects.order_by("id").last()
    next_id = (last_settlement.id + 1) if last_settlement else 1
    return f"SET-{year}-{next_id:06d}"

# ---------------------------------------------------------------------------
# Create & Update
# ---------------------------------------------------------------------------

@transaction.atomic
def create_settlement(
    group, payer, receiver, amount, currency, payment_date, creator,
    original_amount=None, original_currency=None, notes="",
    settlement_category="direct_payment", source="manual", status="active"
):
    amount = Decimal(str(amount))
    original_amount = Decimal(str(original_amount)) if original_amount is not None else amount
    original_currency = original_currency or currency

    validate_settlement(group, payer, receiver, amount, payment_date)

    ref_id = generate_reference_id()

    settlement = Settlement.objects.create(
        reference_id=ref_id,
        group=group,
        payer=payer,
        receiver=receiver,
        amount=amount,
        currency=currency,
        original_amount=original_amount,
        original_currency=original_currency,
        payment_date=payment_date,
        notes=notes,
        settlement_category=settlement_category,
        source=source,
        status=status,
        created_by=creator
    )

    payload = _build_snapshot_payload(settlement, version=1)
    SettlementSnapshot.objects.create(
        settlement=settlement,
        version=1,
        payload_json=payload
    )

    return settlement

@transaction.atomic
def update_settlement(
    settlement,
    amount=None, currency=None, payment_date=None,
    payer=None, receiver=None,
    original_amount=None, original_currency=None, notes=None,
    settlement_category=None, source=None, status=None
):
    if amount is not None:
        settlement.amount = Decimal(str(amount))
    if currency is not None:
        settlement.currency = currency
    if payment_date is not None:
        settlement.payment_date = payment_date
    if payer is not None:
        settlement.payer = payer
    if receiver is not None:
        settlement.receiver = receiver
    if original_amount is not None:
        settlement.original_amount = Decimal(str(original_amount))
    if original_currency is not None:
        settlement.original_currency = original_currency
    if notes is not None:
        settlement.notes = notes
    if settlement_category is not None:
        settlement.settlement_category = settlement_category
    if source is not None:
        settlement.source = source
    if status is not None:
        settlement.status = status

    validate_settlement(
        settlement.group, settlement.payer, settlement.receiver, 
        settlement.amount, settlement.payment_date
    )

    settlement.save()

    latest_version = settlement.snapshots.count()
    new_version = latest_version + 1
    payload = _build_snapshot_payload(settlement, version=new_version)
    SettlementSnapshot.objects.create(
        settlement=settlement,
        version=new_version,
        payload_json=payload
    )

    return settlement

# ---------------------------------------------------------------------------
# Explainability & Prep Helpers
# ---------------------------------------------------------------------------

def get_settlement_breakdown(settlement):
    amount = settlement.amount
    return {
        "settlement_id": settlement.id,
        "reference_id": settlement.reference_id,
        "payer": settlement.payer.username,
        "receiver": settlement.receiver.username,
        "amount": str(amount),
        "currency": settlement.currency,
        "payment_date": str(settlement.payment_date),
        "notes": settlement.notes,
        "category": settlement.settlement_category,
        "source": settlement.source,
        "status": settlement.status,
        "balance_effect": {
            "payer": -amount,
            "receiver": amount,
        }
    }

def calculate_settlement_effect(settlement):
    """
    Returns the effect of a settlement on balances.
    Payer's balance increases (+), Receiver's balance decreases (-).
    """
    amount = settlement.amount
    return {
        "event_type": "settlement",
        "reference_id": settlement.reference_id,
        "payer": settlement.payer.username,
        "payer_id": settlement.payer_id,
        "receiver": settlement.receiver.username,
        "receiver_id": settlement.receiver_id,
        "amount": str(amount),
        "effects": {
            settlement.payer_id: amount,
            settlement.receiver_id: -amount,
        }
    }

def generate_balance_event(settlement):
    """
    Generates the balance event representation of this settlement.
    """
    return calculate_settlement_effect(settlement)

def generate_balance_ledger_entry(settlement):
    """
    Returns the normalized ledger format for the Balance Engine.
    """
    amount = settlement.amount
    return {
        "event_type": "settlement",
        "reference_id": settlement.reference_id,
        "event_date": str(settlement.payment_date),
        "entries": [
            {
                "user_id": settlement.payer_id,
                "delta": amount
            },
            {
                "user_id": settlement.receiver_id,
                "delta": -amount
            }
        ]
    }

# ---------------------------------------------------------------------------
# Import Compatibility Check
# ---------------------------------------------------------------------------

def settlement_can_be_imported(payload):
    """
    Validate if a raw payload (from CSV/external) can be imported.
    """
    errors = []
    
    amount = payload.get("amount")
    if amount is None or Decimal(str(amount)) <= 0:
        errors.append("Invalid or missing amount.")
        
    payer_id = payload.get("payer_id")
    receiver_id = payload.get("receiver_id")
    if payer_id and receiver_id and payer_id == receiver_id:
        errors.append("Payer and receiver cannot be the same person.")
    elif not payer_id or not receiver_id:
        errors.append("Both payer_id and receiver_id are required.")
        
    payment_date = payload.get("payment_date")
    if not payment_date:
        errors.append("Missing payment_date.")
        
    category = payload.get("settlement_category")
    if category and category not in [c[0] for c in Settlement.CATEGORY_CHOICES]:
        errors.append(f"Invalid settlement_category '{category}'.")
        
    return len(errors) == 0, errors
