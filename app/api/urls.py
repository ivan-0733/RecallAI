from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
)

app_name = 'api'

urlpatterns = [
    # Autenticación (API REST)
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]