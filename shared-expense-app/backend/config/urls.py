"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT Auth endpoints
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Accounts app (register, me, logout, dashboard, user search)
    path('api/auth/', include('accounts.urls')),
    path('api/users/', include('accounts.urls')),

    # Core app APIs
    path('api/groups/', include('groups.urls')),
    path('api/expenses/', include('expenses.urls')),
    path('api/settlements/', include('settlements.urls')),
    path('api/balances/', include('balance_engine.urls')),
    path('api/imports/', include('imports.urls')),
]
