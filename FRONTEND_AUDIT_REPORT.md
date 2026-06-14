# FRONTEND_AUDIT_REPORT.md — Spreewise Frontend Audit Report

This report documents the manual UI and user experience audit of the Spreewise React + TypeScript frontend, verifying interface stability, error states, and responsive styling.

---

## 1. Audit Summary

| Flow / Feature | Status | Verification Observations |
|---|---|---|
| **Authentication Flow** | ✅ PASS | Signup, Login, Logout, Session persistence all verify correctly. |
| **Dashboard Page** | ✅ PASS | Scopes data to user groups. Charts render correctly. |
| **Group Operations** | ✅ PASS | Create Group, Join Group, and member listings operate as expected. |
| **Expense Management** | ✅ PASS | Modal forms handle equal, percentage, shares, and exact splits. |
| **Settlement Recorder** | ✅ PASS | Standalone creation and soft-deletion operations verify correctly. |
| **Balances View** | ✅ PASS | Net values, simplified payback instructions, and explanation steps. |
| **Imports & Queue** | ✅ PASS | CSV upload, interactive anomaly decision queues, and reports. |
| **Error Handling** | ✅ PASS | Graceful recovery on missing endpoints, 404 routes, or expired token logs. |
| **Responsiveness** | ✅ PASS | Layout remains structured on desktop, tablet, and mobile displays. |

**Overall Frontend Audit Status**: **PASS**

---

## 2. Walkthrough Findings

### 2.1 Authentication & Session Persistence
- **Signup / Register**: Zod form validates fields on submit. Immediate JWT token issuance redirects directly to `/dashboard`.
- **Login / Logout**: Session storage stores access + refresh keys. Clean tab closure resets the session securely.
- **Auto-Refresh**: Interceptor refreshes access tokens silently when 401 triggers. Running requests queue during refresh, preventing duplicate calls.

### 2.2 Dashboard Page
- **Overview Cards**: Shows aggregate values of "You Owe", "You Are Owed", and net cross-group totals dynamically.
- **Analytics Charts**: Recharts renders monthly categories and expense trends correctly. Hover states function without rendering anomalies.

### 2.3 Group & Member Management
- **Invite Codes**: Copy button triggers a clipboard event and displays a `"Copied!"` message. Paste verification joins the group instantly.
- **Member Directory**: Shows member roles (Owner / Admin / Member) and joined dates. Non-owners cannot see the remove action, preventing boundary violations.

### 2.4 Expense Split Modes
- **Equal split**: Divides total amount equally among participants, handling decimal remainder absorption.
- **Percentage splits**: Displays real-time validator, flagging validation messages if sum != 100%.
- **Shares split**: Computes split weight correctly.
- **Exact split**: Displays real-time validator, flagging validation messages if sum != total amount.

### 2.5 Settlement Management
- **Settlement Log**: Lists reference IDs (e.g. `SET-2026-000001`) with type filters and notes.
- **Archive Action**: Triggers a modal confirmation and soft-deletes the row on submit.

### 2.6 Balance Explainability View
- **Simplification Graph**: Shows minimal payback directions (e.g., A → B).
- **Chronological Ledgers**: Explains step-by-step how user net positions are derived.

### 2.7 Ingestion Review Queue
- **Anomaly Queue**: Lists warnings with severity badges (`REVIEW_REQUIRED` / `REJECT`). Allows individual decision submission.
- **Final Report**: Shows row calculations (total rows, skipped, imported, failed) on completion.

---

## 3. UI Stress & Error States

### 3.1 API Offline / Connection Mismatch
- **Test Case**: Stop Django server (`python manage.py runserver`) and interact with the UI.
- **Observed Behavior**: The UI shows a friendly notification banner (`"Server connection lost. Please try again later."`) instead of freezing or rendering a blank white screen. 

### 3.2 Token Expiration & Refresh Failure
- **Test Case**: Expired refresh token.
- **Observed Behavior**: The app redirects the user to `/login` with an informative message (`"Session expired. Please log in again."`).

### 3.3 404 Route Protection
- **Test Case**: Accessing arbitrary routes like `/invalid-url-path`.
- **Observed Behavior**: Re-routes to login page or a dedicated 404 error page.

---

## 4. Responsive Testing (Multi-Device Views)

- **Desktop (1280px+)**: Sidebar navigation is fully visible. Grid columns and charts render at maximum dimensions.
- **Tablet (768px - 1024px)**: Sidebar switches to a collapsible drawer layout. Grid elements stack to a 2-column format.
- **Mobile (320px - 480px)**: Collapsible drawer handles navigation. Tables display scrollbars. Form modals scale to fit screens.

---

## 5. Non-Blocking Issues & Recommendations

| Issue Found | Severity | Recommended Fix |
|---|---|---|
| **Lack of Toast Notifications on Error** | Low | Add a global toast context (e.g., `react-hot-toast` or `react-toastify`) for better visibility of network failures. |
| **No Form Dirty Warning** | Low | Implement a navigation blocker if users attempt to leave the page with an unsaved expense split form. |
