from django.urls import path
from api.frontend_views import (
    LoginView, 
    RegisterView, 
    DashboardView,
    TextReaderView,
    QuizInterfaceView,
    QuizResultsView,
    MaterialsHistoryView,
    MaterialView,             # <--- Nueva clase
    study_next_material_view  # <--- Nueva función
)

app_name = 'frontend'

urlpatterns = [
    # Autenticación y Dashboard
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Flujo Estándar
    path('text/<int:text_id>/', TextReaderView.as_view(), name='text_reader'),
    path('quiz/<int:text_id>/', QuizInterfaceView.as_view(), name='quiz_interface'),
    path('quiz/<int:text_id>/results/', QuizResultsView.as_view(), name='quiz_results'),

    # --- FLUJO EXPERIMENTAL (Rutas especiales) ---

    # 1. Pre-Test: Usamos la misma vista pero le inyectamos datos extra
    path('text/<int:text_id>/initial-quiz/', 
         QuizInterfaceView.as_view(extra_context={'quiz_mode': 'initial', 'page_title': 'Pre-Test'}), 
         name='initial_quiz'),

    # 2. Post-Test: Lo mismo, inyectando modo post-test
    path('text/<int:text_id>/post-test/', 
         QuizInterfaceView.as_view(extra_context={'quiz_mode': 'post_test', 'page_title': 'Post-Test'}), 
         name='post_test'),

    # 3. Redirección Inteligente (Botón "Ir a Sesión X")
    path('materials/study/<int:text_id>/', study_next_material_view, name='study_material_redirect'),
    
    # 4. Visor de Material
    path('material/<int:material_id>/', MaterialView.as_view(), name='material_viewer'),
    
    # Historial
    path('materials/history/<int:text_id>/', MaterialsHistoryView.as_view(), name='materials_history'),
]