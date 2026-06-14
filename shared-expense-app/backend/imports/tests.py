from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from groups.models import Group, GroupMembership
from expenses.models import Expense
from settlements.models import Settlement
from imports.models import ImportJob, ImportRow, ImportAnomaly, ImportDecision, ImportReport
from imports.services.import_processor import process_import_job
from expenses.services.expense_service import create_expense
from decimal import Decimal
import datetime

User = get_user_model()

class ImportEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create users
        self.u1 = User.objects.create_user(username="aisha", password="password123")
        self.u2 = User.objects.create_user(username="rohan", password="password123")
        
        # Authenticate
        self.client.force_authenticate(user=self.u1)

        # Create group
        self.group = Group.objects.create(
            name="Apartment 4B",
            currency="INR",
            created_by=self.u1
        )
        
        # Setup memberships active from Feb 1st 2026
        self.m1 = GroupMembership.objects.create(
            group=self.group,
            user=self.u1,
            joined_at=datetime.date(2026, 2, 1),
            is_active=True,
            role="owner"
        )
        self.m2 = GroupMembership.objects.create(
            group=self.group,
            user=self.u2,
            joined_at=datetime.date(2026, 2, 1),
            is_active=True,
            role="member"
        )

    def test_import_decision_creation_and_requeue(self):
        """Test that POST /api/imports/anomalies/{id}/decision/ creates an ImportDecision and updates state."""
        # Create an import job
        job = ImportJob.objects.create(
            group=self.group,
            uploaded_by=self.u1,
            original_filename="test.csv",
            status="review_required"
        )
        # Create a row with a review required anomaly
        row = ImportRow.objects.create(
            import_job=job,
            row_number=2,
            raw_data={"date": "2026-02-05", "description": "Pizza Party", "payer": "aisha", "amount": "1200", "currency": "INR", "participants": "aisha,rohan", "split_type": "equal"},
            parsed_data={"date": "2026-02-05", "description": "Pizza Party", "payer": "aisha", "amount": "1200", "currency": "INR", "participants": ["aisha", "rohan"], "split_type": "equal"},
            processing_status="review_required"
        )
        anomaly = ImportAnomaly.objects.create(
            import_job=job,
            import_row=row,
            anomaly_type="duplicate_expense",
            anomaly_category="duplicate",
            severity="high",
            description="Duplicate expense detected",
            detected_action="REVIEW_REQUIRED"
        )

        url = f"/api/imports/anomalies/{anomaly.id}/decision/"
        payload = {
            "decision": "approve",
            "decision_reason": "It was indeed a separate dinner"
        }
        
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify ImportDecision was created
        decision = ImportDecision.objects.filter(anomaly=anomaly).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.decision, "approve")
        self.assertEqual(decision.decided_by, self.u1)
        self.assertEqual(decision.decision_reason, "It was indeed a separate dinner")
        
        # Verify anomaly is updated
        anomaly.refresh_from_db()
        self.assertEqual(anomaly.user_decision, "approve")

        # Verify job is resumed and completed, and expense is created
        row.refresh_from_db()
        self.assertEqual(row.processing_status, "imported")
        
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

        # Verify expense linked to import job
        expense = Expense.objects.filter(group=self.group, import_job=job).first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal("1200.00"))
        self.assertEqual(expense.import_job, job)

    def test_expense_and_settlement_import_linkage(self):
        """Test that imported expenses and settlements have the import_job FK set."""
        # 1. Test clean import with no anomalies
        csv_data = (
            "date,description,payer,amount,currency,participants,split_type\n"
            "2026-02-05,Groceries,aisha,1500,INR,\"aisha,rohan\",equal\n"
        )
        
        job = ImportJob.objects.create(
            group=self.group,
            uploaded_by=self.u1,
            original_filename="clean.csv"
        )
        process_import_job(job, csv_data.encode("utf-8"), self.group, self.u1)
        
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        
        expense = Expense.objects.filter(group=self.group, title="Groceries").first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.import_job, job)

        # 2. Test settlement row (needs review)
        csv_settlement_data = (
            "date,description,payer,amount,currency,participants,split_type\n"
            "2026-02-10,Rohan paid back Aisha,rohan,500,INR,aisha,equal\n"
        )
        
        job2 = ImportJob.objects.create(
            group=self.group,
            uploaded_by=self.u1,
            original_filename="settlement.csv"
        )
        process_import_job(job2, csv_settlement_data.encode("utf-8"), self.group, self.u1)
        
        job2.refresh_from_db()
        self.assertEqual(job2.status, "review_required")
        
        # Get the settlement anomaly
        anomaly = job2.anomalies.filter(anomaly_type="settlement_logged_as_expense").first()
        self.assertIsNotNone(anomaly)
        
        # Approve the decision to treat as settlement
        url = f"/api/imports/anomalies/{anomaly.id}/decision/"
        response = self.client.post(url, {"decision": "approve", "decision_reason": "Confirmed settlement"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job2.refresh_from_db()
        self.assertEqual(job2.status, "completed")
        
        # Verify Settlement created and linked
        settlement = Settlement.objects.filter(group=self.group, import_job=job2).first()
        self.assertIsNotNone(settlement)
        self.assertEqual(settlement.amount, Decimal("500.00"))
        self.assertEqual(settlement.payer, self.u2)
        self.assertEqual(settlement.receiver, self.u1)
        self.assertEqual(settlement.import_job, job2)

    def test_anomaly_category_aggregation_and_report_breakdown(self):
        """Test that anomalies are aggregated by category and correctly report breakdown counts."""
        # We will create a CSV containing various validation errors:
        # Row 1: Negative amount -> validation category (REJECT)
        # Row 2: Unknown payer -> unknown_user category (REJECT)
        # Row 3: Zero amount -> validation category (REVIEW_REQUIRED)
        # Row 4: Duplicate expense -> duplicate category (REVIEW_REQUIRED)
        
        # We need an existing expense to trigger a duplicate
        create_expense(
            group=self.group,
            title="Duplicate Dinner",
            amount=Decimal("1000.00"),
            currency="INR",
            expense_date=datetime.date(2026, 2, 8),
            paid_by=self.u1,
            split_type="equal",
            creator=self.u1,
            participant_users=[self.u1, self.u2]
        )
        
        csv_data = (
            "date,description,payer,amount,currency,participants,split_type\n"
            "2026-02-05,Negative cost,aisha,-200,INR,\"aisha,rohan\",equal\n"
            "2026-02-06,Unknown payer,ghost_user,500,INR,\"aisha,rohan\",equal\n"
            "2026-02-07,Zero cost,aisha,0,INR,\"aisha,rohan\",equal\n"
            "2026-02-08,Duplicate Dinner,aisha,1000,INR,\"aisha,rohan\",equal\n"
        )
        
        job = ImportJob.objects.create(
            group=self.group,
            uploaded_by=self.u1,
            original_filename="messy.csv"
        )
        process_import_job(job, csv_data.encode("utf-8"), self.group, self.u1)
        
        # Check detected anomalies and their categories
        anomalies = job.anomalies.all()
        # Anomaly types expected:
        # Negative amount -> 'negative_amount' (validation)
        # Unknown payer -> 'unknown_user' (unknown_user)
        # Zero amount -> 'zero_amount' (validation)
        # Duplicate expense -> 'duplicate_expense' (duplicate)
        
        categories = [a.anomaly_category for a in anomalies]
        self.assertIn("validation", categories)
        self.assertIn("unknown_user", categories)
        self.assertIn("duplicate", categories)
        
        # Check Report Breakdown
        report = ImportReport.objects.filter(import_job=job).first()
        self.assertIsNotNone(report)
        
        breakdown = report.report_json.get("anomaly_breakdown", {})
        
        # validation category should have negative_amount and zero_amount (total 2)
        self.assertEqual(breakdown.get("validation"), 2)
        # unknown_user category should have 1
        self.assertEqual(breakdown.get("unknown_user"), 1)
        # duplicate category should have 1
        self.assertEqual(breakdown.get("duplicate"), 1)
        
        # Total anomaly count
        self.assertEqual(report.anomaly_count, 4)
