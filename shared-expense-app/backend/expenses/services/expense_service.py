"""
Expense Service Layer
=====================
Centralises all expense business logic.
Re-used by: Expense API, CSV Import Engine, Balance Engine.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from expenses.models import Expense, ExpenseParticipant, ExpenseSplit, ExpenseSnapshot

User = get_user_model()

# ---------------------------------------------------------------------------
# Membership Eligibility Validation
# ---------------------------------------------------------------------------

def validate_membership_eligibility(group, expense_date, paid_by, participants):
    """
    Validate that the group is active, the payer, and all participants
    were active members of the group on the given expense_date.

    This is a reusable service called by:
    - Expense creation
    - CSV Import Engine
    - Balance Engine checks

    Raises ValidationError with a descriptive message on any violation.
    """
    if group.is_archived:
        raise ValidationError(f"Group '{group.name}' is archived. Cannot add expenses.")

    if not group.is_user_member_on_date(paid_by, expense_date):
        raise ValidationError(
            f"Payer '{paid_by.username}' was not an active member of "
            f"'{group.name}' on {expense_date}."
        )

    for user in participants:
        if not group.is_user_member_on_date(user, expense_date):
            raise ValidationError(
                f"Participant '{user.username}' was not an active member of "
                f"'{group.name}' on {expense_date}."
            )


# ---------------------------------------------------------------------------
# Split Calculation
# ---------------------------------------------------------------------------

def calculate_split_amounts(split_type, total_amount, participant_users, splits_data):
    """
    Calculate the final split amounts for each participant.

    Parameters:
    -----------
    split_type       : str  - 'equal', 'percentage', 'shares', 'exact'
    total_amount     : Decimal
    participant_users: list of User objects (in order)
    splits_data      : list of dicts (one per participant), structured differently per split type:
        equal      -> not needed (ignored)
        percentage -> [{"user_id": X, "percentage_value": 30.0}, ...]
        shares     -> [{"user_id": X, "shares_value": 2}, ...]
        exact      -> [{"user_id": X, "exact_amount": 400.00}, ...]

    Returns: list of dicts:
        [{"user": <User>, "calculated_amount": Decimal, "percentage_value": ..., ...}]
    """
    total_amount = Decimal(str(total_amount))
    user_map = {u.id: u for u in participant_users}

    if split_type == "equal":
        n = len(participant_users)
        if n == 0:
            raise ValidationError("At least one participant is required.")
        base_share = (total_amount / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remainder = total_amount - (base_share * n)

        results = []
        for i, user in enumerate(participant_users):
            amount = base_share + (remainder if i == 0 else Decimal("0.00"))
            results.append({
                "user": user,
                "calculated_amount": amount,
                "percentage_value": None,
                "shares_value": None,
                "exact_amount": None,
            })
        return results

    elif split_type == "percentage":
        total_pct = sum(Decimal(str(s["percentage_value"])) for s in splits_data)
        if abs(total_pct - Decimal("100")) > Decimal("0.01"):
            raise ValidationError(
                f"Percentage values must sum to 100. Got {total_pct}."
            )

        results = []
        computed_total = Decimal("0.00")
        for i, s in enumerate(splits_data):
            pct = Decimal(str(s["percentage_value"]))
            if i < len(splits_data) - 1:
                amount = (total_amount * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                # Last person absorbs the rounding remainder
                amount = total_amount - computed_total
            computed_total += amount
            user = user_map[s["user_id"]]
            results.append({
                "user": user,
                "calculated_amount": amount,
                "percentage_value": pct,
                "shares_value": None,
                "exact_amount": None,
            })
        return results

    elif split_type == "shares":
        total_shares = sum(Decimal(str(s["shares_value"])) for s in splits_data)
        if total_shares <= 0:
            raise ValidationError("Total shares must be greater than 0.")

        results = []
        computed_total = Decimal("0.00")
        for i, s in enumerate(splits_data):
            share = Decimal(str(s["shares_value"]))
            if i < len(splits_data) - 1:
                amount = (total_amount * share / total_shares).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                amount = total_amount - computed_total
            computed_total += amount
            user = user_map[s["user_id"]]
            results.append({
                "user": user,
                "calculated_amount": amount,
                "percentage_value": None,
                "shares_value": share,
                "exact_amount": None,
            })
        return results

    elif split_type == "exact":
        exact_total = sum(Decimal(str(s["exact_amount"])) for s in splits_data)
        if abs(exact_total - total_amount) > Decimal("0.01"):
            raise ValidationError(
                f"Exact split amounts must sum to {total_amount}. Got {exact_total}."
            )

        results = []
        for s in splits_data:
            exact = Decimal(str(s["exact_amount"]))
            user = user_map[s["user_id"]]
            results.append({
                "user": user,
                "calculated_amount": exact,
                "percentage_value": None,
                "shares_value": None,
                "exact_amount": exact,
            })
        return results

    else:
        raise ValidationError(f"Unknown split_type: '{split_type}'.")


# ---------------------------------------------------------------------------
# Snapshot Builder
# ---------------------------------------------------------------------------

def _build_snapshot_payload(expense, participants, splits, version):
    """Build the JSON payload for an ExpenseSnapshot."""
    return {
        "version": version,
        "expense": {
            "id": expense.id,
            "title": expense.title,
            "amount": str(expense.amount),
            "currency": expense.currency,
            "original_amount": str(expense.original_amount),
            "original_currency": expense.original_currency,
            "expense_date": str(expense.expense_date),
            "split_type": expense.split_type,
            "status": expense.status,
            "expense_category": expense.expense_category,
            "source": expense.source,
            "paid_by_id": expense.paid_by_id,
            "group_id": expense.group_id,
            "notes": expense.notes,
        },
        "participants": [
            {"user_id": p.user_id, "username": p.user.username}
            for p in participants
        ],
        "splits": [
            {
                "user_id": s.user_id,
                "username": s.user.username,
                "calculated_amount": str(s.calculated_amount),
                "percentage_value": str(s.percentage_value) if s.percentage_value is not None else None,
                "shares_value": str(s.shares_value) if s.shares_value is not None else None,
                "exact_amount": str(s.exact_amount) if s.exact_amount is not None else None,
            }
            for s in splits
        ],
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_inputs(group, amount, paid_by, participant_users, splits_data, split_type):
    """Pre-creation validation independent of membership dates."""
    if amount <= 0:
        raise ValidationError("Expense amount must be greater than 0.")

    if not participant_users:
        raise ValidationError("At least one participant is required.")

    if len(participant_users) != len(set(u.id for u in participant_users)):
        raise ValidationError("Duplicate participants are not allowed.")

    if split_type in ("percentage", "shares", "exact") and not splits_data:
        raise ValidationError(
            f"Split data is required for split_type='{split_type}'."
        )

    if split_type in ("percentage", "shares", "exact"):
        split_user_ids = {s["user_id"] for s in splits_data}
        participant_ids = {u.id for u in participant_users}
        if split_user_ids != participant_ids:
            raise ValidationError(
                "Split data user_ids must exactly match participant user_ids."
            )


# ---------------------------------------------------------------------------
# Create Expense
# ---------------------------------------------------------------------------

@transaction.atomic
def create_expense(
    group,
    title,
    amount,
    currency,
    expense_date,
    paid_by,
    split_type,
    creator,
    participant_users,
    splits_data=None,
    description="",
    notes="",
    original_amount=None,
    original_currency=None,
    status="active",
    expense_category="general",
    source="manual",
):
    """
    Create an Expense with participants, splits, and an initial snapshot.

    Parameters:
    -----------
    participant_users : list of User objects
    splits_data       : list of dicts (required for non-equal splits)
    """
    amount = Decimal(str(amount))
    original_amount = Decimal(str(original_amount)) if original_amount is not None else amount
    original_currency = original_currency or currency

    # Step 1: Pre-create validation
    _validate_inputs(group, amount, paid_by, participant_users, splits_data or [], split_type)

    # Step 2: Membership eligibility check
    validate_membership_eligibility(group, expense_date, paid_by, participant_users)

    # Step 3: Calculate splits
    calculated_splits = calculate_split_amounts(
        split_type, amount, participant_users, splits_data or []
    )

    # Step 4: Create Expense
    expense = Expense.objects.create(
        group=group,
        title=title,
        description=description,
        amount=amount,
        currency=currency,
        original_amount=original_amount,
        original_currency=original_currency,
        expense_date=expense_date,
        paid_by=paid_by,
        split_type=split_type,
        status=status,
        expense_category=expense_category,
        source=source,
        notes=notes,
        created_by=creator,
    )

    # Step 5: Create Participants
    participant_objs = []
    for user in participant_users:
        p = ExpenseParticipant.objects.create(expense=expense, user=user)
        participant_objs.append(p)

    # Step 6: Create Splits
    split_objs = []
    for split in calculated_splits:
        s = ExpenseSplit.objects.create(
            expense=expense,
            user=split["user"],
            percentage_value=split["percentage_value"],
            shares_value=split["shares_value"],
            exact_amount=split["exact_amount"],
            calculated_amount=split["calculated_amount"],
        )
        split_objs.append(s)

    # Step 7: Create initial snapshot (version 1)
    # Re-fetch with select_related for snapshot builder
    for p in participant_objs:
        p.user = next(u for u in participant_users if u.id == p.user_id)
    for s in split_objs:
        s.user = next(u for u in participant_users if u.id == s.user_id)

    payload = _build_snapshot_payload(expense, participant_objs, split_objs, version=1)
    ExpenseSnapshot.objects.create(expense=expense, version=1, payload_json=payload)

    return expense


# ---------------------------------------------------------------------------
# Update Expense
# ---------------------------------------------------------------------------

@transaction.atomic
def update_expense(
    expense,
    title=None,
    amount=None,
    currency=None,
    expense_date=None,
    paid_by=None,
    split_type=None,
    participant_users=None,
    splits_data=None,
    description=None,
    notes=None,
    original_amount=None,
    original_currency=None,
    status=None,
    expense_category=None,
    source=None,
):
    """
    Update an Expense and regenerate participants, splits, and a new versioned snapshot.
    """
    # Apply updates to scalar fields
    if title is not None:
        expense.title = title
    if amount is not None:
        expense.amount = Decimal(str(amount))
    if currency is not None:
        expense.currency = currency
    if expense_date is not None:
        expense.expense_date = expense_date
    if paid_by is not None:
        expense.paid_by = paid_by
    if split_type is not None:
        expense.split_type = split_type
    if description is not None:
        expense.description = description
    if notes is not None:
        expense.notes = notes
    if original_amount is not None:
        expense.original_amount = Decimal(str(original_amount))
    if original_currency is not None:
        expense.original_currency = original_currency
    if status is not None:
        expense.status = status
    if expense_category is not None:
        expense.expense_category = expense_category
    if source is not None:
        expense.source = source

    effective_participants = participant_users if participant_users is not None else list(
        User.objects.filter(expense_participations__expense=expense)
    )
    effective_split_type = expense.split_type
    effective_amount = expense.amount

    # Validate
    _validate_inputs(expense.group, effective_amount, expense.paid_by, effective_participants,
                     splits_data or [], effective_split_type)
    validate_membership_eligibility(expense.group, expense.expense_date, expense.paid_by,
                                    effective_participants)

    expense.save()

    # Recalculate splits
    calculated_splits = calculate_split_amounts(
        effective_split_type, effective_amount, effective_participants, splits_data or []
    )

    # Replace participants and splits
    expense.participants.all().delete()
    expense.splits.all().delete()

    participant_objs = []
    for user in effective_participants:
        p = ExpenseParticipant.objects.create(expense=expense, user=user)
        p.user = user
        participant_objs.append(p)

    split_objs = []
    for split in calculated_splits:
        s = ExpenseSplit.objects.create(
            expense=expense,
            user=split["user"],
            percentage_value=split["percentage_value"],
            shares_value=split["shares_value"],
            exact_amount=split["exact_amount"],
            calculated_amount=split["calculated_amount"],
        )
        s.user = split["user"]
        split_objs.append(s)

    # Create new versioned snapshot
    latest_version = expense.snapshots.count()
    new_version = latest_version + 1
    payload = _build_snapshot_payload(expense, participant_objs, split_objs, version=new_version)
    ExpenseSnapshot.objects.create(expense=expense, version=new_version, payload_json=payload)

    return expense
