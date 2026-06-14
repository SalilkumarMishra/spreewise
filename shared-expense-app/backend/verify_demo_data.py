"""
verify_demo_data.py
===================
Verifies that the seed_assignment_demo.py produced all expected data correctly.

Checks:
  - 6 users created
  - 1 group created
  - Membership history exists (including left_at dates)
  - 6 expenses created with correct split types
  - 3 settlements created with snapshots
  - ImportJob with 5 anomalies in review_required state
  - BalanceSnapshot exists
  - sum(all balances) == 0.00

Usage:
  cd shared-expense-app/backend
  venv\\Scripts\\python.exe verify_demo_data.py
"""
import os, sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from groups.models import Group, GroupMembership
from expenses.models import Expense, ExpenseSnapshot
from settlements.models import Settlement, SettlementSnapshot
from imports.models import ImportJob, ImportAnomaly
from balance_engine.models import BalanceSnapshot
from balance_engine.services.balance_service import calculate_group_balances

User = get_user_model()

DEMO_USERNAMES   = ["aisha", "rohan", "priya", "meera", "sam", "dev"]
DEMO_GROUP_NAME  = "Flatmates Shared Expenses"
PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1

def section(title):
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")

# ─────────────────────────────────────────────────────────────────────────────

section("1. Users")
existing_users = {u.username: u for u in User.objects.filter(username__in=DEMO_USERNAMES)}
check("6 users exist", len(existing_users) == 6, f"Found {len(existing_users)}")
for uname in DEMO_USERNAMES:
    check(f"User '{uname}' exists", uname in existing_users)
    if uname in existing_users:
        u = existing_users[uname]
        check(f"  Email set for '{uname}'", bool(u.email), u.email)
        check(f"  Password works for '{uname}'", u.check_password("Demo@123"))

# ─────────────────────────────────────────────────────────────────────────────

section("2. Group")
try:
    group = Group.objects.get(name=DEMO_GROUP_NAME, is_archived=False)
    check("Group 'Flatmates Shared Expenses' exists", True)
    check("Group currency is INR", group.currency == "INR", group.currency)
    check("Group has invite code (SPW-*)", group.invite_code.startswith("SPW-"), group.invite_code)
    aisha = existing_users.get("aisha")
    if aisha:
        check("Aisha is owner", group.memberships.filter(user=aisha, role="owner", is_active=True).exists())
except Group.DoesNotExist:
    check("Group exists", False, "Not found")
    group = None

# ─────────────────────────────────────────────────────────────────────────────

section("3. Membership Timeline")
if group:
    memberships = {m.user.username: m for m in group.memberships.all()}
    check("6 membership records exist", len(memberships) == 6, f"Found {len(memberships)}")

    # Active members
    for uname in ["aisha", "rohan", "priya", "sam"]:
        if uname in memberships:
            m = memberships[uname]
            check(f"'{uname}' is active member", m.is_active, f"is_active={m.is_active}")

    # Meera — left 2026-03-31
    if "meera" in memberships:
        m = memberships["meera"]
        check("Meera has left_at date", m.left_at is not None, str(m.left_at))
        check("Meera left on 2026-03-31", str(m.left_at) == "2026-03-31", str(m.left_at))
        check("Meera is_active=False", m.is_active == False)

    # Dev — left 2026-03-15
    if "dev" in memberships:
        m = memberships["dev"]
        check("Dev has left_at date", m.left_at is not None)
        check("Dev left on 2026-03-15", str(m.left_at) == "2026-03-15", str(m.left_at))
        check("Dev is_active=False", m.is_active == False)

    # Sam — joined 2026-04-15
    if "sam" in memberships:
        m = memberships["sam"]
        check("Sam joined on 2026-04-15", str(m.joined_at) == "2026-04-15", str(m.joined_at))

# ─────────────────────────────────────────────────────────────────────────────

section("4. Expenses")
if group:
    expenses = list(Expense.objects.filter(group=group).order_by("expense_date"))
    check("At least 6 expenses exist", len(expenses) >= 6, f"Found {len(expenses)}")

    split_types_found = {e.split_type for e in expenses}
    check("Equal split expense exists",      "equal" in split_types_found)
    check("Exact split expense exists",      "exact" in split_types_found)
    check("Shares split expense exists",     "shares" in split_types_found)
    check("Percentage split expense exists", "percentage" in split_types_found)

    # Multi-currency expense
    multi_currency = [e for e in expenses if e.original_currency != e.currency]
    check("Multi-currency expense exists (USD→INR)", len(multi_currency) > 0, str([e.title for e in multi_currency]))

    # Import review status
    import_review = [e for e in expenses if e.status == "import_review"]
    check("Expense with import_review status exists", len(import_review) > 0)

    # Snapshots
    total_snapshots = ExpenseSnapshot.objects.filter(expense__group=group).count()
    check(f"ExpenseSnapshots created ({total_snapshots})", total_snapshots >= 6, f"Found {total_snapshots}")

# ─────────────────────────────────────────────────────────────────────────────

section("5. Settlements")
if group:
    settlements = list(Settlement.objects.filter(group=group).order_by("payment_date"))
    check("3 settlements exist", len(settlements) == 3, f"Found {len(settlements)}")

    settlement_map = {(s.payer.username, s.receiver.username): s for s in settlements}
    check("Settlement: Rohan → Aisha exists", ("rohan", "aisha") in settlement_map)
    check("Settlement: Priya → Rohan exists", ("priya", "rohan") in settlement_map)
    check("Settlement: Sam → Aisha exists",   ("sam", "aisha")   in settlement_map)

    s_snapshots = SettlementSnapshot.objects.filter(settlement__group=group).count()
    check(f"SettlementSnapshots created ({s_snapshots})", s_snapshots >= 3, f"Found {s_snapshots}")

    # Reference IDs
    for s in settlements:
        check(f"Settlement {s.id} has reference_id (SET-*)", s.reference_id.startswith("SET-"), s.reference_id)

# ─────────────────────────────────────────────────────────────────────────────

section("6. CSV Import Job & Anomalies")
if group:
    jobs = ImportJob.objects.filter(group=group, status="review_required")
    check("ImportJob with status=review_required exists", jobs.exists(), f"Found {jobs.count()}")

    if jobs.exists():
        job = jobs.first()
        anomalies = ImportAnomaly.objects.filter(import_job=job)
        check("5 anomalies exist",           anomalies.count() == 5, f"Found {anomalies.count()}")
        categories = set(anomalies.values_list("anomaly_category", flat=True))
        check("Duplicate anomaly present",    "duplicate"    in categories)
        check("Unknown user anomaly present", "unknown_user" in categories)
        check("Date anomaly present",         "date"         in categories)
        check("Settlement anomaly present",   "settlement"   in categories)
        check("Membership anomaly present",   "membership"   in categories)

# ─────────────────────────────────────────────────────────────────────────────

section("7. Balance Engine")
if group:
    snapshots = BalanceSnapshot.objects.filter(group=group)
    check("BalanceSnapshot exists", snapshots.exists(), f"Found {snapshots.count()}")

    balances = calculate_group_balances(group)
    check("Balances computed for all members", len(balances) > 0, f"Found {len(balances)}")

    total = sum(b["balance"] for b in balances)
    check(f"SUM of all balances == 0.00 (got {total:.2f})", total == Decimal("0.00"), f"Sum: {total}")

# ─────────────────────────────────────────────────────────────────────────────

section("SUMMARY")
print(f"\n  Total: {PASS + FAIL} checks — {PASS} passed / {FAIL} failed\n")
if FAIL == 0:
    print("  ✅ ALL CHECKS PASSED — Demo data is complete and correct.\n")
else:
    print(f"  ❌ {FAIL} CHECK(S) FAILED — Run seed_assignment_demo.py to re-seed.\n")

sys.exit(0 if FAIL == 0 else 1)
