from django.urls import path
from api.frontend_views import (
    LoginView, 
    RegisterView, 
    DashboardView,
    TextReaderView,
    QuizInterfaceView,
    QuizResultsView
)

app_name = 'frontend'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Textos y quizzes
    path('text/<int:text_id>/', TextReaderView.as_view(), name='text_reader'),
    path('quiz/<int:text_id>/', QuizInterfaceView.as_view(), name='quiz_interface'),
    path('quiz/<int:text_id>/results/', QuizResultsView.as_view(), name='quiz_results'),
]