from django.urls import path, include
from rest_framework.routers import DefaultRouter
from groups.views import GroupViewSet, GroupMembershipLeaveView

router = DefaultRouter()
router.register(r"", GroupViewSet, basename="group")

urlpatterns = [
    # Note: custom route placed before default router to avoid overlapping pattern matching
    path(
        "<int:group_id>/members/<int:membership_id>/leave/",
        GroupMembershipLeaveView.as_view(),
        name="group-member-leave"
    ),
    path("", include(router.urls)),
]
