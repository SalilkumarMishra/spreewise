from django.urls import path
from balance_engine.views import BalanceViewSet

urlpatterns = [
    path("groups/<int:group_id>/", BalanceViewSet.as_view({"get": "list"})),
    path("groups/<int:group_id>/simplified/", BalanceViewSet.as_view({"get": "simplified"})),
    path("groups/<int:group_id>/users/<int:user_id>/", BalanceViewSet.as_view({"get": "user_explanation"})),
    path("groups/<int:group_id>/ledger/", BalanceViewSet.as_view({"get": "ledger"})),
]
