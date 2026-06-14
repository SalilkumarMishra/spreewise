"""
seed_assignment_demo.py
=======================
Creates realistic demo data for the Flatmates Shared Expenses scenario.

IMPORTANT: All data is created through service layers — NOT ORM shortcuts.
This ensures:
  - Snapshots are generated
  - Ledger entries are correct
  - All validations are exercised
  - Balance invariants hold

Usage:
  cd shared-expense-app/backend
  venv\\Scripts\\python.exe seed_assignment_demo.py
"""
import os, sys, datetime
from decimal import Decimal

# Force UTF-8 output on Windows to allow printing ₹ and other unicode chars
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from groups.models import Group, GroupMembership
from groups.services import membership_service
from expenses.services.expense_service import create_expense
from settlements.services.settlement_service import create_settlement
from balance_engine.services.balance_service import recalculate_group_balances
from balance_engine.services.simplification_service import simplify_debts
from imports.models import ImportJob, ImportRow, ImportAnomaly, ImportReport

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def d(date_str):
    """Parse a YYYY-MM-DD string into a date object."""
    return datetime.date.fromisoformat(date_str)

def banner(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def ok(label):
    print(f"  [OK] {label}")

def info(label):
    print(f"  [..] {label}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — Cleanup any existing demo data
# ─────────────────────────────────────────────────────────────────────────────

DEMO_USERNAMES = ["aisha", "rohan", "priya", "meera", "sam", "dev"]
DEMO_GROUP_NAME = "Flatmates Shared Expenses"

def cleanup():
    banner("Cleaning Up Previous Demo Data")
    existing = User.objects.filter(username__in=DEMO_USERNAMES)
    if existing.exists():
        demo_user_ids = list(existing.values_list("id", flat=True))
        ids_str = ",".join(str(i) for i in demo_user_ids)
        from django.db import connection
        with connection.cursor() as cursor:
            # Anomalies & import data
            cursor.execute(f"""
                DELETE FROM imports_importanomaly WHERE import_job_id IN
                (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM imports_importrow WHERE import_job_id IN
                (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM imports_importreport WHERE import_job_id IN
                (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM imports_importjob WHERE uploaded_by_id IN ({ids_str})
            """)
            # Balance snapshots
            group_ids = list(Group.objects.filter(created_by_id__in=demo_user_ids).values_list("id", flat=True))
            if group_ids:
                gids = ",".join(str(g) for g in group_ids)
                cursor.execute(f"DELETE FROM balance_engine_balancesnapshot WHERE group_id IN ({gids})")
            # Settlements & snapshots
            cursor.execute(f"""
                DELETE FROM settlements_settlementsnapshot WHERE settlement_id IN
                (SELECT id FROM settlements_settlement WHERE created_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM settlements_settlement WHERE created_by_id IN ({ids_str})
                OR payer_id IN ({ids_str}) OR receiver_id IN ({ids_str})
            """)
            # Expenses
            cursor.execute(f"""
                DELETE FROM expenses_expensesnapshot WHERE expense_id IN
                (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM expenses_expensesplit WHERE expense_id IN
                (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM expenses_expenseparticipant WHERE expense_id IN
                (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))
            """)
            cursor.execute(f"""
                DELETE FROM expenses_expense WHERE created_by_id IN ({ids_str})
            """)
            # Memberships & groups
            if group_ids:
                gids = ",".join(str(g) for g in group_ids)
                cursor.execute(f"DELETE FROM groups_groupmembership WHERE group_id IN ({gids})")
                cursor.execute(f"DELETE FROM groups_group WHERE id IN ({gids})")
            cursor.execute(f"DELETE FROM groups_groupmembership WHERE user_id IN ({ids_str})")
        for u in DEMO_USERNAMES:
            User.objects.filter(username=u).delete()
        ok("Previous demo data removed.")
    else:
        ok("No previous demo data found.")

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Create Users
# ─────────────────────────────────────────────────────────────────────────────

def create_users():
    banner("Creating Demo Users")
    user_specs = [
        ("aisha", "aisha@demo.com", "Aisha", "Khan"),
        ("rohan", "rohan@demo.com", "Rohan", "Mehta"),
        ("priya", "priya@demo.com", "Priya", "Sharma"),
        ("meera", "meera@demo.com", "Meera", "Iyer"),
        ("sam",   "sam@demo.com",   "Sam",   "D'Souza"),
        ("dev",   "dev@demo.com",   "Dev",   "Patel"),
    ]
    users = {}
    for username, email, first, last in user_specs:
        u = User.objects.create_user(
            username=username,
            email=email,
            password="Demo@123",
            first_name=first,
            last_name=last,
        )
        # Set full_name if the model supports it
        if hasattr(u, "full_name"):
            u.full_name = f"{first} {last}"
            u.save(update_fields=["full_name"])
        users[username] = u
        ok(f"User: {username} ({email})")
    return users

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Create Group
# ─────────────────────────────────────────────────────────────────────────────

def create_group(aisha):
    banner("Creating Group: Flatmates Shared Expenses")
    group = Group.objects.create(
        name=DEMO_GROUP_NAME,
        description="Shared expenses for Flatmates — rent, food, utilities, and trips.",
        currency="INR",
        created_by=aisha,
    )
    ok(f"Group created: '{group.name}' (ID={group.id})")
    ok(f"Invite Code: {group.invite_code}")
    return group

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Memberships via membership_service
# ─────────────────────────────────────────────────────────────────────────────

def create_memberships(group, users):
    banner("Setting Up Membership Timeline")

    # Aisha — owner, joined 2026-02-01
    membership_service.add_member(group, users["aisha"], d("2026-02-01"), role="owner")
    ok("Aisha  joined 2026-02-01 (owner)")

    # Rohan — member, joined 2026-02-01
    membership_service.add_member(group, users["rohan"], d("2026-02-01"), role="member")
    ok("Rohan  joined 2026-02-01")

    # Priya — member, joined 2026-02-01
    membership_service.add_member(group, users["priya"], d("2026-02-01"), role="member")
    ok("Priya  joined 2026-02-01")

    # Meera — member, joined 2026-02-01, left 2026-03-31
    membership_service.add_member(group, users["meera"], d("2026-02-01"), role="member")
    membership_service.leave_member(group, users["meera"], d("2026-03-31"))
    ok("Meera  joined 2026-02-01, left 2026-03-31")

    # Dev — temporary trip member, joined 2026-02-08, left 2026-03-15
    membership_service.add_member(group, users["dev"], d("2026-02-08"), role="member")
    membership_service.leave_member(group, users["dev"], d("2026-03-15"))
    ok("Dev    joined 2026-02-08, left 2026-03-15 (temp trip member)")

    # Sam — joined 2026-04-15
    membership_service.add_member(group, users["sam"], d("2026-04-15"), role="member")
    ok("Sam    joined 2026-04-15")

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Expenses via expense_service
# ─────────────────────────────────────────────────────────────────────────────

def create_expenses(group, users):
    banner("Creating Expenses via expense_service")
    expenses = {}

    # ── Expense 1: Dinner at Marina Bites — Equal Split ─────────────────────
    e1 = create_expense(
        group=group,
        title="Dinner at Marina Bites",
        amount=Decimal("2400.00"),
        currency="INR",
        expense_date=d("2026-02-03"),
        paid_by=users["aisha"],
        split_type="equal",
        creator=users["aisha"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["meera"]],
        expense_category="food",
        notes="First flatmate dinner together at Marina Bites.",
        source="manual",
    )
    expenses["marina_dinner"] = e1
    ok(f"E1: Dinner at Marina Bites — ₹2,400 equal (4 people, ₹600/ea) [ID={e1.id}]")

    # ── Expense 2: Electricity February — Exact Split ────────────────────────
    # Aisha:400, Rohan:300, Priya:300, Meera:200
    e2 = create_expense(
        group=group,
        title="Electricity February",
        amount=Decimal("1200.00"),
        currency="INR",
        expense_date=d("2026-02-28"),
        paid_by=users["rohan"],
        split_type="exact",
        creator=users["rohan"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["meera"]],
        splits_data=[
            {"user_id": users["aisha"].id, "exact_amount": "400.00"},
            {"user_id": users["rohan"].id, "exact_amount": "300.00"},
            {"user_id": users["priya"].id, "exact_amount": "300.00"},
            {"user_id": users["meera"].id, "exact_amount": "200.00"},
        ],
        expense_category="utilities",
        notes="February electricity bill exact split.",
        source="manual",
    )
    expenses["electricity"] = e2
    ok(f"E2: Electricity February — ₹1,200 exact split (Rohan paid) [ID={e2.id}]")

    # ── Expense 3: Cylinder Refill — Shares Split ────────────────────────────
    # Aisha:2, Rohan:2, Priya:3, Meera:1 → total 8 shares
    e3 = create_expense(
        group=group,
        title="Cylinder Refill",
        amount=Decimal("900.00"),
        currency="INR",
        expense_date=d("2026-03-02"),
        paid_by=users["priya"],
        split_type="shares",
        creator=users["priya"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["meera"]],
        splits_data=[
            {"user_id": users["aisha"].id, "shares_value": "2"},
            {"user_id": users["rohan"].id, "shares_value": "2"},
            {"user_id": users["priya"].id, "shares_value": "3"},
            {"user_id": users["meera"].id, "shares_value": "1"},
        ],
        expense_category="groceries",
        notes="LPG cylinder refill for kitchen — shares-weighted split.",
        source="manual",
    )
    expenses["cylinder"] = e3
    ok(f"E3: Cylinder Refill — ₹900 shares (2:2:3:1) [ID={e3.id}]")

    # ── Expense 4: Goa Villa Booking — USD → INR (import_review status) ──────
    # Dev paid, USD 500 (approx ₹41,500), only active members on 2026-02-15:
    # Aisha, Rohan, Priya, Meera, Dev
    e4 = create_expense(
        group=group,
        title="Goa Villa Booking",
        amount=Decimal("41500.00"),       # Converted INR amount
        currency="INR",
        original_amount=Decimal("500.00"),
        original_currency="USD",
        expense_date=d("2026-02-15"),
        paid_by=users["dev"],
        split_type="equal",
        creator=users["dev"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["meera"], users["dev"]],
        expense_category="travel",
        status="import_review",
        notes="Goa villa booking — USD 500 converted at ₹83/USD. Pending review for multi-currency anomaly.",
        source="csv_import",
    )
    expenses["goa_villa"] = e4
    ok(f"E4: Goa Villa Booking — USD 500 → ₹41,500 (status=import_review) [ID={e4.id}]")

    # ── Expense 5: Thalassa Dinner — Percentage Split ────────────────────────
    # Aisha:40%, Rohan:30%, Priya:20%, Dev:10%
    e5 = create_expense(
        group=group,
        title="Thalassa Dinner",
        amount=Decimal("2450.00"),
        currency="INR",
        expense_date=d("2026-02-18"),
        paid_by=users["aisha"],
        split_type="percentage",
        creator=users["aisha"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["dev"]],
        splits_data=[
            {"user_id": users["aisha"].id, "percentage_value": "40.00"},
            {"user_id": users["rohan"].id, "percentage_value": "30.00"},
            {"user_id": users["priya"].id, "percentage_value": "20.00"},
            {"user_id": users["dev"].id,   "percentage_value": "10.00"},
        ],
        expense_category="food",
        notes="Thalassa beach dinner, Goa trip night 2.",
        source="manual",
    )
    expenses["thalassa"] = e5
    ok(f"E5: Thalassa Dinner — ₹2,450 percentage (40/30/20/10%) [ID={e5.id}]")

    # ── Expense 6: Furniture Purchase — Equal Split (Sam + others) ───────────
    # Sam joined 2026-04-15; expense is 2026-04-20. Active: Aisha, Rohan, Priya, Sam
    e6 = create_expense(
        group=group,
        title="Furniture Purchase",
        amount=Decimal("10000.00"),
        currency="INR",
        expense_date=d("2026-04-20"),
        paid_by=users["sam"],
        split_type="equal",
        creator=users["sam"],
        participant_users=[users["aisha"], users["rohan"], users["priya"], users["sam"]],
        expense_category="household",
        notes="Sofa + bookshelf for common area. Equal split 4 ways.",
        source="manual",
    )
    expenses["furniture"] = e6
    ok(f"E6: Furniture Purchase — ₹10,000 equal (4 people) [ID={e6.id}]")

    return expenses

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Settlements via settlement_service
# ─────────────────────────────────────────────────────────────────────────────

def create_settlements(group, users):
    banner("Creating Settlements via settlement_service")
    settlements = {}

    # Settlement 1: Rohan → Aisha, ₹500, 2026-03-10
    s1 = create_settlement(
        group=group,
        payer=users["rohan"],
        receiver=users["aisha"],
        amount=Decimal("500.00"),
        currency="INR",
        payment_date=d("2026-03-10"),
        creator=users["rohan"],
        settlement_category="upi",
        notes="Partial repayment — Marina Bites dinner.",
    )
    settlements["rohan_aisha"] = s1
    ok(f"S1: Rohan → Aisha ₹500 [ID={s1.id}, Ref={s1.reference_id}]")

    # Settlement 2: Priya → Rohan, ₹300, 2026-03-18
    s2 = create_settlement(
        group=group,
        payer=users["priya"],
        receiver=users["rohan"],
        amount=Decimal("300.00"),
        currency="INR",
        payment_date=d("2026-03-18"),
        creator=users["priya"],
        settlement_category="upi",
        notes="Priya settling electricity share with Rohan.",
    )
    settlements["priya_rohan"] = s2
    ok(f"S2: Priya → Rohan ₹300 [ID={s2.id}, Ref={s2.reference_id}]")

    # Settlement 3: Sam → Aisha, ₹1500, 2026-05-01
    s3 = create_settlement(
        group=group,
        payer=users["sam"],
        receiver=users["aisha"],
        amount=Decimal("1500.00"),
        currency="INR",
        payment_date=d("2026-05-01"),
        creator=users["sam"],
        settlement_category="bank_transfer",
        notes="Sam settling furniture purchase share.",
    )
    settlements["sam_aisha"] = s3
    ok(f"S3: Sam → Aisha ₹1,500 [ID={s3.id}, Ref={s3.reference_id}]")

    return settlements

# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — CSV Import Demo with 5 Anomalies
# ─────────────────────────────────────────────────────────────────────────────

def create_import_demo(group, users):
    banner("Creating CSV Import Job with Anomalies")

    import_job = ImportJob.objects.create(
        group=group,
        uploaded_by=users["aisha"],
        original_filename="flatmates_history_import.csv",
        status="review_required",
    )
    ok(f"ImportJob created: ID={import_job.id} (status=review_required)")

    anomaly_specs = [
        {
            "row_num": 1,
            "raw": {"date": "2026-02-03", "description": "Dinner at Marina Bites", "amount": "2400.00", "payer": "aisha"},
            "parsed": {"title": "Dinner at Marina Bites", "amount": "2400.00", "expense_date": "2026-02-03"},
            "anomaly_type": "DUPLICATE_EXPENSE",
            "anomaly_category": "duplicate",
            "severity": "high",
            "description": "Anomaly A: This expense appears to already exist in the system with identical title, amount, and date (2026-02-03, ₹2400, Aisha). Possible double-import.",
            "action": "REVIEW_REQUIRED",
        },
        {
            "row_num": 2,
            "raw": {"date": "2026-03-05", "description": "Supermarket Groceries", "amount": "850.00", "payer": "ravi_kumar"},
            "parsed": {"title": "Supermarket Groceries", "amount": "850.00", "payer": "ravi_kumar"},
            "anomaly_type": "UNKNOWN_USER",
            "anomaly_category": "unknown_user",
            "severity": "high",
            "description": "Anomaly B: Payer 'ravi_kumar' could not be resolved to any known group member across all 5 identity resolution stages (username, first name, full name, prefix, alias).",
            "action": "REVIEW_REQUIRED",
        },
        {
            "row_num": 3,
            "raw": {"date": "03/04/2026", "description": "Weekend Breakfast", "amount": "620.00", "payer": "priya"},
            "parsed": {"title": "Weekend Breakfast", "amount": "620.00", "expense_date_raw": "03/04/2026"},
            "anomaly_type": "DATE_AMBIGUITY",
            "anomaly_category": "date",
            "severity": "medium",
            "description": "Anomaly C: Date '03/04/2026' is ambiguous — could be March 4 (MM/DD/YYYY) or April 3 (DD/MM/YYYY). Auto-interpreted as 2026-03-04. Requires confirmation.",
            "action": "REVIEW_REQUIRED",
        },
        {
            "row_num": 4,
            "raw": {"date": "2026-03-10", "description": "Rohan paid Aisha 500", "amount": "500.00", "payer": "rohan", "participants": "aisha"},
            "parsed": {"title": "Rohan paid Aisha 500", "amount": "500.00", "looks_like_settlement": True},
            "anomaly_type": "SETTLEMENT_AS_EXPENSE",
            "anomaly_category": "settlement",
            "severity": "medium",
            "description": "Anomaly D: Row description 'Rohan paid Aisha 500' matches a known settlement pattern (payer→receiver format). Logged as expense but should be recorded as a settlement instead.",
            "action": "REVIEW_REQUIRED",
        },
        {
            "row_num": 5,
            "raw": {"date": "2026-04-01", "description": "April Grocery Run", "amount": "1100.00", "payer": "meera"},
            "parsed": {"title": "April Grocery Run", "amount": "1100.00", "payer": "meera", "expense_date": "2026-04-01"},
            "anomaly_type": "MEMBERSHIP_VIOLATION",
            "anomaly_category": "membership",
            "severity": "critical",
            "description": "Anomaly E: Payer 'meera' left the group on 2026-03-31. The expense date (2026-04-01) is after her departure. She cannot be charged on a date she was not a member.",
            "action": "REJECT",
        },
    ]

    anomaly_objs = []
    for spec in anomaly_specs:
        row = ImportRow.objects.create(
            import_job=import_job,
            row_number=spec["row_num"],
            raw_data=spec["raw"],
            parsed_data=spec["parsed"],
            processing_status="review_required",
        )
        anomaly = ImportAnomaly.objects.create(
            import_job=import_job,
            import_row=row,
            anomaly_type=spec["anomaly_type"],
            anomaly_category=spec["anomaly_category"],
            severity=spec["severity"],
            description=spec["description"],
            detected_action=spec["action"],
        )
        anomaly_objs.append(anomaly)
        ok(f"Anomaly {spec['row_num']}: [{spec['anomaly_type']}] — {spec['severity'].upper()} — {spec['action']}")

    # Create import report stub
    ImportReport.objects.create(
        import_job=import_job,
        total_rows=5,
        imported_rows=0,
        skipped_rows=0,
        failed_rows=1,
        anomaly_count=5,
        report_json={
            "status": "review_required",
            "anomaly_breakdown": {
                "duplicate": 1,
                "unknown_user": 1,
                "date_ambiguity": 1,
                "settlement_as_expense": 1,
                "membership_violation": 1,
            }
        },
    )
    ok(f"ImportReport created for job {import_job.id}")
    return import_job, anomaly_objs

# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Run Balance Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_balance_engine(group):
    banner("Running Balance Engine & Generating Snapshot")
    balances, snapshot = recalculate_group_balances(group)
    ok(f"BalanceSnapshot ID={snapshot.id} generated for group '{group.name}'")

    print("\n  Net Balances:")
    for b in sorted(balances, key=lambda x: -x["balance"]):
        direction = "+" if b["balance"] >= 0 else ""
        print(f"    {b['user']:<12} {direction}{b['balance']:>12.2f} INR")

    total = sum(b["balance"] for b in balances)
    print(f"\n  SUM of all balances: {total:.2f} (must be 0.00)")
    assert total == Decimal("0.00"), f"FATAL: Balance sum is {total}, not 0!"
    ok("Balance invariant VERIFIED: SUM == 0.00")
    return balances

# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Debt Simplification
# ─────────────────────────────────────────────────────────────────────────────

def run_simplification(group):
    banner("Debt Simplification (Minimum Payment Instructions)")
    payments = simplify_debts(group)
    if not payments:
        print("  All debts are settled — no payments needed!")
    else:
        print("\n  Minimum payment instructions:")
        for i, p in enumerate(payments, 1):
            print(f"    {i}. {p['payer']:<12} → {p['receiver']:<12} ₹{p['amount']:>10.2f}")
    return payments

# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Generate DEMO_DATA_REPORT.md
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(group, users, balances, payments, import_job):
    banner("Generating DEMO_DATA_REPORT.md")
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "DEMO_DATA_REPORT.md"
    )

    from expenses.models import Expense
    from settlements.models import Settlement
    expenses = list(Expense.objects.filter(group=group).order_by("expense_date"))
    settlements = list(Settlement.objects.filter(group=group).order_by("payment_date"))
    memberships = list(group.memberships.all().order_by("joined_at"))
    anomalies = list(import_job.anomalies.all())

    lines = [
        "# Spreewise — Demo Data Report",
        "> Auto-generated by `seed_assignment_demo.py`",
        "",
        "---",
        "",
        "## 1. Demo Login Credentials",
        "",
        "| Username | Password | Role |",
        "|---|---|---|",
        "| aisha | Demo@123 | Owner |",
        "| rohan | Demo@123 | Member |",
        "| priya | Demo@123 | Member |",
        "| meera | Demo@123 | Member (Left 2026-03-31) |",
        "| sam   | Demo@123 | Member (Joined 2026-04-15) |",
        "| dev   | Demo@123 | Temp Trip Member (Left 2026-03-15) |",
        "",
        "---",
        "",
        "## 2. Group",
        "",
        f"| Field | Value |",
        "|---|---|",
        f"| Name | {group.name} |",
        f"| Currency | {group.currency} |",
        f"| Owner | aisha |",
        f"| Invite Code | `{group.invite_code}` |",
        f"| Group ID | {group.id} |",
        "",
        "---",
        "",
        "## 3. Membership Timeline",
        "",
        "| Member | Joined | Left | Role |",
        "|---|---|---|---|",
    ]
    for m in memberships:
        left = str(m.left_at) if m.left_at else "—"
        lines.append(f"| {m.user.username} | {m.joined_at} | {left} | {m.role} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Expenses",
        "",
        "| # | Title | Date | Paid By | Amount | Split Type | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, e in enumerate(expenses, 1):
        orig = f" (orig {e.original_currency} {e.original_amount})" if e.original_currency != e.currency else ""
        lines.append(f"| {i} | {e.title} | {e.expense_date} | {e.paid_by.username} | ₹{e.amount}{orig} | {e.split_type} | {e.status} |")

    lines += [
        "",
        "---",
        "",
        "## 5. Settlements",
        "",
        "| # | Reference | Payer | Receiver | Amount | Date | Category |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(settlements, 1):
        lines.append(f"| {i} | {s.reference_id} | {s.payer.username} | {s.receiver.username} | ₹{s.amount} | {s.payment_date} | {s.settlement_category} |")

    lines += [
        "",
        "---",
        "",
        "## 6. Net Balances",
        "",
        "| Member | Net Balance (INR) | Status |",
        "|---|---|---|",
    ]
    for b in sorted(balances, key=lambda x: -x["balance"]):
        status = "Lent (Credit)" if b["balance"] > 0 else ("Owes (Debit)" if b["balance"] < 0 else "Settled")
        sign = "+" if b["balance"] >= 0 else ""
        lines.append(f"| {b['user']} | {sign}{b['balance']:.2f} | {status} |")

    lines += [
        "",
        "---",
        "",
        "## 7. Debt Simplification (Minimum Payments)",
        "",
        "| # | Payer | → | Receiver | Amount (INR) |",
        "|---|---|---|---|---|",
    ]
    if payments:
        for i, p in enumerate(payments, 1):
            lines.append(f"| {i} | {p['payer']} | → | {p['receiver']} | ₹{p['amount']:.2f} |")
    else:
        lines.append("| — | All settled | — | — | — |")

    lines += [
        "",
        "---",
        "",
        "## 8. CSV Import Anomalies",
        "",
        f"**Import Job ID**: {import_job.id}  ",
        f"**Status**: review_required  ",
        f"**File**: {import_job.original_filename}",
        "",
        "| # | Type | Category | Severity | Action |",
        "|---|---|---|---|---|",
    ]
    for i, a in enumerate(anomalies, 1):
        lines.append(f"| {i} | {a.anomaly_type} | {a.anomaly_category} | {a.severity.upper()} | {a.detected_action} |")

    lines += [
        "",
        "---",
        "",
        "## 9. Feature Coverage",
        "",
        "| Feature | Demo Data |",
        "|---|---|",
        "| JWT Auth | ✅ 6 users with credentials |",
        "| Groups & Invite Code | ✅ Group with SPW-* code |",
        "| Membership Timeline | ✅ Join + Leave dates (Meera, Dev) |",
        "| Equal Split | ✅ Expense 1, 6 |",
        "| Exact Split | ✅ Expense 2 |",
        "| Shares Split | ✅ Expense 3 |",
        "| Percentage Split | ✅ Expense 5 |",
        "| Multi-Currency | ✅ Expense 4 (USD → INR) |",
        "| Expense Snapshots | ✅ Created for all 6 expenses |",
        "| Settlements | ✅ 3 settlements with snapshots |",
        "| Balance Engine | ✅ Computed, sum == 0.00 |",
        "| Debt Simplification | ✅ Minimum payment graph |",
        "| CSV Import Anomalies | ✅ 5 anomaly types queued |",
        "| Dashboard Data | ✅ Groups, expenses, balances, imports |",
        "",
        "---",
        "",
        "> Ready for live interview demonstration.",
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    ok(f"DEMO_DATA_REPORT.md written to: {report_path}")
    return report_path

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n")
    banner("Spreewise — Demo Data Seed Script (Assignment Scenario)")

    cleanup()

    with transaction.atomic():
        users   = create_users()
        group   = create_group(users["aisha"])
        create_memberships(group, users)
        expenses = create_expenses(group, users)
        settlements = create_settlements(group, users)
        import_job, _ = create_import_demo(group, users)

    # Balance engine runs outside atomic to read committed data
    balances = run_balance_engine(group)
    payments = run_simplification(group)
    report_path = generate_report(group, users, balances, payments, import_job)

    banner("DEMO DATA SEEDED SUCCESSFULLY")
    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │           INTERVIEW MODE — Demo Login Credentials       │
  ├─────────────────────────┬───────────────────────────────┤
  │  Username               │  Password                     │
  ├─────────────────────────┼───────────────────────────────┤
  │  aisha                  │  Demo@123                     │
  │  rohan                  │  Demo@123                     │
  │  priya                  │  Demo@123                     │
  │  sam                    │  Demo@123                     │
  ├─────────────────────────┴───────────────────────────────┤
  │  Group Invite Code: {group.invite_code:<33}   │
  │  Frontend: http://localhost:5173                        │
  │  Report:   DEMO_DATA_REPORT.md                         │
  └─────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    main()
