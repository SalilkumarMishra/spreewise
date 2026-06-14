"""
run_all_audits.py
=================
Consolidated test runner executing:
  1. Django unit tests
  2. verify_jwt_auth.py suite
  3. verify_audit_enhancements.py suite
  4. Performance benchmarks (Group list, Expense list, Balance calculation, CSV import)
"""
import os
import sys
import time
import subprocess

backend_dir = os.path.dirname(os.path.abspath(__file__))

def run_script(name, args=[]):
    print(f"\n>>> Running {name}...")
    py_executable = sys.executable
    res = subprocess.run([py_executable, name] + args, cwd=backend_dir)
    return res.returncode == 0

def run_django_tests():
    print("\n>>> Running Django Core Unit Tests...")
    py_executable = sys.executable
    res = subprocess.run([py_executable, "manage.py", "test", "--verbosity=2"], cwd=backend_dir)
    return res.returncode == 0

def run_performance_benchmarks():
    print("\n" + "=" * 60)
    print("   Spreewise API Performance Benchmarks")
    print("=" * 60)
    
    # Setup django
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    from groups.models import Group, GroupMembership
    from expenses.models import Expense
    from django.db import connection, reset_queries
    import datetime

    User = get_user_model()
    # Ensure clean state
    test_user_username = "perf_test_user"
    
    def clean_perf_data():
        try:
            perf_users = User.objects.filter(username=test_user_username)
            for u in perf_users:
                # delete expenses
                Expense.objects.filter(created_by=u).delete()
                # delete memberships
                GroupMembership.objects.filter(group__created_by=u).delete()
                GroupMembership.objects.filter(user=u).delete()
                # delete groups
                Group.objects.filter(created_by=u).delete()
                u.delete()
        except Exception as e:
            print(f"Cleanup error: {e}")

    clean_perf_data()
    
    user = User.objects.create_user(username=test_user_username, password="PerfPass#2026!")
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token.access_token)}")
    
    # 1. Benchmark: Group list
    # Create 5 groups using client post to auto-create memberships
    for i in range(5):
        client.post("/api/groups/", {"name": f"Perf Group {i}", "currency": "INR"}, format="json")
    
    reset_queries()
    start_time = time.perf_counter()
    resp = client.get("/api/groups/")
    group_list_time = (time.perf_counter() - start_time) * 1000
    group_list_queries = len(connection.queries)
    print(f"  Group List (5 groups):")
    print(f"    - Response Time: {group_list_time:.2f} ms")
    print(f"    - DB Queries Executed: {group_list_queries}")
    
    # Get group ID
    group_id = resp.data[0]["id"]


    # 2. Benchmark: Expense list
    # Create 20 mock expenses
    for i in range(20):
        client.post("/api/expenses/", {
            "group_id": group_id,
            "title": f"Mock Expense {i}",
            "amount": "100.00",
            "expense_date": datetime.date.today().strftime("%Y-%m-%d"),
            "paid_by_id": user.id,
            "split_type": "equal",
            "participant_ids": [user.id]
        }, format="json")
        
    reset_queries()
    start_time = time.perf_counter()
    resp_exp = client.get(f"/api/expenses/?group_id={group_id}")
    expense_list_time = (time.perf_counter() - start_time) * 1000
    expense_list_queries = len(connection.queries)
    print(f"  Expense List (20 expenses):")
    print(f"    - Response Time: {expense_list_time:.2f} ms")
    print(f"    - DB Queries Executed: {expense_list_queries}")

    # 3. Benchmark: Balance Calculation
    reset_queries()
    start_time = time.perf_counter()
    resp_bal = client.get(f"/api/balances/groups/{group_id}/")
    balance_calc_time = (time.perf_counter() - start_time) * 1000
    balance_calc_queries = len(connection.queries)
    print(f"  Balance Engine Calculation:")
    print(f"    - Response Time: {balance_calc_time:.2f} ms")
    print(f"    - DB Queries Executed: {balance_calc_queries}")

    # 4. Benchmark: CSV Import Ingestion (Simulation)
    from imports.services.csv_parser import parse_csv
    from imports.models import ImportJob
    
    csv_data = (
        b"Date,Description,Payer,Amount,Currency,Split Type,Participants\n"
        b"2026-02-15,Weekly Groceries,aisha,1500.00,INR,equal,aisha,rohan\n"
        b"2026-03-01,Electricity Bill,aisha,3000.00,INR,percentage,aisha,rohan\n"
        b"2026-04-10,Dinner Outing,rohan,1200.00,INR,shares,aisha,rohan\n"
    )
    
    start_time = time.perf_counter()
    parsed_rows, parse_errors = parse_csv(csv_data)
    csv_parse_time = (time.perf_counter() - start_time) * 1000
    print(f"  CSV Parsing & Resolution (3 rows):")
    print(f"    - Response Time: {csv_parse_time:.2f} ms")
    
    # Cleanup
    clean_perf_data()
    print("=" * 60)
    print("Performance benchmarks completed.\n")

def main():
    success = True
    
    # Run django unit tests
    if not run_django_tests():
        success = False
        print("[FAIL] Django Unit Tests failed.")
    else:
        print("[PASS] Django Unit Tests completed successfully.")
        
    # Run JWT suite
    if not run_script("verify_jwt_auth.py"):
        success = False
        print("[FAIL] verify_jwt_auth.py suite failed.")
    else:
        print("[PASS] verify_jwt_auth.py suite completed successfully.")
        
    # Run boundary/abuse suite
    if not run_script("verify_audit_enhancements.py"):
        success = False
        print("[FAIL] verify_audit_enhancements.py suite failed.")
    else:
        print("[PASS] verify_audit_enhancements.py suite completed successfully.")
        
    # Run performance benchmarks
    run_performance_benchmarks()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
