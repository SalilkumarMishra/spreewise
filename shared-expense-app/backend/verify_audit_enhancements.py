"""
verify_audit_enhancements.py
============================
Automated verification script to actively attempt to break the application and test:
  1. Authentication abuse (invalid, expired, modified tokens, missing headers)
  2. Cross-user resource isolation (User A vs. User B)
  3. Group role boundaries (Owner vs. Member permissions)
  4. Expense split validations (equal, percentage, exact, shares edge cases)
  5. Membership lifecycle validation (charging before join/after leave)
  6. Settlement validation (payer == receiver, negative amount, inactive user)
  7. Balance engine net sum verification (always 0)
  8. CSV stress ingestion (empty, corrupted, missing headers)
"""
import os
import sys
import django
import json
from decimal import Decimal
import datetime

# Setup Django context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from groups.models import Group, GroupMembership
from expenses.models import Expense
from settlements.models import Settlement
from imports.models import ImportJob

User = get_user_model()

# Setup test clients & variables
client_a = APIClient()
client_b = APIClient()

TEST_USERNAMES = ["user_a_audit", "user_b_audit", "user_c_audit"]

passed = 0
failed = 0

def check(label: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  [PASS] {label}")
        passed += 1
    else:
        print(f"  [FAIL] {label}{' --- ' + detail if detail else ''}")
        failed += 1

def cleanup():
    """Clean up audit test users and all associated data."""
    from django.db import connection
    test_user_ids = list(User.objects.filter(username__in=TEST_USERNAMES).values_list("id", flat=True))
    if test_user_ids:
        ids_str = ",".join(str(i) for i in test_user_ids)
        
        # Soft deletes and cascade items
        with connection.cursor() as cursor:
            # Clean settlements first
            cursor.execute(f"DELETE FROM settlements_settlementsnapshot WHERE settlement_id IN (SELECT id FROM settlements_settlement WHERE created_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM settlements_settlement WHERE created_by_id IN ({ids_str}) OR payer_id IN ({ids_str}) OR receiver_id IN ({ids_str})")
            
            # Clean expenses
            cursor.execute(f"DELETE FROM expenses_expensesnapshot WHERE expense_id IN (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM expenses_expensesplit WHERE expense_id IN (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM expenses_expenseparticipant WHERE expense_id IN (SELECT id FROM expenses_expense WHERE created_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM expenses_expense WHERE created_by_id IN ({ids_str})")
            
            # Clean imports
            cursor.execute(f"DELETE FROM imports_importanomaly WHERE import_job_id IN (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM imports_importrow WHERE import_job_id IN (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM imports_importreport WHERE import_job_id IN (SELECT id FROM imports_importjob WHERE uploaded_by_id IN ({ids_str}))")
            cursor.execute(f"DELETE FROM imports_importjob WHERE uploaded_by_id IN ({ids_str})")
            
            # Clean groups & memberships
            group_ids = list(Group.objects.filter(created_by_id__in=test_user_ids).values_list("id", flat=True))
            if group_ids:
                gids_str = ",".join(str(i) for i in group_ids)
                cursor.execute(f"DELETE FROM groups_groupmembership WHERE group_id IN ({gids_str})")
                cursor.execute(f"DELETE FROM groups_group WHERE id IN ({gids_str})")
            cursor.execute(f"DELETE FROM groups_groupmembership WHERE user_id IN ({ids_str})")
            
        for username in TEST_USERNAMES:
            User.objects.filter(username=username).delete()

    print("\n[Cleanup] Removed audit test data.\n")

print("=" * 60)
print("   Spreewise Production Security & Boundary Audit")
print("=" * 60)

try:
    cleanup()

    # Create test users
    user_a = User.objects.create_user(username="user_a_audit", password="AuditPass#2026!")
    user_b = User.objects.create_user(username="user_b_audit", password="AuditPass#2026!")
    user_c = User.objects.create_user(username="user_c_audit", password="AuditPass#2026!")

    token_a = RefreshToken.for_user(user_a)
    token_b = RefreshToken.for_user(user_b)
    token_c = RefreshToken.for_user(user_c)

    access_a = str(token_a.access_token)
    access_b = str(token_b.access_token)

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[1] Authentication Abuse Tests")
    # ─────────────────────────────────────────────────────────────────────────
    client = APIClient()
    
    # Missing Auth header
    resp = client.get("/api/auth/me/")
    check("Missing Authorization header -> 401", resp.status_code == 401, f"Status: {resp.status_code}")
    
    # Invalid JWT token
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token_here")
    resp = client.get("/api/auth/me/")
    check("Invalid JWT token -> 401", resp.status_code == 401, f"Status: {resp.status_code}")
    
    # Modified JWT token (let's replace a character in the middle of the signature)
    # The signature is the third part after the second dot.
    parts = access_a.split(".")
    if len(parts) == 3:
        sig = parts[2]
        # Modify first character of signature
        new_sig = ("0" if sig[0] != "0" else "1") + sig[1:]
        modified_token = f"{parts[0]}.{parts[1]}.{new_sig}"
    else:
        modified_token = access_a + "modified"
    
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {modified_token}")
    resp = client.get("/api/auth/me/")
    check("Modified JWT token -> 401", resp.status_code == 401, f"Status: {resp.status_code}, Body: {resp.data if hasattr(resp, 'data') else ''}")
    
    # Expired token
    expired_token = RefreshToken.for_user(user_a).access_token
    expired_token.set_exp(lifetime=datetime.timedelta(seconds=-10))
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(expired_token)}")
    resp = client.get("/api/auth/me/")
    check("Expired JWT token -> 401", resp.status_code == 401, f"Status: {resp.status_code}")

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[2] Authorization Tests (Cross-user Boundaries)")
    # ─────────────────────────────────────────────────────────────────────────
    client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {access_a}")
    client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {access_b}")

    # User B creates a private group
    group_b_resp = client_b.post("/api/groups/", {"name": "User B Group", "currency": "INR"}, format="json")
    group_b_id = group_b_resp.data["id"]
    invite_code_b = group_b_resp.data["invite_code"]

    # User A tries to view User B's group details
    resp = client_a.get(f"/api/groups/{group_b_id}/")
    check("User A cannot view User B group -> 404/403", resp.status_code in (403, 404))

    # User B creates an expense in their group (User B joined today)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    expense_b_resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "B Private Dinner",
        "amount": "120.00",
        "currency": "INR",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id]
    }, format="json")
    
    check("User B creates valid expense successfully -> 201", expense_b_resp.status_code == 201, str(expense_b_resp.data))
    expense_b_id = expense_b_resp.data.get("id")

    # User A tries to view/edit User B's expense
    resp_get = client_a.get(f"/api/expenses/{expense_b_id}/")
    resp_put = client_a.put(f"/api/expenses/{expense_b_id}/", {"title": "Hacked Title"}, format="json")
    check("User A cannot get User B expense -> 404/403", resp_get.status_code in (403, 404))
    check("User A cannot edit User B expense -> 404/403", resp_put.status_code in (403, 404))

    # User B creates an import job (using a mock request check)
    resp = client_a.get("/api/imports/")
    check("User A list does not show User B's import jobs", not any(j.get("group") == group_b_id for j in resp.data))

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[3] Group Access Tests (Role Boundary Check)")
    # ─────────────────────────────────────────────────────────────────────────
    # User B adds User A to Group B as a regular 'member' (not owner/admin)
    today = datetime.date.today()
    GroupMembership.objects.create(
        group_id=group_b_id,
        user=user_a,
        joined_at=today,
        is_active=True,
        role="member"
    )
    
    # User A (member) attempts to archive group B
    resp_archive = client_a.delete(f"/api/groups/{group_b_id}/")
    check("Member cannot archive group -> 403 Forbidden", resp_archive.status_code == 403)

    # User A (member) attempts to remove the owner (User B) from Group B
    membership_b = GroupMembership.objects.get(group_id=group_b_id, user=user_b)
    resp_remove = client_a.delete(f"/api/groups/{group_b_id}/members/{membership_b.id}/remove/")
    check("Member cannot remove group owner -> 403 Forbidden", resp_remove.status_code == 403)

    # User A (member) attempts to change role of another member
    membership_a = GroupMembership.objects.get(group_id=group_b_id, user=user_a)
    resp_role = client_a.post(f"/api/groups/{group_b_id}/members/{membership_a.id}/role/", {"role": "owner"}, format="json")
    check("Member cannot modify roles -> 403 Forbidden", resp_role.status_code == 403)

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[4] Expense Validation Tests")
    # ─────────────────────────────────────────────────────────────────────────
    
    # Amount = 0
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Zero Expense",
        "amount": "0.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id]
    }, format="json")
    check("Expense amount = 0 -> 400 Bad Request", resp.status_code == 400)

    # Amount < 0
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Negative Expense",
        "amount": "-50.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id]
    }, format="json")
    check("Expense amount < 0 -> 400 Bad Request", resp.status_code == 400)

    # Duplicate participants
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Dup Participants",
        "amount": "100.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id, user_b.id]
    }, format="json")
    check("Duplicate participants -> 400 Bad Request", resp.status_code == 400)

    # Percentage splits > 100%
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Pct over 100",
        "amount": "100.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "percentage",
        "participant_ids": [user_b.id, user_a.id],
        "splits": [
            {"user_id": user_b.id, "percentage_value": "60.00"},
            {"user_id": user_a.id, "percentage_value": "50.00"}
        ]
    }, format="json")
    check("Percentage splits > 100 -> 400 Bad Request", resp.status_code == 400)

    # Percentage splits < 100%
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Pct under 100",
        "amount": "100.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "percentage",
        "participant_ids": [user_b.id, user_a.id],
        "splits": [
            {"user_id": user_b.id, "percentage_value": "40.00"},
            {"user_id": user_a.id, "percentage_value": "50.00"}
        ]
    }, format="json")
    check("Percentage splits < 100 -> 400 Bad Request", resp.status_code == 400)

    # Exact split mismatch
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Exact mismatch",
        "amount": "100.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "exact",
        "participant_ids": [user_b.id, user_a.id],
        "splits": [
            {"user_id": user_b.id, "exact_amount": "40.00"},
            {"user_id": user_a.id, "exact_amount": "50.00"}
        ]
    }, format="json")
    check("Exact splits mismatch sum -> 400 Bad Request", resp.status_code == 400)

    # Shares split sum <= 0
    resp = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Shares zero",
        "amount": "100.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "shares",
        "participant_ids": [user_b.id, user_a.id],
        "splits": [
            {"user_id": user_b.id, "shares_value": "0.00"},
            {"user_id": user_a.id, "shares_value": "0.00"}
        ]
    }, format="json")
    check("Shares sum <= 0 -> 400 Bad Request", resp.status_code == 400)

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[5] Membership Date Validation Tests")
    # ─────────────────────────────────────────────────────────────────────────
    # User C is added to Group B with a join date in the future
    join_date_c = today + datetime.timedelta(days=10)
    leave_date_c = today + datetime.timedelta(days=20)
    
    GroupMembership.objects.create(
        group_id=group_b_id,
        user=user_c,
        joined_at=join_date_c,
        left_at=leave_date_c,
        is_active=False,
        role="member"
    )

    # Attempt to charge User C on today (before joining)
    resp_before = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Dinner Before C Joined",
        "amount": "150.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id, user_c.id]
    }, format="json")
    check("Charge user before joining -> 400 Bad Request", resp_before.status_code == 400, str(resp_before.data))
    
    # Attempt to charge User C in the far future (after leaving)
    after_date_str = (today + datetime.timedelta(days=25)).strftime("%Y-%m-%d")
    resp_after = client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Dinner After C Left",
        "amount": "150.00",
        "expense_date": after_date_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id, user_c.id]
    }, format="json")
    check("Charge user after leaving -> 400 Bad Request", resp_after.status_code == 400, str(resp_after.data))

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[6] Settlement Validation Tests")
    # ─────────────────────────────────────────────────────────────────────────
    
    # Payer == receiver
    resp_same = client_b.post("/api/settlements/", {
        "group_id": group_b_id,
        "payer_id": user_b.id,
        "receiver_id": user_b.id,
        "amount": "50.00",
        "payment_date": today_str
    }, format="json")
    check("Payer cannot equal Receiver -> 400 Bad Request", resp_same.status_code == 400)

    # Amount <= 0
    resp_zero = client_b.post("/api/settlements/", {
        "group_id": group_b_id,
        "payer_id": user_b.id,
        "receiver_id": user_a.id,
        "amount": "-10.00",
        "payment_date": today_str
    }, format="json")
    check("Settlement amount <= 0 -> 400 Bad Request", resp_zero.status_code == 400)

    # Inactive member (User C outside active window)
    resp_inactive = client_b.post("/api/settlements/", {
        "group_id": group_b_id,
        "payer_id": user_b.id,
        "receiver_id": user_c.id,
        "amount": "50.00",
        "payment_date": today_str
    }, format="json")
    check("Settlement with inactive member -> 400 Bad Request", resp_inactive.status_code == 400)

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[7] Balance Engine Consistency (Net Balance Sum == 0)")
    # ─────────────────────────────────────────────────────────────────────────
    # Create valid expenses and settlements
    client_b.post("/api/expenses/", {
        "group_id": group_b_id,
        "title": "Lunch",
        "amount": "90.00",
        "expense_date": today_str,
        "paid_by_id": user_b.id,
        "split_type": "equal",
        "participant_ids": [user_b.id, user_a.id]
    }, format="json")

    client_b.post("/api/settlements/", {
        "group_id": group_b_id,
        "payer_id": user_a.id,
        "receiver_id": user_b.id,
        "amount": "20.00",
        "payment_date": today_str
    }, format="json")

    balance_resp = client_b.get(f"/api/balances/groups/{group_b_id}/")
    check("Balance query returned 200", balance_resp.status_code == 200)
    
    balances = balance_resp.data
    net_sum = sum(Decimal(str(b["balance"])) for b in balances)
    check("Sum of all group net balances is exactly 0.00", net_sum == Decimal("0.00"), f"Sum: {net_sum}")

    # ─────────────────────────────────────────────────────────────────────────
    print("\n[8] CSV Import Ingestion Stress Tests")
    # ─────────────────────────────────────────────────────────────────────────
    from imports.services.csv_parser import parse_csv
    import io

    # Empty CSV
    empty_csv = b""
    result, errors = parse_csv(empty_csv)
    check("Empty CSV returns gracefully (no crashes)", len(result) == 0)

    # Corrupt CSV / Missing headers
    corrupt_csv = b"title,amount,date,payer\nNo headers matching,100,2026-01-01,Aisha\n"
    result, errors = parse_csv(corrupt_csv)
    check("Corrupt/Missing columns CSV returns gracefully", len(result) == 0 or len(errors) > 0)

    # Invalid values
    # Must include all required columns to avoid failing at column validation level
    invalid_val_csv = (
        b"Date,Description,Payer,Amount,Currency,Split Type,Participants\n"
        b"2026-01-01,Dinner,Aisha,ten,INR,equal,aisha\n"
    )
    result, errors = parse_csv(invalid_val_csv)
    # Since parse_csv returns raw row parses, we check row parse_errors
    first_row = result[0] if result else {}
    check("Non-numeric amount caught gracefully in parsing", bool(first_row.get("parse_errors")), str(first_row.get("parse_errors")))

    print("\n" + "=" * 60)
    print(f"   Audit Results: {passed} passed / {failed} failed / {passed + failed} total")
    print("=" * 60)

finally:
    cleanup()

sys.exit(0 if failed == 0 else 1)
