from rest_framework import serializers
from imports.models import ImportJob, ImportRow, ImportAnomaly, ImportDecision, ImportReport

class ImportAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportAnomaly
        fields = [
            "id", "import_job", "import_row", "anomaly_type", "anomaly_category",
            "severity", "description", "detected_action", "user_decision", "created_at"
        ]
        read_only_fields = ["id", "created_at", "import_job", "import_row", "detected_action"]

class ImportDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportDecision
        fields = ["id", "anomaly", "decision", "decided_by", "decision_reason", "created_at"]
        read_only_fields = ["id", "created_at", "decided_by"]

class ImportRowSerializer(serializers.ModelSerializer):
    anomalies = ImportAnomalySerializer(many=True, read_only=True)

    class Meta:
        model = ImportRow
        fields = ["id", "row_number", "raw_data", "parsed_data", "processing_status", "anomalies"]

class ImportReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportReport
        fields = [
            "id", "import_job", "total_rows", "imported_rows", "skipped_rows",
            "failed_rows", "anomaly_count", "report_json"
        ]

class ImportJobSerializer(serializers.ModelSerializer):
    row_count = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = [
            "id", "group", "uploaded_by", "original_filename", "status",
            "created_at", "completed_at", "row_count"
        ]
        read_only_fields = ["id", "status", "created_at", "completed_at", "uploaded_by"]

    def get_row_count(self, obj):
        return obj.rows.count()

class ImportDecisionInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject", "ignore"])
    decision_reason = serializers.CharField(required=False, allow_blank=True, default="")
