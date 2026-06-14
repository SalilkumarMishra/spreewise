from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from imports.models import ImportJob, ImportAnomaly, ImportDecision
from imports.serializers import (
    ImportJobSerializer, ImportAnomalySerializer,
    ImportDecisionSerializer, ImportDecisionInputSerializer, ImportReportSerializer
)
from imports.services.import_processor import process_import_job, resume_import_after_decisions
from groups.models import Group

class ImportJobViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """GET /api/imports/ — list all jobs for the current user."""
        jobs = ImportJob.objects.filter(uploaded_by=request.user).order_by("-created_at")
        return Response(ImportJobSerializer(jobs, many=True).data)

    def retrieve(self, request, pk=None):
        """GET /api/imports/{id}/ — get a job's details."""
        job = get_object_or_404(ImportJob, pk=pk, uploaded_by=request.user)
        return Response(ImportJobSerializer(job).data)

    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request):
        """
        POST /api/imports/upload/
        Expected: multipart/form-data with fields:
          - file: CSV file
          - group_id: integer
        Requires: owner or admin role in the group.
        """
        from groups.models import GroupMembership
        from rest_framework.exceptions import PermissionDenied

        file_obj = request.FILES.get("file")
        group_id = request.data.get("group_id")

        if not file_obj:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        if not group_id:
            return Response({"error": "group_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        group = get_object_or_404(Group, id=group_id)

        # Only group owners and admins can upload CSVs
        membership = GroupMembership.objects.filter(
            group=group, user=request.user, is_active=True
        ).first()
        if not membership:
            raise PermissionDenied("You are not a member of this group.")
        if membership.role not in ["owner", "admin"]:
            raise PermissionDenied("Only group owners and admins can upload CSV files.")

        import_job = ImportJob.objects.create(
            group=group,
            uploaded_by=request.user,
            original_filename=file_obj.name,
            status="pending",
        )

        csv_content = file_obj.read()
        process_import_job(import_job, csv_content, group, request.user)

        return Response(ImportJobSerializer(import_job).data, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=["get"], url_path="anomalies")
    def anomalies(self, request, pk=None):
        """GET /api/imports/{id}/anomalies/ — list all anomalies for a job."""
        job = get_object_or_404(ImportJob, pk=pk, uploaded_by=request.user)
        anomalies = job.anomalies.select_related("import_row").order_by("import_row__row_number")
        return Response(ImportAnomalySerializer(anomalies, many=True).data)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        """GET /api/imports/{id}/report/ — get the import report."""
        job = get_object_or_404(ImportJob, pk=pk, uploaded_by=request.user)
        if not hasattr(job, "report"):
            return Response({"error": "Report not yet generated."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ImportReportSerializer(job.report).data)


class ImportAnomalyDecisionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, pk=None):
        """
        POST /api/imports/anomalies/{id}/decision/
        Body: { "decision": "approve"|"reject"|"ignore", "decision_reason": "..." }
        """
        anomaly = get_object_or_404(ImportAnomaly, pk=pk)
        serializer = ImportDecisionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        decision_value = serializer.validated_data["decision"]
        reason = serializer.validated_data.get("decision_reason", "")

        # Record the decision
        decision_obj, _ = ImportDecision.objects.update_or_create(
            anomaly=anomaly,
            defaults={
                "decision": decision_value,
                "decided_by": request.user,
                "decision_reason": reason,
            }
        )

        # Update anomaly user_decision
        anomaly.user_decision = decision_value
        anomaly.save(update_fields=["user_decision"])

        # If approved: mark row as pending so it gets processed
        if decision_value == "approve":
            import_row = anomaly.import_row
            # Only re-queue if no remaining REJECT anomalies on this row
            remaining_rejects = import_row.anomalies.filter(
                detected_action="REJECT",
                user_decision__isnull=True,
            ).count()
            if remaining_rejects == 0:
                import_row.processing_status = "pending"
                import_row.save(update_fields=["processing_status"])

        elif decision_value == "reject":
            anomaly.import_row.processing_status = "skipped"
            anomaly.import_row.save(update_fields=["processing_status"])

        # Check if all review anomalies for this job are now decided
        import_job = anomaly.import_job
        undecided = import_job.anomalies.filter(
            detected_action="REVIEW_REQUIRED",
            user_decision__isnull=True,
        ).count()

        if undecided == 0 and import_job.status == "review_required":
            # All decisions made — resume processing
            resume_import_after_decisions(import_job, import_job.group, request.user)

        return Response(ImportDecisionSerializer(decision_obj).data, status=status.HTTP_200_OK)
