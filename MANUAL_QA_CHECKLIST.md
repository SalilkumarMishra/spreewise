# Spreewise: Pre-Deployment Manual QA Checklist

This document lists every workflow and edge case that must be tested and verified before deploying Spreewise.

---

## 1. Authentication & Security
- [ ] **Valid Login**: Enter correct username/password; verify immediate redirect to Dashboard.
- [ ] **Invalid Login**: Enter incorrect password; verify that a validation alert appears and access is denied.
- [ ] **Routing Guards**: Attempt to navigate directly to `/` or `/groups` when logged out; verify automatic redirect to `/login`.
- [ ] **Session Persistence**: Close the browser tab while logged in, reopen it, and navigate back; verify the user remains authenticated.
- [ ] **Logout Flush**: Click logout; verify that the token is deleted from storage and direct URL navigation to protected pages is blocked.
- [ ] **Expired Session Handling**: Simulate a stale token by modifying session storage; verify the API interceptor catches the `401` response and redirects to `/login`.

---

## 2. Group Management
- [ ] **Create Group (INR)**: Create a group with base currency INR; verify it appears in the active group dropdown list.
- [ ] **Create Group (USD)**: Create a group with base currency USD; verify that values are calculated and formatted accordingly.
- [ ] **Edit Group Metadata**: Modify a group name/description; verify changes persist on the UI.
- [ ] **Archive Group**: Soft-delete a group; verify it is immediately hidden from the default active list but remains present in the database as `is_archived=True`.

---

## 3. Membership Lifecycle
- [ ] **Add Group Member**: Add a user by ID; verify they appear in the members log.
- [ ] **Duplicate Membership block**: Try to add a user who is already active; verify that a validation warning is returned.
- [ ] **Leave Group**: Deactivate a member; verify their status changes to inactive and their leave date is registered.
- [ ] **Joined/Leave Date validation**: Attempt to leave a group with a date prior to the join date; verify the system rejects the operation.
- [ ] **Rejoin Group**: Reactivate an inactive member; verify that a new membership interval is created and they show as active.
- [ ] **Historical Preservation**: Verify that a user's previous active intervals remain preserved in the `GroupMembership` database table.

---

## 4. Expense Engine & Splits
- [ ] **Equal Split validation**: Create an expense split equally; verify that each participant gets an equal share and that rounding remainders are absorbed by the first user.
- [ ] **Percentage Split validation**: Create an expense with user-defined percentages; verify that if they do not sum to 100%, submission is blocked.
- [ ] **Shares Split validation**: Create a shares-weighted split; verify that individual shares are computed correctly from the total sum of weights.
- [ ] **Exact Split validation**: Create an exact amount split; verify that the sum of inputs must match the total expense amount.
- [ ] **Edit Expense snapshots**: Edit an expense amount/date; verify that a new record is added to the `ExpenseSnapshot` table and that old versions remain viewable.
- [ ] **Delete Expense**: Archive an expense; verify that its delta is removed from ledger calculations.

---

## 5. Settlement Engine
- [ ] **Record Settlement**: Enter a payer, receiver, and amount; verify that it generates a formatted ID (`SET-YYYY-00000X`).
- [ ] **Self-Payment Block**: Attempt to set the payer and receiver as the same user; verify that validation blocks the action.
- [ ] **Audit Trail**: Edit/delete a settlement; verify that Settlement snapshots are generated and that their payloads are immutable.

---

## 6. Balance Engine Invariants
- [ ] **Zero-Sum Balance check**: Verify that the sum of net balances for all group members equals exactly `0.00`.
- [ ] **Simplified paybacks**: Add transactions; verify that the payback lists match the optimized transactions.
- [ ] **Explainability Trace**: Inspect Rohan's Trace timeline; verify that the running balance is computed step-by-step.

---

## 7. CSV Ingestion & Anomaly reviews
- [ ] **Clean CSV Import**: Upload a valid CSV; verify that all lines are processed immediately, transactions are generated, and a completed report appears.
- [ ] **Invalid CSV structure**: Upload a corrupted file; verify that the job fails with appropriate file parsing errors.
- [ ] **Point-in-Time Membership dates check**: Ingest a row with a date outside a participant's active window; verify it flags a `payer_not_active_on_date` or `participant_not_active_on_date` anomaly and rejects the row.
- [ ] **Duplicate anomaly detection**: Upload an expense matching an existing one; verify that a duplicate anomaly is flagged.
- [ ] **Meera Approval Audit Logs**: Approve, reject, or ignore anomalies; verify that an `ImportDecision` audit record is created for each action.
- [ ] **Report Aggregation**: Verify that the anomaly counts and breakdown statistics in the final `ImportReport` are mathematically correct.

---

## 8. Multi-Currency Support (Priya Requirement)
- [ ] **Conversion verification**: Log a USD transaction in an INR group; verify that the converted INR amount is used for ledger calculations.
- [ ] **Preserve Original inputs**: Verify that the expense details modal shows both the converted balance and the original USD currency/amount.

---

## 9. Client Side Responsiveness
- [ ] **Desktop view**: Verify navigation sidebar, charts, tables, and modal dialogues are well aligned and spaced.
- [ ] **Tablet view**: Verify columns stack correctly and that tables are scrollable.
- [ ] **Mobile view**: Verify sidebar collapses into a hamburger or navigation overlay, and that forms do not overflow the screen boundaries.

---

## 10. Error Handling & Validation states
- [ ] **Backend Off state**: Stop the Django server and interact with the UI; verify that user action results in a "Backend offline" or "Connection failed" warning banner.
- [ ] **Empty Form inputs**: Click submit on empty forms; verify that client-side validations block request submissions.
