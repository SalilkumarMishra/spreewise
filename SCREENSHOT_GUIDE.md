# SCREENSHOT_GUIDE.md — Required Screenshots for Submission

> Guide to the 12 screenshots required for the Spreewise submission package. For each screen, this document explains what to capture and why it matters.

---

## How to Take Screenshots

1. Ensure both servers are running:
   - Backend: `python manage.py runserver` → http://127.0.0.1:8000
   - Frontend: `npm run dev` → http://localhost:5173

2. Use a browser with a viewport of at least 1280×800 for consistent layout.

3. Name files clearly: `01_login.png`, `02_signup.png`, etc.

4. Store screenshots in: `/docs/screenshots/`

---

## Screenshot 1 — Login Page

**URL:** `http://localhost:5173/login`

**What to capture:**
- The full login form with Spreewise branding (logo + title)
- "Create an account" and "Have an invite code?" links at the bottom

**Why it matters:**
Demonstrates the JWT authentication entry point. Shows the professional design of the auth flow and the links to signup and join-group — demonstrating a complete multi-user onboarding experience.

**Tips:**
- Do NOT be logged in when capturing — you must be on the login screen
- Enter a username in the field to show the form is functional

---

## Screenshot 2 — Signup Page

**URL:** `http://localhost:5173/signup`

**What to capture:**
- The full registration form showing all fields: Full Name, Username, Email, Password, Confirm Password
- The "Back to Login" link

**Why it matters:**
Demonstrates self-service user registration — a core requirement of the multi-user SaaS upgrade. Shows that new users don't need admin intervention to get started.

**Tips:**
- Fill in all fields before screenshotting to show the form in use

---

## Screenshot 3 — Dashboard

**URL:** `http://localhost:5173/dashboard`

**What to capture:**
- The "My Overview" section at the top: You Owe / You Are Owed / Net Balance cards
- The group expense timeline chart (bar chart)
- The category breakdown pie chart
- The member net balances table at the bottom

**Why it matters:**
The dashboard is the most comprehensive view of the system. It shows personalized cross-group balance data, visual analytics, and demonstrates the full balance engine integration.

**Tips:**
- Ensure there is data in the system (at least 3-4 expenses) so the charts render
- Select a group with data in the active group dropdown at the top

---

## Screenshot 4 — Group Detail with Members

**URL:** `http://localhost:5173/groups/{id}`

**What to capture:**
- Group name, currency, and invite code (`SPW-XXXXXXXX`)
- The member list showing at least 2 members
- Role badges (OWNER, ADMIN, MEMBER)
- Membership join/leave dates

**Why it matters:**
Shows the invite code system, role-based membership model, and historical membership lifecycle — all of which are key architectural decisions.

**Tips:**
- Hover over the invite code copy button to show the interaction
- If possible, show a member with a `left_at` date to demonstrate the lifecycle

---

## Screenshot 5 — Expense Creation

**URL:** `http://localhost:5173/groups/{id}` — "Add Expense" modal/form

**What to capture:**
- The expense creation form with fields: title, amount, date, paid by, split type
- Split type selector showing options: Equal / Percentage / Shares / Exact
- At least one split type (e.g., Percentage) with the split breakdown inputs visible

**Why it matters:**
Demonstrates the flexibility of the expense engine. The 4 split types are a key differentiator of Spreewise's implementation.

**Tips:**
- Capture the Percentage split type specifically, as it shows the most complex form
- Fill in realistic values (e.g., "Electricity Bill", ₹3,000, 3 participants)

---

## Screenshot 6 — Settlement Creation

**URL:** Settlement creation form

**What to capture:**
- Settlement form with: Payer, Receiver, Amount, Date, Category (UPI/Cash/Bank Transfer)
- A realistic settlement (e.g., "Rohan paid Aisha ₹1,500 via UPI")

**Why it matters:**
Demonstrates the separate settlement model — a deliberate architectural decision (ADR-05). Shows that debt repayments are tracked distinctly from shared expenses, which is critical for correct balance computation.

---

## Screenshot 7 — Balances View

**URL:** Balances tab for a group

**What to capture:**
- The net balance table: each member's name, net position (green for positive, red for negative)
- Status badges: Lent / Owes / Settled

**Why it matters:**
The balance engine is the core value proposition of Spreewise. Showing accurate net positions for a group with multiple expenses and settlements demonstrates the engine works correctly.

**Tips:**
- Ensure the data shows both positive and negative balances (someone lent, someone owes)

---

## Screenshot 8 — Debt Simplification

**URL:** Balances → "Simplified Payments" or debt simplification view

**What to capture:**
- The minimum payment graph: "Rohan → Aisha: ₹500", "Dev → Priya: ₹300"
- The number of simplified transactions vs. the total number of balances

**Why it matters:**
The greedy debt simplification algorithm is a key technical feature. Showing that 5 people with complex debts can be settled with just 3 payments demonstrates the practical value.

**Tips:**
- Set up a 4-5 person group with multiple expenses before this screenshot

---

## Screenshot 9 — CSV Upload

**URL:** `http://localhost:5173/imports`

**What to capture:**
- The CSV upload interface showing file selection, group selection
- The "Upload" button
- If possible: an in-progress upload or the results immediately after upload

**Why it matters:**
The CSV import pipeline is the most complex feature of the system. Showing the entry point and upload flow demonstrates the full import lifecycle.

---

## Screenshot 10 — Anomaly Review Queue

**URL:** `http://localhost:5173/imports/{id}` — review queue tab

**What to capture:**
- A list of anomalies with: row number, anomaly type, severity badge, description
- Approve / Reject buttons for each anomaly
- At least 2-3 different anomaly types visible (e.g., `duplicate_expense`, `unknown_user`, `settlement_logged_as_expense`)

**Why it matters:**
The anomaly review workflow is the most sophisticated part of the import pipeline. It demonstrates the three-tier policy system (AUTO_FIX / REVIEW_REQUIRED / REJECT) and the human-in-the-loop design decision.

**Tips:**
- Upload the provided `expenses_export.csv` file to get a rich set of anomalies
- Do not resolve any anomalies before screenshotting — capture the full review queue

---

## Screenshot 11 — Import Report

**URL:** `http://localhost:5173/imports/{id}` — report tab

**What to capture:**
- The import report showing: Total Rows / Imported / Skipped / Failed / Anomaly Count
- If available: a breakdown of anomaly types detected
- The "completed" status badge

**Why it matters:**
The import report is the final output of the CSV pipeline. It demonstrates that the system tracks the complete lifecycle from upload → parsing → anomaly review → commit → report.

---

## Screenshot 12 — Invite Code Join

**URL:** `http://localhost:5173/join-group`

**What to capture:**
- The join page showing the invite code input field with placeholder `SPW-AB12CD34`
- A code entered in the field (e.g., paste a real group's code)
- Optionally: the success state showing "You've joined the group!" with the group name

**Why it matters:**
The invite code system is a key feature of the JWT upgrade. Showing the join flow end-to-end demonstrates the full user onboarding experience — from signup → join group → immediately see data.

---

## Bonus Screenshots (Optional but Recommended)

### Sidebar with Role Badge
Capture the left sidebar showing:
- User avatar with initials
- Username and role badge (e.g., "OWNER")
- Navigation items: Dashboard, Groups, CSV Imports, Join Group

### Mobile Responsiveness
If the layout is responsive, capture on a narrower viewport (768px) to show adaptability.
