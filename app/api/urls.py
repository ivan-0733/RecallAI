# ========================================
# URLs CORREGIDAS (SOLUCIÓN ERROR 404 SYNC)
# app/api/urls.py
# ========================================

from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter

# 1. Importar vistas de autenticación (api/views.py)
from api.views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    UserProfileView,
)

# 2. Importar vistas de la aplicación (apps/pdi_texts/views.py)
from apps.pdi_texts.views import (
    PDITextViewSet,
    QuizAttemptViewSet,
    UserProfileViewSet,
    UserDidacticMaterialViewSet,
    TrackingViewSet,
    AnalyticsViewSet,
    UserActivePathsView 
)

app_name = 'api'

# Router para ViewSets estándar
router = DefaultRouter()
router.register(r'texts', PDITextViewSet, basename='texts')
router.register(r'attempts', QuizAttemptViewSet, basename='attempts')
router.register(r'profile', UserProfileViewSet, basename='user-profile')
router.register(r'materials', UserDidacticMaterialViewSet, basename='materials')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    # === RUTAS DE TRACKING (PRIORIDAD ALTA) ===
    # El error 404 suele darse por el slash final. Definimos ambas opciones por seguridad.
    path('tracking/session/start/', TrackingViewSet.as_view({'post': 'start_session'}), name='tracking-start'),
    path('tracking/session/sync/', TrackingViewSet.as_view({'post': 'sync_session'}), name='tracking-sync'),
    path('tracking/session/end/', TrackingViewSet.as_view({'post': 'end_session'}), name='tracking-end'),
    
    # Esta ruta es para ver detalles, debe ir después de las específicas
    path('tracking/session/<str:session_id>/', TrackingViewSet.as_view({'get': 'get_session_details'}), name='tracking-details'),

    # === AUTENTICACIÓN ===
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # === RUTAS DEL FLUJO DE APRENDIZAJE ===
    path('user/paths/', UserActivePathsView.as_view(), name='user-paths'),
    
    # Router de ViewSets (SIEMPRE AL FINAL)
    path('', include(router.urls)),
]