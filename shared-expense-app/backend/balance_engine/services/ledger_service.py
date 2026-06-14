from expenses.models import Expense
from settlements.models import Settlement
from expenses.services import expense_service
from settlements.services import settlement_service

def get_group_ledger(group):
    """
    Returns a unified, chronologically sorted ledger of all events
    (expenses and settlements) for the given group.
    Returns a list of BalanceEvents.
    """
    ledger = []

    # Get all active expenses
    expenses = Expense.objects.filter(group=group, is_archived=False)
    for exp in expenses:
        ledger.append(expense_service.generate_balance_ledger_entry(exp))

    # Get all active settlements
    settlements = Settlement.objects.filter(group=group, is_archived=False)
    for stl in settlements:
        ledger.append(settlement_service.generate_balance_ledger_entry(stl))

    # Sort chronologically by event_date
    ledger.sort(key=lambda x: x["event_date"])
    return ledger

def get_user_ledger(group, user):
    """
    Filters the group ledger to only include events affecting the given user.
    """
    group_ledger = get_group_ledger(group)
    user_ledger = []
    
    for event in group_ledger:
        # Check if user has an entry with a non-zero delta
        for entry in event["entries"]:
            if entry["user_id"] == user.id and entry["delta"] != 0:
                user_ledger.append(event)
                break
                
    return user_ledger
