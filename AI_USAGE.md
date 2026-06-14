# AI_USAGE.md — AI Tool Usage Documentation

> This document describes how AI coding assistants were used during the development of Spreewise, including specific examples where AI-generated output was incorrect and how each issue was identified and corrected.

---

## AI Tools Used

| Tool | Usage |
|---|---|
| **Antigravity (Google DeepMind)** | Primary coding assistant — used throughout development for backend architecture, frontend components, migration strategies, and verification scripts |
| **ChatGPT (OpenAI)** | Supplementary tool — used for researching specific patterns (e.g., greedy debt simplification algorithms, JWT best practices) and drafting initial documentation structure |

---

## How AI Was Used

### Architecture Design
AI was used to discuss high-level architecture decisions: whether to use soft deletes vs. hard deletes, whether to use snapshot patterns vs. audit logs, and how to structure the balance engine (on-demand computation vs. cached state). AI provided the initial framework for each decision, which was then evaluated, refined, and sometimes rejected in favor of a different approach.

### Boilerplate Generation
AI generated the initial scaffolding for:
- Django model definitions (Group, GroupMembership, Expense, Settlement, ImportJob, etc.)
- DRF serializer classes and ViewSet patterns
- React component structures, API client modules, and AuthContext patterns
- Database migration files for multi-step operations (e.g., the invite code backfill migration)

### Business Logic Implementation
Key algorithms were either written or reviewed with AI assistance:
- The greedy debt simplification algorithm in `simplification_service.py`
- The 5-stage user resolution layer in `user_resolver.py`
- The anomaly detection rules in `anomaly_detector.py`

### Testing
AI generated the structure for the verification suites (`verify_jwt_auth.py`, `verify_user_resolution.py`). The test scenarios were defined by the developer; AI implemented the test code.

### Documentation
All documentation files (README.md, SCOPE.md, DECISIONS.md, this file) were generated with AI assistance based on inspection of the actual codebase. No placeholder content was used — AI read the source files and produced documentation matching the implemented behavior.

---

## Incorrect AI Output — Examples

The following are concrete examples where AI-generated code or suggestions were incorrect, identified through testing or reasoning, and corrected.

---

### Bug #1 — Settlement Sign Convention Error

**What AI Suggested:**
When implementing the balance engine, AI initially suggested treating settlements the same as expenses in the ledger:

```python
# AI's initial suggestion (WRONG)
for settlement in settlements:
    ledger[settlement.payer_id] -= settlement.amount  # payer "spends" money
    ledger[settlement.receiver_id] -= settlement.amount  # receiver "receives" money (WRONG)
```

**Why It Was Wrong:**
This double-counted the settlement. A settlement is a debt cancellation, not a new expense. The correct behavior is:
- The **payer** of a settlement reduces their debt (their balance increases — they've paid off what they owe)
- The **receiver** of a settlement reduces their credit (their balance decreases — they've been repaid)

```python
# Corrected sign convention
for settlement in settlements:
    ledger[settlement.payer_id] += settlement.amount   # payer's debt is reduced
    ledger[settlement.receiver_id] -= settlement.amount # receiver is repaid
```

**How It Was Corrected:**
The sign convention was verified by constructing a simple test case manually: Aisha paid ₹1,000 for 2 people (equal split → each owes ₹500). Rohan settled ₹500 to Aisha. Expected result: both balances are 0. AI's version produced Rohan's balance as -₹500 (still owing) and Aisha's balance as -₹500 (which made no sense). The fix was identified by tracing the ledger computation on paper.

---

### Bug #2 — Missing Membership Validation in Expense Creation

**What AI Suggested:**
When implementing the expense creation endpoint, AI's initial serializer and view did not validate that the `paid_by` user and all participants are active members of the group at the time of the expense date:

```python
# AI's initial serializer (WRONG — no membership check)
class ExpenseSerializer(serializers.ModelSerializer):
    def validate(self, data):
        # AI only checked that participants are registered users
        return data
```

**Why It Was Wrong:**
A user who left the group in March should not be able to create or be included in expenses dated in April. Without this check, the balance engine would include expenses for users who were not members at the relevant time, producing incorrect balances.

**How It Was Corrected:**
A membership date check was added to the expense creation logic. For CSV imports, Rule I (`payer_not_active_on_date`, `participant_not_active_on_date`) in the anomaly detector explicitly validates membership using `group.is_user_member_on_date(user, expense_date)` before allowing a row to be committed.

---

### Bug #3 — Automatic Duplicate Removal Without Review

**What AI Suggested:**
When implementing the CSV import duplicate detection, AI initially suggested automatically skipping (silently rejecting) duplicate rows:

```python
# AI's initial anomaly handler (WRONG)
if duplicate_qs.exists():
    import_row.processing_status = "skipped"
    import_row.save()
    continue  # Skip this row entirely, no anomaly recorded
```

**Why It Was Wrong:**
Silently skipping duplicates is dangerous in financial software. The "duplicate" might be a legitimately different expense that happens to have the same title, amount, and date (e.g., two ₹500 grocery runs on the same day). The user must be shown the conflict and make an explicit decision.

Additionally, silently skipping rows with no audit trail means the user has no way to know rows were dropped from their CSV.

**How It Was Corrected:**
Duplicates generate a `duplicate_expense` anomaly with policy `REVIEW_REQUIRED`. The row is held in `review_required` status. The human reviewer sees the existing expense and the CSV row side by side and explicitly approves (import anyway) or rejects (don't import). Only after a decision is recorded does the row proceed.

---

### Bug #4 — User Resolution False Positives

**What AI Suggested:**
For the prefix matching stage (Stage 4) of the user resolution layer, AI initially implemented it without the uniqueness check:

```python
# AI's initial prefix match (WRONG — no uniqueness guard)
for u in all_users:
    if u.username.lower().startswith(normalized):
        return u, "prefix_match"  # Returns the first match, even if multiple exist
```

**Why It Was Wrong:**
If the group has users `priya` and `priya_sharma`, a CSV entry of "Priya" would match `priya` (first in iteration order) — but the intended user might be `priya_sharma`. This would silently assign the expense to the wrong person, causing balance errors that would be very difficult to detect.

**How It Was Corrected:**
Stage 4 collects all matching candidates and only resolves if exactly one candidate is found:

```python
# Corrected: collect all candidates first
candidates = []
for u in all_users:
    # ... prefix check ...
    if is_match:
        candidates.append(u)

# Deduplicate by PK
unique_candidates = list({u.id: u for u in candidates}.values())

# Only resolve if unambiguous
if len(unique_candidates) == 1:
    return unique_candidates[0], "prefix_match"

return None, "failed"  # Multiple candidates → safe to fail
```

---

### Bug #5 — Overly Aggressive AUTO_FIX Rules

**What AI Suggested:**
AI initially proposed marking several anomaly types as `AUTO_FIX` that should have been `REVIEW_REQUIRED`:

```python
# AI's initial policy mapping (WRONG)
ANOMALY_POLICIES = {
    "duplicate_expense": "AUTO_FIX",        # Would silently skip duplicates
    "unknown_user": "AUTO_FIX",             # Would silently map to a "best guess" user
    "settlement_logged_as_expense": "AUTO_FIX",  # Would auto-route to settlement engine
    "currency_conversion_required": "AUTO_FIX",  # Would use a hardcoded exchange rate
}
```

**Why It Was Wrong:**
Each of these involves a financial decision that cannot be made safely without human input:
- **Duplicate expense**: may be intentional (two identical purchases on the same day)
- **Unknown user**: any "best guess" mapping could assign debt to the wrong person
- **Settlement vs. expense**: changing the record type changes the balance calculation
- **Currency conversion**: applying a hardcoded rate could introduce systematic errors

**How It Was Corrected:**
All four were changed to `REVIEW_REQUIRED`. Only truly deterministic, low-risk operations like `unsupported_currency` (always a data error, not a financial decision) use `REJECT`. `AUTO_FIX` is reserved for future use with cases like normalizing currency strings (`"inr"` → `"INR"`) where the fix is provably correct.

---

## Summary Assessment

AI was highly effective for:
- Generating well-structured boilerplate code quickly
- Suggesting established patterns (JWT flow, snapshot patterns, soft deletes)
- Writing comprehensive test suites given clear scenario descriptions

AI required careful human review for:
- Sign conventions in financial computations
- Security-sensitive logic (membership validation, access scoping)
- Ambiguity resolution in user-facing workflows (always err on the side of requiring human decisions)
- Edge cases involving multiple candidates or overlapping conditions

**All AI-generated code was reviewed, tested, and in several cases significantly modified before being included in the final codebase.**
