# API_HEALTH_REPORT.md — Spreewise API Health Report

This report catalogs all REST API endpoints of the Spreewise shared-expense application, detailing request methods, authorization requirements, response types, error payloads, and audit statuses.

---

## 1. Auth Endpoints

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **POST** | `/api/auth/register/` | Public | `{username, email, password, confirm_password, full_name}` | `201 Created` + `{access, refresh, user}` | `400` validation mismatch | **PASS** |
| **POST** | `/api/auth/login/` | Public | `{username, password}` | `200 OK` + `{access, refresh}` | `401` bad credentials | **PASS** |
| **POST** | `/api/auth/refresh/` | Public | `{refresh}` | `200 OK` + `{access}` | `401` expired refresh | **PASS** |
| **POST** | `/api/auth/logout/` | JWT | `{refresh}` | `200 OK` + `{detail}` | `401` missing header | **PASS** |
| **GET** | `/api/auth/me/` | JWT | None | `200 OK` + `{username, email, full_name}` | `401` modified token | **PASS** |
| **GET** | `/api/auth/dashboard/` | JWT | None | `200 OK` + `{my_groups, net_balance, ...}` | `401` unauthorized | **PASS** |

---

## 2. Groups & Memberships

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **GET** | `/api/groups/` | JWT | None | `200 OK` + List of user's active groups | `401` unauthorized | **PASS** |
| **POST** | `/api/groups/` | JWT | `{name, description, currency}` | `201 Created` + Group details with `SPW-...` code | `400` missing name | **PASS** |
| **GET** | `/api/groups/{id}/` | JWT | None | `200 OK` + Group detail + nested members | `404` group not found / not member | **PASS** |
| **DELETE**| `/api/groups/{id}/` | JWT | None | `200 OK` + `{detail: "Group archived"}` | `403` if not Owner | **PASS** |
| **POST** | `/api/groups/join/` | JWT | `{invite_code}` | `201 Created` + `{group_id, membership}` | `400` invalid / duplicate code | **PASS** |
| **POST** | `/api/groups/{id}/members/` | JWT | `{user_id, joined_at, role}` | `201 Created` + Membership details | `403` if not Owner/Admin | **PASS** |
| **DELETE**| `/api/groups/{id}/members/{mid}/remove/` | JWT | None | `200 OK` + `{detail: "Member removed"}` | `403` if not Owner/Admin | **PASS** |
| **POST** | `/api/groups/{id}/members/{mid}/role/` | JWT | `{role}` | `200 OK` + `{detail: "Role updated"}` | `403` if not Owner | **PASS** |

---

## 3. Expenses Engine

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **GET** | `/api/expenses/?group_id=`| JWT | Query param `group_id` | `200 OK` + List of active group expenses | `404` if not group member | **PASS** |
| **POST** | `/api/expenses/` | JWT | `{group_id, title, amount, expense_date, paid_by_id, split_type, participant_ids, splits}` | `201 Created` + Expense splits + snapshot | `400` sum mismatch or invalid member dates | **PASS** |
| **GET** | `/api/expenses/{id}/` | JWT | None | `200 OK` + Full detail + nested splits/snapshots | `404` if not group member | **PASS** |
| **PUT** | `/api/expenses/{id}/` | JWT | Full payload updates | `200 OK` + Updated details + snapshot v2 | `400` split calculations invalid | **PASS** |
| **DELETE**| `/api/expenses/{id}/` | JWT | None | `200 OK` + `{detail: "Expense archived"}` | `404` if not group member | **PASS** |

---

## 4. Settlements

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **GET** | `/api/settlements/?group_id=`| JWT | Query param `group_id` | `200 OK` + List of settlements | `404` if not group member | **PASS** |
| **POST** | `/api/settlements/` | JWT | `{group_id, payer_id, receiver_id, amount, payment_date}` | `201 Created` + Settlement + snapshot | `400` payer == receiver or negative amount | **PASS** |
| **DELETE**| `/api/settlements/{id}/` | JWT | None | `200 OK` + `{detail: "Settlement archived"}` | `404` if not group member | **PASS** |

---

## 5. Balance Engine

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **GET** | `/api/balances/groups/{gid}/` | JWT | None | `200 OK` + Net balance per member | `403` if not active member | **PASS** |
| **GET** | `/api/balances/groups/{gid}/simplified/` | JWT | None | `200 OK` + Minimal payback directions | `403` if not active member | **PASS** |
| **GET** | `/api/balances/groups/{gid}/users/{uid}/` | JWT | None | `200 OK` + Explained breakdown | `403` if not active member | **PASS** |
| **GET** | `/api/balances/groups/{gid}/ledger/` | JWT | None | `200 OK` + Chronological events | `403` if not active member | **PASS** |

---

## 6. CSV Imports

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **POST** | `/api/imports/upload/` | JWT | `{group_id, csv_file}` | `201 Created` + Import job with status | `403` if member (requires admin/owner) | **PASS** |
| **GET** | `/api/imports/{id}/anomalies/` | JWT | None | `200 OK` + List of anomalies | `404` if job not found | **PASS** |
| **POST** | `/api/imports/{id}/decide/` | JWT | `{decisions: [{anomaly_id, decision, reason}]}` | `200 OK` + Status details | `400` invalid decision type | **PASS** |
| **POST** | `/api/imports/{id}/commit/` | JWT | None | `200 OK` + Final report details | `400` if unresolved anomalies exist | **PASS** |

---

## 7. User Discovery

| Method | Endpoint | Auth | Expected Payload | Response (Success) | Error Case | Status |
|---|---|---|---|---|---|---|
| **GET** | `/api/users/search/?q=` | JWT | Query string `q` | `200 OK` + Matches list (excluding self) | `401` unauthorized | **PASS** |
