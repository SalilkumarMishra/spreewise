# DECISIONS

## Group and Membership Lifecycle Decisions (Priority 2)

### 1. Group Archiving vs Hard Deletion
- **Decision**: Deleting a group through the API performs a soft delete (marking `is_archived = True`) instead of a physical SQL `DELETE`.
- **Rationale**: Financial and expense histories must remain completely auditable for all group members, even if the group is no longer active. Deleting the group database records would break database cascades, leading to dangling/orphaned expenses or loss of historical ledger data.

### 2. Historical Membership Preservation (Soft-Departure)
- **Decision**: Memberships are never hard deleted. Leaving a group changes the membership status to inactive (`is_active = False`) and records the exact date of departure in the `left_at` field.
- **Rationale**: The core balance engine, CSV import parser, and expense distribution rules depend on membership state relative to dates (e.g. Meera leaves on March 31, Sam joins on April 15). Removing these records entirely would corrupt the history of who was active in the group when past expenses were logged.

### 3. Support for Multiple Lifetimes (Leave/Rejoin History)
- **Decision**: Users are allowed to leave and rejoin the same group multiple times. This is implemented by maintaining a list of discrete membership records in the database, with a partial unique constraint allowing at most one *active* membership record per user per group at any given time.
- **Rationale**: Enables auditability of non-contiguous memberships. A user can leave for a vacation or period, and rejoin later, creating two separate records to denote distinct active windows.

## Expense Management Architecture (Priority 3)

### 4. Expense Snapshots and Immutability
- **Decision**: Every creation and update to an Expense automatically generates an immutable `ExpenseSnapshot` record capturing the exact state of the expense, participants, and splits at that version.
- **Rationale**: Expense histories need to be auditable. A change in a split amount today shouldn't obscure what was originally agreed upon yesterday. This snapshotting mechanism ensures complete transparency and aids in debugging balance mismatches or disputes without overwriting historical data.

### 5. Original Currency Preservation
- **Decision**: The `Expense` model stores both `amount` / `currency` (the working values used for calculations) and `original_amount` / `original_currency` (the values originally input or imported).
- **Rationale**: CSV imports often contain transactions in various currencies (e.g., USD expenses in an INR group). Preserving the original amounts guarantees that users can always trace back to the exact receipt amount ("Why does it say ₹44,928 when I spent $540?").

### 6. Expense Source and Status Fields
- **Decision**: Added `source` (`manual`, `csv_import`, `system`) and `status` (`active`, `disputed`, `import_review`) fields with strict validation.
- **Rationale**: Distinguishes between manual user entries, automated CSV imports, and system-generated settlements. The `status` field specifically enables anomaly workflows, where imported expenses can be parked under `import_review` or flagged as `disputed` before they affect active balances.

### 7. Explainability Support
- **Decision**: The system provides detailed breakdown helpers (`get_expense_breakdown`) and preserves exact split values (like `shares_value` and `percentage_value`).
- **Rationale**: Financial systems must be able to answer "Why do I owe this amount?" Preserving the explicit logic (e.g., "Rohan owes ₹250 because he has 1 share out of 4 total shares") builds user trust and makes debugging significantly easier.

## Settlement Engine Architecture (Priority 4)

### 8. Settlements as Independent Entities
- **Decision**: Settlements (payments between users) are modeled separately from Shared Expenses rather than being a specific `Expense` split type.
- **Rationale**: While an expense represents an outbound cost shared by N people, a settlement represents an internal transfer from person A to person B to resolve debt. Separating them prevents convoluted `Expense` splits where `payer` = `receiver` with negative amounts, keeping the logic for the Balance Engine explicit and straightforward.

### 9. Reference ID Generation
- **Decision**: Every settlement automatically generates a unique `reference_id` (e.g., `SET-2026-000001`).
- **Rationale**: Makes UI traceability and debugging significantly easier. The Balance Engine and explainability logs can point to human-readable IDs ("Rohan's balance decreased due to SET-2026-000001").

### 10. Settlement Snapshots
- **Decision**: Similar to Expenses, Settlements maintain immutable `SettlementSnapshot` versions. The snapshot payload stores the `reference_id` and all scalar values.
- **Rationale**: If Aisha corrects a ₹500 settlement to ₹700, the change must be tracked to prevent disputes. The snapshot system ensures there is always a verifiable audit trail of changes over time.

### 11. Balance Engine Generation (Events)
- **Decision**: Instead of directly touching a ledger model, the Settlement service implements `generate_balance_event()`.
- **Rationale**: This is a push-forward architectural choice. The upcoming Balance Engine will consume discrete immutable events (`+` or `-` amounts on a user's account) from both the Expense module and the Settlement module, establishing an event-sourced ledger capable of complete reconstruction at any point in time.

### 12. Normalized Ledger Format
- **Decision**: Introduced `generate_balance_ledger_entry()` to convert settlements into a normalized ledger structure (a list of zero-sum deltas).
- **Rationale**: The Balance Engine should not need to understand the internal structure of every business object (Expenses, Settlements, Refunds, Adjustments). By normalizing these distinct entities into standard ledger entries (e.g. `[{user: payer, delta: -700}, {user: receiver, delta: 700}]`), the Balance Engine's responsibility is simplified to purely consuming and summing normalized deltas.

## Balance Engine Architecture (Priority 5)

### 13. BalanceSnapshot Model
- **Decision**: Introduced `BalanceSnapshot` to preserve JSON snapshots of the entire group's net balances at a specific point in time.
- **Rationale**: Bulk operations like CSV imports change massive amounts of data at once. Having a point-in-time snapshot of what the balances were immediately after a major event assists heavily in rollback strategies, historical analysis, and auditing.

### 14. Zero-Sum Invariant Enforcement
- **Decision**: Added a dedicated `validate_balance_invariants()` method that explicitly guarantees `sum(all_balances) == 0`.
- **Rationale**: Floating point or decimal rounding errors can introduce "cent leakage". Explicitly validating invariants guarantees the absolute mathematical correctness of the system before exposing simplifications to the user.

### 15. Debt Simplification Algorithm
- **Decision**: Implemented a greedy algorithm that splits users into creditors and debtors and settles largest-to-largest debts first.
- **Rationale**: This guarantees that money is not needlessly circular and provides the absolute fewest number of transactions required for a group to settle up, massively improving the user experience.

### 16. Explanation Tracing
- **Decision**: The API natively returns a `calculation_trace` array showing the running balance at every chronological step.
- **Rationale**: Trust is everything in financial software. A user needs to be able to see line-by-line exactly how their balance reached its current state.

### 17. Balance Engine Invariant (Settlement Signs)
- **Decision**: The normalized ledger sign convention dictates that Expenses *create* obligations (Payer gets `+`, Ower gets `-`) and Settlements *reduce* obligations (Debtor/Payer gets `+`, Creditor/Receiver gets `-`).
- **Rationale**: A settlement event must always move balances closer to zero, not farther away. By keeping the logic identical in the event stream, the Balance Engine simply sums all historical deltas cleanly.
