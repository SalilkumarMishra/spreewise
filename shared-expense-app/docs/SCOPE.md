# SCOPE.md — Spreewise: Shared Expense Management System
## Project Scope Document

---

## 1. System Overview

**Spreewise** is a backend-first shared expense management application built with Django, PostgreSQL, and Django REST Framework. It is designed to handle all financial obligations arising from a shared-living or group-expense scenario with strict auditability, explainability, and historical correctness.

The system supports:
- Group creation and lifecycle management with membership date tracking
- Expense recording with multiple split types (equal, percentage, shares, exact)
- Settlement recording (peer-to-peer debt payments)
- A normalized Balance Engine that calculates net obligations from all events
- A CSV Import Engine that ingests historical data with full anomaly detection
- Immutable audit snapshots on every financial record

---

## 2. Implemented Priorities

| Priority | Module | Status |
|---|---|---|
| P1 | Infrastructure (Django, PostgreSQL, DRF, Auth) | ✅ Complete |
| P2 | Group Management & Membership Lifecycle | ✅ Complete |
| P3 | Expense Engine (all split types, snapshots, explainability) | ✅ Complete |
| P4 | Settlement Engine (payments, reference IDs, snapshots) | ✅ Complete |
| P5 | Balance Engine (ledger, simplification, explanation) | ✅ Complete |
| P6 | CSV Import Engine + Anomaly Detection | ✅ Complete |

---

## 3. Business Rules

### 3.1 Group & Membership
- Groups are never permanently deleted — they are archived (`is_archived=True`).
- Group membership tracks `joined_at` and `left_at` dates.
- The `is_member_on_date(user, date)` method is the single authoritative check for membership eligibility.
- A user can rejoin a group after leaving.

### 3.2 Expenses
- Every expense records both `amount/currency` (in group currency, post-conversion) and `original_amount/original_currency` (as entered, for auditability).
- Every expense creation or update generates an immutable `ExpenseSnapshot` (version-controlled JSON).
- Split types: `equal`, `percentage`, `shares`, `exact`.
- Remainder from rounding is always assigned to the **first participant**.
- Expenses can have status: `active`, `disputed`, `import_review`.
- Source: `manual`, `csv_import`, `system`.

### 3.3 Settlements
- Settlements are modelled separately from Expenses (a `Settlement` moves `amount` from `payer` to `receiver`).
- Every settlement has a unique `reference_id` (e.g. `SET-2026-000001`).
- Every settlement generates an immutable `SettlementSnapshot`.
- Settlement sign convention: **Settlements reduce debt** — the payer's balance moves toward zero, the receiver's balance moves toward zero.

### 3.4 Balance Engine
- The Balance Engine consumes **normalized ledger entries** (`{user_id, delta}` arrays that always sum to zero) from both Expenses and Settlements.
- `sum(all_group_balances) == 0` is a hard invariant enforced by `validate_balance_invariants()`.
- Debt simplification uses a greedy algorithm (largest creditor matched with largest debtor) to generate minimum payment instructions.
- Every balance recalculation produces a `BalanceSnapshot` for historical audit.

---

## 4. CSV Import Engine — Anomaly Detection Catalogue

The import engine never silently modifies or discards data. Every anomaly generates an `ImportAnomaly` record with a policy and leaves an audit trail.

### Anomaly Policies

| Policy | Meaning |
|---|---|
| `REJECT` | Row is immediately failed. No import. |
| `REVIEW_REQUIRED` | Human must explicitly approve or reject before row is processed. |
| `AUTO_FIX` | Engine resolves automatically (reserved for future use). |

### Anomaly Rules

| ID | Anomaly Type | Category | Severity | Policy | Description |
|---|---|---|---|---|---|
| A | `duplicate_expense` | `duplicate` | High | `REVIEW_REQUIRED` | Same title, date, payer, and amount already exists in the group. |
| B | `duplicate_settlement` | `duplicate` | High | `REVIEW_REQUIRED` | Same payer, receiver, date, and amount settlement already recorded. |
| C | `negative_amount` | `validation` | High | `REJECT` | Financial amounts must be positive. Negative values are rejected. |
| D | `zero_amount` | `validation` | Medium | `REVIEW_REQUIRED` | Zero-amount rows are likely placeholders or errors. |
| E | `unknown_user` | `unknown_user` | Critical | `REJECT` | Payer or participant username does not exist in the system. |
| F | `invalid_date` | `date` | High | `REJECT` | Date field is missing or uses an unrecognised format. |
| G | `unsupported_currency` | `currency` | High | `REJECT` | Currency code is not in the supported set (INR, USD, EUR, GBP). |
| H | `missing_required_fields` | `validation` | High | `REJECT` | One or more required columns are missing or unparseable. |
| I | `payer_not_active_on_date` / `participant_not_active_on_date` | `membership` | High | `REJECT` | User was not an active group member on the expense/payment date (validated via `is_member_on_date()`). |
| J | `settlement_logged_as_expense` | `settlement` | High | `REVIEW_REQUIRED` | Row description contains settlement keywords (e.g. "paid back", "reimbursement", "settled"). Must be classified by human reviewer. |
| K | `currency_conversion_required` | `currency` | Medium | `REVIEW_REQUIRED` | Row currency differs from group currency (e.g. USD row in INR group). Manual conversion review required. |
| L | `split_validation_failure` | `split` | High | `REJECT` | Non-equal split type was specified but no `splits_data` was provided. |

### Settlement Keyword Detection
The following description keywords trigger anomaly J (`settlement_logged_as_expense`):
`paid back`, `reimbursement`, `reimburse`, `payback`, `pay back`, `settled`, `settlement`, `transfer`, `repaid`, `repay`

---

## 5. CSV Import Review Workflow (Meera's Requirement)

1. User uploads a CSV file via `POST /api/imports/upload/`.
2. The pipeline parses all rows and detects anomalies.
3. If any row has a `REVIEW_REQUIRED` anomaly, the `ImportJob` status is set to `review_required` and processing pauses.
4. User reviews anomalies via `GET /api/imports/{id}/anomalies/`.
5. User submits a decision for each anomaly via `POST /api/imports/anomalies/{id}/decision/`.
6. Decision choices: `approve`, `reject`, `ignore`.
7. Each decision is recorded as an immutable `ImportDecision` record (with `decided_by`, `decision_reason`, and timestamp).
8. Once all `REVIEW_REQUIRED` anomalies are decided, the pipeline resumes and processes approved rows.
9. A final `ImportReport` is generated with a full anomaly breakdown.

**Rule: No data is ever silently modified or deleted. Every action has an audit trail.**

---

## 6. API Endpoints

### Groups
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/groups/` | Create group |
| GET | `/api/groups/` | List groups |
| GET | `/api/groups/{id}/` | Get group detail |
| POST | `/api/groups/{id}/members/` | Add member |
| POST | `/api/groups/{id}/leave/` | Leave group |

### Expenses
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/expenses/` | Create expense |
| GET | `/api/expenses/` | List expenses |
| GET | `/api/expenses/{id}/` | Expense detail |
| PUT | `/api/expenses/{id}/` | Update expense |
| DELETE | `/api/expenses/{id}/` | Soft-delete expense |

### Settlements
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/settlements/` | Record settlement |
| GET | `/api/settlements/` | List settlements |
| GET | `/api/settlements/{id}/` | Settlement detail |
| PUT | `/api/settlements/{id}/` | Update settlement |
| DELETE | `/api/settlements/{id}/` | Soft-delete settlement |

### Balance Engine
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/balances/groups/{id}/` | Group balance summary |
| GET | `/api/balances/groups/{id}/simplified/` | Simplified payback instructions |
| GET | `/api/balances/groups/{id}/users/{uid}/` | User balance explanation |
| GET | `/api/balances/groups/{id}/ledger/` | Raw chronological ledger |

### CSV Import
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/imports/upload/` | Upload CSV file |
| GET | `/api/imports/` | List import jobs |
| GET | `/api/imports/{id}/` | Import job detail |
| GET | `/api/imports/{id}/anomalies/` | List anomalies |
| POST | `/api/imports/anomalies/{id}/decision/` | Submit anomaly decision |
| GET | `/api/imports/{id}/report/` | Final import report |

---

## 7. Data Integrity Guarantees

1. **No hard deletes** — All records support soft-delete via `is_archived`.
2. **Immutable snapshots** — `ExpenseSnapshot` and `SettlementSnapshot` raise `ValidationError` on any update attempt.
3. **Zero-sum invariant** — Every ledger event (expense or settlement) must produce entries that sum to exactly zero.
4. **Membership date validation** — Every financial event validates all participants were active members on the event date.
5. **Audit trail** — Every `ImportDecision` preserves who made a decision, when, and why.
6. **Import traceability** — Every `Expense` and `Settlement` created via CSV import carries a `import_job` FK pointing back to the `ImportJob`.

---

## 8. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | Django 6.x |
| API | Django REST Framework |
| Database | PostgreSQL |
| Auth | Django built-in + Session/Basic auth |
| Migrations | Django ORM migrations |
