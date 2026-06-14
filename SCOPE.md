# SCOPE.md — Spreewise Data Schema & Anomaly Catalog

> Complete reference for database models, field definitions, relationships, and the full anomaly detection catalog.

---

## DATABASE SCHEMA

---

### GROUPS

#### `Group`

**Purpose**: Represents a named group of people sharing expenses together (e.g., "Flatmates 2026", "Goa Trip").

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `name` | CharField(255) | Group display name |
| `description` | TextField | Optional description |
| `currency` | CharField(10) | Default: `INR` — base currency for all balances |
| `is_archived` | BooleanField | Soft delete flag |
| `invite_code` | CharField(20, unique) | Auto-generated `SPW-XXXXXXXX` on first save |
| `created_by` | FK → User (PROTECT) | The user who created the group |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated on modification |

**Relationships:**
- Has many `GroupMembership` records (via `memberships`)
- Has many `Expense` records (via `expenses`)
- Has many `Settlement` records (via `settlements`)
- Has many `ImportJob` records (via `import_jobs`)
- Has many `BalanceSnapshot` records (via `balance_snapshots`)

**Business Rules:**
- `invite_code` is auto-generated on save using `secrets.choice` with 8 alphanumeric uppercase characters
- `delete()` is overridden to soft-archive instead of hard delete
- `is_user_member_on_date(user, date)` helper used by balance engine and anomaly detector
- `get_user_role(user)` returns the user's current active role or `None`

---

#### `GroupMembership`

**Purpose**: Records the lifecycle of a user's participation in a group, including role, join date, leave date, and invite audit trail.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `group` | FK → Group (CASCADE) | Parent group |
| `user` | FK → User (PROTECT) | Member user |
| `joined_at` | DateField | Date membership started |
| `left_at` | DateField (nullable) | Date membership ended; `NULL` = still active |
| `is_active` | BooleanField | `True` if currently active member |
| `role` | CharField(20) | `owner`, `admin`, or `member` |
| `joined_via_invite` | BooleanField | `True` if joined via invite code |
| `invite_code_used` | CharField(20, nullable) | The exact invite code used to join |
| `created_at` | DateTimeField | Auto-set |

**Constraints:**
- `UniqueConstraint` on `(group, user)` where `is_active=True` — prevents duplicate active memberships
- `clean()` validates: `left_at >= joined_at`; auto-sets `is_active=False` when `left_at` is set

**Business Rules:**
- A user can re-join a group after leaving, but the new `joined_at` must be on or after the previous `left_at`
- Membership validation at expense date is checked in the anomaly detector (Rule I)

---

### EXPENSES

#### `Expense`

**Purpose**: A single shared expense event — e.g., "Dinner at Marina Bites for ₹1,200, paid by Aisha, split equally between Aisha/Rohan/Priya."

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `group` | FK → Group (PROTECT) | Parent group |
| `title` | CharField(255) | Human-readable expense name |
| `description` | TextField (nullable) | Optional longer description |
| `amount` | Decimal(14,2) | Amount in group currency |
| `currency` | CharField(10) | Currency of `amount` |
| `original_amount` | Decimal(14,2) | Amount as entered/imported (before any conversion) |
| `original_currency` | CharField(10) | Currency of `original_amount` |
| `expense_category` | CharField(50) | `food`, `rent`, `utilities`, `travel`, `groceries`, `entertainment`, `settlement`, `refund`, `general` |
| `source` | CharField(20) | `manual`, `csv_import`, or `system` |
| `expense_date` | DateField | The date the expense occurred |
| `paid_by` | FK → User (PROTECT) | User who paid the full amount |
| `split_type` | CharField(20) | `equal`, `percentage`, `shares`, or `exact` |
| `status` | CharField(20) | `active`, `disputed`, or `import_review` |
| `notes` | TextField (nullable) | Optional internal notes |
| `import_job` | FK → ImportJob (SET_NULL, nullable) | Traceability link to source CSV import |
| `created_by` | FK → User (PROTECT) | User who created the record |
| `created_at` | DateTimeField | Auto-set |
| `updated_at` | DateTimeField | Auto-updated |
| `is_archived` | BooleanField | Soft delete flag |

**Ordering:** `-expense_date`, `-created_at`

---

#### `ExpenseParticipant`

**Purpose**: Records which users are included in an expense (regardless of split amounts).

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `expense` | FK → Expense (CASCADE) | Parent expense |
| `user` | FK → User (PROTECT) | Participating user |

**Constraint:** `unique_together = [(expense, user)]`

---

#### `ExpenseSplit`

**Purpose**: Stores both the original split input values AND the computed amount each participant owes. Preserving originals enables explainability ("Why do I owe ₹2,300?").

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `expense` | FK → Expense (CASCADE) | Parent expense |
| `user` | FK → User (PROTECT) | The user this split belongs to |
| `percentage_value` | Decimal(7,4, nullable) | Populated for `percentage` splits only |
| `shares_value` | Decimal(10,2, nullable) | Populated for `shares` splits only |
| `exact_amount` | Decimal(14,2, nullable) | Populated for `exact` splits only |
| `calculated_amount` | Decimal(14,2) | Final computed share for this user |

**Constraint:** `unique_together = [(expense, user)]`

---

#### `ExpenseSnapshot`

**Purpose**: Immutable audit record capturing the complete state of an expense + splits at a given version. Created on every write.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `expense` | FK → Expense (CASCADE) | Parent expense |
| `version` | IntegerField | Increments on each save |
| `payload_json` | JSONField | Full snapshot: expense data + participants + splits |
| `created_at` | DateTimeField | Auto-set |

**Immutability:** `save()` raises `ValidationError` if attempting to modify an existing snapshot.

**Ordering:** `version` (ascending — oldest first)

---

### SETTLEMENTS

#### `Settlement`

**Purpose**: Records that one group member paid another to settle a debt. Distinct from expenses — settlements reduce balances rather than creating new debts.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `reference_id` | CharField(50, unique) | System-generated unique reference |
| `group` | FK → Group (PROTECT) | Parent group |
| `payer` | FK → User (PROTECT) | User making the payment |
| `receiver` | FK → User (PROTECT) | User receiving the payment |
| `amount` | Decimal(14,2) | Amount in group currency |
| `currency` | CharField(10) | Currency of `amount` |
| `original_amount` | Decimal(14,2) | Amount as entered/imported |
| `original_currency` | CharField(10) | Currency of `original_amount` |
| `payment_date` | DateField | Date payment was made |
| `notes` | TextField (nullable) | Optional notes |
| `settlement_category` | CharField(30) | `direct_payment`, `bank_transfer`, `cash`, `upi`, `imported` |
| `source` | CharField(20) | `manual`, `csv_import`, or `system` |
| `status` | CharField(20) | `active`, `disputed`, or `import_review` |
| `import_job` | FK → ImportJob (SET_NULL, nullable) | Traceability link |
| `created_by` | FK → User (PROTECT) | User who created the record |
| `created_at` | DateTimeField | Auto-set |
| `updated_at` | DateTimeField | Auto-updated |
| `is_archived` | BooleanField | Soft delete flag |

**Ordering:** `-payment_date`, `-created_at`

---

#### `SettlementSnapshot`

**Purpose**: Immutable audit record of a settlement at a given version.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `settlement` | FK → Settlement (CASCADE) | Parent settlement |
| `version` | IntegerField | Increments on each save |
| `payload_json` | JSONField | Full snapshot: version, reference_id, settlement details |
| `created_at` | DateTimeField | Auto-set |

**Immutability:** Same as `ExpenseSnapshot` — raises `ValidationError` on any modification attempt.

---

### BALANCES

#### `BalanceSnapshot`

**Purpose**: Periodic cache of group balance computations for audit and performance logging.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `group` | FK → Group (CASCADE) | The group this snapshot belongs to |
| `snapshot_date` | DateTimeField | When the snapshot was taken |
| `payload_json` | JSONField | Full balance summary at snapshot time |
| `created_at` | DateTimeField | Auto-set |

**Note:** Balances are computed on-demand by `balance_service.calculate_group_balances()` and are never read from this snapshot for live views. The snapshot is an audit record only.

---

### IMPORTS

#### `ImportJob`

**Purpose**: Represents a single CSV file upload and the full lifecycle of processing it.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `group` | FK → Group (CASCADE, nullable) | Target group for the import |
| `uploaded_by` | FK → User (SET_NULL, nullable) | User who uploaded the file |
| `original_filename` | CharField(255) | Filename of the uploaded CSV |
| `status` | CharField(20) | `pending`, `processing`, `review_required`, `completed`, `failed` |
| `created_at` | DateTimeField | Auto-set |
| `completed_at` | DateTimeField (nullable) | When processing finished |

---

#### `ImportRow`

**Purpose**: Stores each row of a CSV file with its raw data, parsed output, and processing status.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `import_job` | FK → ImportJob (CASCADE) | Parent import job |
| `row_number` | IntegerField | Original row number in the CSV |
| `raw_data` | JSONField | Raw CSV row as a Python dictionary |
| `parsed_data` | JSONField (nullable) | Structured representation after parsing |
| `processing_status` | CharField(20) | `pending`, `imported`, `skipped`, `review_required`, `failed` |

---

#### `ImportAnomaly`

**Purpose**: Represents a single detected problem with a CSV row. Multiple anomalies can exist per row.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `import_job` | FK → ImportJob (CASCADE) | Parent import job |
| `import_row` | FK → ImportRow (CASCADE) | The specific row with the problem |
| `anomaly_type` | CharField(50) | Machine-readable type (e.g., `duplicate_expense`) |
| `anomaly_category` | CharField(50) | `duplicate`, `membership`, `currency`, `date`, `settlement`, `split`, `validation`, `unknown_user` |
| `severity` | CharField(20) | `low`, `medium`, `high`, `critical` |
| `description` | TextField | Human-readable description of the problem |
| `detected_action` | CharField(50) | `AUTO_FIX`, `REVIEW_REQUIRED`, or `REJECT` |
| `user_decision` | CharField(20, nullable) | `approve`, `reject`, or `ignore` |
| `created_at` | DateTimeField | Auto-set |

---

#### `ImportDecision`

**Purpose**: Stores the human reviewer's decision on a specific anomaly.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `anomaly` | OneToOneField → ImportAnomaly | The anomaly being decided on |
| `decision` | CharField(20) | `approve`, `reject`, or `ignore` |
| `decided_by` | FK → User (SET_NULL, nullable) | Reviewer |
| `decision_reason` | TextField | Optional explanation of the decision |
| `created_at` | DateTimeField | Auto-set |

---

#### `ImportReport`

**Purpose**: Summary statistics for a completed import job.

| Field | Type | Notes |
|---|---|---|
| `id` | Integer (PK) | Auto-generated |
| `import_job` | OneToOneField → ImportJob | Parent import job |
| `total_rows` | IntegerField | Total rows in the CSV |
| `imported_rows` | IntegerField | Successfully imported rows |
| `skipped_rows` | IntegerField | Rows skipped (anomaly rejected) |
| `failed_rows` | IntegerField | Rows that failed to import |
| `anomaly_count` | IntegerField | Total anomalies detected |
| `report_json` | JSONField | Full detail report as JSON |

---

## ANOMALY CATALOG

The anomaly detector (`imports/services/anomaly_detector.py`) implements 13 rules, labeled A through M.

---

### Rule A — Duplicate Expense

| Field | Value |
|---|---|
| **`anomaly_type`** | `duplicate_expense` |
| **Category** | `duplicate` |
| **Severity** | `high` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
Queries `Expense.objects.filter(group, expense_date, amount, paid_by, title, is_archived=False)`.
If a matching expense already exists, the row is flagged.

**Example:**
```
CSV Row: "Dinner at Marina Bites", 1200, Aisha, 2026-02-14
DB: Same title, amount, date, and payer already exists → DUPLICATE
```

**Human Action Required:** Reviewer must decide whether to approve (override) or reject the row.

---

### Rule B — Duplicate Settlement

| Field | Value |
|---|---|
| **`anomaly_type`** | `duplicate_settlement` |
| **Category** | `duplicate` |
| **Severity** | `high` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
Only runs if the row is identified as a settlement (Rule J fired). Queries `Settlement.objects.filter(group, payment_date, amount, payer, receiver, is_archived=False)`.

**Example:**
```
CSV Row: "Rohan paid Aisha 500", 2026-02-20
DB: A settlement for the same amount, date, payer, and receiver already exists → DUPLICATE
```

---

### Rule C — Negative Amount

| Field | Value |
|---|---|
| **`anomaly_type`** | `negative_amount` |
| **Category** | `validation` |
| **Severity** | `medium` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
If `amount < 0`.

**Example:**
```
CSV Row: amount = -500
Could be a refund → REVIEW_REQUIRED (not auto-rejected, as refunds may be intentional)
```

---

### Rule D — Zero Amount

| Field | Value |
|---|---|
| **`anomaly_type`** | `zero_amount` |
| **Category** | `validation` |
| **Severity** | `high` |
| **Policy** | `REJECT` |

**Detection Logic:**
If `amount == 0.00`. Zero-amount rows are always rejected — they represent placeholders or errors.

---

### Rule E — Unknown User (Payer)

| Field | Value |
|---|---|
| **`anomaly_type`** | `unknown_user` |
| **Category** | `unknown_user` |
| **Severity** | `medium` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
After the 5-stage User Resolution Layer runs, if no user is matched for the payer field, an `unknown_user` anomaly is generated.

**User Resolution Strategies (before anomaly fires):**
1. Case-insensitive username match (`Aisha` → `aisha`)
2. First-name match
3. Full-name match
4. Unique prefix match (`Priya S` → `priya`)
5. Alias dictionary fallback

**Example:**
```
CSV payer: "Unknown Person"
Resolution: No match in 5 strategies → unknown_user anomaly
```

---

### Rule E (variant) — Unknown Participant

| Field | Value |
|---|---|
| **`anomaly_type`** | `unknown_participant` |
| **Category** | `unknown_user` |
| **Severity** | `high` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
For each participant in the row, checks if a user with that username exists. All unresolved participants are listed in a single anomaly.

---

### Rule F — Invalid Date

| Field | Value |
|---|---|
| **`anomaly_type`** | `invalid_date` |
| **Category** | `date` |
| **Severity** | `high` |
| **Policy** | `REJECT` |

**Detection Logic:**
Triggered if the date field cannot be parsed into a valid `datetime.date`. Caught both during parsing (`parse_errors`) and post-parse (`p.get("date") is None`).

Subsequent rules skip processing when this fires — a date is required for membership validation.

---

### Rule G — Unsupported Currency

| Field | Value |
|---|---|
| **`anomaly_type`** | `unsupported_currency` |
| **Category** | `currency` |
| **Severity** | `high` |
| **Policy** | `REJECT` |

**Detection Logic:**
Checks the parsed `currency` against `SUPPORTED_CURRENCIES` (defined in `csv_parser.py`).

**Example:**
```
CSV currency: "XYZ" → REJECT (not in supported list)
```

---

### Rule H — Missing Required Fields

| Field | Value |
|---|---|
| **`anomaly_type`** | `missing_required_fields` |
| **Category** | `validation` |
| **Severity** | `high` |
| **Policy** | `REJECT` |

**Detection Logic:**
Triggered when the CSV parser cannot extract required fields (description, amount, payer). `parse_errors` list is populated by the parser. Date-related errors are separated into Rule F.

---

### Rule I — User Not Active On Date

| Field | Value |
|---|---|
| **`anomaly_type`** | `payer_not_active_on_date` / `participant_not_active_on_date` |
| **Category** | `membership` |
| **Severity** | `high` |
| **Policy** | `REJECT` |

**Detection Logic:**
Uses `group.is_user_member_on_date(user, expense_date)` which queries `GroupMembership` for a record where `joined_at <= date` and (`left_at IS NULL` OR `left_at >= date`).

**Example:**
```
Meera left the group on 2026-03-31.
CSV row: "Electricity", 2026-04-05, Meera participant
→ participant_not_active_on_date REJECT
```

This is the most critical rule — it prevents polluting the balance engine with historically invalid data.

---

### Rule J — Settlement Logged As Expense

| Field | Value |
|---|---|
| **`anomaly_type`** | `settlement_logged_as_expense` |
| **Category** | `settlement` |
| **Severity** | `high` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
The CSV parser checks the description/title for keywords suggesting a settlement: `paid back`, `settled`, `reimbursed`, `transfer`, etc. Sets `is_possible_settlement=True` in parsed data.

**Example:**
```
CSV: "Rohan paid back Aisha 500"
→ settlement_logged_as_expense REVIEW_REQUIRED
Human decides: route to Settlement engine or keep as Expense
```

---

### Rule K — Currency Conversion Required

| Field | Value |
|---|---|
| **`anomaly_type`** | `currency_conversion_required` |
| **Category** | `currency` |
| **Severity** | `medium` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
Currency is valid (not Rule G) but differs from the group's base currency.

**Example:**
```
Group currency: INR
CSV currency: USD
→ currency_conversion_required REVIEW_REQUIRED
Human must manually confirm the correct INR equivalent
```

---

### Rule L — Split Validation Failure

| Field | Value |
|---|---|
| **`anomaly_type`** | `split_validation_failure` |
| **Category** | `split` |
| **Severity** | `high` or `critical` |
| **Policy** | `REJECT` |

**Detection Logic:**
Three sub-checks:
1. Non-equal split type with no `splits_data` → `REJECT` (high)
2. `percentage` splits don't sum to 100% → `REJECT` (critical)
3. `exact` splits don't sum to total amount → `REJECT` (high)

**Example:**
```
split_type: percentage
splits_data: Aisha 40%, Rohan 40% (total 80%, not 100%)
→ split_validation_failure REJECT (critical)
```

---

### Rule M — Date Ambiguity

| Field | Value |
|---|---|
| **`anomaly_type`** | `date_ambiguity` |
| **Category** | `date` |
| **Severity** | `high` |
| **Policy** | `REVIEW_REQUIRED` |

**Detection Logic:**
Uses regex to detect dates where both the first and second numeric components could be a valid month (e.g., `03/04/2026` could be March 4th or April 3rd). Only fires if `val1 != val2` (non-ambiguous dates like `15/06/2026` don't trigger this).

**Example:**
```
Raw date: "03/04/2026"
→ Could be 3rd April or 4th March → date_ambiguity REVIEW_REQUIRED
```
