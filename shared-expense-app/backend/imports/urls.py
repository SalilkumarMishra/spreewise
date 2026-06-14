from django.urls import path
from imports.views import ImportJobViewSet, ImportAnomalyDecisionViewSet

urlpatterns = [
    path("", ImportJobViewSet.as_view({"get": "list"})),
    path("upload/", ImportJobViewSet.as_view({"post": "upload"})),
    path("<int:pk>/", ImportJobViewSet.as_view({"get": "retrieve"})),
    path("<int:pk>/anomalies/", ImportJobViewSet.as_view({"get": "anomalies"})),
    path("<int:pk>/report/", ImportJobViewSet.as_view({"get": "report"})),
    path("anomalies/<int:pk>/decision/", ImportAnomalyDecisionViewSet.as_view({"post": "decision"})),
]
