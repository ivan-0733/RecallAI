from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from django.views.generic import RedirectView
from django.views.generic import TemplateView

# Endpoint para swagger
schema_view = get_schema_view(
    openapi.Info(
        title="RecallAI API Documentation",
        default_version="v1",
        description="API para sistema de aprendizaje adaptativo con IA",
        license=openapi.License(name="FreeBSD License"),
        contact=openapi.Contact(email="default@email.com", name="RecallAI Team"),
    ),
    public=True,
)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    
    # Redirección de raíz a login
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),
    
    # Frontend (Templates HTML)
    path('', include('api.frontend_urls')),
    
    # API REST (para AJAX)
    path("api/", include("api.urls")),
    
    # Autenticación de DRF (para Swagger)
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    
    # Swagger Documentation
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

    path("material/<int:material_id>/", TemplateView.as_view(template_name="texts/material_viewer.html"), name="material_viewer"),
]

# ✅ CRÍTICO: Servir archivos media
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)