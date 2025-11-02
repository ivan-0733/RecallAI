from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.application_user.models import User


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
        help_text="Contenido completo extraído del PDF/TXT"
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
        max_length=50,
        default='gemini-pro',
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