from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Expense(models.Model):
    SPLIT_TYPE_CHOICES = [
        ("equal", "Equal"),
        ("percentage", "Percentage"),
        ("shares", "Shares"),
        ("exact", "Exact"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("disputed", "Disputed"),
        ("import_review", "Import Review"),
    ]
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("csv_import", "CSV Import"),
        ("system", "System"),
    ]
    CATEGORY_CHOICES = [
        ("food", "Food"),
        ("rent", "Rent"),
        ("utilities", "Utilities"),
        ("travel", "Travel"),
        ("groceries", "Groceries"),
        ("entertainment", "Entertainment"),
        ("settlement", "Settlement"),
        ("refund", "Refund"),
        ("general", "General"),
    ]

    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.PROTECT,
        related_name="expenses"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Recorded amounts (may be converted to group currency)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")

    # Original amounts as entered / imported (for audit / explainability)
    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    original_currency = models.CharField(max_length=10, default="INR")

    expense_category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="general"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="manual"
    )

    expense_date = models.DateField()
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paid_expenses"
    )
    split_type = models.CharField(
        max_length=20,
        choices=SPLIT_TYPE_CHOICES,
        default="equal"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_expenses"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def delete(self, *args, **kwargs):
        """Soft delete the expense instead of hard deleting."""
        self.is_archived = True
        self.save()

    # ------------------------------------------------------------------
    # Audit helper methods — used by Balance Engine, CSV Import, etc.
    # ------------------------------------------------------------------

    def is_imported(self):
        """Return True if this expense was created via CSV import."""
        return self.source == "csv_import"

    def is_manual(self):
        """Return True if this expense was manually entered by a user."""
        return self.source == "manual"

    def is_under_review(self):
        """Return True if this expense is pending import review."""
        return self.status == "import_review"

    def is_disputed(self):
        """Return True if this expense is flagged as disputed."""
        return self.status == "disputed"

    def get_latest_snapshot(self):
        """Return the most recent ExpenseSnapshot for this expense."""
        return self.snapshots.order_by("-version").first()

    def get_snapshot_history(self):
        """Return all ExpenseSnapshots ordered from oldest to newest."""
        return self.snapshots.order_by("version")

    def __str__(self):
        return f"{self.title} - {self.amount} {self.currency} on {self.expense_date}"


class ExpenseParticipant(models.Model):
    """Tracks which users participate in an expense."""
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expense_participations"
    )

    class Meta:
        unique_together = [("expense", "user")]

    def __str__(self):
        return f"{self.user.username} in '{self.expense.title}'"


class ExpenseSplit(models.Model):
    """
    Stores the original split values AND calculated amounts for each participant.
    Preserving original values (percentage, shares, exact) is critical for
    explainability: "Why do I owe ₹2300?" can be answered from this data.
    """
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="splits"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expense_splits"
    )

    # Original split input values (only one will be set based on split_type)
    percentage_value = models.DecimalField(
        max_digits=7, decimal_places=4,
        blank=True, null=True,
        help_text="Only for 'percentage' split type"
    )
    shares_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        blank=True, null=True,
        help_text="Only for 'shares' split type"
    )
    exact_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        blank=True, null=True,
        help_text="Only for 'exact' split type"
    )

    # Final computed share for this user
    calculated_amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = [("expense", "user")]

    def __str__(self):
        return f"{self.user.username} owes {self.calculated_amount} for '{self.expense.title}'"


class ExpenseSnapshot(models.Model):
    """
    Immutable audit snapshot of an expense at a point in time.
    Each create/update generates a new version snapshot.
    Supports explainability, audit, and historical balance calculations.
    """
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="snapshots"
    )
    version = models.IntegerField()
    payload_json = models.JSONField(
        help_text="Full snapshot: expense data, participants, and splits at this version"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["version"]
        unique_together = [("expense", "version")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("ExpenseSnapshots are immutable and cannot be modified once created.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Snapshot v{self.version} for '{self.expense.title}'"

