from decimal import Decimal
from balance_engine.services.balance_service import calculate_group_balances

def simplify_debts(group):
    """
    Implements a greedy debt simplification algorithm.
    It separates users into debtors (-) and creditors (+),
    and generates minimal {payer, receiver, amount} payment instructions.
    """
    balances = calculate_group_balances(group)
    
    debtors = []
    creditors = []
    
    # Separate into debtors and creditors
    for b in balances:
        amt = Decimal(str(b["balance"]))
        if amt < 0:
            debtors.append({"user_id": b["user_id"], "user": b["user"], "amount": abs(amt)})
        elif amt > 0:
            creditors.append({"user_id": b["user_id"], "user": b["user"], "amount": amt})
            
    # Sort to optimize slightly (largest debts matched with largest credits)
    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)
    
    payments = []
    i = 0  # debtors index
    j = 0  # creditors index
    
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        
        # Calculate how much can be settled in this step
        settle_amount = min(debtor["amount"], creditor["amount"])
        
        if settle_amount > 0:
            payments.append({
                "payer_id": debtor["user_id"],
                "payer": debtor["user"],
                "receiver_id": creditor["user_id"],
                "receiver": creditor["user"],
                "amount": settle_amount
            })
            
        # Update remaining balances
        debtor["amount"] -= settle_amount
        creditor["amount"] -= settle_amount
        
        # Move to next if fully settled
        if debtor["amount"] == 0:
            i += 1
        if creditor["amount"] == 0:
            j += 1
            
    return payments
