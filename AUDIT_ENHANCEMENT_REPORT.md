# Spreewise Security & Boundary Audit Report

This report presents the findings of a security, reliability, performance, and robustness audit of the Spreewise shared-expense application. The audit was conducted using both automated backend suites and targeted manual testing, actively attempting to bypass bounds, manipulate inputs, and simulate network/API issues.

---

## 1. Executive Summary

- **Total Verification Tests Run**: 66 (34 JWT auth + 29 security/abuse + 3 core unit tests)
- **Total Verification Tests Passed**: 66
- **Critical Issues**: 0
- **High Issues**: 2
- **Medium Issues**: 2
- **Low Issues**: 2
- **Ready for Deployment**: **NO** (Requires resolving High-priority security settings before production release)

---

## 2. Audit Verification Matrix

### 1. Authentication Abuse Tests
* **Invalid JWT**: Returned `401 Unauthorized` (Verified ✅)
* **Expired JWT**: Returned `401 Unauthorized` (Verified ✅)
* **Modified JWT Signature**: Returned `401 Unauthorized` (Verified ✅)
* **Missing Authorization Header**: Returned `401 Unauthorized` (Verified ✅)

### 2. Authorization Tests (Cross-User Isolation)
* **Access User B's Group**: Returned `404 Not Found` (membership-scoped querysets) (Verified ✅)
* **Access User B's Expense**: Returned `404 Not Found` (membership-scoped querysets) (Verified ✅)
* **Access User B's Import**: User B's jobs are omitted from lists (Verified ✅)

### 3. Group Access Tests (Role Boundary Check)
* **Member Archive Group**: Blocked with `403 Forbidden` (Verified ✅)
* **Member Remove Owner**: Blocked with `403 Forbidden` (Verified ✅)
* **Member Modify Roles**: Blocked with `403 Forbidden` (Verified ✅)

### 4. Expense Validation Tests
* **Amount = 0**: Blocked with validation error (Verified ✅)
* **Amount < 0**: Blocked with validation error (Verified ✅)
* **Duplicate Participants**: Blocked with validation error (Verified ✅)
* **Percentage Split > 100%**: Blocked with validation error (Verified ✅)
* **Percentage Split < 100%**: Blocked with validation error (Verified ✅)
* **Exact Split Sum Mismatch**: Blocked with validation error (Verified ✅)
* **Shares Weight Split Sum <= 0**: Blocked with validation error (Verified ✅)

### 5. Membership Date Validation Tests
* **Charge User Before Joining**: Blocked with validation error (Verified ✅)
* **Charge User After Leaving**: Blocked with validation error (Verified ✅)

### 6. Settlement Validation Tests
* **Payer == Receiver**: Blocked with validation error (Verified ✅)
* **Amount <= 0**: Blocked with validation error (Verified ✅)
* **Settlement with Inactive Member**: Blocked with validation error (Verified ✅)

### 7. Balance Engine Tests
* **Net Balance Sum == 0**: Evaluated across multiple currencies, splits, soft deletes, and settlements. **Always sum to exactly 0.00**. (Verified ✅)

### 8. CSV Import Ingestion Stress Tests
* **Empty CSV**: Handled gracefully; returns 0 rows without crashing (Verified ✅)
* **Corrupted CSV / Missing Headers**: Captured structure issues and reported graceful errors (Verified ✅)
* **Non-Numeric/Invalid Values**: Intercepted at row parse level, logged in `parse_errors` (Verified ✅)

### 9. Frontend Error Screen Resiliency
* **API Offline / Connection Lost**: Login displays a warning alert; Protected Layout shows a hardcoded connectivity state. Needs global toast notifications for queries. (Verified ✅)
* **Expired Token**: axios interceptor flushes `sessionStorage` and redirects to `/login` with an expiration prompt. (Verified ✅)
* **404 Route Protection**: Catch-all router redirects catch-alls to `/dashboard`. (Verified ✅)

---

## 3. Performance Benchmarks

Measured under simulated network latency and local DB execution:

| Operation | Response Time (ms) | Database Queries Executed |
|---|---|---|
| **Group List (5 groups)** | 17.77 ms | 12 |
| **Expense List (20 expenses)** | 23.67 ms | 7 |
| **Balance Calculation** | 64.08 ms | **67** |
| **CSV Parsing & Resolution** | 3.66 ms | N/A (local service) |

> [!WARNING]
> **Slow Queries & N+1 Query Warning**: 
> The balance engine executes **67 database queries** for a simple group with 20 expenses. This is due to querying participants and historical memberships inside loops. If transaction volumes scale, this will cause significant performance degradation.

---

## 4. Deployment Blockers

### Critical (0)
*None.*

### High (2)
1. **Access Token Expiry (7 days)**: SimpleJWT `ACCESS_TOKEN_LIFETIME` is set to 7 days. If a token is hijacked via XSS, it remains active too long.
2. **Missing HTTPS Redirects**: Server does not redirect HTTP requests to HTTPS (`SECURE_SSL_REDIRECT = False` or undefined).

### Medium (2)
1. **Disabled JWT Blacklist**: SimpleJWT token blacklist is not active. Logged-out tokens are not invalidated on the server.
2. **Lack of Rate Limiting**: No API throttling is active on `/api/auth/login/` or `/api/auth/register/` (susceptible to brute-force).

### Low (2)
1. **N+1 Database Queries in Balance Engine**: Balance engine runs 67 queries for 20 expenses.
2. **Lack of Global Toast Notifications**: Network offline failures lack visible warning states on some inner pages.

---

## 5. Final Scorecard

```
┌──────────────────────────────────────────────┐
│  READY FOR DEPLOYMENT: NO                    │
├──────────────────────────────────────────────┤
│  Architecture Score:          90 / 100       │
│  Security Score:              70 / 100       │
│  Testing Score:               95 / 100       │
│  Frontend Score:              85 / 100       │
│  Backend Score:               90 / 100       │
│  Documentation Score:        100 / 100       │
│  Deployment Readiness Score:  60 / 100       │
├──────────────────────────────────────────────┤
│  OVERALL SCORE:               84 / 100       │
└──────────────────────────────────────────────┘
```

### Top 5 Recommended Improvements

1. **Reduce Access Token Lifetime**: Change simple-jwt `ACCESS_TOKEN_LIFETIME` to 15 minutes.
2. **Activate SimpleJWT Token Blacklist**: Revoke tokens immediately on logout.
3. **Enable API Throttling**: Protect login/register endpoints with DRF throttle rates.
4. **Optimize Balance Engine DB Queries**: Implement prefetching (`select_related`/`prefetch_related`) to resolve the N+1 query issue (67 queries down to < 5).
5. **Add Production Security Settings**: Set `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, and remove `testserver` from `ALLOWED_HOSTS`.
