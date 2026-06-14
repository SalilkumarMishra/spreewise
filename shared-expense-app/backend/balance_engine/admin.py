from django.contrib import admin
from balance_engine.models import BalanceSnapshot

@admin.register(BalanceSnapshot)
class BalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ["group", "snapshot_date", "created_at"]
    list_filter = ["group"]
    search_fields = ["group__name"]
    ordering = ["-snapshot_date"]
    readonly_fields = ["group", "snapshot_date", "payload_json", "created_at"]
