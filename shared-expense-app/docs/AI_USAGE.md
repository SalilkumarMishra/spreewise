# AI_USAGE.md — Spreewise AI Assistant Usage Log

This document details how the AI coding assistant was utilized during the development of Spreewise, along with specific examples of errors encountered and their corrections.

---

## 1. AI Tool and Scope of Use

- **AI Tool Used**: **Antigravity**
- **Primary Tasks**:
  - **Architecture Generation**: Outlining ledger structures, greedy debt simplification paths, and anomaly-detection models.
  - **Boilerplate Generation**: Drafting models, Django REST Framework viewsets, and serialisers.
  - **API Scaffolding**: Mapping URL endpoints and setting permission validations.

---

## 2. Examples of Incorrect AI Output & Corrections

During development, the AI generated code containing logic issues or missing validations. These were identified during review and corrected as follows:

### Example 1: Settlement Sign Convention Bug
- **Problem**:
  In early drafts, the AI treated settlements (payments between users) under the same sign convention as shared expenses. It suggested that a settlement from Aisha to Rohan should add a negative delta to Aisha and a positive delta to Rohan. However, because settlements *reduce* existing debt, this convention actually caused net group obligations to balloon instead of moving towards zero.
- **Correction**:
  Adjusted the normalized ledger delta calculation in [settlements/services/settlement_service.py](file:///c:/Users/salil/OneDrive/Desktop/spreewise/shared-expense-app/backend/settlements/services/settlement_service.py#L221-L241). Settlements must reduce debt: when a debtor pays, their balance moves closer to zero (increasing a negative balance), and the creditor's balance moves closer to zero (reducing a positive balance).

---

### Example 2: Missing Membership Eligibility Validation
- **Problem**:
  The AI generated code for expense creation and CSV import row creation that allowed expenses to be logged without checking if the users were active members of the group on the transaction date. This would allow a user to participate in an expense logged on a date before they joined the group or after they left.
- **Correction**:
  Introduced the shared `validate_membership_eligibility` function in [expenses/services/expense_service.py](file:///c:/Users/salil/OneDrive/Desktop/spreewise/shared-expense-app/backend/expenses/services/expense_service.py#L20-L47). This validates both the payer and all participants against the group membership dates using the membership's `is_member_on_date()` method before creating any transaction record.

---

### Example 3: Missing Audit Trail for Imports
- **Problem**:
  During CSV Import Engine scaffolding, the AI suggested automatically dropping duplicate rows or silently auto-converting currency values during ingestion to make the pipeline run without interruption. This violated the requirement that all actions must be auditable, leaving no trace of what was skipped or why.
- **Correction**:
  Removed the automatic dropping logic and implemented an interactive review queue. Flagged anomalies are written as `ImportAnomaly` records, and the job status is set to `review_required`. Users must explicitly submit decisions via `POST /api/imports/anomalies/{id}/decision/`, which are logged in the database under `ImportDecision` for audit tracking.
