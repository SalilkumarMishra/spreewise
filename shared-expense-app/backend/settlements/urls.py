from django.urls import path, include
from rest_framework.routers import DefaultRouter
from settlements.views import SettlementViewSet

router = DefaultRouter()
router.register(r"", SettlementViewSet, basename="settlement")

urlpatterns = [
    path("", include(router.urls)),
]
