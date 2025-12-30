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

# ==============================================================================
# AGREGAR ESTO AL FINAL DE app/api/frontend_views.py
# ==============================================================================

from django.shortcuts import redirect, get_object_or_404
from apps.pdi_texts.models import StudentLearningPath, UserDidacticMaterial, PDIText

class MaterialView(TemplateView):
    """Vista para ver un material específico (HTML generado)"""
    template_name = 'texts/material_viewer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        material_id = self.kwargs.get('material_id')
        context['material'] = get_object_or_404(UserDidacticMaterial, id=material_id)
        return context

def study_next_material_view(request, text_id):
    """
    Vista Lógica: Encuentra qué material le toca al alumno y redirige.
    """
    # 1. Verificar si hay un Path activo
    path = StudentLearningPath.objects.filter(user=request.user, text_id=text_id).first()
    
    if not path:
        # Si no hay path, redirigir al inicio del texto
        return redirect('frontend:text_reader', text_id=text_id)

    # 2. Buscar el material más reciente generado para este texto y usuario
    # (Idealmente filtraríamos por sesión, pero por ahora el último creado funciona)
    material = UserDidacticMaterial.objects.filter(
        user=request.user,
        text_id=text_id
    ).order_by('-created_at').first()
    
    if material:
        # Redirigir a la vista que acabamos de crear arriba
        return redirect('frontend:material_viewer', material_id=material.id)
    else:
        # Caso raro: Path existe pero material no se ha generado aun
        return redirect('frontend:dashboard')