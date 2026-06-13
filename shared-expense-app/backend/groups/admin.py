from django.contrib import admin
from groups.models import Group, GroupMembership

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "currency", "is_archived", "created_at"]
    list_filter = ["is_archived", "currency", "created_at"]
    search_fields = ["name", "created_by__username"]
    ordering = ["-created_at"]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "joined_at", "left_at", "is_active", "role"]
    list_filter = ["is_active", "role", "group"]
    search_fields = ["user__username", "group__name"]
    ordering = ["group", "joined_at"]
