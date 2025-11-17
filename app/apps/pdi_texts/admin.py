from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from apps.pdi_texts.models import PDIText, InitialQuiz, QuizAttempt, UserProfile
from apps.pdi_texts.tasks import generate_initial_quiz
from apps.pdi_texts.utils import (
    extract_text_from_pdf, 
    extract_text_from_txt, 
    estimate_reading_time
)


@admin.register(PDIText)
class PDITextAdmin(admin.ModelAdmin):
    list_display = [
        'title_with_icon', 
        'topic_badge', 
        'difficulty_badge', 
        'status_badge',
        'has_quiz_icon',
        'word_count_display',
        'estimated_time_minutes',
        'order',
        'created_at',
        'actions_column'
    ]
    
    list_filter = ['status', 'difficulty', 'topic', 'has_quiz', 'created_at']
    
    search_fields = ['title', 'description', 'content', 'topic']
    
    readonly_fields = [
        'word_count_display', 
        'has_quiz', 
        'created_by', 
        'created_at', 
        'updated_at',
        'content_preview'
    ]
    
    fieldsets = (
        ('📋 Información Básica', {
            'fields': ('title', 'description', 'topic', 'difficulty', 'status', 'order')
        }),
        ('📄 Contenido', {
            'fields': ('file', 'content', 'content_preview'),
            'description': 'Sube un PDF/TXT o pega el contenido manualmente. Si subes archivo, el contenido se extraerá automáticamente.'
        }),
        ('⏱️ Estimaciones', {
            'fields': ('estimated_time_minutes', 'word_count_display')
        }),
        ('📊 Estado del Cuestionario', {
            'fields': ('has_quiz',),
            'classes': ('collapse',)
        }),
        ('🔍 Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_texts',
        'archive_texts',
        'generate_quizzes',
        'regenerate_quizzes'
    ]
    
    class Media:
        js = ('admin/js/pdi_text_admin.js',)
    
    def get_urls(self):
        """Agregar URL personalizada para generar quiz vía AJAX"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:text_id>/generate-quiz/',
                self.admin_site.admin_view(self.generate_quiz_view),
                name='pdi_texts_pditext_generate_quiz',
            ),
        ]
        return custom_urls + urls
    
    def generate_quiz_view(self, request, text_id):
        """Vista para generar quiz vía AJAX - Funciona igual que la acción masiva"""
        try:
            text = PDIText.objects.get(id=text_id)
            
            # Verificar si ya tiene contenido
            if not text.content or text.content.strip() == "":
                return JsonResponse({
                    'status': 'error',
                    'message': '❌ El texto no tiene contenido. Primero debes guardar el texto con contenido.'
                }, status=400)
            
            # Verificar si ya tiene quiz
            if hasattr(text, 'initial_quiz'):
                return JsonResponse({
                    'status': 'error',
                    'message': '⚠️ Este texto ya tiene un cuestionario. Usa "RE-generar" si quieres crear uno nuevo.'
                }, status=400)
            
            # Encolar tarea Celery (IGUAL QUE LA ACCIÓN MASIVA)
            generate_initial_quiz.delay(text_id)
            
            # Mostrar mensaje en el admin (IGUAL QUE LA ACCIÓN MASIVA)
            self.message_user(
                request,
                f"🚀 Se encoló la tarea para generar cuestionario de '{text.title}'. Esto puede tomar varios minutos.",
                messages.SUCCESS
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'🚀 Generando cuestionario para "{text.title}"... Esto puede tomar varios minutos.',
                'reload': True  # ✅ NUEVO: indica al JS que debe recargar
            })
            
        except PDIText.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': '❌ Texto no encontrado'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'❌ Error: {str(e)}'
            }, status=500)
    
    def save_model(self, request, obj, form, change):
        """Al guardar, procesar archivo si se subió uno"""
        
        # Asignar usuario creador si es nuevo
        if not change:
            obj.created_by = request.user
        
        # Si se subió un archivo, extraer texto
        if 'file' in form.changed_data and obj.file:
            try:
                file_extension = obj.file.name.split('.')[-1].lower()
                
                if file_extension == 'pdf':
                    extracted_text, metadata = extract_text_from_pdf(obj.file)
                    obj.content = extracted_text
                    self.message_user(
                        request,
                        f"✅ Texto extraído exitosamente del PDF ({metadata['pages']} páginas, método: {metadata['method']})",
                        messages.SUCCESS
                    )
                
                elif file_extension == 'txt':
                    obj.content = extract_text_from_txt(obj.file)
                    self.message_user(
                        request,
                        "✅ Texto cargado exitosamente desde archivo TXT",
                        messages.SUCCESS
                    )
                
                # Auto-calcular tiempo estimado
                if obj.content:
                    obj.estimated_time_minutes = estimate_reading_time(obj.content)
            
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Error al procesar archivo: {str(e)}",
                    messages.ERROR
                )
        
        # Validar que tenga contenido antes de guardar
        if not obj.content or obj.content.strip() == "":
            if obj.file:
                self.message_user(
                    request,
                    "⚠️ No se pudo extraer texto del archivo. Verifica que sea un PDF/TXT válido.",
                    messages.WARNING
                )
            else:
                self.message_user(
                    request,
                    "⚠️ Debes proporcionar contenido o subir un archivo PDF/TXT.",
                    messages.WARNING
                )
        
        super().save_model(request, obj, form, change)
    
    # Custom display methods
    def title_with_icon(self, obj):
        icon = '📖'
        return format_html(
            '<span style="font-size: 14px;">{} <strong>{}</strong></span>',
            icon, obj.title
        )
    title_with_icon.short_description = 'Título'
    
    def topic_badge(self, obj):
        return format_html(
            '<span class="badge badge-info">{}</span>',
            obj.topic
        )
    topic_badge.short_description = 'Tema'
    
    def difficulty_badge(self, obj):
        colors = {
            'beginner': 'success',
            'intermediate': 'warning',
            'advanced': 'danger'
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.difficulty, 'secondary'),
            obj.get_difficulty_display()
        )
    difficulty_badge.short_description = 'Dificultad'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'active': 'success',
            'archived': 'dark'
        }
        icons = {
            'draft': '📝',
            'active': '✅',
            'archived': '📦'
        }
        return format_html(
            '<span class="badge badge-{}">{} {}</span>',
            colors.get(obj.status, 'secondary'),
            icons.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def has_quiz_icon(self, obj):
        if obj.has_quiz:
            return format_html(
                '<span style="color: green; font-size: 18px;" title="Tiene cuestionario">✅</span>'
            )
        return format_html(
            '<span style="color: red; font-size: 18px;" title="Sin cuestionario">❌</span>'
        )
    has_quiz_icon.short_description = 'Quiz'
    
    def word_count_display(self, obj):
        count = obj.word_count()
        return format_html(
            '<span class="badge badge-primary">{} palabras</span>',
            count
        )
    word_count_display.short_description = 'Palabras'
    
    def content_preview(self, obj):
        """Muestra preview del contenido"""
        if obj.content:
            preview = obj.content[:500] + '...' if len(obj.content) > 500 else obj.content
            return format_html(
                '<div style="background: #f4f4f4; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">'
                '<pre style="white-space: pre-wrap; font-size: 12px;">{}</pre>'
                '</div>',
                preview
            )
        return "Sin contenido"
    content_preview.short_description = 'Vista Previa'
    
    def actions_column(self, obj):
        """Columna con botones de acción"""
        buttons = []
        
        # Ver/Editar texto
        view_url = reverse('admin:pdi_texts_pditext_change', args=[obj.pk])
        buttons.append(
            f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Ver/Editar Texto">'
            '<i class="fas fa-edit"></i></a>'
        )
        
        # Botón de Quiz
        if not obj.has_quiz:
            # Si NO tiene quiz: Botón para GENERAR
            generate_url = reverse('admin:pdi_texts_pditext_generate_quiz', args=[obj.pk])
            buttons.append(
                f'<a href="javascript:void(0);" onclick="generateQuiz({obj.pk}, \'{generate_url}\');" '
                f'class="btn btn-sm btn-success" title="Generar Cuestionario" id="quiz-btn-{obj.pk}">'
                '<i class="fas fa-plus-circle"></i> Generar Quiz</a>'  # ✅ CAMBIO AQUÍ: "Quiz" → "Generar Quiz"
            )
        else:
            # Si YA tiene quiz: Botón para VER (redirige al quiz) - NO TOCAR
            try:
                quiz_url = reverse('admin:pdi_texts_initialquiz_change', args=[obj.initial_quiz.pk])
                buttons.append(
                    f'<a href="{quiz_url}" class="btn btn-sm btn-info" title="Ver Cuestionario Generado">'
                    '<i class="fas fa-clipboard-list"></i> <span class="d-none d-lg-inline">Ver Quiz</span></a>'
                )
            except Exception as e:
                # Si hay error al obtener el quiz
                generate_url = reverse('admin:pdi_texts_pditext_generate_quiz', args=[obj.pk])
                buttons.append(
                    f'<a href="javascript:void(0);" onclick="generateQuiz({obj.pk}, \'{generate_url}\');" '
                    f'class="btn btn-sm btn-warning" title="Regenerar Cuestionario (error detectado)" id="quiz-btn-{obj.pk}">'
                    '<i class="fas fa-exclamation-triangle"></i> Re-generar</a>'
                )
        
        return format_html(' '.join(buttons))
    actions_column.short_description = 'Acciones'
    
    # Admin actions
    def activate_texts(self, request, queryset):
        """Activar textos seleccionados"""
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f"✅ {updated} texto(s) activado(s) exitosamente",
            messages.SUCCESS
        )
    activate_texts.short_description = "✅ Activar textos seleccionados"
    
    def archive_texts(self, request, queryset):
        """Archivar textos seleccionados"""
        updated = queryset.update(status='archived')
        self.message_user(
            request,
            f"📦 {updated} texto(s) archivado(s) exitosamente",
            messages.SUCCESS
        )
    archive_texts.short_description = "📦 Archivar textos seleccionados"
    
    def generate_quizzes(self, request, queryset):
        """Generar cuestionarios para textos sin quiz"""
        texts_without_quiz = queryset.filter(has_quiz=False)
        
        if not texts_without_quiz.exists():
            self.message_user(
                request,
                "ℹ️ Todos los textos seleccionados ya tienen cuestionario",
                messages.INFO
            )
            return
        
        count = 0
        for text in texts_without_quiz:
            if text.content and text.content.strip():
                generate_initial_quiz.delay(text.id)
                count += 1
            else:
                self.message_user(
                    request,
                    f"⚠️ '{text.title}' no tiene contenido, se omitió",
                    messages.WARNING
                )
        
        if count > 0:
            self.message_user(
                request,
                f"🚀 Se encolaron {count} tarea(s) para generar cuestionarios. Esto puede tomar varios minutos.",
                messages.SUCCESS
            )
    generate_quizzes.short_description = "🚀 Generar cuestionarios (textos sin quiz)"
    
    def regenerate_quizzes(self, request, queryset):
        """Regenerar cuestionarios (elimina el existente)"""
        count = 0
        for text in queryset:
            if not text.content or text.content.strip() == "":
                self.message_user(
                    request,
                    f"⚠️ '{text.title}' no tiene contenido, se omitió",
                    messages.WARNING
                )
                continue
            
            # Eliminar quiz existente si lo hay
            if hasattr(text, 'initial_quiz'):
                text.initial_quiz.delete()
                text.has_quiz = False
                text.save()
            
            # Generar nuevo
            generate_initial_quiz.delay(text.id)
            count += 1
        
        if count > 0:
            self.message_user(
                request,
                f"🔄 Se encolaron {count} tarea(s) para RE-generar cuestionarios.",
                messages.WARNING
            )
    regenerate_quizzes.short_description = "🔄 RE-generar cuestionarios (sobrescribe existentes)"


@admin.register(InitialQuiz)
class InitialQuizAdmin(admin.ModelAdmin):
    list_display = [
        'quiz_title',
        'text_link',
        'total_questions',
        'model_badge',
        'generation_time_display',
        'created_at',
        'validation_status'
    ]
    
    list_filter = ['model_used', 'created_at']
    
    search_fields = ['text__title']
    
    readonly_fields = [
        'text',
        'total_questions',
        'generation_prompt',
        'generation_time_seconds',
        'model_used',
        'created_at',
        'updated_at',
        'questions_preview',
        'validation_result'
    ]
    
    fieldsets = (
        ('📝 Información del Quiz', {
            'fields': ('text', 'total_questions', 'model_used', 'generation_time_seconds')
        }),
        ('❓ Preguntas (JSON)', {
            'fields': ('questions_json', 'questions_preview')
        }),
        ('🤖 Generación con IA', {
            'fields': ('generation_prompt',),
            'classes': ('collapse',)
        }),
        ('✅ Validación', {
            'fields': ('validation_result',)
        }),
        ('🔍 Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """No permitir crear quizzes manualmente"""
        return False
    
    def quiz_title(self, obj):
        return format_html(
            '<span style="font-size: 14px;"><strong>{}</strong></span>',
            f"Quiz: {obj.text.title}"
        )
    quiz_title.short_description = 'Título del Quiz'
    
    def text_link(self, obj):
        url = reverse('admin:pdi_texts_pditext_change', args=[obj.text.pk])
        return format_html(
            '<a href="{}" class="btn btn-sm btn-outline-primary">'
            '<i class="fas fa-book"></i> Ver Texto</a>',
            url
        )
    text_link.short_description = 'Texto Asociado'
    
    def model_badge(self, obj):
        return format_html(
            '<span class="badge badge-success">{}</span>',
            obj.model_used
        )
    model_badge.short_description = 'Modelo IA'
    
    def generation_time_display(self, obj):
        if obj.generation_time_seconds:
            return format_html(
                '<span class="badge badge-info">{} seg</span>',
                obj.generation_time_seconds
            )
        return '-'
    generation_time_display.short_description = 'Tiempo Gen.'
    
    def questions_preview(self, obj):
        """Muestra las preguntas de forma legible"""
        questions = obj.get_questions()
        
        if not questions:
            return "Sin preguntas"
        
        html = '<div style="max-height: 400px; overflow-y: auto;">'
        
        for i, q in enumerate(questions, 1):
            html += f'''
            <div style="background: #f8f9fa; padding: 15px; margin-bottom: 15px; border-left: 4px solid #007bff; border-radius: 4px;">
                <h4 style="color: #007bff; margin-top: 0;">Pregunta {i}</h4>
                <p style="font-size: 14px; font-weight: bold;">{q.get('pregunta', 'N/A')}</p>
                
                <div style="margin: 10px 0;">
                    <strong>Opciones:</strong>
                    <ul style="margin: 5px 0;">
            '''
            
            for opcion in q.get('opciones', []):
                is_correct = opcion.startswith(q.get('respuesta_correcta', ''))
                color = 'green' if is_correct else 'black'
                icon = '✅' if is_correct else ''
                html += f'<li style="color: {color};">{opcion} {icon}</li>'
            
            html += f'''
                    </ul>
                </div>
                
                <div style="background: #e8f5e9; padding: 8px; border-radius: 4px; margin-top: 10px;">
                    <strong>📌 Tema:</strong> <span class="badge badge-info">{q.get('tema', 'N/A')}</span>
                </div>
                
                <div style="background: #fff3cd; padding: 8px; border-radius: 4px; margin-top: 5px;">
                    <strong>💡 Explicación:</strong> {q.get('explicacion', 'N/A')}
                </div>
            </div>
            '''
        
        html += '</div>'
        
        return format_html(html)
    questions_preview.short_description = 'Vista Previa de Preguntas'
    
    def validation_status(self, obj):
        """Muestra si el quiz tiene estructura válida"""
        is_valid, message = obj.validate_structure()
        
        if is_valid:
            return format_html(
                '<span style="color: green; font-size: 16px;" title="{}">✅</span>',
                message
            )
        return format_html(
            '<span style="color: red; font-size: 16px;" title="{}">❌</span>',
            message
        )
    validation_status.short_description = 'Válido'
    
    def validation_result(self, obj):
        """Resultado detallado de validación"""
        is_valid, message = obj.validate_structure()
        
        color = 'success' if is_valid else 'danger'
        icon = '✅' if is_valid else '❌'
        
        return format_html(
            '<div class="alert alert-{}" role="alert">'
            '<h4 class="alert-heading">{} Validación de Estructura</h4>'
            '<p>{}</p>'
            '</div>',
            color, icon, message
        )
    validation_result.short_description = 'Resultado de Validación'

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'user_email',
        'text_title',
        'attempt_number',
        'score_badge',
        'time_display',
        'created_at'
    ]
    
    list_filter = ['created_at', 'quiz__text']
    search_fields = ['user__email', 'quiz__text__title']
    readonly_fields = ['user', 'quiz', 'attempt_number', 'score', 'answers_json', 'weak_topics', 'time_spent_seconds', 'created_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Usuario'
    
    def text_title(self, obj):
        return obj.quiz.text.title
    text_title.short_description = 'Texto'
    
    def score_badge(self, obj):
        color = 'success' if obj.passed() else 'danger'
        score_formatted = f"{obj.score:.1f}%"
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, score_formatted
        )
    score_badge.short_description = 'Puntuación'
    
    def time_display(self, obj):
        minutes = obj.time_spent_seconds // 60
        seconds = obj.time_spent_seconds % 60
        return f"{minutes}:{seconds:02d}"
    time_display.short_description = 'Tiempo'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'study_streak', 'total_study_time_display', 'last_study_date']
    search_fields = ['user__email']
    readonly_fields = ['user', 'created_at', 'updated_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Usuario'
    
    def total_study_time_display(self, obj):
        hours = obj.total_study_time_minutes // 60
        minutes = obj.total_study_time_minutes % 60
        return f"{hours}h {minutes}min"
    total_study_time_display.short_description = 'Tiempo Total'


# ========================================
# ADMIN PARA TRACKING Y ANALYTICS
# Agregar a app/apps/pdi_texts/admin.py
# ========================================

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render
from django.db.models import Sum, Avg, Count, F, Q
from django.utils import timezone
from datetime import timedelta

from apps.pdi_texts.models import (
    StudySession,
    InteractionEvent,
    SectionTimeTracking,
    HeatmapData
)


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id_short',
        'user_link',
        'material_link',
        'started_at',
        'duration_badge',
        'engagement_badge',
        'interactions_badge',
        'completion_badge',
        'actions_column'
    ]
    
    list_filter = [
        'is_active',
        'completed',
        'exit_type',
        'device_type',
        'browser',
        'started_at'
    ]
    
    search_fields = [
        'user__email',
        'material__text__title',
        'session_id'
    ]
    
    readonly_fields = [
        'session_id',
        'user',
        'material',
        'started_at',
        'ended_at',
        'engagement_score_display',
        'activity_chart',
        'sections_breakdown',
        'heatmap_preview',
        'event_timeline'
    ]
    
    fieldsets = (
        ('📊 Información de Sesión', {
            'fields': (
                'session_id',
                'user',
                'material',
                'started_at',
                'ended_at',
                'is_active',
                'completed'
            )
        }),
        ('⏱️ Métricas de Tiempo', {
            'fields': (
                'total_time_seconds',
                'active_time_seconds',
                'idle_time_seconds',
                'engagement_score_display'
            )
        }),
        ('🖱️ Métricas de Interacción', {
            'fields': (
                'total_interactions',
                'click_events',
                'scroll_events',
                'hover_events',
                'focus_changes',
                'max_scroll_depth'
            )
        }),
        ('📱 Dispositivo', {
            'fields': (
                'device_type',
                'browser',
                'screen_resolution'
            ),
            'classes': ('collapse',)
        }),
        ('📈 Análisis Detallado', {
            'fields': (
                'activity_chart',
                'sections_breakdown',
                'heatmap_preview',
                'event_timeline'
            ),
            'classes': ('wide',)
        })
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'analytics/',
                self.admin_site.admin_view(self.analytics_dashboard_view),
                name='pdi_texts_studysession_analytics',
            ),
            path(
                '<int:session_id>/heatmap/',
                self.admin_site.admin_view(self.heatmap_view),
                name='pdi_texts_studysession_heatmap',
            ),
        ]
        return custom_urls + urls
    
    # ============================================
    # COLUMNAS DE DISPLAY
    # ============================================
    
    def session_id_short(self, obj):
        return format_html(
            '<code style="font-size: 11px;">{}</code>',
            str(obj.session_id)[:8]
        )
    session_id_short.short_description = 'ID'
    
    def user_link(self, obj):
        url = reverse('admin:application_user_user_change', args=[obj.user.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.user.email
        )
    user_link.short_description = 'Usuario'
    
    def material_link(self, obj):
        url = reverse('admin:pdi_texts_userdidacticmaterial_change', args=[obj.material.pk])
        material_type_icon = {
            'flashcard': '📇',
            'decision_tree': '🌳',
            'mind_map': '🧠',
            'summary': '📄'
        }.get(obj.material.material_type, '📚')
        
        return format_html(
            '<a href="{}">{} {}</a>',
            url,
            material_type_icon,
            obj.material.text.title[:30]
        )
    material_link.short_description = 'Material'
    
    def duration_badge(self, obj):
        duration_formatted = obj.duration_formatted()
        active_pct = obj.active_percentage()
        
        color = 'success' if active_pct >= 70 else 'warning' if active_pct >= 50 else 'danger'
        
        return format_html(
            '<span class="badge badge-{}" title="{}% activo">{}</span>',
            color,
            round(active_pct, 1),
            duration_formatted
        )
    duration_badge.short_description = 'Duración'
    
    def engagement_badge(self, obj):
        score = obj.engagement_score()
        
        if score >= 80:
            color = 'success'
            icon = '🔥'
        elif score >= 60:
            color = 'info'
            icon = '✅'
        elif score >= 40:
            color = 'warning'
            icon = '⚠️'
        else:
            color = 'danger'
            icon = '❌'
        
        return format_html(
            '<span class="badge badge-{}" style="font-size: 14px;">{} {}</span>',
            color, icon, round(score, 1)
        )
    engagement_badge.short_description = 'Engagement'
    
    def interactions_badge(self, obj):
        return format_html(
            '<span class="badge badge-primary">{}</span>',
            obj.total_interactions
        )
    interactions_badge.short_description = 'Interacciones'
    
    def completion_badge(self, obj):
        if obj.completed:
            return format_html('<span class="badge badge-success">✓ Completó</span>')
        else:
            return format_html(
                '<span class="badge badge-secondary">{:.0f}% leído</span>',
                obj.max_scroll_depth
            )
    completion_badge.short_description = 'Completitud'
    
    def actions_column(self, obj):
        heatmap_url = reverse('admin:pdi_texts_studysession_heatmap', args=[obj.pk])
        return format_html(
            '<a href="{}" class="btn btn-sm btn-info" target="_blank">'
            '<i class="fas fa-fire"></i> Ver Heatmap</a>',
            heatmap_url
        )
    actions_column.short_description = 'Acciones'
    
    # ============================================
    # CAMPOS READONLY CON VISUALIZACIONES
    # ============================================
    
    def engagement_score_display(self, obj):
        score = obj.engagement_score()
        
        # Crear barra de progreso
        color = 'success' if score >= 70 else 'warning' if score >= 50 else 'danger'
        
        return format_html(
            '''
            <div class="progress" style="height: 25px;">
                <div class="progress-bar bg-{}" role="progressbar" 
                     style="width: {}%;" aria-valuenow="{}" 
                     aria-valuemin="0" aria-valuemax="100">
                    <strong>{:.1f}%</strong>
                </div>
            </div>
            <small class="text-muted">
                Basado en tiempo activo, interacciones, scroll depth y completitud
            </small>
            ''',
            color, score, score, score
        )
    engagement_score_display.short_description = 'Score de Engagement'
    
    def activity_chart(self, obj):
        """Gráfico de actividad a lo largo de la sesión"""
        events = obj.events.all().order_by('timestamp')
        
        if not events:
            return format_html('<p class="text-muted">No hay eventos registrados</p>')
        
        # Agrupar eventos por minuto
        event_counts_by_minute = {}
        for event in events:
            minute = int(event.time_since_session_start // 60)
            event_counts_by_minute[minute] = event_counts_by_minute.get(minute, 0) + 1
        
        # Crear HTML para el gráfico simple
        max_events = max(event_counts_by_minute.values()) if event_counts_by_minute else 1
        
        chart_html = '<div style="display: flex; align-items: flex-end; height: 200px; gap: 2px;">'
        
        for minute in range(max(event_counts_by_minute.keys()) + 1):
            count = event_counts_by_minute.get(minute, 0)
            height = (count / max_events) * 180
            
            color = '#28a745' if count > max_events * 0.7 else '#ffc107' if count > max_events * 0.4 else '#dc3545'
            
            chart_html += f'''
                <div style="
                    width: 10px;
                    height: {height}px;
                    background-color: {color};
                    border-radius: 2px;
                    position: relative;
                " title="Minuto {minute}: {count} eventos"></div>
            '''
        
        chart_html += '</div>'
        chart_html += '<p class="text-muted mt-2"><small>Eventos por minuto durante la sesión</small></p>'
        
        return format_html(chart_html)
    activity_chart.short_description = 'Gráfico de Actividad'
    
    def sections_breakdown(self, obj):
        """Desglose de tiempo por sección"""
        sections = obj.section_times.all().order_by('-total_time_seconds')[:10]
        
        if not sections:
            return format_html('<p class="text-muted">No hay datos de secciones</p>')
        
        total_time = sum(s.total_time_seconds for s in sections)
        
        html = '<table class="table table-sm table-striped">'
        html += '''
            <thead>
                <tr>
                    <th>Sección</th>
                    <th>Tipo</th>
                    <th>Tiempo</th>
                    <th>% Total</th>
                    <th>Vistas</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for section in sections:
            percentage = (section.total_time_seconds / total_time) * 100 if total_time > 0 else 0
            
            section_type_icon = {
                'weak_section': '🔴',
                'review_section': '🟢',
                'flashcard': '📇',
                'tree_node': '🌳',
                'comparison_table': '📊'
            }.get(section.section_type, '📄')
            
            html += f'''
                <tr>
                    <td><small>{section.section_id[:30]}</small></td>
                    <td>{section_type_icon} {section.get_section_type_display()}</td>
                    <td><strong>{section.total_time_seconds:.1f}s</strong></td>
                    <td>
                        <div class="progress" style="height: 15px; width: 60px;">
                            <div class="progress-bar" style="width: {percentage}%"></div>
                        </div>
                    </td>
                    <td><span class="badge badge-info">{section.view_count}</span></td>
                </tr>
            '''
        
        html += '</tbody></table>'
        
        return format_html(html)
    sections_breakdown.short_description = 'Desglose por Sección'
    
    def heatmap_preview(self, obj):
        """Preview del heatmap"""
        heatmap = obj.heatmap_data.first()
        
        if not heatmap:
            return format_html('<p class="text-muted">No hay datos de heatmap</p>')
        
        clicks_count = len(heatmap.clicks)
        hot_zones_count = len(heatmap.hot_zones)
        
        html = f'''
            <div class="card">
                <div class="card-body">
                    <h5>📍 {clicks_count} clics registrados</h5>
                    <h5>🔥 {hot_zones_count} zonas calientes detectadas</h5>
                    <a href="{reverse('admin:pdi_texts_studysession_heatmap', args=[obj.pk])}" 
                       class="btn btn-primary btn-sm mt-2" target="_blank">
                        Ver Heatmap Completo
                    </a>
                </div>
            </div>
        '''
        
        return format_html(html)
    heatmap_preview.short_description = 'Heatmap'
    
    def event_timeline(self, obj):
        """Timeline de eventos importantes"""
        events = obj.events.filter(
            event_type__in=['flashcard_flip', 'node_expand', 'copy_text', 'tab_hidden', 'tab_visible']
        ).order_by('timestamp')[:50]
        
        if not events:
            return format_html('<p class="text-muted">No hay eventos destacados</p>')
        
        html = '<div class="timeline" style="max-height: 400px; overflow-y: auto;">'
        
        for event in events:
            icon = {
                'flashcard_flip': '📇',
                'node_expand': '🌳',
                'copy_text': '📋',
                'tab_hidden': '👁️',
                'tab_visible': '👀'
            }.get(event.event_type, '•')
            
            html += f'''
                <div class="mb-2 p-2" style="border-left: 3px solid #007bff;">
                    <strong>{icon} {event.get_event_type_display()}</strong>
                    <span class="text-muted"> @ {event.time_since_session_start:.0f}s</span>
                    <br>
                    <small>{event.element_text[:100] if event.element_text else ''}</small>
                </div>
            '''
        
        html += '</div>'
        
        return format_html(html)
    event_timeline.short_description = 'Timeline de Eventos'
    
    # ============================================
    # VISTAS PERSONALIZADAS
    # ============================================
    
    def analytics_dashboard_view(self, request):
        """Dashboard general de analytics"""
        
        # Filtros de tiempo
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Sesiones totales
        total_sessions = StudySession.objects.filter(is_active=False).count()
        sessions_this_week = StudySession.objects.filter(
            started_at__gte=week_ago,
            is_active=False
        ).count()
        
        # Tiempo total de estudio
        total_study_time = StudySession.objects.filter(
            is_active=False
        ).aggregate(total=Sum('total_time_seconds'))['total'] or 0
        
        # Promedio de engagement
        avg_engagement = StudySession.objects.filter(
            is_active=False,
            total_time_seconds__gt=0
        ).aggregate(
            avg=Avg(F('active_time_seconds') * 100.0 / F('total_time_seconds'))
        )['avg'] or 0
        
        # Top usuarios más activos
        top_users = StudySession.objects.filter(
            is_active=False
        ).values(
            'user__email',
            'user__first_name',
            'user__last_name'
        ).annotate(
            total_sessions=Count('id'),
            total_time=Sum('total_time_seconds'),
            avg_engagement=Avg(F('active_time_seconds') * 100.0 / F('total_time_seconds'))
        ).order_by('-total_time')[:10]
        
        # Materiales más estudiados
        top_materials = StudySession.objects.filter(
            is_active=False
        ).values(
            'material__text__title',
            'material__material_type'
        ).annotate(
            total_sessions=Count('id'),
            avg_completion=Avg('max_scroll_depth')
        ).order_by('-total_sessions')[:10]
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Analytics Dashboard',
            'total_sessions': total_sessions,
            'sessions_this_week': sessions_this_week,
            'total_study_time_hours': round(total_study_time / 3600, 2),
            'avg_engagement': round(avg_engagement, 2),
            'top_users': top_users,
            'top_materials': top_materials
        }
        
        return render(request, 'admin/tracking/analytics_dashboard.html', context)
    
    def heatmap_view(self, request, session_id):
        """Vista del heatmap interactivo"""
        session = StudySession.objects.get(pk=session_id)
        heatmap = session.heatmap_data.first()
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Heatmap - Sesión {str(session.session_id)[:8]}',
            'session': session,
            'heatmap': heatmap
        }
        
        return render(request, 'admin/tracking/heatmap_view.html', context)


@admin.register(InteractionEvent)
class InteractionEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_type',
        'session_link',
        'time_display',
        'element_preview',
        'timestamp'
    ]
    
    list_filter = ['event_type', 'timestamp']
    search_fields = ['session__session_id', 'element_text']
    readonly_fields = ['session', 'event_type', 'timestamp', 'metadata']
    
    def session_link(self, obj):
        url = reverse('admin:pdi_texts_studysession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">Sesión {}</a>',
            url,
            str(obj.session.session_id)[:8]
        )
    session_link.short_description = 'Sesión'
    
    def time_display(self, obj):
        return f"{obj.time_since_session_start:.1f}s"
    time_display.short_description = 'Tiempo'
    
    def element_preview(self, obj):
        if obj.element_text:
            return obj.element_text[:50] + '...' if len(obj.element_text) > 50 else obj.element_text
        return '-'
    element_preview.short_description = 'Elemento'


@admin.register(SectionTimeTracking)
class SectionTimeTrackingAdmin(admin.ModelAdmin):
    list_display = [
        'section_id',
        'section_type',
        'session_link',
        'time_display',
        'view_count',
        'fully_read_badge'
    ]
    
    list_filter = ['section_type', 'fully_read']
    search_fields = ['section_id', 'section_content_preview']
    
    def session_link(self, obj):
        url = reverse('admin:pdi_texts_studysession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">Ver Sesión</a>',
            url
        )
    session_link.short_description = 'Sesión'
    
    def time_display(self, obj):
        return f"{obj.total_time_seconds:.1f}s"
    time_display.short_description = 'Tiempo'
    
    def fully_read_badge(self, obj):
        if obj.fully_read:
            return format_html('<span class="badge badge-success">✓</span>')
        return format_html('<span class="badge badge-secondary">-</span>')
    fully_read_badge.short_description = 'Leído'


@admin.register(HeatmapData)
class HeatmapDataAdmin(admin.ModelAdmin):
    list_display = [
        'session_link',
        'data_points_badge',
        'clicks_count',
        'hot_zones_count',
        'captured_at'
    ]
    
    readonly_fields = ['session', 'clicks', 'mouse_movements', 'scroll_points', 'hot_zones']
    
    def session_link(self, obj):
        url = reverse('admin:pdi_texts_studysession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">Sesión {}</a>',
            url,
            str(obj.session.session_id)[:8]
        )
    session_link.short_description = 'Sesión'
    
    def data_points_badge(self, obj):
        return format_html(
            '<span class="badge badge-info">{}</span>',
            obj.data_points_count
        )
    data_points_badge.short_description = 'Puntos de Datos'
    
    def clicks_count(self, obj):
        return len(obj.clicks)
    clicks_count.short_description = 'Clics'
    
    def hot_zones_count(self, obj):
        return len(obj.hot_zones)
    hot_zones_count.short_description = 'Zonas Calientes'