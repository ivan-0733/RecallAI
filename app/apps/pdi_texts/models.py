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
        ('decision_tree', 'Árbol de Decisión'),
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
        ('decision_tree', 'Árbol de Decisión'),
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
        ('decision_tree', 'Árbol de Decisión'),
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
    
    def __str__(self):
        return f"{self.user.email} - {self.material_type}"