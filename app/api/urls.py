# ========================================
# URLs ACTUALIZADAS CON TRACKING
# Reemplazar contenido de app/api/urls.py
# ========================================

from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter

from api.views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
)

from apps.pdi_texts.views import (
    PDITextViewSet,
    QuizAttemptViewSet,
    UserProfileViewSet,
    UserDidacticMaterialViewSet,
    TrackingViewSet,
    AnalyticsViewSet
)

app_name = 'api'

# Router para ViewSets
router = DefaultRouter()
router.register(r'texts', PDITextViewSet, basename='texts')
router.register(r'attempts', QuizAttemptViewSet, basename='attempts')
router.register(r'profile', UserProfileViewSet, basename='user-profile')
router.register(r'materials', UserDidacticMaterialViewSet, basename='materials')

# NUEVAS RUTAS DE TRACKING
router.register(r'tracking', TrackingViewSet, basename='tracking')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    # Autenticación (API REST)
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Router de ViewSets
    path('', include(router.urls)),
]