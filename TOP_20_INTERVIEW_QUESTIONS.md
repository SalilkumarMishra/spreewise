# Top 20 Technical Interview Questions & Answers: Spreewise Architecture

This document contains simulated technical interview questions and ideal answers explaining the design, algorithms, and architectural decisions made in the Spreewise shared-expense management application.

---

### 1. How does the Balance Engine ensure mathematical correctness across group transactions?
**Ideal Answer**:
The Balance Engine enforces a **Ledger Invariant**: every transaction (expense or settlement) must resolve to a balanced set of entries whose deltas sum to exactly `0.00`. 
- For an expense, the payer gets a positive delta (`amount paid - their calculated share`), and each participant gets a negative delta (`-their calculated share`). The sum of all participants' shares equals the total amount, meaning the deltas sum to zero.
- For a settlement of value `V`, the payer gets a delta of `+V` (reducing their debt or adding credit) and the receiver gets a delta of `-V`. The sum is `+V + (-V) = 0.00`.
By aggregating all deltas chronologically, the net sum of all user balances in any group is mathematically guaranteed to remain exactly `0.00`.

---

### 2. Describe the Debt Simplification algorithm. How does it optimize peer-to-peer repayments?
**Ideal Answer**:
Spreewise implements a **Greedy Debt Simplification** algorithm. 
1. First, the engine fetches the net balances for all group members.
2. It partitions the members into two sorted lists: **Debtors** (members with negative balances) and **Creditors** (members with positive balances), sorted in descending order of absolute value.
3. It repeatedly pairs the largest debtor with the largest creditor.
4. The transaction amount is calculated as `min(debtor_outstanding, creditor_receivable)`.
5. The transaction is recorded (e.g., *Debtor A pays Creditor B amount X*), and the outstanding balances for both are updated.
6. The fully settled party is removed from the queue, and the loop repeats until all balances are zero. This matches the largest debts with the largest credits, minimizing the total number of peer-to-peer transfers required.

---

### 3. What is the time and space complexity of the Greedy Debt Simplification algorithm?
**Ideal Answer**:
- **Time Complexity**: $O(N \log N)$ where $N$ is the number of users in the group. Sorting the debtors and creditors takes $O(N \log N)$. The matching loop runs at most $N-1$ times, since each step fully settles at least one debtor or creditor.
- **Space Complexity**: $O(N)$ auxiliary space to store the debtor and creditor lists.
This is highly efficient and easily operates in sub-millisecond times for typical group sizes (under 100 members).

---

### 4. How does Spreewise validate point-in-time membership windows when recording expenses or settlements?
**Ideal Answer**:
Spreewise enforces point-in-time membership constraints rather than assuming a user was always in the group. The helper method `is_user_member_on_date(user, check_date)` on the `Group` model queries the `GroupMembership` table:
```python
return self.memberships.filter(
    user=user,
    joined_at__lte=check_date
).filter(
    models.Q(left_at__isnull=True) | models.Q(left_at__gte=check_date)
).exists()
```
Before any expense or settlement is persisted (either manually or during CSV import), the service layer validates that the payer and all participants were active members on that specific transaction date. If a transaction date falls outside their active window, a `ValidationError` is raised and the transaction is aborted.

---

### 5. How is the CSV Import Engine pipeline designed to support pausing and resuming on anomalies?
**Ideal Answer**:
The CSV Import Engine is modeled as a multi-stage transactional pipeline:
1. **Upload & Parse**: The raw CSV file is uploaded and parsed into individual `ImportRow` records with a status of `pending`.
2. **Anomaly Check**: Every row is evaluated against the anomaly catalog. If any row triggers a `REVIEW_REQUIRED` anomaly, the `ImportJob` status is updated to `review_required` and execution pauses.
3. **Decide**: The user is presented with the review queue in the UI. For each anomaly, the user submits a decision (`approve`, `reject`, or `ignore`) along with a reason. This decision is stored in the `ImportDecision` table.
4. **Resume**: Once all review anomalies on a row are decided:
   - Approved rows are processed (creating the corresponding `Expense` or `Settlement` record).
   - Rejected rows are skipped.
   - Ignored rows are bypassed.
5. **Finalize**: The job status is updated to `completed`, and the balance engine recalculates net group positions.

---

### 6. Explain the difference between `REJECT` and `REVIEW_REQUIRED` anomaly policies in your import engine.
**Ideal Answer**:
- **`REJECT`**: Applied to fatal anomalies that render a row invalid. Examples include negative amounts, unknown users, invalid dates, and missing required fields. These rows cannot be resolved by user decisions, so they are marked as `failed` and skipped.
- **`REVIEW_REQUIRED`**: Applied to semantic anomalies that require human judgment to resolve. Examples include duplicate transactions (same date, payer, and amount), currency conversion mismatches, or settlements logged as expenses. The user can approve, reject, or ignore these anomalies via the UI review queue.

---

### 7. How does the system prevent duplicate transactions from being imported via CSV?
**Ideal Answer**:
Spreewise checks for duplicates during the anomaly detection stage of import processing:
- **Duplicate Expense**: The engine queries the `Expense` model for active, non-archived expenses matching the group, date, amount, payer, and description:
  ```python
  Expense.objects.filter(group=group, expense_date=p["date"], amount=amount, paid_by=payer_user, title=p["description"], is_archived=False)
  ```
- **Duplicate Settlement**: For possible settlement rows, the engine queries the `Settlement` model for existing records matching the payer, receiver, amount, and date.
If a match is found, a `duplicate_expense` or `duplicate_settlement` anomaly is flagged as `REVIEW_REQUIRED`. The user must review and explicitly approve the row if it was indeed a separate, valid transaction.

---

### 8. How are multi-currency expenses handled, and how is original data preserved?
**Ideal Answer**:
To support multi-currency expenses without losing audit fidelity:
- The `Expense` model stores both the converted amount in the group's default currency (`amount`, `currency`) and the original input values (`original_amount`, `original_currency`).
- During CSV import, if a row's currency differs from the group's currency, a `currency_conversion_required` anomaly is flagged, pausing the import for review.
- The UI displays both values (e.g., *₹8,400.00 (Original: $100.00 USD)*), preserving full transparency and explainability for all group members.

---

### 9. Why did you choose an event-sourced delta ledger over storing running balances directly on User/Group models?
**Ideal Answer**:
Storing running balances directly on the model is a common anti-pattern that creates race conditions, database lock contention, and makes auditing difficult. 
Instead, Spreewise uses a read-optimized event ledger. Balances are derived dynamically by summing deltas from all active expenses and settlements. This approach:
1. **Guarantees Consistency**: Eliminates out-of-sync states between transactions and running totals.
2. **Allows Retroactive Adjustments**: If an expense from last week is edited or deleted, the balance engine recalculates the ledger chronologically, correcting all subsequent balances automatically.
3. **Supports Auditing**: Enables step-by-step running balance traces (Rohan's requirement) by compiling transactions as chronological events.

---

### 10. How is the audit trail implemented for Meera's anomaly approval workflow?
**Ideal Answer**:
Meera's requirement is implemented via the `ImportDecision` model:
- `ImportDecision` has a `OneToOneField` relationship to `ImportAnomaly` to ensure each anomaly has exactly one decision record.
- It includes fields for `decision` (`approve`, `reject`, `ignore`), `decided_by` (ForeignKey to Django User), `decision_reason` (TextField), and a `created_at` timestamp.
- The `submitAnomalyDecision` API validates that a user provides a decision reason before persisting the record. This ensures a complete, traceable audit trail for all resolved anomalies.

---

### 11. Explain how the Ledger Trace endpoint works and what data it returns.
**Ideal Answer**:
The Ledger Trace endpoint (`/api/balances/groups/{id}/explain/`) implements Rohan's requirement:
1. It retrieves all active expenses and settlements for a group, sorted chronologically by date.
2. It filters this timeline to events affecting the requested user.
3. It iterates through the events, calculating the user's delta for each transaction and maintaining a running balance:
   - For an expense: `delta = amount_paid - user_calculated_share`.
   - For a settlement: `delta = +amount` if they paid, `-amount` if they received.
4. It returns the step-by-step trace showing the event name, date, delta, and running balance, allowing users to verify how their balance evolved over time.

---

### 12. How does the database schema support non-contiguous active windows for a user in a group?
**Ideal Answer**:
Spreewise supports this by decoupling the group membership join/leave dates from the user record:
- The `GroupMembership` table represents a single active membership interval for a user, containing `joined_at` and `left_at` fields.
- A user can leave a group (setting `left_at`) and rejoin later (creating a new `GroupMembership` record).
- To prevent overlapping active memberships, the database enforces a conditional unique constraint `unique_active_group_membership`:
  ```python
  models.Q(is_active=True)
  ```
  This allows multiple inactive membership records for the same user, but limits them to at most one active membership window at any given time.

---

### 13. How do you handle database concurrency and transactional integrity during bulk imports?
**Ideal Answer**:
Spreewise handles database concurrency and transactional integrity by wrapping core service methods in Django's `@transaction.atomic` block:
- When a bulk import resumes, the row-by-row creation of transactions (`_create_record_from_row`) is executed atomically.
- This ensures that if any row fail-saves during the save process (e.g. database validation failures), the database rolls back the changes for that specific row, preventing partial or corrupt records.

---

### 14. What are ExpenseSnapshots and SettlementSnapshots, and how is their immutability enforced?
**Ideal Answer**:
- **Snapshots**: Store versioned JSON payloads representing the state of an expense or settlement at a point in time (including all participants and split allocations).
- **Immutability**: Enforced in the snapshot model's `save()` method:
  ```python
  def save(self, *args, **kwargs):
      if self.pk is not None:
          raise ValidationError("Snapshots are immutable and cannot be modified.")
      super().save(*args, **kwargs)
  ```
  This prevents any modifications to snapshot records once they are written to the database, ensuring a tamper-proof audit trail of transaction edits.

---

### 15. How does the system handle split rounding issues (e.g., splitting ₹100.00 equally among 3 users)?
**Ideal Answer**:
Rounding errors are handled using Python's `Decimal` type and rounding remainders:
- For equal splits, the engine calculates the base share:
  ```python
  base_share = (total_amount / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
  ```
- Any rounding remainder (`total_amount - (base_share * n)`) is absorbed by the first participant in the list.
This ensures the sum of all calculated splits always matches the total expense amount down to the exact cent, preventing balance leaks in the system.

---

### 16. What are the split types supported by the Expense Engine, and how are they validated?
**Ideal Answer**:
Spreewise supports four split types:
1. **Equal**: Split amount is divided evenly among participants, with the first participant absorbing any rounding remainder.
2. **Percentage**: User inputs custom percentages for participants. The engine validates that the sum of all percentages equals exactly `100%`.
3. **Shares**: User assigns share weights (e.g., 2 shares, 1 share). The engine calculates shares dynamically: `amount * (user_shares / total_shares)`.
4. **Exact**: User inputs exact currency amounts for each participant. The engine validates that the sum of all exact inputs matches the total expense amount.

---

### 17. How does the frontend form architecture validate split allocations before submitting?
**Ideal Answer**:
The React frontend handles form validation at two layers:
- **Form State**: Managed using `react-hook-form` and validated against Zod schemas (`zodResolver`).
- **Dynamic Rules Validation**: During form submission, the page checks split balances (e.g. validating that percentages sum to 100 or exact amounts sum to the total). If a validation check fails, submission is blocked and a helpful error notification is displayed, preventing unnecessary backend API requests.

---

### 18. Why is a Settlement decoupled from a standard Expense record?
**Ideal Answer**:
Although both are ledger events, settlements (direct peer-to-peer repayments) are structurally and semantically different from expenses:
- Expenses represent outgoing costs shared among group members.
- Settlements are direct, binary balance transfers intended to settle outstanding debts between two specific members.
Decoupling them into separate models (`Expense` and `Settlement`) keeps the database schema clean, prevents incorrect split calculations, and makes it easier to model direct payment options (UPI, cash, bank transfer) for repayments.

---

### 19. How is session security managed between React and Django?
**Ideal Answer**:
Spreewise uses Basic Authentication over session headers for developer setup:
- Upon login, the frontend generates a Base64-encoded token from the username and password (`btoa(username:password)`).
- This token is saved in `sessionStorage` and appended to the `Authorization` header of all subsequent API requests via an Axios interceptor.
- If a request returns a `401 Unauthorized` status (e.g. from an expired session or invalid credentials), an interceptor intercepting responses automatically clears the token and redirects the user to the login screen.

---

### 20. If you had to scale the Balance Engine to support millions of active groups, how would you optimize calculation times?
**Ideal Answer**:
Querying and recalculating all historical transaction events on every page load would eventually become a bottleneck. To scale the Balance Engine, I would implement:
1. **Incremental Snapshotting**: Store a periodic balance checkpoint (e.g., monthly) for each group. When recalculating balances, the engine would start from the latest checkpoint and only aggregate transactions created after that date.
2. **Event-Driven Cache Invalidation**: Cache net balances in Redis. Any new expense or settlement event would trigger an asynchronous background task to update the cache, allowing GET requests to return balances in sub-milliseconds.
