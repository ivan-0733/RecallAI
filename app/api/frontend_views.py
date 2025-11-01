from django.shortcuts import render
from django.views.generic import TemplateView


class LoginView(TemplateView):
    """Vista para página de login"""
    template_name = 'auth/login.html'


class RegisterView(TemplateView):
    """Vista para página de registro"""
    template_name = 'auth/register.html'


class DashboardView(TemplateView):
    """Vista para dashboard principal"""
    template_name = 'dashboard/dashboard.html'