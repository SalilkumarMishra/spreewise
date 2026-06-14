# TOP_30_INTERVIEW_QUESTIONS.md — Spreewise Technical Interview Preparation

> Model answers to the 30 most likely questions in a technical interview for Spreewise. Read all answers before the interview. Practice explaining each aloud.

---

## System Design

---

### Q1. Walk me through the overall architecture of Spreewise.

**Model Answer:**
Spreewise has a three-layer architecture:

1. **Frontend** — React + TypeScript built with Vite. Uses React Query for server state, Axios for API calls with a Bearer token interceptor, and AuthContext for JWT state management. All sensitive data is stored in sessionStorage, not localStorage.

2. **Backend** — Django + Django REST Framework. Organized into 6 apps: `accounts` (auth), `groups` (membership), `expenses`, `settlements`, `balance_engine`, and `imports`. All API endpoints require JWT authentication and enforce membership-scoped access.

3. **Database** — PostgreSQL. The schema uses foreign keys with `PROTECT` on user references (to prevent accidental user deletion cascading to expenses) and `SET_NULL` on audit references (so an `ImportJob` deletion doesn't cascade to orphan expenses).

The balance engine does not store balances in the database — it computes them on-demand by walking the full ledger of expenses and settlements.

---

### Q2. Why did you choose Django + DRF over FastAPI or Node.js?

**Model Answer:**
Three reasons: 1) Django ORM provides a mature migration system that was critical for the complex membership and snapshot models. 2) Django Admin provided instant data management without building a separate admin interface. 3) DRF's ViewSet + Router pattern reduces boilerplate while remaining highly customizable. FastAPI is faster for pure API scenarios, but Django's ecosystem (admin, migrations, ORM) was the right trade-off for this data-heavy application.

---

### Q3. How does the request lifecycle work end-to-end for loading the dashboard?

**Model Answer:**
1. User opens dashboard — React renders with no data
2. `useQuery(['dashboard'])` fires → Axios GET to `/api/auth/dashboard/`
3. API client injects `Authorization: Bearer <access_token>` header
4. DRF JWT middleware validates the token
5. `DashboardView.get()` queries `GroupMembership` to find the user's groups
6. For each group, `balance_service.calculate_group_balances()` computes net balances
7. Response returns: `my_groups`, `net_balance` (you_owe/you_are_owed/net), `pending_import_reviews`
8. React renders the three overview cards and charts

If the access token is expired: Axios interceptor catches the 401, calls `POST /api/auth/refresh/`, gets a new access token, retries the original request transparently.

---

## Database Design

---

### Q4. Explain the GroupMembership model and why it tracks join/leave dates.

**Model Answer:**
`GroupMembership` has `joined_at` and `left_at` DateFields. When a user leaves a group, `left_at` is set and `is_active` becomes `False`. The record is NOT deleted.

This matters for two reasons: 1) **Balance correctness** — if Meera was in a group from February to March, her historical expenses still count toward balances even after she leaves. 2) **CSV import validation** — when importing historical data, Rule I in the anomaly detector checks `group.is_user_member_on_date(user, expense_date)` to reject rows where the payer/participant wasn't active on that date.

---

### Q5. Why do you use soft deletes instead of hard deletes?

**Model Answer:**
Three reasons: 1) **Balance integrity** — an expense contributes to net balances. If Alice paid ₹1,000 and it's hard-deleted after Rohan settled ₹500 back, the ledger becomes corrupted. 2) **Import traceability** — each expense has an `import_job` FK. Hard-deleting the expense would orphan the import reference. 3) **Auditability** — financial systems must always answer "why did this balance change?" Archived records enable answering that question.

---

### Q6. What is the purpose of ExpenseSnapshot?

**Model Answer:**
`ExpenseSnapshot` is an immutable audit record. Every time an expense is created or updated, a new snapshot version is created containing the full state: expense fields, all participants, all split amounts. The snapshot's `save()` method raises `ValidationError` if called on an existing snapshot — it's immutable by design.

This serves three purposes: 1) **Audit trail** — you can reconstruct exactly what the expense looked like when a given balance was computed. 2) **Dispute resolution** — if a user disputes their share, you can show them version 1 vs. version 2 of the expense. 3) **Explainability** — the balance explanation service can reference the snapshot that determined the user's calculated_amount.

---

### Q7. How does the settlement reference_id work?

**Model Answer:**
`Settlement.reference_id` is a unique CharField generated server-side (UUID or sequential identifier). Its primary purpose is idempotency in CSV imports — if the same settlement appears in two different CSV files, the second import will detect the duplicate by checking `reference_id` or the (payer, receiver, amount, date) composite. The unique constraint also prevents UI bugs from creating duplicate settlements via double-form-submission.

---

## Balance Engine

---

### Q8. Explain the balance computation algorithm.

**Model Answer:**
`balance_service.calculate_group_balances()` does this:

1. Fetch all non-archived expenses for the group
2. For each expense: the `paid_by` user gains credit equal to `amount`. Each participant's `calculated_amount` from `ExpenseSplit` is subtracted from their balance
3. Fetch all non-archived settlements
4. For each settlement: the payer's balance increases (their debt is reduced), the receiver's balance decreases (they've been repaid)
5. Return the net balance per user

Example: Aisha pays ₹900 for 3 equal-split dinner. Each person's share = ₹300.
- Aisha: +900 - 300 = +600 (is owed ₹600)
- Rohan: 0 - 300 = -300 (owes ₹300)
- Priya: 0 - 300 = -300 (owes ₹300)

If Rohan settles ₹300 to Aisha:
- Rohan: -300 + 300 = 0 (settled)
- Aisha: +600 - 300 = +300 (still owed ₹300 from Priya)

---

### Q9. Why is the settlement sign convention important?

**Model Answer:**
This was an actual bug in the initial implementation. A settlement is NOT a new expense — it's a debt cancellation. The sign convention is:
- Settlement payer: balance INCREASES (they're reducing their debt)
- Settlement receiver: balance DECREASES (they've been repaid)

Applying the wrong sign (treating settlements like expenses) would cause balances to diverge from reality — users would appear to owe more after making a payment. I verified the convention by constructing a simple 2-person test case, computing the expected result manually, and comparing to the engine output.

---

### Q10. Explain the debt simplification algorithm.

**Model Answer:**
`simplification_service.simplify_debts()` implements a greedy algorithm:

1. Call `calculate_group_balances()` to get net positions
2. Separate into debtors (balance < 0) and creditors (balance > 0)
3. Sort both lists by amount descending (largest first)
4. Iteratively match: the largest debtor pays the largest creditor up to `min(debtor_amount, creditor_amount)`. Subtract the settled amount from both. Move to the next debtor/creditor when either reaches zero

This produces the minimum (or near-minimum) number of payments. For a group of N people, this runs in O(N log N) time due to sorting.

Example: A owes ₹500, B owes ₹300, C is owed ₹800.
Greedy result: A→C ₹500, B→C ₹300. Total: 2 payments instead of potentially many more.

---

### Q11. What is the ledger service?

**Model Answer:**
`ledger_service.py` exposes the raw chronological list of ledger entries that `balance_service` uses to compute balances. Each entry is a dict with: type (expense/settlement), date, amount, who paid, and what each person owes. This powers the `GET /balances/groups/{id}/ledger/` endpoint, which lets users trace exactly how their balance was computed — "On Feb 14, Aisha paid ₹1,200 for Dinner; your share was ₹400."

---

## CSV Import

---

### Q12. Walk me through the CSV import pipeline end-to-end.

**Model Answer:**
1. **Upload**: User uploads a CSV file to `POST /api/imports/upload/`. The file is validated as CSV. An `ImportJob` is created with status `processing`.

2. **Parsing** (`csv_parser.py`): Each row is parsed into a structured dict: description → title, amount (validated), date (validated), payer (raw name), participants (list), split type, currency.

3. **User Resolution** (`user_resolver.py`): Before anomaly detection, each payer/participant name is run through the 5-stage resolver. Resolved user IDs are stored in `parsed_data`.

4. **Anomaly Detection** (`anomaly_detector.py`): 13 rules run against each parsed row. Each rule creates an `ImportAnomaly` with a policy: `REJECT`, `REVIEW_REQUIRED`, or `AUTO_FIX`.

5. **Review Queue**: If any `REVIEW_REQUIRED` anomalies exist, the `ImportJob` status becomes `review_required`. The user visits the review queue to approve/reject each anomaly.

6. **Commit** (`import_processor.py`): After all decisions are made, `POST /api/imports/{id}/commit/` processes each row. Approved rows become `Expense` or `Settlement` records. Rejected rows are skipped. A final `ImportReport` is generated.

---

### Q13. What is the User Resolution Layer and why was it needed?

**Model Answer:**
CSV files contain human-typed names ("Aisha", "ROHAN", "Priya S") while the database stores usernames in lowercase ("aisha", "rohan", "priya"). Without resolution, every name mismatch generates a false-positive `unknown_user` anomaly.

The 5-stage resolver runs before anomaly detection:
1. Case-insensitive username match ("Aisha" → "aisha")
2. First-name match
3. Full-name match
4. Unique prefix match ("Priya S" → "priya" if only one user matches)
5. Alias dictionary fallback

Only if all 5 stages fail does the `unknown_user` anomaly fire. This eliminated the majority of false positives in the test dataset.

---

### Q14. What happens when the anomaly detector detects a duplicate expense?

**Model Answer:**
Rule A queries the database for an existing expense with the same (group, date, amount, paid_by, title, is_archived=False). If found, an `ImportAnomaly` is created with type `duplicate_expense`, severity `high`, and policy `REVIEW_REQUIRED`.

The row is held in `review_required` status — it is NOT automatically skipped. The human reviewer sees the existing expense alongside the CSV row and makes an explicit decision: "Approve" (import anyway — it's a legitimate duplicate purchase) or "Reject" (don't import — it's truly a duplicate).

I specifically avoided auto-removing duplicates because in financial software, a "duplicate" may be an intentional purchase (two ₹500 grocery runs on the same day).

---

### Q15. How does Rule I (Membership Violation) work?

**Model Answer:**
`group.is_user_member_on_date(user, date)` checks `GroupMembership.objects.filter(group=group, user=user, joined_at__lte=date, is_active=True)` combined with `Q(left_at__isnull=True) | Q(left_at__gte=date)`.

If the payer was not an active member on the expense date, a `payer_not_active_on_date` anomaly is created with policy `REJECT`. Same for each participant. This rule fires before duplicate detection — there's no point checking for duplicates if the user wasn't even in the group.

This is critical for imports of historical CSV data where membership changed over time.

---

## JWT Authentication

---

### Q16. Explain the JWT token flow in Spreewise.

**Model Answer:**
1. **Login**: User posts credentials to `/api/auth/login/`. simplejwt returns an access token (7-day lifetime) and a refresh token (30-day lifetime).
2. **Requests**: Every API request includes `Authorization: Bearer <access_token>` in the header.
3. **Expiry handling**: When the access token expires, the API returns 401. The Axios interceptor in `api/client.ts` catches the 401, calls `POST /api/auth/refresh/` with the refresh token, receives a new access token, and retries the original request.
4. **Request queue**: During the refresh call, any concurrent requests that also get 401 are queued and retried after the new token is received — preventing multiple simultaneous refresh calls.
5. **Logout**: User posts the refresh token to `/api/auth/logout/`. The token is invalidated.

---

### Q17. Why store tokens in sessionStorage instead of localStorage?

**Model Answer:**
`localStorage` persists across browser sessions — if an attacker gains XSS access to the page, they can steal tokens and use them even after the user closes the browser. `sessionStorage` is scoped to the browser tab — when the tab is closed, the tokens are gone. This reduces the window of opportunity for token theft. The trade-off is that users need to log in again after closing the browser, which is acceptable for a financial application.

---

### Q18. How do you enforce that User A cannot see User B's data?

**Model Answer:**
Every ViewSet `get_queryset()` method filters by the authenticated user's group memberships:

```python
# Example from groups/views.py
user_group_ids = GroupMembership.objects.filter(
    user=request.user, is_active=True
).values_list("group_id", flat=True)
return Group.objects.filter(id__in=user_group_ids, is_archived=False)
```

The same pattern applies to Expenses, Settlements, and Imports. For Balances, `_assert_group_member()` raises 403 if the requesting user is not an active member of the target group. This means URL manipulation (e.g., `GET /api/expenses/?group_id=999`) returns an empty queryset rather than leaking data.

---

## Invite Codes

---

### Q19. How are invite codes generated?

**Model Answer:**
In `Group.save()`:
```python
if not self.invite_code:
    self.invite_code = "SPW-" + "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )
```

`secrets.choice` uses the OS's cryptographically secure random number generator, making codes unpredictable. The format `SPW-XXXXXXXX` gives 36^8 = ~2.8 trillion possible codes. The `unique=True` constraint on the database field prevents collisions from being silently ignored.

---

### Q20. What happens when a user tries to join a group with an invalid invite code?

**Model Answer:**
`JoinGroupByInviteCodeView` does: `Group.objects.get(invite_code=code, is_archived=False)`. If no group is found, a 400 response is returned with detail "Invalid invite code." If the group is archived, it also returns 400. If the user is already an active member, a 400 with "Already a member" is returned. Only on success does a new `GroupMembership` record get created with `joined_via_invite=True` and `invite_code_used=code`.

---

## Security

---

### Q21. How do you prevent a member from accessing admin-only endpoints?

**Model Answer:**
Role checks are implemented in the ViewSet. For example, the CSV upload endpoint:
```python
role = group.get_user_role(request.user)
if role not in ["owner", "admin"]:
    return Response({"detail": "Only group owners and admins can upload CSV files."}, status=403)
```

Group archival is owner-only. Member role changes are owner-only. Adding/removing members requires admin or owner. These checks are in the view layer, not the serializer, to ensure they run before any data modification.

---

### Q22. What SQL injection risks exist and how are they mitigated?

**Model Answer:**
None — Django ORM uses parameterized queries for all database operations. The raw SQL in `verify_jwt_auth.py` cleanup function uses Python string formatting but is only in a test script that never runs in production. All production queries go through the ORM. The `.filter()`, `.get()`, and `.exclude()` methods all use parameterized SQL under the hood.

---

## Performance

---

### Q23. How does balance computation scale with group size?

**Model Answer:**
The current implementation loads all non-archived expenses and settlements into memory and computes balances in Python. For a group with 1,000 expenses and 200 members, this requires one DB query per entity type and O(N*M) memory where N=expenses and M=members. For typical groups (10-50 members, 100-500 expenses), this is fast (<100ms).

For production scale with very large groups, the next step would be: aggregate balances at the database level using Django `annotate()` with conditional sum, or maintain a running balance cache in Redis invalidated on each write.

---

### Q24. Are there any N+1 query problems?

**Model Answer:**
The main risk area is the balance service when called per-group in the dashboard view. The current implementation calls `balance_service.calculate_group_balances()` once per group the user belongs to. With `select_related("paid_by")` and `prefetch_related("splits")` on the expense queryset, the N+1 is controlled. The dashboard view wraps this in a try/except to fail gracefully if any single group's computation fails without breaking the entire dashboard response.

---

## AI Usage

---

### Q25. How did you use AI in this project, and what were its limitations?

**Model Answer:**
I used Antigravity (Google DeepMind) as the primary coding assistant and ChatGPT for research. AI was effective for: boilerplate generation (models, serializers, ViewSets), structuring the balance engine, and writing the verification suite scaffolding.

The key limitations I encountered:
1. **Sign conventions**: AI got the settlement sign wrong — it treated settlements like expenses. I caught this by tracing a simple 2-person test manually.
2. **Auto-fix overconfidence**: AI suggested auto-fixing duplicates, unknown users, and currency mismatches without review. In financial software, these all require human decisions.
3. **Missing membership validation**: The initial expense serializer didn't validate that participants were active members on the expense date.
4. **False positive user resolution**: The prefix matching stage initially returned the first match without checking uniqueness, risking silent misattribution of expenses.
5. **Overly aggressive cleanup**: The test cleanup function initially violated FK constraints by trying to delete users before their owned groups.

All AI output was reviewed, tested, and in several cases significantly corrected. See `AI_USAGE.md` for full details.

---

### Q26. Show me a specific piece of code that AI got wrong and how you fixed it.

**Model Answer:**
Prefix match in the User Resolution Layer. AI's version:
```python
for u in all_users:
    if u.username.lower().startswith(normalized):
        return u, "prefix_match"  # Returns first match — WRONG
```

This silently resolves "Priya" to the first user whose username starts with "priya" — dangerous if there are multiple such users.

Corrected version:
```python
candidates = []
for u in all_users:
    if any(name.startswith(normalized) for name in db_names):
        candidates.append(u)

unique_candidates = list({u.id: u for u in candidates}.values())
if len(unique_candidates) == 1:
    return unique_candidates[0], "prefix_match"

return None, "failed"  # Ambiguous → don't guess
```

The key insight: in financial software, an incorrect assignment is worse than no assignment. Failing safely and generating a review anomaly is always preferable to silently guessing wrong.

---

## Deep Dives

---

### Q27. What is the trickiest bug you encountered and how did you debug it?

**Model Answer:**
The invite code migration bug. After adding `invite_code` as a unique field to `Group`, applying the migration to a database that already had group records failed with `IntegrityError` — all existing groups would have `NULL` invite codes, which violated the unique constraint if backfilling failed.

The fix was a 3-step migration:
1. Add `invite_code` as `nullable=True, unique=False`
2. Write a data migration to backfill all existing groups with generated codes
3. Alter the field to `unique=True, nullable=False`

This pattern — add nullable, backfill, then constrain — is the standard Django approach for adding unique fields to existing tables.

---

### Q28. If you had another week, what would you improve?

**Model Answer:**
1. **Access token lifetime**: Reduce from 7 days to 15 minutes in production config — the current setting is intentionally long for development convenience
2. **Invite code rotation**: Add a `POST /api/groups/{id}/regenerate-invite/` endpoint so owners can invalidate a compromised code
3. **Real-time balance updates**: Use Django Channels (WebSockets) to push balance updates to the dashboard when a new expense is created
4. **Email notifications**: Notify members when they're added to a group or when a new expense is created
5. **CSV template download**: Provide a downloadable CSV template matching the expected format to reduce import errors
6. **Test coverage**: Add Django unit tests for the balance engine (sign conventions, edge cases), membership lifecycle validation, and each anomaly detection rule

---

### Q29. How would you design Spreewise for 10,000 concurrent users?

**Model Answer:**
1. **Database**: Add read replicas. Route balance queries (read-heavy, compute-intensive) to replica. Write all expense/settlement creates to primary.
2. **Balance caching**: Compute balances on write and cache in Redis. Invalidate cache on any group expense/settlement write. Read dashboard from cache.
3. **Background processing**: Move CSV processing to a Celery task queue (Redis broker). Upload the file, queue the task, poll for status — eliminates the 30-second upload block.
4. **Horizontal scaling**: Django is stateless (JWT tokens). Deploy multiple Gunicorn workers behind Nginx. Use a load balancer.
5. **CDN**: Serve the React frontend from a CDN. Only API calls hit the backend.
6. **Connection pooling**: Use PgBouncer in transaction mode to pool PostgreSQL connections across workers.

---

### Q30. What does `is_user_member_on_date` return for a user who left and rejoined?

**Model Answer:**
A user can have multiple `GroupMembership` records for the same group (each with different `joined_at`/`left_at` dates). `is_user_member_on_date` queries all records for that user in that group and returns `True` if any record covers the given date. So:

- Membership 1: joined_at=Feb 1, left_at=Mar 31
- Membership 2: joined_at=Apr 15, left_at=NULL

For date Feb 14: ✅ covered by Membership 1
For date Apr 1: ❌ not covered by either
For date Apr 20: ✅ covered by Membership 2

This is why historical membership tracking (ADR-01) was essential — a simple `is_active` flag cannot answer this question correctly.
