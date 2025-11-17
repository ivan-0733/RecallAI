# ========================================
# URLs CORREGIDAS (MODO EXPLÍCITO)
# app/api/urls.py
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

# Router para ViewSets estándar
router = DefaultRouter()
router.register(r'texts', PDITextViewSet, basename='texts')
router.register(r'attempts', QuizAttemptViewSet, basename='attempts')
router.register(r'profile', UserProfileViewSet, basename='user-profile')
router.register(r'materials', UserDidacticMaterialViewSet, basename='materials')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

# ⚠️ ELIMINAMOS EL REGISTRO AUTOMÁTICO DE TRACKING PARA EVITAR EL ERROR 405
# router.register(r'tracking/session', TrackingViewSet, basename='tracking-session')

urlpatterns = [
    # === RUTAS DE TRACKING EXPLÍCITAS (SOLUCIÓN DEFINITIVA) ===
    path('tracking/session/start/', TrackingViewSet.as_view({'post': 'start_session'}), name='tracking-start'),
    path('tracking/session/sync/', TrackingViewSet.as_view({'post': 'sync_session'}), name='tracking-sync'),
    path('tracking/session/end/', TrackingViewSet.as_view({'post': 'end_session'}), name='tracking-end'),
    # Ruta para obtener detalles (GET) usando regex para el UUID
    path('tracking/session/<str:session_id>/', TrackingViewSet.as_view({'get': 'get_session_details'}), name='tracking-details'),

    # Autenticación (API REST)
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Router de ViewSets (al final)
    path('', include(router.urls)),
]