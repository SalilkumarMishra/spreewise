"""
Report Service
==============
Generates ImportReport with enhanced breakdown by anomaly category.
"""
from django.db.models import Count
from imports.models import ImportReport, ImportAnomaly

def generate_report(import_job):
    """
    Generate or update an ImportReport for the given job.
    """
    rows = import_job.rows.all()
    total_rows     = rows.count()
    imported_rows  = rows.filter(processing_status="imported").count()
    skipped_rows   = rows.filter(processing_status="skipped").count()
    failed_rows    = rows.filter(processing_status="failed").count()
    review_rows    = rows.filter(processing_status="review_required").count()

    anomalies = import_job.anomalies.all()
    anomaly_count = anomalies.count()

    # Anomaly breakdown by category
    breakdown_qs = (
        anomalies
        .values("anomaly_category")
        .annotate(count=Count("id"))
    )
    anomaly_breakdown = {row["anomaly_category"]: row["count"] for row in breakdown_qs}

    report_json = {
        "total_rows": total_rows,
        "imported_rows": imported_rows,
        "skipped_rows": skipped_rows,
        "failed_rows": failed_rows,
        "review_required_rows": review_rows,
        "anomaly_count": anomaly_count,
        "anomaly_breakdown": anomaly_breakdown,
        "anomalies": [
            {
                "id": a.id,
                "row_number": a.import_row.row_number,
                "anomaly_type": a.anomaly_type,
                "anomaly_category": a.anomaly_category,
                "severity": a.severity,
                "description": a.description,
                "detected_action": a.detected_action,
                "user_decision": a.user_decision,
            }
            for a in anomalies.select_related("import_row")
        ],
    }

    report, _ = ImportReport.objects.update_or_create(
        import_job=import_job,
        defaults={
            "total_rows": total_rows,
            "imported_rows": imported_rows,
            "skipped_rows": skipped_rows,
            "failed_rows": failed_rows,
            "anomaly_count": anomaly_count,
            "report_json": report_json,
        }
    )
    return report
