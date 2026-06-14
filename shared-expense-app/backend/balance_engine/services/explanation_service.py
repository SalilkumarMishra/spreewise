from decimal import Decimal
from balance_engine.services.balance_service import calculate_user_balance
from balance_engine.services.ledger_service import get_user_ledger
from expenses.models import Expense
from settlements.models import Settlement
from expenses.services.expense_service import get_expense_breakdown
from settlements.services.settlement_service import get_settlement_breakdown

def explain_user_balance(group, user):
    """
    Generates a detailed breakdown of a user's net balance.
    Includes expenses they contributed to and settlements they participated in.
    """
    balance_info = calculate_user_balance(group, user)
    ledger = get_user_ledger(group, user)
    
    expense_contributions = []
    settlement_contributions = []
    calculation_trace = []
    
    current_balance = Decimal("0.00")
    
    for event in ledger:
        # Find the delta for this user
        user_delta = Decimal("0.00")
        for entry in event["entries"]:
            if entry["user_id"] == user.id:
                user_delta = Decimal(str(entry["delta"]))
                break
                
        if user_delta == Decimal("0.00"):
            continue
            
        current_balance += user_delta
        
        trace_step = {
            "date": event["event_date"],
            "event_type": event["event_type"],
            "reference_id": event["reference_id"],
            "delta": user_delta,
            "running_balance": current_balance
        }
        calculation_trace.append(trace_step)
        
        if event["event_type"] == "expense":
            # Fetch expense details
            expense_id = event["reference_id"].replace("EXP-", "")
            try:
                exp = Expense.objects.get(id=expense_id)
                # Owed logic specifically requested by Rohan Requirement: {"title": "Rent", "owed": 1800} 
                # This could mean "amount I owe to the group" (if delta < 0, they owe. if delta > 0, they paid more).
                # To be precise, we provide the full breakdown.
                brk = explain_expense_contribution(exp)
                expense_contributions.append({
                    "expense_id": exp.id,
                    "title": exp.title,
                    "delta": user_delta,
                    "breakdown": brk
                })
            except Expense.DoesNotExist:
                pass
                
        elif event["event_type"] == "settlement":
            # Fetch settlement details
            try:
                stl = Settlement.objects.get(reference_id=event["reference_id"])
                brk = explain_settlement_contribution(stl)
                settlement_contributions.append({
                    "reference_id": stl.reference_id,
                    "amount": stl.amount,
                    "delta": user_delta,
                    "breakdown": brk
                })
            except Settlement.DoesNotExist:
                pass
                
    return {
        "user_id": user.id,
        "user": user.username,
        "total_paid": balance_info["total_paid"],
        "total_owed": balance_info["total_owed"],
        "net_balance": balance_info["net_balance"],
        "expense_contributions": expense_contributions,
        "settlement_contributions": settlement_contributions,
        "calculation_trace": calculation_trace
    }

def explain_expense_contribution(expense):
    return get_expense_breakdown(expense)

def explain_settlement_contribution(settlement):
    return get_settlement_breakdown(settlement)
