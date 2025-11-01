from django.urls import path
from api.frontend_views import LoginView, RegisterView, DashboardView

app_name = 'frontend'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]