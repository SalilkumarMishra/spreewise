from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Settlement(models.Model):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("csv_import", "CSV Import"),
        ("system", "System"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("disputed", "Disputed"),
        ("import_review", "Import Review"),
    ]
    CATEGORY_CHOICES = [
        ("direct_payment", "Direct Payment"),
        ("bank_transfer", "Bank Transfer"),
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("imported", "Imported")
    ]

    reference_id = models.CharField(max_length=50, unique=True)
    group = models.ForeignKey("groups.Group", on_delete=models.PROTECT, related_name="settlements")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="settlements_paid")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="settlements_received")

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")

    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    original_currency = models.CharField(max_length=10, default="INR")

    payment_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    settlement_category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="direct_payment")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_settlements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def delete(self, *args, **kwargs):
        self.is_archived = True
        self.save()

    def is_imported(self):
        return self.source == "csv_import"

    def is_manual(self):
        return self.source == "manual"

    def is_under_review(self):
        return self.status == "import_review"

    def is_disputed(self):
        return self.status == "disputed"

    def get_latest_snapshot(self):
        return self.snapshots.order_by("-version").first()

    def get_snapshot_history(self):
        return self.snapshots.order_by("version")

    def __str__(self):
        return f"{self.reference_id}: {self.payer.username} paid {self.receiver.username} {self.amount} {self.currency}"

class SettlementSnapshot(models.Model):
    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE, related_name="snapshots")
    version = models.IntegerField()
    payload_json = models.JSONField(help_text="Full snapshot: version, reference_id, and settlement details")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["version"]
        unique_together = [("settlement", "version")]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("SettlementSnapshots are immutable and cannot be modified once created.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Snapshot v{self.version} for {self.settlement.reference_id}"
