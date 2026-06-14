# SUBMISSION_CHECKLIST.md — Spreewise Submission Package

> Pre-submission verification checklist. Mark each item complete before submitting.

---

## Submission Package Status

### Core Deliverables

| Item | Status | Location |
|---|---|---|
| GitHub Repository | ✅ Done | https://github.com/SalilkumarMishra/spreewise |
| README.md | ✅ Done | `/README.md` |
| SCOPE.md | ✅ Done | `/SCOPE.md` |
| DECISIONS.md | ✅ Done | `/DECISIONS.md` |
| AI_USAGE.md | ✅ Done | `/AI_USAGE.md` |
| JWT_UPGRADE_REPORT.md | ✅ Done | `/JWT_UPGRADE_REPORT.md` |
| Verification Suite | ✅ Done | `backend/verify_jwt_auth.py` (34/34 pass) |

---

### Application Functionality Checklist

#### Backend
- [x] JWT Registration endpoint (`POST /api/auth/register/`)
- [x] JWT Login endpoint (`POST /api/auth/login/`)
- [x] JWT Refresh endpoint (`POST /api/auth/refresh/`)
- [x] JWT Logout endpoint (`POST /api/auth/logout/`)
- [x] Current User endpoint (`GET /api/auth/me/`)
- [x] Personalized Dashboard endpoint (`GET /api/auth/dashboard/`)
- [x] User Search endpoint (`GET /api/users/search/?q=`)
- [x] Group CRUD with invite code generation
- [x] Join group via invite code (`POST /api/groups/join/`)
- [x] Role-based permissions (Owner / Admin / Member)
- [x] Membership-scoped group queryset
- [x] Membership-scoped expense queryset
- [x] Membership-scoped settlement queryset
- [x] Membership-scoped balance access (403 for non-members)
- [x] Membership-scoped import jobs
- [x] CSV upload with 13 anomaly detection rules
- [x] User Resolution Layer (5-stage identity matching)
- [x] Import review workflow (approve/reject anomalies)
- [x] Balance engine with greedy debt simplification
- [x] Expense snapshots (immutable version history)
- [x] Settlement snapshots (immutable version history)
- [x] Soft deletes on Group, Expense, Settlement

#### Frontend
- [x] Login page (`/login`)
- [x] Signup page (`/signup`)
- [x] Dashboard with personal overview (`/dashboard`)
- [x] Groups list and detail pages (`/groups`)
- [x] Join Group page (`/join-group`)
- [x] Expense creation and listing
- [x] Settlement creation and listing
- [x] Balance view with debt simplification
- [x] CSV Import upload page (`/imports`)
- [x] Anomaly review queue
- [x] Import report view
- [x] Protected routes (redirect unauthenticated users to `/login`)
- [x] JWT auto-refresh interceptor in API client
- [x] User role badge in sidebar (OWNER / ADMIN / MEMBER)
- [x] Active group selector in header

---

### Documentation Checklist

- [x] Architecture Mermaid diagram in README
- [x] Setup instructions (backend + frontend + database)
- [x] All API endpoints documented
- [x] All 13 anomaly types documented in SCOPE.md
- [x] All 11 ADRs written in DECISIONS.md
- [x] 5 AI bug examples documented in AI_USAGE.md
- [x] JWT upgrade architecture report

---

### Testing Checklist

- [x] `verify_jwt_auth.py` — 34/34 tests pass
- [x] `verify_user_resolution.py` — user resolution tests pass
- [x] `python manage.py test` — 3/3 Django unit tests pass

---

### Pre-Interview Checklist

- [ ] Run backend: `cd backend && venv\Scripts\activate && python manage.py runserver`
- [ ] Run frontend: `cd frontend && npm run dev`
- [ ] Create a test user via `/signup`
- [ ] Create a group — note the `SPW-...` invite code
- [ ] Create a second user and join via invite code
- [ ] Create at least 2 expenses (different split types)
- [ ] Create a settlement
- [ ] Verify balances update correctly
- [ ] Upload the test CSV file
- [ ] Review and resolve anomalies
- [ ] Commit the import
- [ ] Verify the import report
- [ ] Know the answers to the TOP_30_INTERVIEW_QUESTIONS.md

---

### Screenshots Required

See `SCREENSHOT_GUIDE.md` for the full list of required screenshots and why each is important.

- [ ] Login page
- [ ] Signup page
- [ ] Dashboard (with personal overview cards)
- [ ] Group detail with members
- [ ] Expense creation form
- [ ] Settlement creation form
- [ ] Balances with debt simplification
- [ ] CSV upload page
- [ ] Anomaly review queue
- [ ] Import report
- [ ] Invite code join page

---

## GitHub Repository Checklist

- [x] All files committed (37 files in commit `8c571bd`)
- [x] `.gitignore` excludes `venv/`, `*.pyc`, `.env`
- [x] `requirements.txt` is up to date
- [x] `README.md` renders correctly on GitHub
- [x] Mermaid diagram renders in GitHub's Markdown renderer
- [ ] Repository is public (verify before submission)
- [ ] Repository description is set
- [ ] Repository topics/tags are set (e.g., `django`, `react`, `expense-tracker`, `jwt`)

---

## Final Sign-Off

| Criterion | Status |
|---|---|
| Backend starts without errors | ✅ |
| Frontend starts without errors | ✅ |
| User can register and log in | ✅ |
| JWT token refresh works | ✅ |
| Group invite system works | ✅ |
| CSV import pipeline works | ✅ |
| Balance engine is correct | ✅ |
| All verification tests pass | ✅ (34/34) |
| Documentation is accurate | ✅ |
| Ready for technical interview | ✅ |
