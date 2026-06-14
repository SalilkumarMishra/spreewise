from django.contrib import admin
from settlements.models import Settlement, SettlementSnapshot

@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = [
        "reference_id", "group", "payer", "receiver", 
        "amount", "currency", "settlement_category", 
        "source", "status", "payment_date", "is_archived"
    ]
    list_filter = [
        "settlement_category", "source", "status", 
        "is_archived", "currency", "payment_date"
    ]
    search_fields = ["reference_id", "payer__username", "receiver__username", "group__name"]
    ordering = ["-payment_date", "-created_at"]
    readonly_fields = ["reference_id", "created_at", "updated_at"]

@admin.register(SettlementSnapshot)
class SettlementSnapshotAdmin(admin.ModelAdmin):
    list_display = ["settlement", "version", "created_at"]
    list_filter = ["settlement__group"]
    search_fields = ["settlement__reference_id"]
    ordering = ["settlement", "version"]
    readonly_fields = ["settlement", "version", "payload_json", "created_at"]
