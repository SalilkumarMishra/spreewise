from django.core.exceptions import ValidationError
from groups.models import GroupMembership, Group

def add_member(group, user, joined_at, role="member"):
    """
    Business logic for adding a user to a group.
    Ensures:
    1. Group is not archived.
    2. User does not already have an active membership in the group.
    3. The new join date is after any historical leave dates.
    """
    if group.is_archived:
        raise ValidationError("Cannot add members to an archived group.")

    # Check for active membership
    active_membership_exists = GroupMembership.objects.filter(
        group=group,
        user=user,
        is_active=True
    ).exists()
    
    if active_membership_exists:
        raise ValidationError("User is already an active member of this group.")

    # Handle history validation: Joined date must be after previous leave date
    latest_left = GroupMembership.objects.filter(
        group=group,
        user=user,
        is_active=False
    ).order_by("-left_at").first()

    if latest_left and latest_left.left_at and joined_at < latest_left.left_at:
        raise ValidationError(
            f"User previously left the group on {latest_left.left_at}. "
            f"New join date ({joined_at}) must be on or after the previous leave date."
        )

    # Create new membership
    membership = GroupMembership(
        group=group,
        user=user,
        joined_at=joined_at,
        role=role,
        is_active=True
    )
    # Triggers clean() validation (including joined_at <= left_at)
    membership.full_clean()
    membership.save()
    return membership


def leave_membership(membership, left_at):
    """
    Business logic for a member leaving a group.
    """
    if not membership.is_active:
        raise ValidationError("Membership is already inactive (user has already left).")

    if left_at < membership.joined_at:
        raise ValidationError(
            f"Leave date ({left_at}) cannot be before the join date ({membership.joined_at})."
        )

    membership.left_at = left_at
    membership.is_active = False
    membership.full_clean()
    membership.save()
    return membership


def leave_member(group, user, left_at):
    """
    Wrapper logic for a user leaving a group via group & user references.
    """
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=user,
            is_active=True
        )
    except GroupMembership.DoesNotExist:
        raise ValidationError("User is not an active member of this group.")

    return leave_membership(membership, left_at)
