# SECURITY_AUDIT_REPORT.md — Spreewise Security Audit Report

This report evaluates the security posture of the Spreewise shared-expense platform, specifically auditing multi-tenant data isolation boundaries, authorization controls, credential policies, and token configurations.

---

## 1. Audit Summary

| Security Vector | Status | Evaluation Findings |
|---|---|---|
| **Multi-Tenant Data Isolation** | 🛡️ SECURE | Scopes all querysets to the requesting user's active group memberships. User A cannot view User B's groups or associated records. |
| **Direct Object Access (ID manipulation)** | 🛡️ SECURE | Accessing resources using guessed IDs (e.g. `/api/expenses/{id}/`) returns exactly `404 Not Found` (by filtering on scoped querysets) or `403 Forbidden` (on balance checks). |
| **JWT Token Security** | ⚠️ ADEQUATE | Uses DRF simple-jwt. Signature validation prevents tampering. Refresh tokens have rotation enabled. Risk: Access token lifetime is 7 days in dev. |
| **Password & Auth Policy** | 🛡️ SECURE | Standard Django password validation is active. Hashes passwords using PBKDF2 with SHA256. |
| **Frontend Token Leakage** | 🛡️ SECURE | Tokens are kept in `sessionStorage` instead of `localStorage`, preventing persistent exposure if the tab is closed. |

**Overall Security Status**: **PASS**

---

## 2. Multi-Tenant Data Isolation Test Results

We ran target boundary abuse tests using User A (`user_a_audit`) and User B (`user_b_audit`).

### 2.1 Cross-Group Boundary Attempt
- **Method**: User B created a private group (Group ID 99). User A attempted to view details via `GET /api/groups/99/`.
- **Result**: **404 Not Found**. 
- **Mechanism**: The view's `get_queryset()` returns `Group.objects.filter(id__in=user_group_ids)`. Since User A is not a member, the record is excluded from User A's database lookup space, returning 404 instead of leaking group metadata.

### 2.2 Cross-Expense Manipulation Attempt
- **Method**: User B created an expense (ID 102) in their private group. User A attempted to retrieve the details via `GET /api/expenses/102/` and modify it via `PUT /api/expenses/102/`.
- **Result**: **404 Not Found** for both calls.
- **Mechanism**: Querysets for `ExpenseViewSet` are restricted to the user's active membership group IDs. Since User A's groups do not include the group of expense 102, the lookup fails with 404, preventing unauthorized direct object access.

### 2.3 Cross-Import Log Leakage Attempt
- **Method**: User B created an import job. User A listed import jobs via `GET /api/imports/`.
- **Result**: **PASS**. User B's import jobs were omitted from User A's response.

### 2.4 Balance Engine Scoping
- **Method**: User A attempted to fetch balances for Group B via `/api/balances/groups/99/`.
- **Result**: **403 Forbidden**.
- **Mechanism**: `_assert_group_member()` explicitly verifies membership in the database before calculating or returning balances.

---

## 3. Vulnerability Review & Risk Scoring

### 3.1 Token Expiry Mismatch (Severity: Medium)
* **Finding**: `ACCESS_TOKEN_LIFETIME` is configured to `timedelta(days=7)` in `settings.py`.
* **Risk**: If an access token is compromised (via XSS or device exposure), the attacker can access the system for 7 days without needing credentials.
* **Remediation**: Reduce `ACCESS_TOKEN_LIFETIME` to `15 minutes` in production settings, relying on the client's silent auto-refresh interceptor to get new tokens.

### 3.2 Missing Token Blacklist (Severity: Low)
* **Finding**: SimpleJWT's logout blacklist app is not activated (`BLACKLIST_AFTER_ROTATION = False`).
* **Risk**: Logging out removes the token from the browser context but does not invalidate it on the server. If the token was intercepted, it remains valid until its natural expiration.
* **Remediation**: Enable `rest_framework_simplejwt.token_blacklist` and call the blacklist method inside `/api/auth/logout/`.

### 3.3 Rate Limiting / Brute Force (Severity: Medium)
* **Finding**: No API throttling is active on `/api/auth/login/` or `/api/auth/register/`.
* **Risk**: Attackers can execute brute-force password attacks against user accounts.
* **Remediation**: Configure DRF `AnonRateThrottle` and `UserRateThrottle` classes in `settings.py`.

---

## 4. Key Security Controls in Place

1. **`UserAttributeSimilarityValidator` / `MinimumLengthValidator`**: Enforces secure passwords during signup.
2. **`sessionStorage`**: Prevents persistent storage of tokens on disk, closing tab-scoped token hijacking vectors.
3. **Database Cascading Protections**: Use of `PROTECT` on primary relationships prevents users from cascading deletions onto ledger balances, preserving database state consistency.
