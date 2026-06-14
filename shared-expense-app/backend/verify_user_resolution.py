import os
import django
import sys

# Setup Django context
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from imports.services.user_resolver import resolve_user

User = get_user_model()

# Ensure base test users exist
test_usernames = ["aisha", "rohan", "priya", "sam", "dev"]
for uname in test_usernames:
    User.objects.get_or_create(username=uname)

# Test cases: (Input string, expected username, expected strategy)
test_cases = [
    ("Aisha", "aisha", "username_case_insensitive"),
    (" AISHA ", "aisha", "username_case_insensitive"),
    ("ROHAN", "rohan", "username_case_insensitive"),
    ("Priya", "priya", "username_case_insensitive"),
    ("Priya S", "priya", "prefix_match"),
    ("UnknownGuy", None, "failed"),
]

print("=== STARTING USER RESOLUTION TESTS ===")
all_passed = True

for raw_name, expected_username, expected_strategy in test_cases:
    resolved_user, strategy = resolve_user(raw_name)
    
    if expected_username is None:
        if resolved_user is None and strategy == expected_strategy:
            print(f"PASS: '{raw_name}' successfully failed resolution as expected (Strategy: {strategy})")
        else:
            print(f"FAIL: '{raw_name}' expected to fail, but got {resolved_user} (Strategy: {strategy})")
            all_passed = False
    else:
        if resolved_user and resolved_user.username == expected_username and strategy == expected_strategy:
            print(f"PASS: '{raw_name}' resolved to User ID={resolved_user.id} ({resolved_user.username}) via Strategy: {strategy}")
        else:
            actual_username = resolved_user.username if resolved_user else None
            print(f"FAIL: '{raw_name}' expected {expected_username} (via {expected_strategy}), but got {actual_username} (via {strategy})")
            all_passed = False

if all_passed:
    print("=== ALL USER RESOLUTION TESTS PASSED! ===")
    sys.exit(0)
else:
    print("=== SOME USER RESOLUTION TESTS FAILED! ===")
    sys.exit(1)
