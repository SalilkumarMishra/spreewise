from django.contrib import admin
from expenses.models import Expense, ExpenseParticipant, ExpenseSplit, ExpenseSnapshot


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "title", "group", "amount", "currency",
        "paid_by", "expense_date", "split_type",
        "status", "expense_category", "source", "is_archived",
    ]
    list_filter = [
        "split_type", "status", "expense_category",
        "source", "is_archived", "currency", "expense_date",
    ]
    search_fields = ["title", "paid_by__username", "group__name"]
    ordering = ["-expense_date", "-created_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ExpenseParticipant)
class ExpenseParticipantAdmin(admin.ModelAdmin):
    list_display = ["expense", "user"]
    list_filter = ["expense__group"]
    search_fields = ["user__username", "expense__title"]


@admin.register(ExpenseSplit)
class ExpenseSplitAdmin(admin.ModelAdmin):
    list_display = [
        "expense", "user", "calculated_amount",
        "percentage_value", "shares_value", "exact_amount",
    ]
    list_filter = ["expense__split_type", "expense__group"]
    search_fields = ["user__username", "expense__title"]


@admin.register(ExpenseSnapshot)
class ExpenseSnapshotAdmin(admin.ModelAdmin):
    list_display = ["expense", "version", "created_at"]
    list_filter = ["expense__group"]
    search_fields = ["expense__title"]
    ordering = ["expense", "version"]
    readonly_fields = ["expense", "version", "payload_json", "created_at"]
