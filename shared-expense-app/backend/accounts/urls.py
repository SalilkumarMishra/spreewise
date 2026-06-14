from django.urls import path
from accounts.views import RegisterView, LogoutView, MeView, UserSearchView, DashboardView

urlpatterns = [
    # Auth
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('dashboard/', DashboardView.as_view(), name='auth-dashboard'),

    # User search  — accessible under /api/users/search/
    path('search/', UserSearchView.as_view(), name='user-search'),
]
