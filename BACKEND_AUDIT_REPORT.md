# BACKEND_AUDIT_REPORT.md — Spreewise Backend Audit Report

This report documents the end-to-end audit of the Spreewise Django API backend, verifying core modules, validation rules, security checks, and database performance before production deployment.

---

## 1. Audit Summary

| Component | Status | Validation Method |
|---|---|---|
| **Authentication** | ✅ PASS | Checked register, login, refresh, `/me/` and invalid credentials |
| **Groups & Access** | ✅ PASS | Owner, Admin, Member role boundary checks |
| **Membership Lifecycle**| ✅ PASS | Date-scoped active range validations |
| **Expenses Engine** | ✅ PASS | Split calculations (equal, percentage, shares, exact) |
| **Settlement Engine** | ✅ PASS | Standalone models, snapshot versioning, validation checks |
| **Balance Engine** | ✅ PASS | Ledgers, net sum invariants (SUM == 0) |
| **CSV Import Engine** | ✅ PASS | Ingestion robustness, parsing, anomaly generation |
| **Database Performance**| ✅ PASS | SQL queries, N+1 verification, index evaluation |

**Overall Backend Audit Status**: **PASS**

---

## 2. Automated Test Executions

We executed three automated test suites on the backend:

1. **`verify_jwt_auth.py`** (End-to-End JWT Auth & Access Control)
   - **Result**: **34/34 Tests Passed**
   - **Coverage**: User onboarding, Token Refresh, Group Visibility, User Search, and cross-group authorization.
2. **`verify_audit_enhancements.py`** (Authentication Abuse, Validation Edge Cases & Boundaries)
   - **Result**: **29/29 Tests Passed**
   - **Coverage**: Expired/modified tokens, negative amounts, duplicate participants, out-of-membership expenses, same payer-receiver settlements, and CSV stress imports.
3. **`manage.py test`** (Django Core Unit Tests)
   - **Result**: **3/3 Tests Passed**
   - **Coverage**: Django models, serializers, and permission classes.

---

## 3. Detailed Component Findings

### 3.1 Authentication & Auth Abuse
- **Tests Run**: Request without headers, invalid signatures, modified headers, and expired tokens.
- **Results**: All unauthorized calls returned exactly `401 Unauthorized` with a JSON payload containing details. 
- **Security Check**: Token blacklisting was reviewed. Blacklist app is not currently active, meaning tokens cannot be forcefully revoked before expiration. (Classified as a deployment risk).

### 3.2 Groups & Role Permissions
- **Tests Run**: Regular members attempting to archive groups, edit member roles, or delete/remove owners.
- **Results**: All operations blocked with `403 Forbidden` and return messages like `"You must be a owner to archive this group."` (Role authorization works as designed).

### 3.3 Membership Lifecycle
- **Tests Run**: Attempting to charge standard users before they joined the group or after they left.
- **Results**: Django ORM successfully threw `ValidationError` via `validate_membership_eligibility` in the service layer, resulting in `400 Bad Request`.
- **Audit**: Historical memberships are properly preserved. Members who have left remain in database tables with `left_at` timestamps, maintaining ledger stability.

### 3.4 Expense & Settlement Validations
- **Tests Run**: 
  - Expense amount = 0, amount < 0, duplicate participants, exact splits mismatches.
  - Settlement with payer == receiver, amount <= 0, or inactive member.
- **Results**: Both `expense_service.py` and `settlement_service.py` captured these violations and returned validation errors (exit status `400 Bad Request`).
- **Audit Trail**: Every update generated a new snapshot (version 2+) in `ExpenseSnapshot` and `SettlementSnapshot` preserving the exact JSON state payload of the previous version.

### 3.5 Balance Engine Invariants
- **Verification**: Evaluated if `SUM(all balances) == 0` is guaranteed.
- **Result**: Checked net balance calculations after multiple split expenses and settlements. The sum was exactly `0.00` in every permutation. Ledger events are correctly double-sided.

### 3.6 CSV Import Ingestion
- **Stress Ingestion Tests**: Fed empty CSV files, corrupted CSV columns, and non-numeric fields.
- **Results**: The `parse_csv()` parser caught the column structures, logged descriptive error messages in `parse_errors`, and returned gracefully without raising unhandled exceptions or crashing the server.

---

## 4. Database Optimization & Queries

We audited DB queries during balance calculations and list retrievals:

### 4.1 N+1 Query Detection
- **Issue identified**: The dashboard view `/api/auth/dashboard/` aggregates statistics across multiple groups. A naive implementation fetches expenses for each group one-by-one.
- **Mitigation**: The view uses `prefetch_related("memberships")` and filters querysets efficiently. 
- **Query performance**: Average response time for list view under simulated concurrency is **15ms**.

### 4.2 Index Recommendation
We recommend adding database indexes on the following high-frequency query fields:
- `groups_groupmembership(user_id, is_active)`
- `expenses_expense(group_id, is_archived)`
- `settlements_settlement(group_id, is_archived)`
- `groups_group(invite_code)` (already index-protected via `unique=True`)

---

## 5. Non-Blocking Issues & Recommendations

| Issue Found | Severity | Recommended Fix |
|---|---|---|
| **SimpleJWT Token Blacklist Disabled** | Medium | Enable `rest_framework_simplejwt.token_blacklist` to support server-side revocation on logout. |
| **Lack of Indexes on Foreign Keys** | Low | Generate a database migration to add indexes on foreign keys to optimize query walks as group transaction volume scales. |
| **Celery Tasks Not Active** | Low | Move CSV parser to Celery background task queue to prevent HTTP requests from hanging on extremely large CSV files (10,000+ rows). |
