from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Group(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, default="INR")
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_groups"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        """Soft delete the group instead of hard deleting."""
        self.is_archived = True
        self.save()

    def is_user_member_on_date(self, user, check_date):
        """
        Helper method to check if a specific user was an active member
        of this group on a specific date.
        """
        return self.memberships.filter(
            user=user,
            joined_at__lte=check_date
        ).filter(
            models.Q(left_at__isnull=True) | models.Q(left_at__gte=check_date)
        ).exists()

    def __str__(self):
        return f"{self.name} ({'Archived' if self.is_archived else 'Active'})"


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="group_memberships"
    )
    joined_at = models.DateField()
    left_at = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="member"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Enforce that a user can have at most one active membership in a group
            models.UniqueConstraint(
                fields=["group", "user"],
                condition=models.Q(is_active=True),
                name="unique_active_group_membership"
            )
        ]
        ordering = ["joined_at", "created_at"]

    def clean(self):
        super().clean()
        # Business Rule: left_at must be >= joined_at
        if self.left_at and self.joined_at > self.left_at:
            raise ValidationError("joined_at date cannot be greater than left_at date.")
        
        # Business Rule: If left_at is set, is_active must be False
        if self.left_at:
            self.is_active = False

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_member_on_date(self, check_date):
        """
        Check if this membership was active on a given date.
        """
        if self.joined_at > check_date:
            return False
        if self.left_at and self.left_at < check_date:
            return False
        return True

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({self.role})"
