from django.contrib import admin
from imports.models import ImportJob, ImportRow, ImportAnomaly, ImportDecision, ImportReport

@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ["id", "original_filename", "group", "uploaded_by", "status", "created_at", "completed_at"]
    list_filter = ["status", "group"]
    search_fields = ["original_filename"]
    ordering = ["-created_at"]

@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ["id", "import_job", "row_number", "processing_status"]
    list_filter = ["processing_status"]
    ordering = ["import_job", "row_number"]

@admin.register(ImportAnomaly)
class ImportAnomalyAdmin(admin.ModelAdmin):
    list_display = ["id", "import_job", "import_row", "anomaly_type", "anomaly_category", "severity", "detected_action", "user_decision"]
    list_filter = ["severity", "detected_action", "anomaly_category", "user_decision"]
    search_fields = ["anomaly_type", "description"]
    ordering = ["-created_at"]

@admin.register(ImportDecision)
class ImportDecisionAdmin(admin.ModelAdmin):
    list_display = ["id", "anomaly", "decision", "decided_by", "created_at"]
    list_filter = ["decision"]
    ordering = ["-created_at"]

@admin.register(ImportReport)
class ImportReportAdmin(admin.ModelAdmin):
    list_display = ["id", "import_job", "total_rows", "imported_rows", "failed_rows", "anomaly_count"]
    ordering = ["-import_job"]
