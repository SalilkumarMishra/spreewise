# Spreewise: Local Manual Testing Guide

This guide provides step-by-step instructions to run, test, and verify the Spreewise shared-expense application locally.

---

## 1. Local Environment Configuration

- **Backend API Base URL**: `http://127.0.0.1:8000` (pointing to the Django application server)
- **Django Admin Portal**: `http://127.0.0.1:8000/admin`
- **Frontend App URL**: `http://localhost:5173` (pointing to the Vite development server)

---

## 2. Test Accounts Setup

Since Spreewise uses the default Django user database, you can create test accounts via the Django administrative shell.

### 2.1 Create an Administrator Account
Run the createsuperuser command in your terminal inside the `shared-expense-app/backend/` directory:
```bash
# Ensure virtual environment is active:
# CMD: venv\Scripts\activate.bat
# PowerShell: venv\Scripts\Activate.ps1
# Unix: source venv/bin/activate

python manage.py createsuperuser
```
Follow the prompts to configure an admin account:
- **Username**: `admin`
- **Password**: `password123` (or any password)

### 2.2 Create Standard Test Users
To test multi-user group transactions, run the following script in the Django python shell:
```bash
python manage.py shell
```
Inside the interactive Python console, paste the following code:
```python
from django.contrib.auth import get_user_model
User = get_user_model()

# Create standard test users
users = [
    ("aisha", "password123"),
    ("rohan", "password123"),
    ("priya", "password123"),
    ("sam", "password123")
]

for username, pwd in users:
    if not User.objects.filter(username=username).exists():
        User.objects.create_user(username=username, password=pwd)
        print(f"Created user: {username}")
    else:
        print(f"User {username} already exists.")
```
Exit the shell: `exit()`.

> [!TIP]
> **Checking User DB IDs:**
> The frontend requires adding group members by their primary key database ID. Since IDs depend on the order of database record creation, run this command to find the correct User IDs:
> ```bash
> python manage.py shell -c "from django.contrib.auth import get_user_model; print([(u.id, u.username) for u in get_user_model().objects.all()])"
> ```
> This outputs a list like `[(1, 'salilmishra'), (2, 'aisha'), (9, 'rohan'), (10, 'priya')]`. Use these printed IDs in the steps below.

---

## 3. Step-by-Step Manual Test Workflows

### 3.1 Login & Session Verification
1. Access the frontend app at `http://localhost:5173/login`.
2. Input credentials:
   - **Username**: `aisha`
   - **Password**: `password123`
3. Click **Login**. Upon success, you are redirected to the main Dashboard.
4. Refresh the page to verify that the session persists (using cached `sessionStorage` token data).
5. Click **Logout** in the navigation bar to ensure that the token is deleted and you are redirected back to the login screen.

### 3.2 Group Management
1. Log in as `aisha`.
2. Navigate to **Groups** in the sidebar.
3. Click the **Create Group** button.
4. Input details:
   - **Group Name**: `Apartment 4B`
   - **Description**: `Shared expenses for Rohan, Aisha, and Priya`
   - **Base Currency**: `INR`
5. Submit the form. Verify that the group is listed and that click-through navigates to the group details page.
6. Verify archiving: On the Groups list page, click the **Archive** button on a group. The group should be soft-deleted (hidden from the active groups view).

### 3.3 Member Lifecycle Management
1. Log in as `aisha` and open the `Apartment 4B` group details page.
2. Select the **Members** tab.
3. Verify that `aisha` is listed as the `Owner` with a join date of today.
4. Click **Add Member**.
5. Input:
   - **User DB ID**: `[Rohan's User ID from Step 2.2]`
   - **Join Date**: `2026-02-01`
6. Submit. Verify `rohan` is now listed as `Active`.
7. Repeat the process to add **priya** (using Priya's User ID from Step 2.2) with a join date of `2026-02-01`.
8. **Test Leave workflow**: Click **Set Leave** next to `priya`. Input `2026-06-01` as the departure date and confirm. Verify her status changes to `Inactive` and her leave date is displayed.
9. **Test Rejoin workflow**: Click **Rejoin** next to `priya`. Verify she is reactivated with a new membership window.

### 3.4 Expense Creation (All Split Types)
Navigate to the **Expenses** tab of your group and click **New Expense** to verify each split option.

#### A. Equal Split
- **Title**: `Weekly Groceries`
- **Amount**: `1500.00`
- **Category**: `Groceries`
- **Paid By**: `aisha`
- **Date**: `2026-02-15`
- **Participants**: Select `aisha` and `rohan`.
- **Split Type**: Select `Equal split`.
- **Expected Result**: Aisha and Rohan each owe `700.00`. Since Aisha paid, Rohan has an outstanding debit of `750.00` to Aisha.

#### B. Percentage Split
- **Title**: `Electricity Bill`
- **Amount**: `3000.00`
- **Category**: `Utilities`
- **Paid By**: `aisha`
- **Date**: `2026-03-01`
- **Participants**: Select `aisha` and `rohan`.
- **Split Type**: Select `Percentage shares`.
- **Splits Details**:
  - `aisha`: `60` %
  - `rohan`: `40` %
- **Expected Result**: Aisha's share is `1800.00`, Rohan's share is `1200.00`. Rohan owes Aisha `1200.00`.

#### C. Shares Split
- **Title**: `Dinner Outing`
- **Amount**: `1200.00`
- **Category**: `Food`
- **Paid By**: `rohan`
- **Date**: `2026-04-10`
- **Participants**: Select `aisha` and `rohan`.
- **Split Type**: Select `Shares weight`.
- **Splits Details**:
  - `aisha`: `2` shares
  - `rohan`: `1` share
- **Expected Result**: Total shares = 3. Aisha owes `800.00` (2 shares), Rohan owes `400.00` (1 share). Aisha owes Rohan `800.00`.

#### D. Exact Split
- **Title**: `Concert Tickets`
- **Amount**: `2000.00`
- **Category**: `Entertainment`
- **Paid By**: `aisha`
- **Date**: `2026-05-05`
- **Participants**: Select `aisha` and `rohan`.
- **Split Type**: Select `Exact amounts`.
- **Splits Details**:
  - `aisha`: `1400.00` INR
  - `rohan`: `600.00` INR
- **Expected Result**: Aisha's share is `1400.00`, Rohan's share is `600.00`. Rohan owes Aisha `600.00`.

*Note: Verify that editing an expense updates the splits and adds a versioned audit trail card in the expense's **Audits** modal.*

---

### 3.5 Settlement Recording
1. Click **Record Settlement** from the header or settlements tab.
2. Input details:
   - **From (Payer)**: `rohan`
   - **To (Receiver)**: `aisha`
   - **Amount**: `500.00`
   - **Payment Date**: `2026-05-15`
   - **Category**: `Cash`
3. Click **Record Settlement**. Verify it shows in the Settlements log with an autogenerated ID (e.g. `SET-2026-000001`).

---

### 3.6 Balance Engine Verification
Open the **Balances** tab on the Group Details page. Verify that:
- **Net Position**: Displays each member's final balance relative to the group (positive balances in green, negative balances in red). Sum of all balances must equal `0.00`.
- **Simplified Payback Instructions**: Displays optimized payback paths (e.g., *Rohan owes Aisha 2,050.00 INR*).
- **Ledger Trace (Rohan's Request)**: Go to the **Trace** tab. Select `rohan` from the dropdown list. Review the chronological step-by-step history showing how each expense/settlement modified his running balance.

---

### 3.7 CSV Ingestion & Anomaly Review
1. Go to the **CSV Imports** page via the sidebar navigation.
2. Click **Upload CSV** and select a file (you can use the sample [expenses_export.csv](file:///c:/Users/salil/OneDrive/Desktop/spreewise/shared-expense-app/expenses_export.csv) located in your workspace).
3. Select the target group `Apartment 4B` and click **Upload**.
4. If the CSV contains review anomalies (e.g., duplicates, possible settlements, or foreign currencies), the status will change to **Review Required**.
5. Click on the import job to open the anomaly review queue.
6. For each anomaly:
   - Read the description and click **Resolve**.
   - Select a decision (**Approve**, **Reject**, or **Ignore**) and input a reason for the audit trail.
7. Once all anomalies are resolved, verify that the status changes to **Completed** and review the generated **Import Report** summarizing the rows processed.
