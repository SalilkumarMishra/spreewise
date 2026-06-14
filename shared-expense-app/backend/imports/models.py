from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ImportJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("review_required", "Review Required"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="import_jobs", null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Import {self.id} ({self.original_filename})"

class ImportRow(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("imported", "Imported"),
        ("skipped", "Skipped"),
        ("review_required", "Review Required"),
        ("failed", "Failed"),
    ]

    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="rows")
    row_number = models.IntegerField()
    raw_data = models.JSONField(help_text="Raw CSV row as dictionary")
    parsed_data = models.JSONField(null=True, blank=True, help_text="Structured representation after parsing")
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

class ImportAnomaly(models.Model):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    
    CATEGORY_CHOICES = [
        ("duplicate", "Duplicate"),
        ("membership", "Membership"),
        ("currency", "Currency"),
        ("date", "Date"),
        ("settlement", "Settlement"),
        ("split", "Split"),
        ("validation", "Validation"),
        ("unknown_user", "Unknown User"),
    ]

    import_job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="anomalies")
    import_row = models.ForeignKey(ImportRow, on_delete=models.CASCADE, related_name="anomalies")
    anomaly_type = models.CharField(max_length=50)
    anomaly_category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="validation")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    detected_action = models.CharField(max_length=50, help_text="Action suggested by policy (e.g. AUTO_FIX, REVIEW_REQUIRED, REJECT)")
    user_decision = models.CharField(max_length=20, null=True, blank=True, help_text="approve, reject, ignore")
    created_at = models.DateTimeField(auto_now_add=True)

class ImportDecision(models.Model):
    DECISION_CHOICES = [
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("ignore", "Ignore"),
    ]
    
    anomaly = models.OneToOneField(ImportAnomaly, on_delete=models.CASCADE, related_name="decision_record")
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ImportReport(models.Model):
    import_job = models.OneToOneField(ImportJob, on_delete=models.CASCADE, related_name="report")
    total_rows = models.IntegerField(default=0)
    imported_rows = models.IntegerField(default=0)
    skipped_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    anomaly_count = models.IntegerField(default=0)
    report_json = models.JSONField(default=dict)
