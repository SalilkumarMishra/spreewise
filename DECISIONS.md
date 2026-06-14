# DECISIONS.md — Architecture Decision Records

> This document records the significant technical decisions made during the development of Spreewise. Each ADR explains the problem, the options considered, the chosen solution, and the trade-offs accepted.

---

## ADR-01: Historical Membership Tracking

**Problem:**
When importing historical CSV data, expenses dated months in the past need to be validated against who was actually in the group at that time. A simple "is the user a member now?" check would fail for users who have since left or joined.

**Options Considered:**
1. Store only current membership state (is_active boolean)
2. Store `joined_at` and `left_at` dates per membership record
3. Keep a full event log (join/leave events as separate rows)

**Chosen Solution:**
Option 2 — `GroupMembership` stores `joined_at`, `left_at`, and `is_active`. The `Group.is_user_member_on_date(user, date)` helper queries: `joined_at <= date AND (left_at IS NULL OR left_at >= date)`.

**Why:**
- Simple, single-query membership date check
- Supports re-joins (a user can have multiple `GroupMembership` records in the same group)
- Minimal schema complexity vs. a full event log
- Sufficient for the anomaly detector's membership violation checks

**Trade-offs:**
- Does not natively support overlapping memberships (edge case, handled by UniqueConstraint on active membership)
- Re-join validation (new `joined_at` must be >= previous `left_at`) is enforced in `membership_service.py`, not the DB

---

## ADR-02: Soft Deletes

**Problem:**
When an expense or settlement is "deleted", should the record be permanently removed from the database?

**Options Considered:**
1. Hard delete — remove the row entirely
2. Soft delete — set `is_archived=True`, keep the row

**Chosen Solution:**
Soft delete across all primary models (`Group`, `Expense`, `Settlement`). Each model's `delete()` method is overridden to set `is_archived=True` and call `save()` instead of deleting.

**Why:**
- **Balance integrity**: Deleting an expense that contributed to a settled balance would corrupt historical records
- **Audit trail**: Archived records remain available for debugging, CSV import references, and snapshot lineage
- **Data recovery**: Accidental deletions can be recovered by an admin setting `is_archived=False`
- **Import traceability**: `Expense.import_job` FK would become a dangling reference if the expense were hard-deleted

**Trade-offs:**
- Queries must always filter `is_archived=False` (enforced in all ViewSet `get_queryset()` methods)
- Database size grows over time (acceptable trade-off for auditability)

---

## ADR-03: Expense Snapshots

**Problem:**
How do we track the history of changes to an expense (amount changes, participant changes, split changes)?

**Options Considered:**
1. No history — only current state stored
2. Django Simple History (third-party library)
3. Custom `ExpenseSnapshot` model with JSON payloads

**Chosen Solution:**
Custom `ExpenseSnapshot` model. Each expense create/update generates a new version snapshot containing the full expense + participants + splits as a JSON payload. `save()` raises `ValidationError` if an existing snapshot is modified.

**Why:**
- **Immutability by design**: snapshots cannot be altered, making them reliable for audit
- **Explainability**: balance explanations can reference the snapshot version that determined a user's share
- **No third-party dependency**: avoids version compatibility risks with Django Simple History
- **Full state capture**: JSON payload includes all related data, not just field diffs

**Trade-offs:**
- Storage overhead: every update creates a new row
- No field-level diff tracking (you get full snapshots, not "what changed")
- `payload_json` can become large for expenses with many participants

---

## ADR-04: Settlement Snapshots

**Problem:**
Same as ADR-03 but for settlements.

**Options Considered:**
Same as ADR-03.

**Chosen Solution:**
Identical pattern to `ExpenseSnapshot` — `SettlementSnapshot` with immutable versioned JSON payloads.

**Why:**
Consistency with the expense snapshot pattern. Settlements can be updated (e.g., amount correction) and the full audit trail must be preserved.

**Trade-offs:**
Same as ADR-03. Settlements are typically simpler records, so the storage overhead is lower.

---

## ADR-05: Separate Settlement Model

**Problem:**
Should settlements (payments between members to settle debts) be stored as a special type of Expense, or as a separate model?

**Options Considered:**
1. Use `Expense` with `expense_category=settlement`
2. Separate `Settlement` model with explicit `payer` and `receiver` fields

**Chosen Solution:**
Separate `Settlement` model (Option 2).

**Why:**
- **Balance engine correctness**: Expenses create debts (Alice paid, others owe Alice). Settlements cancel debts (Bob pays Alice back). These have opposite sign conventions and must be processed differently
- **Sign convention clarity**: `Settlement(payer=Bob, receiver=Alice, amount=500)` is unambiguous. An expense with `category=settlement` is semantically confusing
- **Anomaly detection**: Rule J detects rows that *look like* settlements but were logged as expenses — this detection is only possible because the two are conceptually distinct
- **Data integrity**: `Settlement.reference_id` is unique, enabling idempotent imports

**Trade-offs:**
- Two models to maintain instead of one
- Slightly more complex queries when building the ledger (must union expenses and settlements)

---

## ADR-06: Normalized Ledger Pattern

**Problem:**
How should the balance engine calculate how much each member owes?

**Options Considered:**
1. Store running balances per user (updated on every expense/settlement)
2. Recompute from scratch on every request by walking all expenses and settlements
3. Cache balances in `BalanceSnapshot` and invalidate on writes

**Chosen Solution:**
Option 2 — compute on-demand from the full ledger. `balance_service.calculate_group_balances()` walks all non-archived expenses and settlements, computes each user's net position, and returns the result. `BalanceSnapshot` is used for audit logging only.

**Why:**
- **Correctness**: No cached state to invalidate. Balances are always computed from ground truth
- **Simplicity**: No cache invalidation logic to maintain
- **Appropriate scale**: For groups with hundreds of expenses, the computation is fast enough on modern hardware
- **Explainability**: `ledger_service.py` exposes the individual ledger entries that led to the final balance, enabling `GET /balances/groups/{id}/ledger/`

**Trade-offs:**
- Performance degrades for very large groups (10,000+ expenses). Acceptable for the current use case
- No real-time balance streaming — every request recomputes

---

## ADR-07: Greedy Debt Simplification

**Problem:**
If Alice owes Bob ₹200, Bob owes Carol ₹300, and Carol owes Alice ₹100, the total number of payments can be reduced. How should minimal settlement instructions be computed?

**Options Considered:**
1. Show all pairwise balances (N² complexity in display)
2. Greedy algorithm: separate into debtors and creditors, match largest debtor with largest creditor
3. Optimal algorithm: minimum number of transactions (NP-hard in general case)

**Chosen Solution:**
Greedy algorithm (Option 2) — `simplification_service.simplify_debts()`.

**Algorithm:**
1. Call `calculate_group_balances()`
2. Separate users into `debtors` (net < 0) and `creditors` (net > 0)
3. Sort both by amount descending
4. Iteratively match largest debtor with largest creditor until all debts are settled

**Why:**
- **Near-optimal results** for typical group sizes: usually produces the minimum or near-minimum number of payments
- **Linear time**: O(N log N) due to sorting
- **Simple to implement and reason about**: no graph theory or LP solver required
- **Practical**: for groups of 3–20 people, the greedy result equals the optimal result in almost all cases

**Trade-offs:**
- Not guaranteed optimal for all cases (a debt graph with specific structure can require one extra payment vs. optimal)
- No cycle elimination (e.g., A→B→C→A debt cycles are handled implicitly by the net balance computation)

---

## ADR-08: Import Review Workflow

**Problem:**
When a CSV row has anomalies, should the system automatically reject/fix it, or should a human review it?

**Options Considered:**
1. Auto-fix all anomalies silently
2. Reject all anomalous rows automatically
3. Three-tier policy: `AUTO_FIX`, `REVIEW_REQUIRED`, `REJECT`

**Chosen Solution:**
Three-tier policy system (Option 3).

| Policy | When Used | Action |
|---|---|---|
| `AUTO_FIX` | Low-risk, deterministic fixes (e.g., uppercase currency) | Engine applies fix, no human needed |
| `REVIEW_REQUIRED` | Ambiguous situations (duplicate candidate, unknown user, currency mismatch) | Human must approve or reject before commit |
| `REJECT` | Invalid data (zero amount, invalid date, split math failure) | Row is rejected immediately |

**Why:**
- **Financial data requires human oversight**: auto-fixing a duplicate expense deletion could cause a user to lose ₹5,000 in perceived debt
- **Flexibility**: different anomalies warrant different responses
- **Auditability**: every decision is stored in `ImportDecision` with the reviewer's identity and reason

**Trade-offs:**
- More complex import UX — users must visit a review queue before committing
- `review_required` status on `ImportJob` blocks finalization until all anomalies are decided

---

## ADR-09: JWT Authentication

**Problem:**
What authentication mechanism should Spreewise use?

**Options Considered:**
1. Session-based authentication (Django sessions + cookies)
2. Basic Authentication (username:password in every request header)
3. JWT (JSON Web Tokens) with access + refresh token flow

**Chosen Solution:**
JWT with `djangorestframework-simplejwt` (Option 3).

**Why:**
- **Stateless**: the server does not need to maintain session state — suitable for future API consumers (mobile apps, third-party integrations)
- **Refresh token flow**: short-lived access tokens (7 days in dev, should be 15 minutes in production) + long-lived refresh tokens (30 days) enable automatic renewal
- **Standard**: JWT is the industry standard for REST API authentication
- **Security**: Basic Auth over HTTP (even HTTPS) sends credentials on every request; JWT sends credentials once

**Token storage decision:**
`sessionStorage` (not `localStorage`) — tokens are cleared when the browser tab is closed, reducing the window for token theft via XSS.

**Trade-offs:**
- Stateless means tokens cannot be invalidated server-side without a blacklist (current config: `BLACKLIST_AFTER_ROTATION=False` for simplicity)
- Access token lifetime of 7 days is too long for production — should be reduced to 15 minutes

---

## ADR-10: Invite Code System

**Problem:**
How should new users join existing groups?

**Options Considered:**
1. Admin manually adds users by searching their username
2. Email invitation link (requires email server setup)
3. Shareable invite code

**Chosen Solution:**
Invite code system (Option 3). Format: `SPW-XXXXXXXX` (prefix + 8 random uppercase alphanumeric characters, generated with Python's `secrets` module).

**Why:**
- **No email infrastructure required**: codes can be shared via WhatsApp, Telegram, Signal, etc.
- **Cryptographically secure**: `secrets.choice` provides better randomness than `random.choice`
- **Auditable**: `GroupMembership.joined_via_invite` and `invite_code_used` fields record who joined via code
- **Simple UX**: user pastes the code at `/join-group`, instantly becomes a member

**Considerations:**
- Invite codes are permanent (not single-use or time-limited) — simplicity trade-off
- Code can be regenerated by an owner if it needs to be invalidated (endpoint not yet implemented; rotation is a future improvement)

**Trade-offs:**
- Permanent codes mean anyone with the code can join indefinitely
- No per-invite expiry or usage limits

---

## ADR-11: User Resolution Layer

**Problem:**
CSV files contain user names in human-typed form (e.g., "Aisha", "ROHAN", "Priya S"). The database stores users with usernames like `aisha`, `rohan`, `priya`. Naive string matching generates false-positive `unknown_user` anomalies.

**Options Considered:**
1. Require exact username match in CSV
2. Case-insensitive username match only
3. Multi-stage resolution: username → first name → full name → prefix → alias

**Chosen Solution:**
5-stage resolution in `imports/services/user_resolver.py`:

```
Stage 1: Case-insensitive username match  ("Aisha" → "aisha")
Stage 2: First-name match                 ("Aisha" → first_name="Aisha")
Stage 3: Full-name match                  ("Aisha Khan" → "Aisha" + "Khan")
Stage 4: Unique prefix match              ("Priya S" → only one user whose name starts with "Priya")
Stage 5: Alias dictionary fallback        (CSV alias → known DB username)
```

`normalize_name()` strips whitespace, collapses duplicate spaces, lowercases, and removes edge punctuation before matching.

**Why:**
- Eliminated the majority of false-positive `unknown_user` anomalies in the test CSV dataset
- Non-destructive: if resolution fails after all 5 stages, the `unknown_user` anomaly fires correctly
- `resolved_user_id` is stored in `parsed_data`, enabling the anomaly detector to skip redundant username lookups
- The alias dictionary provides a future-proof escape hatch for known mismatches

**Trade-offs:**
- Stage 4 (prefix match) can produce false positives if two users share a name prefix (e.g., "Priya" and "Priya S" both in the system). The uniqueness check mitigates this — if multiple candidates match, the stage fails
- Stage 2 (first-name match) is ambiguous for common names — same uniqueness protection applies
