from decimal import Decimal
from django.contrib.auth import get_user_model
from balance_engine.services.ledger_service import get_group_ledger
from balance_engine.models import BalanceSnapshot

User = get_user_model()

def calculate_group_balances(group):
    """
    Computes net balances for all group members from the ledger.
    Returns:
    [
        {"user_id": X, "user": "Aisha", "balance": Decimal(2000.00)},
        {"user_id": Y, "user": "Rohan", "balance": Decimal(-1200.00)}
    ]
    """
    ledger = get_group_ledger(group)
    balances_map = {}

    for event in ledger:
        for entry in event["entries"]:
            uid = entry["user_id"]
            if uid not in balances_map:
                balances_map[uid] = Decimal("0.00")
            balances_map[uid] += Decimal(str(entry["delta"]))

    # Add 0.00 for active members who have no activity
    for membership in group.memberships.filter(is_active=True).select_related("user"):
        if membership.user_id not in balances_map:
            balances_map[membership.user_id] = Decimal("0.00")

    result = []
    # Pre-fetch users to avoid N+1
    users = {u.id: u for u in User.objects.filter(id__in=balances_map.keys())}
    
    for uid, balance in balances_map.items():
        user = users.get(uid)
        username = user.username if user else f"User {uid}"
        result.append({
            "user_id": uid,
            "user": username,
            "balance": balance
        })

    return result

def calculate_user_balance(group, user):
    """
    Computes total_paid, total_owed, and net_balance for a specific user.
    """
    ledger = get_group_ledger(group)
    total_paid = Decimal("0.00") # Credits (+)
    total_owed = Decimal("0.00") # Debits (-)
    net_balance = Decimal("0.00")

    for event in ledger:
        for entry in event["entries"]:
            if entry["user_id"] == user.id:
                delta = Decimal(str(entry["delta"]))
                net_balance += delta
                if delta > 0:
                    total_paid += delta
                else:
                    total_owed += abs(delta)

    return {
        "user_id": user.id,
        "total_paid": total_paid,
        "total_owed": total_owed,
        "net_balance": net_balance
    }

def validate_balance_invariants(group):
    """
    Validates the mathematical correctness of balances.
    """
    report = {
        "is_valid": True,
        "errors": []
    }
    
    balances = calculate_group_balances(group)
    sum_balances = sum(b["balance"] for b in balances)
    
    if sum_balances != Decimal("0.00"):
        report["is_valid"] = False
        report["errors"].append(f"Sum of all balances must be 0. Got {sum_balances}")
        
    ledger = get_group_ledger(group)
    for event in ledger:
        event_sum = sum(Decimal(str(entry["delta"])) for entry in event["entries"])
        if event_sum != Decimal("0.00"):
            report["is_valid"] = False
            report["errors"].append(f"Ledger event {event['reference_id']} delta sum is {event_sum}, not 0.")

    # Also check that no user appears as both debtor and creditor in simplifications (done later in simpl_service but good to conceptually link)
    return report

def recalculate_group_balances(group):
    """
    Recalculates group balances and creates a BalanceSnapshot.
    Useful after bulk CSV imports.
    """
    balances = calculate_group_balances(group)
    
    payload = {
        "group_id": group.id,
        "balances": [
            {
                "user_id": b["user_id"],
                "user": b["user"],
                "balance": str(b["balance"])
            }
            for b in balances
        ]
    }
    
    snapshot = BalanceSnapshot.objects.create(
        group=group,
        payload_json=payload
    )
    
    return balances, snapshot
