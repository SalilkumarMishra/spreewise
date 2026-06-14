from django.urls import path, include
from rest_framework.routers import DefaultRouter
from groups.views import GroupViewSet, GroupMembershipLeaveView, JoinGroupByInviteCodeView

router = DefaultRouter()
router.register(r"", GroupViewSet, basename="group")

urlpatterns = [
    # Invite code join — before router to avoid pattern conflicts
    path("join/", JoinGroupByInviteCodeView.as_view(), name="group-join"),

    # Member leave
    path(
        "<int:group_id>/members/<int:membership_id>/leave/",
        GroupMembershipLeaveView.as_view(),
        name="group-member-leave"
    ),

    path("", include(router.urls)),
]
