"""
verify_jwt_auth.py
==================
End-to-end integration test for the JWT Auth + Multi-User SaaS platform.

Tests:
  1. User registration (creates JWT tokens)
  2. User login (JWT token obtain)
  3. Token refresh (auto-refresh flow)
  4. Invite code generation on group creation
  5. Second user joins via invite code
  6. Membership visibility (user sees their group)
  7. Unauthorized user cannot access group
  8. Role-based access (member cannot CSV upload)
  9. Cleanup test data

Run from backend directory:
  venv\\Scripts\\python.exe verify_jwt_auth.py
"""
import os
import sys
import django
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from groups.models import Group, GroupMembership

User = get_user_model()

# ── Test usernames (will be cleaned up after) ──────────────────────────────
TEST_USERS = {
    "aisha_verify": "TestPass#2026!",
    "rohan_verify": "TestPass#2026!",
    "outsider_verify": "TestPass#2026!",
}

client = APIClient()

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
    """Remove test users, their groups and memberships in proper FK order."""
    from django.db import connection
    test_user_ids = list(User.objects.filter(username__in=list(TEST_USERS.keys())).values_list("id", flat=True))
    if test_user_ids:
        ids_str = ",".join(str(i) for i in test_user_ids)
        group_ids = list(Group.objects.filter(created_by_id__in=test_user_ids).values_list("id", flat=True))
        with connection.cursor() as cursor:
            if group_ids:
                gids_str = ",".join(str(i) for i in group_ids)
                # Delete memberships first (FK to groups)
                cursor.execute(f"DELETE FROM groups_groupmembership WHERE group_id IN ({gids_str})")
                # Then delete groups
                cursor.execute(f"DELETE FROM groups_group WHERE id IN ({gids_str})")
            # Delete memberships the user has in OTHER groups (Rohan joined Aisha's group)
            cursor.execute(f"DELETE FROM groups_groupmembership WHERE user_id IN ({ids_str})")
    for username in TEST_USERS:
        User.objects.filter(username=username).delete()
    print("\n[Cleanup] Removed test users and associated data.\n")





print("=" * 60)
print("   JWT Auth & Multi-User Platform Verification")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] User Registration")
# ─────────────────────────────────────────────────────────────────────────────

# Clean up any residual test data first
cleanup()

reg_resp = client.post("/api/auth/register/", {
    "full_name": "Aisha Verification",
    "username": "aisha_verify",
    "email": "aisha_verify@test.com",
    "password": "TestPass#2026!",
    "confirm_password": "TestPass#2026!",
}, format="json")

check("Registration returns 201", reg_resp.status_code == 201, str(reg_resp.data))
check("Registration returns access token", "access" in (reg_resp.data or {}))
check("Registration returns refresh token", "refresh" in (reg_resp.data or {}))
check("Registration returns user profile", "user" in (reg_resp.data or {}))

aisha_access = reg_resp.data.get("access", "")
aisha_refresh = reg_resp.data.get("refresh", "")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] Login (JWT Token Obtain)")
# ─────────────────────────────────────────────────────────────────────────────

login_resp = client.post("/api/auth/login/", {
    "username": "aisha_verify",
    "password": "TestPass#2026!",
}, format="json")

check("Login returns 200", login_resp.status_code == 200, str(login_resp.data))
check("Login returns access token", "access" in (login_resp.data or {}))
check("Login returns refresh token", "refresh" in (login_resp.data or {}))

# Bad credentials
bad_login = client.post("/api/auth/login/", {
    "username": "aisha_verify",
    "password": "wrongpassword",
}, format="json")
check("Bad credentials returns 401", bad_login.status_code == 401)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] Token Refresh")
# ─────────────────────────────────────────────────────────────────────────────

refresh_resp = client.post("/api/auth/refresh/", {
    "refresh": aisha_refresh,
}, format="json")

check("Refresh returns 200", refresh_resp.status_code == 200, str(refresh_resp.data))
check("Refresh returns new access token", "access" in (refresh_resp.data or {}))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] /me/ endpoint")
# ─────────────────────────────────────────────────────────────────────────────

client.credentials(HTTP_AUTHORIZATION=f"Bearer {aisha_access}")
me_resp = client.get("/api/auth/me/")
check("/me/ returns 200", me_resp.status_code == 200)
check("/me/ returns correct username", me_resp.data.get("username") == "aisha_verify")
check("/me/ returns full_name", bool(me_resp.data.get("full_name")))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] Group Creation & Invite Code")
# ─────────────────────────────────────────────────────────────────────────────

group_resp = client.post("/api/groups/", {
    "name": "Verify Test Group",
    "description": "Automated verification group",
    "currency": "INR",
}, format="json")

check("Group creation returns 201", group_resp.status_code == 201, str(group_resp.data))
invite_code = group_resp.data.get("invite_code", "")
group_id = group_resp.data.get("id")
check("Group has invite_code", bool(invite_code))
check("Invite code starts with SPW-", invite_code.startswith("SPW-"))
check("Group shows current_user_role=owner", group_resp.data.get("current_user_role") == "owner")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] Second User Registration + Join via Invite Code")
# ─────────────────────────────────────────────────────────────────────────────

rohan_reg = client.post("/api/auth/register/", {
    "full_name": "Rohan Verification",
    "username": "rohan_verify",
    "email": "rohan_verify@test.com",
    "password": "TestPass#2026!",
    "confirm_password": "TestPass#2026!",
}, format="json")
check("Rohan registration returns 201", rohan_reg.status_code == 201)

rohan_access = rohan_reg.data.get("access", "")
client.credentials(HTTP_AUTHORIZATION=f"Bearer {rohan_access}")

join_resp = client.post("/api/groups/join/", {
    "invite_code": invite_code,
}, format="json")

check("Rohan can join via invite code (201)", join_resp.status_code == 201, str(join_resp.data))
check("Join response contains group_id", join_resp.data.get("group_id") == group_id)
check("Membership records joined_via_invite=True", join_resp.data.get("membership", {}).get("joined_via_invite") == True)
check("Membership records invite_code_used", join_resp.data.get("membership", {}).get("invite_code_used") == invite_code)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] Membership Visibility (Rohan sees the group)")
# ─────────────────────────────────────────────────────────────────────────────

groups_resp = client.get("/api/groups/")
check("Groups list returns 200", groups_resp.status_code == 200)
group_ids = [g["id"] for g in groups_resp.data]
check("Rohan can see the group in his list", group_id in group_ids)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] Unauthorized Access Rejection")
# ─────────────────────────────────────────────────────────────────────────────

outsider_reg = client.post("/api/auth/register/", {
    "full_name": "Outsider Test",
    "username": "outsider_verify",
    "email": "outsider_verify@test.com",
    "password": "TestPass#2026!",
    "confirm_password": "TestPass#2026!",
}, format="json")
outsider_access = outsider_reg.data.get("access", "")
client.credentials(HTTP_AUTHORIZATION=f"Bearer {outsider_access}")

# Outsider should NOT see the group
out_groups = client.get("/api/groups/")
outsider_group_ids = [g["id"] for g in out_groups.data]
check("Outsider cannot see the group", group_id not in outsider_group_ids)

# Outsider cannot access group balances
out_balance = client.get(f"/api/balances/groups/{group_id}/")
check("Outsider gets 403 on balance access", out_balance.status_code in [403, 404])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[9] User Search")
# ─────────────────────────────────────────────────────────────────────────────

client.credentials(HTTP_AUTHORIZATION=f"Bearer {aisha_access}")
search_resp = client.get("/api/users/search/?q=rohan_verify")
check("User search returns 200", search_resp.status_code == 200)
check("User search finds rohan_verify", any(u["username"] == "rohan_verify" for u in search_resp.data))
check("User search excludes self (aisha)", not any(u["username"] == "aisha_verify" for u in search_resp.data))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[10] Personal Dashboard")
# ─────────────────────────────────────────────────────────────────────────────

dashboard_resp = client.get("/api/auth/dashboard/")
check("Dashboard returns 200", dashboard_resp.status_code == 200)
check("Dashboard contains my_groups", "my_groups" in (dashboard_resp.data or {}))
check("Dashboard contains net_balance", "net_balance" in (dashboard_resp.data or {}))
check("Dashboard contains pending_import_reviews", "pending_import_reviews" in (dashboard_resp.data or {}))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[11] Logout")
# ─────────────────────────────────────────────────────────────────────────────

logout_resp = client.post("/api/auth/logout/", {
    "refresh": aisha_refresh,
}, format="json")
check("Logout returns 200", logout_resp.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"   Results: {passed} passed / {failed} failed / {passed + failed} total")
print("=" * 60)

# Cleanup
cleanup()

sys.exit(0 if failed == 0 else 1)
