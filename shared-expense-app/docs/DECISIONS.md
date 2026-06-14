# DECISIONS.md — Spreewise Architectural Decisions

This document outlines the core architectural and design decisions made in Spreewise.

---

## 1. Historical Membership Preservation (A)

### Problem
In shared-living groups, members join and leave at various times (e.g., Meera leaves on March 31, Sam joins on April 15). If we only track active/inactive membership status, calculating balances and validating imports retrospectively becomes impossible. We need to know who was in the group on any specific past date.

### Options Considered
1. **Simple Status Flag**: Add a boolean `is_active` to a flat user-group map. (Cannot track date intervals or historical periods).
2. **Audit Logs / Event Stream**: Query system logs to reconstruct memberships. (Highly complex, slow, and error-prone database queries).
3. **Date-Interval Membership Records**: Store active memberships with explicit `joined_at` and `left_at` fields, allowing a user to have multiple non-overlapping membership records. (Final Choice).

### Final Choice & Reasoning
We implemented **Date-Interval Membership Records** using the `GroupMembership` model. This structure supports querying who was an active member on any past date (`is_member_on_date(user, check_date)`), keeping balance computations and historical CSV imports mathematically sound and auditable.

---

## 2. Group Archiving vs Hard Deletion (B)

### Problem
If a group is deleted, what happens to the financial transactions logged in it? Bypassing database cascades by hard-deleting the group records breaks ledger audit trails, while keeping cascading rules deletes user transactions and corrupts individual financial statements.

### Options Considered
1. **Hard Cascade Delete**: Delete groups and all related expenses, settlements, splits, and snapshots. (Violates financial data retention and audit requirements).
2. **Dangling Foreign Keys (SET NULL)**: Delete groups but set the `group_id` foreign key on expenses and settlements to null. (Leaves orphan records and destroys context of which group the expenses belonged to).
3. **Soft Delete (Archiving)**: Prevent physical deletions by setting `is_archived = True` on the group. (Final Choice).

### Final Choice & Reasoning
We chose **Soft Delete (Archiving)**. The group remains in the database to support historical ledger queries and balance explanation traces, but is hidden from active operations.

---

## 3. Expense Snapshots and Immutability (C)

### Problem
Shared expenses can be edited (e.g., changing split shares or title). If we simply update the database row, we overwrite what was agreed upon in the past, making dispute resolution and balance audit impossible.

### Options Considered
1. **Fully Mutable Rows**: Overwrite fields directly. (Provides no audit trail or history of updates).
2. **Normalized History Tables**: Mirror all model fields in a separate history table. (Increases complexity, duplicates database columns, and requires schema changes for both tables).
3. **Immutable JSON Snapshots**: Save version-controlled JSON payloads capturing the exact state of expenses, participants, and splits on every insert/update. (Final Choice).

### Final Choice & Reasoning
We chose **Immutable JSON Snapshots** using the `ExpenseSnapshot` model. It separates live operational columns from audit records, is easy to serialize, and raises validation errors on any modify attempt, ensuring a perfect audit log.

---

## 4. Settlements as Separate Entities (D)

### Problem
Settlements (direct peer-to-peer payments) behave differently from expenses. An expense represents external costs split among N people, creating debt. A settlement represents an internal transfer from payer to receiver to reduce debt.

### Options Considered
1. **Shared Expense with Settlement Flag**: Log settlements as standard expenses using a special `settlement` split type and category. (Leads to complicated splits where the payer is credited and the receiver is debited, complicating the balance engine logic).
2. **Decoupled Settlement Model**: Create an independent `Settlement` model with fields for `payer`, `receiver`, `reference_id`, and `payment_date`. (Final Choice).

### Final Choice & Reasoning
We selected the **Decoupled Settlement Model**. This keeps both the split calculation code and the ledger balance engine clear. Expenses create obligations, whereas Settlements resolve them.

---

## 5. Normalized Ledger Format (E)

### Problem
The Balance Engine must ingest financial data from multiple sources (manual expenses, manual settlements, bulk imports). Having the engine understand the detailed schemas of every model creates high coupling and makes it difficult to add new event types (like refunds or adjustments).

### Options Considered
1. **Direct Model Queries**: Have the Balance Engine directly query both the `Expense` and `Settlement` models and compute obligations using model-specific properties. (Highly coupled, hard to maintain or expand).
2. **Event-Sourced Ledger**: Map all transactions into a normalized ledger entry format: `{"event_type": ..., "reference_id": ..., "entries": [{"user_id": ..., "delta": ...}]}` where the sum of deltas is exactly zero. (Final Choice).

### Final Choice & Reasoning
We selected the **Normalized Ledger Format**. Both the Expense service and the Settlement service convert their states into a standard ledger record. The Balance Engine simply aggregates these events, reducing obligations calculation to summing numerical deltas.

---

## 6. Debt Simplification using Greedy Matching (F)

### Problem
If A owes B $10, and B owes C $10, direct settlements require two separate transactions. If there are many circular debts, users face an unnecessary volume of peer-to-peer transfers.

### Options Considered
1. **Direct Settlement**: Users settle debts directly with everyone they owe. (High transaction volume).
2. **Greedy Debt Simplification**: Split users into Net Creditors and Net Debtors, sorting them by amount. Match the largest debtor with the largest creditor, reducing their obligations iteratively until all balances settle to zero. (Final Choice).

### Final Choice & Reasoning
We implemented **Greedy Debt Simplification**. It reduces transaction overhead to the minimum possible number of p2p transfers.

---

## 7. CSV Import Review Workflow (G)

### Problem
CSV data uploaded by users is often messy, containing duplicate rows, zero amounts, conversion mismatches, or settlements logged as expenses. Silently modifying, skipping, or auto-fixing rows breaks financial safety and audit trails.

### Options Considered
1. **Strict Reject**: Fail the entire import job on any anomaly. (Terrible user experience for large files).
2. **Silent Drop/Fix**: Automatically drop duplicates or auto-convert currencies. (Violates financial safety).
3. **Interactive Review Queue**: Process safe rows, flag anomalies in an anomaly table, pause the import job under a `review_required` status, and demand explicit user decisions (`approve`, `reject`, `ignore`) with reasons before resuming. (Final Choice).

### Final Choice & Reasoning
We built the **Interactive Review Queue** using the `ImportAnomaly` and `ImportDecision` models. This guarantees complete audit trace and gives the user control to resolve ambiguous rows manually.

---

## 8. Original Currency Preservation (H)

### Problem
Imports may contain expenses in non-group currencies (e.g., a USD receipt in an INR group). If we only store the converted amount, users cannot verify the transaction against their receipts.

### Options Considered
1. **Store Converted Only**: Convert foreign amounts immediately and store only the converted amount. (Deletes the receipt trace).
2. **Dual-Currency Storage**: Store the converted `amount`/`currency` for balance calculations and the `original_amount`/`original_currency` for explainability. (Final Choice).

### Final Choice & Reasoning
We chose **Dual-Currency Storage** on both `Expense` and `Settlement` models. This allows users to reconcile their transactions with original receipts.

---

## 9. Balance Snapshots (I)

### Problem
Reconstructing balances from historical ledger records can become slow as the volume of events grows. We need an audit capture of obligations at key points in time (e.g., right after a massive CSV import).

### Options Considered
1. **Dynamic ledger scanning**: Scan and sum all deltas on every query. (Computations become slower as database rows grow).
2. **Balance Snapshotting**: Save a point-in-time JSON snapshot of all net balances in the database. (Final Choice).

### Final Choice & Reasoning
We selected **Balance Snapshotting** via `BalanceSnapshot`. We trigger it automatically at the end of bulk imports, preserving an immutable trace of balances.
