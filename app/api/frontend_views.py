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


class TextReaderView(TemplateView):
    """Vista para leer un texto"""
    template_name = 'texts/text_reader.html'


class QuizInterfaceView(TemplateView):
    """Vista para tomar cuestionario"""
    template_name = 'texts/quiz_interface.html'


class QuizResultsView(TemplateView):
    """Vista para ver resultados de cuestionario"""
    template_name = 'texts/quiz_results.html'

class MaterialsHistoryView(TemplateView):
    """Vista para historial de materiales didácticos"""
    template_name = 'texts/materials_history.html'