from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.application_user.models import User
from django.db.models.signals import post_save


class PDIText(models.Model):
    """
    Modelo para almacenar textos académicos de Procesamiento Digital de Imágenes
    """
    
    DIFFICULTY_CHOICES = [
        ('beginner', 'Principiante'),
        ('intermediate', 'Intermedio'),
        ('advanced', 'Avanzado'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('archived', 'Archivado'),
    ]
    
    title = models.CharField(
        max_length=255,
        verbose_name="Título",
        help_text="Título del texto académico"
    )
    
    description = models.TextField(
        verbose_name="Descripción",
        help_text="Breve descripción del contenido",
        blank=True
    )
    
    content = models.TextField(
        verbose_name="Contenido",
        help_text="Contenido completo extraído del PDF/TXT",
        blank=True,  
        default="" 
    )
    
    file = models.FileField(
        upload_to='pdi_texts/%Y/%m/',
        verbose_name="Archivo",
        help_text="Archivo PDF o TXT original",
        null=True,
        blank=True
    )
    
    topic = models.CharField(
        max_length=100,
        verbose_name="Tema Principal",
        help_text="Ej: Filtros, Transformaciones, Segmentación",
        default="General"
    )
    
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='intermediate',
        verbose_name="Dificultad"
    )
    
    estimated_time_minutes = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(180)],
        verbose_name="Tiempo Estimado (minutos)",
        help_text="Tiempo estimado de lectura"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Estado"
    )
    
    order = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de presentación (menor número = primero)"
    )
    
    has_quiz = models.BooleanField(
        default=False,
        verbose_name="¿Tiene Cuestionario?",
        help_text="Se marca automáticamente cuando se genera el cuestionario"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_texts',
        verbose_name="Creado por"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        db_table = 'pdi_text'
        verbose_name = 'Texto PDI'
        verbose_name_plural = 'Textos PDI'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['status', 'order']),
            models.Index(fields=['topic']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_difficulty_display()}"
    
    def word_count(self):
        """Cuenta palabras del contenido"""
        if not self.content:
            return 0
        return len(self.content.split())
    
    def activate(self):
        """Activa el texto para que sea visible a los alumnos"""
        self.status = 'active'
        self.save()
    
    def archive(self):
        """Archiva el texto"""
        self.status = 'archived'
        self.save()


class InitialQuiz(models.Model):
    """
    Cuestionario inicial único por texto, generado por Gemini Pro
    """
    
    text = models.OneToOneField(
        PDIText,
        on_delete=models.CASCADE,
        related_name='initial_quiz',
        verbose_name="Texto PDI"
    )
    
    questions_json = models.JSONField(
        verbose_name="Preguntas (JSON)",
        help_text="Array de objetos con estructura: {pregunta, opciones[], respuesta_correcta, tema, explicacion}"
    )
    
    total_questions = models.IntegerField(
        default=20,
        verbose_name="Total de Preguntas"
    )
    
    generation_prompt = models.TextField(
        verbose_name="Prompt Usado",
        help_text="Prompt enviado a Gemini Pro para generar este quiz",
        blank=True
    )
    
    generation_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tiempo de Generación (segundos)"
    )
    
    model_used = models.CharField(
        max_length=16000,
        default='gemini-2.5-pro',
        verbose_name="Modelo de IA Usado"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de generación"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        db_table = 'initial_quiz'
        verbose_name = 'Cuestionario Inicial'
        verbose_name_plural = 'Cuestionarios Iniciales'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Quiz: {self.text.title} ({self.total_questions} preguntas)"
    
    def get_questions(self):
        """Retorna las preguntas como lista de Python"""
        return self.questions_json if isinstance(self.questions_json, list) else []
    
    def validate_structure(self):
        """Valida que el JSON tenga la estructura correcta"""
        required_keys = ['pregunta', 'opciones', 'respuesta_correcta', 'tema']
        
        if not isinstance(self.questions_json, list):
            return False, "El JSON debe ser una lista"
        
        for i, q in enumerate(self.questions_json):
            for key in required_keys:
                if key not in q:
                    return False, f"Pregunta {i+1} le falta el campo '{key}'"
            
            if not isinstance(q['opciones'], list) or len(q['opciones']) < 2:
                return False, f"Pregunta {i+1} debe tener al menos 2 opciones"
        
        return True, "Estructura válida"
    

@receiver(post_delete, sender=InitialQuiz)
def update_text_quiz_flag_on_delete(sender, instance, **kwargs):
    """
    Cuando se elimina un quiz, actualizar el flag has_quiz del texto a False
    """
    try:
        text = instance.text
        text.has_quiz = False
        text.save(update_fields=['has_quiz'])
    except PDIText.DoesNotExist:
        pass

class QuizAttempt(models.Model):
    """
    Registro de intentos de cuestionarios por parte de los alumnos
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        verbose_name="Alumno"
    )
    
    quiz = models.ForeignKey(
        InitialQuiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name="Cuestionario"
    )
    
    attempt_number = models.IntegerField(
        verbose_name="Número de Intento",
        help_text="1, 2, 3..."
    )
    
    score = models.FloatField(
        verbose_name="Puntuación",
        help_text="Porcentaje de respuestas correctas (0-100)"
    )
    
    answers_json = models.JSONField(
        verbose_name="Respuestas (JSON)",
        help_text="Array de objetos: [{question_id, selected_answer, is_correct}]"
    )
    
    weak_topics = models.JSONField(
        verbose_name="Temas Débiles",
        help_text="Lista de temas donde falló: ['Filtros Gaussianos', 'Canny']",
        default=list
    )
    
    time_spent_seconds = models.IntegerField(
        verbose_name="Tiempo Empleado (segundos)",
        help_text="Tiempo que tardó en completar el cuestionario"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha del intento"
    )
    
    class Meta:
        db_table = 'quiz_attempt'
        verbose_name = 'Intento de Cuestionario'
        verbose_name_plural = 'Intentos de Cuestionarios'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['quiz', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.quiz.text.title} - Intento #{self.attempt_number} ({self.score}%)"
    
    def passed(self):
        """Verifica si aprobó (score >= 80%)"""
        return self.score >= 80.0
    
    def get_answers(self):
        """Retorna las respuestas como lista de Python"""
        return self.answers_json if isinstance(self.answers_json, list) else []


class UserProfile(models.Model):
    """
    Perfil extendido del usuario con estadísticas de aprendizaje
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Usuario"
    )
    
    weak_topics = models.JSONField(
        verbose_name="Temas Débiles Acumulados",
        help_text="Historial de todos los temas donde ha fallado",
        default=list
    )
    
    study_streak = models.IntegerField(
        default=0,
        verbose_name="Racha de Estudio (días)",
        help_text="Días consecutivos estudiando"
    )
    
    last_study_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Última Fecha de Estudio"
    )
    
    material_preferences = models.JSONField(
        verbose_name="Preferencias de Material",
        help_text="Tipos de material que prefiere el usuario",
        default=dict
    )
    
    total_study_time_minutes = models.IntegerField(
        default=0,
        verbose_name="Tiempo Total de Estudio (minutos)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        db_table = 'user_profile'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'
    
    def __str__(self):
        return f"Perfil de {self.user.email}"
    
    def update_weak_topics(self, new_weak_topics):
        """Agrega nuevos temas débiles sin duplicar"""
        current = set(self.weak_topics)
        current.update(new_weak_topics)
        self.weak_topics = list(current)
        self.save()
    
    def add_study_time(self, minutes):
        """Incrementa el tiempo total de estudio"""
        self.total_study_time_minutes += minutes
        self.save()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crear perfil automáticamente al crear usuario"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Guardar perfil cuando se guarda usuario"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

class MaterialEffectiveness(models.Model):
    """
    Registra la efectividad de cada tipo de material para cada usuario
    """
    
    MATERIAL_TYPES = [
        ('flashcard', 'Flashcards'),
        ('decision_tree', 'Mapa Conceptual'),
        ('mind_map', 'Mapa Mental'),
        ('summary', 'Resumen Estructurado'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='material_effectiveness',
        verbose_name="Usuario"
    )
    
    text = models.ForeignKey(
        PDIText,
        on_delete=models.CASCADE,
        related_name='material_effectiveness',
        verbose_name="Texto"
    )
    
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPES,
        verbose_name="Tipo de Material"
    )
    
    quiz_before_score = models.FloatField(
        verbose_name="Score Antes",
        help_text="Puntuación antes de usar el material"
    )
    
    quiz_after_score = models.FloatField(
        verbose_name="Score Después",
        help_text="Puntuación después de usar el material"
    )
    
    improvement = models.FloatField(
        verbose_name="Mejora",
        help_text="Diferencia: after - before"
    )
    
    time_spent_minutes = models.IntegerField(
        verbose_name="Tiempo Estudiado (minutos)",
        help_text="Tiempo que pasó estudiando el material"
    )
    
    interactions_count = models.IntegerField(
        default=0,
        verbose_name="Interacciones",
        help_text="Número de clics, flips, expansiones"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        db_table = 'material_effectiveness'
        verbose_name = 'Efectividad de Material'
        verbose_name_plural = 'Efectividad de Materiales'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'text', 'material_type']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.material_type} - Mejora: {self.improvement}%"


class MaterialRequest(models.Model):
    """
    Historial de solicitudes de material
    """
    
    MATERIAL_TYPES = [
        ('flashcard', 'Flashcards'),
        ('decision_tree', 'Mapa Conceptual'),
        ('mind_map', 'Mapa Mental'),
        ('summary', 'Resumen Estructurado'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='material_requests',
        verbose_name="Usuario"
    )
    
    text = models.ForeignKey(
        PDIText,
        on_delete=models.CASCADE,
        related_name='material_requests',
        verbose_name="Texto"
    )
    
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='material_requests',
        verbose_name="Intento de Quiz"
    )
    
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPES,
        verbose_name="Tipo de Material"
    )
    
    was_recommended = models.BooleanField(
        default=False,
        verbose_name="¿Fue Recomendado?"
    )
    
    followed_recommendation = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="¿Siguió la Recomendación?"
    )
    
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Solicitud"
    )
    
    class Meta:
        db_table = 'material_request'
        verbose_name = 'Solicitud de Material'
        verbose_name_plural = 'Solicitudes de Material'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'text']),
            models.Index(fields=['-requested_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.material_type}"


class UserDidacticMaterial(models.Model):
    """
    Material didáctico generado por IA
    """
    
    MATERIAL_TYPES = [
        ('flashcard', 'Flashcards'),
        ('decision_tree', 'Mapa Conceptual'),
        ('mind_map', 'Mapa Mental'),
        ('summary', 'Resumen Estructurado'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='didactic_materials',
        verbose_name="Usuario"
    )
    
    text = models.ForeignKey(
        PDIText,
        on_delete=models.CASCADE,
        related_name='didactic_materials',
        verbose_name="Texto"
    )
    
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='didactic_materials',
        verbose_name="Intento"
    )
    
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPES,
        verbose_name="Tipo"
    )
    
    html_content = models.TextField(
        verbose_name="HTML",
        help_text="HTML sanitizado"
    )
    
    weak_topics = models.JSONField(
        verbose_name="Temas Enfocados"
    )
    
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Solicitado"
    )
    
    generated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Generado"
    )
    
    generation_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tiempo Generación"
    )
    
    was_effective = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="¿Efectivo?"
    )
    
    class Meta:
        db_table = 'user_didactic_material'
        verbose_name = 'Material Didáctico'
        verbose_name_plural = 'Materiales Didácticos'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'text']),
            models.Index(fields=['material_type']),
            models.Index(fields=['-requested_at']),
        ]

    def get_aggregated_stats(self):
        """
        Calcula estadísticas totales acumulando todas las sesiones de estudio de este material.
        """
        sessions = self.study_sessions.all()
        total_sessions = sessions.count()
        
        aggregates = sessions.aggregate(
            total_time=Sum('total_time_seconds'),
            total_active=Sum('active_time_seconds'),
            total_interactions=Sum('total_interactions'),
            total_clicks=Sum('click_events'),
            total_scrolls=Sum('scroll_events')
        )
        
        # Calcular completitud promedio
        avg_completion = 0
        if total_sessions > 0:
            total_depth = sum(s.max_scroll_depth for s in sessions)
            avg_completion = total_depth / total_sessions

        return {
            'sessions_count': total_sessions,
            'total_time': aggregates['total_time'] or 0,
            'total_active': aggregates['total_active'] or 0,
            'total_interactions': aggregates['total_interactions'] or 0,
            'total_clicks': aggregates['total_clicks'] or 0,
            'total_scrolls': aggregates['total_scrolls'] or 0,
            'avg_completion': avg_completion
        }
    
    def __str__(self):
        return f"{self.user.email} - {self.material_type}"
    
# ============================================
# MODELOS DE TRACKING DETALLADO
# Agregar al final de app/apps/pdi_texts/models.py
# ============================================

import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class StudySession(models.Model):
    """
    Sesión de estudio completa - captura TODO lo que hace el usuario
    mientras estudia un material didáctico
    """
    
    EXIT_TYPES = [
        ('normal', 'Salida Normal'),
        ('timeout', 'Timeout por Inactividad'),
        ('browser_close', 'Cerró Navegador'),
        ('navigation', 'Navegó a otra página'),
    ]
    
    # Identificación
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name="ID de Sesión"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='study_sessions',
        verbose_name="Usuario"
    )
    
    material = models.ForeignKey(
        'UserDidacticMaterial',
        on_delete=models.CASCADE,
        related_name='study_sessions',
        verbose_name="Material"
    )
    
    # Tiempos
    started_at = models.DateTimeField(
        verbose_name="Inicio"
    )
    
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fin"
    )
    
    total_time_seconds = models.IntegerField(
        default=0,
        verbose_name="Tiempo Total (segundos)"
    )
    
    active_time_seconds = models.IntegerField(
        default=0,
        verbose_name="Tiempo Activo (segundos)",
        help_text="Tiempo real de interacción (sin idle)"
    )
    
    idle_time_seconds = models.IntegerField(
        default=0,
        verbose_name="Tiempo Inactivo (segundos)"
    )
    
    # Métricas de actividad
    total_interactions = models.IntegerField(
        default=0,
        verbose_name="Total de Interacciones"
    )
    
    scroll_events = models.IntegerField(
        default=0,
        verbose_name="Eventos de Scroll"
    )
    
    click_events = models.IntegerField(
        default=0,
        verbose_name="Eventos de Click"
    )
    
    hover_events = models.IntegerField(
        default=0,
        verbose_name="Eventos de Hover"
    )
    
    focus_changes = models.IntegerField(
        default=0,
        verbose_name="Cambios de Foco"
    )
    
    # Métricas de contenido
    sections_visited = models.JSONField(
        default=list,
        verbose_name="Secciones Visitadas"
    )
    
    max_scroll_depth = models.FloatField(
        default=0,
        verbose_name="Profundidad Máxima de Scroll (%)"
    )
    
    revisits_count = models.IntegerField(
        default=0,
        verbose_name="Número de Revisitas"
    )
    
    # Estado
    is_active = models.BooleanField(
        default=True,
        verbose_name="Sesión Activa"
    )
    
    completed = models.BooleanField(
        default=False,
        verbose_name="Completó el Material"
    )
    
    exit_type = models.CharField(
        max_length=20,
        choices=EXIT_TYPES,
        null=True,
        blank=True,
        verbose_name="Tipo de Salida"
    )
    
    # Metadata del dispositivo
    device_type = models.CharField(
        max_length=20,
        null=True,
        verbose_name="Tipo de Dispositivo"
    )
    
    browser = models.CharField(
        max_length=50,
        null=True,
        verbose_name="Navegador"
    )
    
    screen_resolution = models.CharField(
        max_length=20,
        null=True,
        verbose_name="Resolución"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )
    
    class Meta:
        db_table = 'study_session'
        verbose_name = 'Sesión de Estudio'
        verbose_name_plural = 'Sesiones de Estudio'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['material', '-started_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Sesión {self.session_id} - {self.user.email}"
    
    def duration_formatted(self):
        """Retorna duración en formato HH:MM:SS"""
        hours = self.total_time_seconds // 3600
        minutes = (self.total_time_seconds % 3600) // 60
        seconds = self.total_time_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def active_percentage(self):
        """Porcentaje de tiempo activo vs total"""
        if self.total_time_seconds == 0:
            return 0
        return (self.active_time_seconds / self.total_time_seconds) * 100
    
    def engagement_score(self):
        """
        Calcula un score de engagement (0-100) basado en:
        - Tiempo activo
        - Número de interacciones
        - Profundidad de scroll
        - Completitud
        """
        score = 0
        
        # 40 puntos por tiempo activo (mínimo 5 minutos = 100%)
        if self.active_time_seconds >= 300:
            score += 40
        else:
            score += (self.active_time_seconds / 300) * 40
        
        # 30 puntos por interacciones (mínimo 50 = 100%)
        if self.total_interactions >= 50:
            score += 30
        else:
            score += (self.total_interactions / 50) * 30
        
        # 20 puntos por scroll depth
        score += (self.max_scroll_depth / 100) * 20
        
        # 10 puntos si completó
        if self.completed:
            score += 10
        
        return min(100, round(score, 2))


class InteractionEvent(models.Model):
    """
    Evento granular de interacción - cada click, scroll, hover, etc.
    """
    
    EVENT_TYPES = [
        ('click', 'Click'),
        ('scroll', 'Scroll'),
        ('hover', 'Hover'),
        ('focus', 'Cambio de Foco'),
        ('flashcard_flip', 'Voltear Flashcard'),
        ('node_expand', 'Expandir Nodo'),
        ('node_collapse', 'Colapsar Nodo'),
        ('section_view', 'Ver Sección'),
        ('copy_text', 'Copiar Texto'),
        ('tab_visible', 'Tab Visible'),
        ('tab_hidden', 'Tab Oculta'),
        ('resume_study', 'Reanudar Estudio'),
        ('pause_study', 'Pausar Estudio'),
    ]
    
    session = models.ForeignKey(
        StudySession,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name="Sesión"
    )
    
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPES,
        verbose_name="Tipo de Evento"
    )
    
    # Datos del evento
    element_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="ID del Elemento"
    )
    
    element_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Tipo de Elemento"
    )
    
    element_text = models.TextField(
        null=True,
        blank=True,
        verbose_name="Texto del Elemento"
    )
    
    # Posición
    x_position = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posición X"
    )
    
    y_position = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posición Y"
    )
    
    scroll_position = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posición de Scroll"
    )
    
    viewport_height = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Alto del Viewport"
    )
    
    # Timing
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Timestamp"
    )
    
    time_since_session_start = models.FloatField(
        verbose_name="Tiempo desde Inicio (segundos)"
    )
    
    # Contexto adicional
    metadata = models.JSONField(
        default=dict,
        verbose_name="Metadata Adicional"
    )
    
    class Meta:
        db_table = 'interaction_event'
        verbose_name = 'Evento de Interacción'
        verbose_name_plural = 'Eventos de Interacción'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"{self.event_type} @ {self.time_since_session_start:.1f}s"


class SectionTimeTracking(models.Model):
    """
    Tracking de tiempo por sección específica del material
    """
    
    SECTION_TYPES = [
        ('weak_section', 'Sección de Temas Débiles'),
        ('review_section', 'Sección de Repaso'),
        ('flashcard', 'Flashcard'),
        ('tree_node', 'Nodo del Árbol'),
        ('summary_block', 'Bloque de Resumen'),
        ('comparison_table', 'Tabla Comparativa'),
        ('code_block', 'Bloque de Código'),
    ]
    
    session = models.ForeignKey(
        StudySession,
        on_delete=models.CASCADE,
        related_name='section_times',
        verbose_name="Sesión"
    )
    
    # Identificación de sección
    section_id = models.CharField(
        max_length=255,
        verbose_name="ID de Sección"
    )
    
    section_type = models.CharField(
        max_length=50,
        choices=SECTION_TYPES,
        verbose_name="Tipo de Sección"
    )
    
    section_content_preview = models.TextField(
        max_length=500,
        verbose_name="Preview del Contenido"
    )
    
    # Métricas de tiempo
    first_view_at = models.DateTimeField(
        verbose_name="Primera Vista"
    )
    
    last_view_at = models.DateTimeField(
        verbose_name="Última Vista"
    )
    
    total_time_seconds = models.FloatField(
        default=0,
        verbose_name="Tiempo Total (segundos)"
    )
    
    view_count = models.IntegerField(
        default=0,
        verbose_name="Número de Vistas"
    )
    
    # Interacciones específicas
    interaction_count = models.IntegerField(
        default=0,
        verbose_name="Interacciones en Sección"
    )
    
    scroll_depth_percent = models.FloatField(
        default=0,
        verbose_name="Profundidad de Scroll (%)"
    )
    
    # Flags
    fully_read = models.BooleanField(
        default=False,
        verbose_name="Leído Completamente"
    )
    
    interacted_with = models.BooleanField(
        default=False,
        verbose_name="Interactuó con la Sección"
    )
    
    class Meta:
        db_table = 'section_time_tracking'
        verbose_name = 'Tracking de Tiempo por Sección'
        verbose_name_plural = 'Tracking de Tiempo por Sección'
        ordering = ['-total_time_seconds']
        indexes = [
            models.Index(fields=['session', 'section_id']),
            models.Index(fields=['section_type']),
        ]
        unique_together = ['session', 'section_id']
    
    def __str__(self):
        return f"{self.section_id} - {self.total_time_seconds:.1f}s"


class HeatmapData(models.Model):
    """
    Datos para generar heatmaps de interacción
    """
    
    session = models.ForeignKey(
        StudySession,
        on_delete=models.CASCADE,
        related_name='heatmap_data',
        verbose_name="Sesión"
    )
    
    # Datos de clics (array de objetos)
    clicks = models.JSONField(
        default=list,
        verbose_name="Clics",
        help_text="Array de {x, y, timestamp}"
    )
    
    # Datos de movimiento del mouse (sample cada 100ms)
    mouse_movements = models.JSONField(
        default=list,
        verbose_name="Movimientos del Mouse",
        help_text="Array de {x, y, timestamp}"
    )
    
    # Datos de scroll
    scroll_points = models.JSONField(
        default=list,
        verbose_name="Puntos de Scroll",
        help_text="Array de {position, timestamp}"
    )
    
    # Zonas calientes (calculadas en backend)
    hot_zones = models.JSONField(
        default=list,
        verbose_name="Zonas Calientes",
        help_text="Áreas con más actividad: [{x, y, width, height, intensity}]"
    )
    
    # Metadata
    captured_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Capturado"
    )
    
    data_points_count = models.IntegerField(
        default=0,
        verbose_name="Número de Puntos de Datos"
    )
    
    class Meta:
        db_table = 'heatmap_data'
        verbose_name = 'Datos de Heatmap'
        verbose_name_plural = 'Datos de Heatmap'
        ordering = ['-captured_at']
    
    def __str__(self):
        return f"Heatmap - Sesión {self.session.session_id} - {self.data_points_count} puntos"
    
    def calculate_hot_zones(self, grid_size=50):
        """
        Calcula zonas calientes basadas en densidad de clics
        Divide la pantalla en una grid y calcula intensidad por celda
        """
        if not self.clicks:
            return []
        
        # Obtener dimensiones de la pantalla
        max_x = max(c['x'] for c in self.clicks)
        max_y = max(c['y'] for c in self.clicks)
        
        # Crear grid
        grid = {}
        for click in self.clicks:
            grid_x = int(click['x'] // grid_size)
            grid_y = int(click['y'] // grid_size)
            key = f"{grid_x},{grid_y}"
            
            if key not in grid:
                grid[key] = {
                    'x': grid_x * grid_size,
                    'y': grid_y * grid_size,
                    'width': grid_size,
                    'height': grid_size,
                    'count': 0
                }
            grid[key]['count'] += 1
        
        # Calcular intensidad normalizada (0-100)
        max_count = max(zone['count'] for zone in grid.values())
        hot_zones = []
        
        for zone in grid.values():
            intensity = (zone['count'] / max_count) * 100
            if intensity >= 20:  # Solo guardar zonas con >20% intensidad
                hot_zones.append({
                    'x': zone['x'],
                    'y': zone['y'],
                    'width': zone['width'],
                    'height': zone['height'],
                    'intensity': round(intensity, 2)
                })
        
        return sorted(hot_zones, key=lambda z: z['intensity'], reverse=True)