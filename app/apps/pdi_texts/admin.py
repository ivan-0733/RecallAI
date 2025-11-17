from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Sum, Avg, Count, F, Q
from django.utils import timezone
from datetime import timedelta

from apps.pdi_texts.models import (
    PDIText, InitialQuiz, QuizAttempt, UserProfile,
    UserDidacticMaterial, MaterialRequest, MaterialEffectiveness,
    StudySession, InteractionEvent, SectionTimeTracking, HeatmapData
)
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
        ('📊 Estadísticas', {
            'fields': ('word_count_display', 'estimated_time_minutes'),
            'classes': ('collapse',)
        }),
        ('🔍 Metadata', {
            'fields': ('has_quiz', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_texts', 'deactivate_texts', 'mark_as_published']
    
    # Mostrar campos read-only con formato
    def content_preview(self, obj):
        """Muestra preview del contenido"""
        if obj.content:
            preview = obj.content[:500] + '...' if len(obj.content) > 500 else obj.content
            return format_html(
                '<div style="white-space: pre-wrap; max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f9f9f9;">{}</div>',
                preview
            )
        return '(Sin contenido)'
    content_preview.short_description = 'Preview del Contenido'
    
    def title_with_icon(self, obj):
        """Título con icono según difficulty"""
        icons = {
            'beginner': '🟢',
            'intermediate': '🟡',
            'advanced': '🔴'
        }
        icon = icons.get(obj.difficulty, '📄')
        return format_html('{} {}', icon, obj.title)
    title_with_icon.short_description = 'Título'
    
    def topic_badge(self, obj):
        """Badge con el topic"""
        return format_html(
            '<span class="badge" style="background: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            obj.topic
        )
    topic_badge.short_description = 'Tema'
    
    def difficulty_badge(self, obj):
        """Badge con la dificultad"""
        colors = {
            'beginner': '#28a745',
            'intermediate': '#ffc107',
            'advanced': '#dc3545'
        }
        color = colors.get(obj.difficulty, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_difficulty_display()
        )
    difficulty_badge.short_description = 'Dificultad'
    
    def status_badge(self, obj):
        """Badge con el status"""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'draft': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        icons = {
            'active': '✅',
            'inactive': '⏸️',
            'draft': '📝'
        }
        icon = icons.get(obj.status, '❓')
        return format_html(
            '{} <span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            icon, color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def has_quiz_icon(self, obj):
        """Icono si tiene quiz"""
        if obj.has_quiz:
            return format_html('<span style="font-size: 20px;" title="Tiene cuestionario">✅</span>')
        return format_html('<span style="font-size: 20px;" title="Sin cuestionario">❌</span>')
    has_quiz_icon.short_description = 'Quiz'
    
    def word_count_display(self, obj):
        """Contador de palabras formateado"""
        if not obj.content:
            return '0 palabras'
        
        word_count = len(obj.content.split())
        return format_html(
            '<strong>{}</strong> palabras',
            word_count
        )
    word_count_display.short_description = 'Palabras'
    
    def actions_column(self, obj):
        """Botones de acción"""
        buttons = []
        
        # Botón para ver el texto (frontend)
        view_url = f'/texts/{obj.pk}/'
        buttons.append(
            f'<a href="{view_url}" class="btn btn-sm btn-primary" target="_blank" title="Ver en frontend">'
            '<i class="fas fa-eye"></i> <span class="d-none d-lg-inline">Ver</span></a>'
        )
        
        # Botón para generar/ver quiz
        if not obj.has_quiz:
            # Si NO tiene quiz: Botón para GENERAR (con loading en JS)
            generate_url = reverse('admin:pdi_texts_pditext_generate_quiz', args=[obj.pk])
            buttons.append(
                f'<a href="javascript:void(0);" onclick="generateQuiz({obj.pk}, \'{generate_url}\');" '
                f'class="btn btn-sm btn-success" title="Generar Cuestionario" id="quiz-btn-{obj.pk}">'
                '<i class="fas fa-plus-circle"></i> Generar Quiz</a>'
            )
        else:
            # Si YA tiene quiz: Botón para VER (redirige al quiz)
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
            f'{updated} texto(s) activado(s) correctamente.',
            messages.SUCCESS
        )
    activate_texts.short_description = 'Activar textos seleccionados'
    
    def deactivate_texts(self, request, queryset):
        """Desactivar textos seleccionados"""
        updated = queryset.update(status='inactive')
        self.message_user(
            request,
            f'{updated} texto(s) desactivado(s) correctamente.',
            messages.SUCCESS
        )
    deactivate_texts.short_description = 'Desactivar textos seleccionados'
    
    def mark_as_published(self, request, queryset):
        """Marcar como publicado"""
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f'{updated} texto(s) marcado(s) como publicado(s).',
            messages.SUCCESS
        )
    mark_as_published.short_description = 'Marcar como publicado'
    
    # Sobrescribir save_model para extraer texto de PDF/TXT
    def save_model(self, request, obj, form, change):
        """Extraer texto automáticamente si se sube archivo"""
        if obj.file:
            try:
                file_ext = obj.file.name.split('.')[-1].lower()
                
                if file_ext == 'pdf':
                    extracted_text = extract_text_from_pdf(obj.file.path)
                elif file_ext == 'txt':
                    extracted_text = extract_text_from_txt(obj.file.path)
                else:
                    extracted_text = None
                
                if extracted_text:
                    obj.content = extracted_text
                    self.message_user(
                        request,
                        f'✅ Texto extraído automáticamente del archivo ({len(extracted_text)} caracteres)',
                        messages.SUCCESS
                    )
            except Exception as e:
                self.message_user(
                    request,
                    f'❌ Error al extraer texto: {str(e)}',
                    messages.ERROR
                )
        
        # Guardar sin generar el usuario automáticamente
        if not change:  # Solo al crear
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change)
    
    # URLs personalizadas
    def get_urls(self):
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
        """Vista para generar cuestionario asíncronamente"""
        text = get_object_or_404(PDIText, pk=text_id)
        
        if text.has_quiz:
            return JsonResponse({
                'status': 'error',
                'message': 'Este texto ya tiene un cuestionario'
            }, status=400)
        
        # Lanzar tarea asíncrona
        task = generate_initial_quiz.delay(text_id)
        
        return JsonResponse({
            'status': 'success',
            'message': f'Generando cuestionario para "{text.title}"...',
            'task_id': task.id
        })
    
    # JavaScript inline para botones
    class Media:
        js = ('admin/js/quiz_generator.js',)


@admin.register(InitialQuiz)
class InitialQuizAdmin(admin.ModelAdmin):
    list_display = [
        'text_title',
        'questions_count',
        'validation_status',
        'created_at_formatted',
        'questions_preview'
    ]
    
    list_filter = ['text__topic', 'text__difficulty', 'created_at']
    search_fields = ['text__title', 'questions']
    
    readonly_fields = [
        'text',
        'questions',
        'created_at',
        'questions_preview',
        'validation_result'
    ]
    
    fieldsets = (
        ('📋 Información', {
            'fields': ('text', 'created_at')
        }),
        ('❓ Preguntas', {
            'fields': ('questions', 'questions_preview', 'validation_result'),
            'description': 'Las preguntas están en formato JSON. Usa el botón de preview para visualizarlas mejor.'
        }),
    )
    
    def text_title(self, obj):
        return obj.text.title
    text_title.short_description = 'Texto'
    
    def questions_count(self, obj):
        """Contador de preguntas"""
        try:
            count = len(obj.questions.get('questions', []))
            return format_html(
                '<span class="badge badge-primary">{} preguntas</span>',
                count
            )
        except:
            return format_html('<span class="badge badge-danger">Error en JSON</span>')
    questions_count.short_description = 'Total'
    
    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_formatted.short_description = 'Creado'
    
    def questions_preview(self, obj):
        """Vista previa de las preguntas en formato HTML"""
        try:
            questions = obj.questions.get('questions', [])
            
            if not questions:
                return format_html('<p class="text-muted">No hay preguntas disponibles</p>')
            
            html = '<div style="max-height: 600px; overflow-y: auto;">'
            
            for idx, q in enumerate(questions, 1):
                html += f'''
                <div class="card mb-3" style="border: 1px solid #ddd;">
                    <div class="card-header" style="background: #f5f5f5; font-weight: bold;">
                        Pregunta {idx} - Tema: {q.get('tema', 'N/A')}
                    </div>
                    <div class="card-body">
                        <p style="font-weight: bold; margin-bottom: 10px;">{q.get('pregunta', '')}</p>
                        
                        <div class="list-group">
                '''
                
                opciones = q.get('opciones', [])
                respuesta_correcta = q.get('respuesta_correcta', '')
                
                for letra, opcion in zip(['A', 'B', 'C', 'D'], opciones):
                    is_correct = (letra == respuesta_correcta)
                    color = 'success' if is_correct else 'light'
                    icon = '✅' if is_correct else ''
                    
                    html += f'''
                        <div class="list-group-item list-group-item-{color}">
                            {icon} <strong>{letra})</strong> {opcion}
                        </div>
                    '''
                
                html += f'''
                        </div>
                        <div class="alert alert-info mt-3" style="margin-bottom: 0;">
                            <strong>Explicación:</strong> {q.get('explicacion', 'N/A')}
                        </div>
                    </div>
                </div>
                '''
            
            html += '</div>'
            
            return format_html(html)
        
        except Exception as e:
            return format_html(
                '<div class="alert alert-danger">Error al mostrar preview: {}</div>',
                str(e)
            )
   
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


# ==========================================================================
#  NUEVO: ADMIN CENTRALIZADO PARA MATERIAL DIDÁCTICO (TRACKING ACUMULADO)
# ==========================================================================

@admin.register(UserDidacticMaterial)
class UserDidacticMaterialAdmin(admin.ModelAdmin):
    list_display = [
        'material_type_badge',
        'user_link',
        'text_link',
        'stats_summary_columns',
        'created_at_formatted',
        'was_effective_icon'
    ]
    
    list_filter = ['material_type', 'was_effective', 'requested_at', 'text__title']
    search_fields = ['user__email', 'text__title', 'weak_topics']
    
    # ✅ CORRECCIÓN PROBLEMA 5: Eliminar acción de eliminar por defecto de Django
    # Acción para eliminar solo el material y no el intento de quiz
    actions = ['delete_selected_materials_only']
    
    def get_actions(self, request):
        """
        Sobrescribir para remover la acción 'delete_selected' de Django
        y dejar solo nuestra acción personalizada
        """
        actions = super().get_actions(request)
        # Eliminar la acción por defecto de Django
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    readonly_fields = [
        'analytics_dashboard_panel', # <--- AQUÍ ESTÁ TU PANEL CENTRALIZADO
        'html_content_preview',
        'associated_quiz_link_detailed', # <--- Enlace detallado
        'user',
        'text',
        'attempt'
    ]
    
    fieldsets = (
        ('📊 PANEL DE CONTROL & ANALÍTICA', {
            'fields': ('analytics_dashboard_panel',),
            'classes': ('wide',),
            'description': 'Resumen total de actividad para este material específico.'
        }),
        ('📋 Información del Material', {
            'fields': ('user', 'text', 'material_type', 'requested_at', 'generated_at', 'generation_time_seconds')
        }),
        ('🔗 Quiz de Origen', {
            'fields': ('attempt', 'associated_quiz_link_detailed'),
            'description': 'El intento de quiz que originó este material didáctico.'
        }),
        ('📝 Contenido HTML', {
            'fields': ('html_content_preview',),
            'classes': ('collapse',)
        }),
        ('🎯 Temas Enfocados', {
            'fields': ('weak_topics',),
            'classes': ('collapse',)
        }),
        ('✅ Efectividad', {
            'fields': ('was_effective',),
        })
    )

    # --- COLUMNAS DE DISPLAY ---

    def material_type_badge(self, obj):
        badges = {
            'flashcard': ('📇', 'info', 'Flashcards'),
            'decision_tree': ('🌳', 'success', 'Mapa Conceptual'),
            'mind_map': ('🧠', 'primary', 'Mapa Mental'),
            'summary': ('📄', 'secondary', 'Resumen')
        }
        icon, color, label = badges.get(obj.material_type, ('📚', 'secondary', 'Desconocido'))
        return format_html(
            '{} <span class="badge badge-{}">{}</span>',
            icon, color, label
        )
    material_type_badge.short_description = 'Tipo'

    def user_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:application_user_user_change', args=[obj.user.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.user.email
        )
    user_link.short_description = 'Usuario'

    def text_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:pdi_texts_pditext_change', args=[obj.text.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.text.title[:40]
        )
    text_link.short_description = 'Texto'

    def stats_summary_columns(self, obj):
        """
        Muestra las stats acumuladas en formato compacto de columnas.
        """
        stats = obj.get_aggregated_stats()
        
        # Formatear tiempos
        def format_time(seconds):
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}m {secs}s"
        
        total_time_fmt = format_time(stats['total_time'])
        active_time_fmt = format_time(stats['active_time'])
        
        # Colores para completion
        completion_color = 'green' if stats['avg_completion'] > 70 else 'orange'
        
        html = f"""
        <div style="display: flex; gap: 15px; align-items: center;">
            <div style="text-align: center;">
                <div style="font-size: 0.75em; color: #666;">Sesiones</div>
                <div style="font-weight: bold; font-size: 1.1em;">{stats['total_sessions']}</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75em; color: #666;">Tiempo Total</div>
                <div style="font-weight: bold; font-size: 1.1em;">{total_time_fmt}</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75em; color: #666;">Tiempo Activo</div>
                <div style="font-weight: bold; font-size: 1.1em;">{active_time_fmt}</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75em; color: #666;">Interacciones</div>
                <div style="font-weight: bold; font-size: 1.1em;">{stats['total_interactions']}</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75em; color: #666;">Completado</div>
                <div style="font-weight: bold; font-size: 1.1em; color: {completion_color};">{stats['avg_completion']:.0f}%</div>
            </div>
        </div>
        """
        return format_html(html)
    stats_summary_columns.short_description = 'Estadísticas Acumuladas'

    def created_at_formatted(self, obj):
        return obj.requested_at.strftime('%d/%m/%Y %H:%M')
    created_at_formatted.short_description = 'Creado'

    def was_effective_icon(self, obj):
        if obj.was_effective is None:
            return format_html('<span style="font-size: 18px;" title="Sin evaluar">❔</span>')
        elif obj.was_effective:
            return format_html('<span style="font-size: 18px;" title="Efectivo">✅</span>')
        else:
            return format_html('<span style="font-size: 18px;" title="No efectivo">❌</span>')
    was_effective_icon.short_description = 'Efectivo'

    # --- READONLY FIELD CUSTOM ---

    def analytics_dashboard_panel(self, obj):
        """
        Calcula y reúne TODA la información de tracking de todas las sesiones.
        """
        # Obtener todas las sesiones asociadas
        sessions = obj.study_sessions.all().order_by('-started_at')
        total_sessions = sessions.count()
        
        # Calcular agregados (Totales)
        aggregates = sessions.aggregate(
            total_time=Sum('total_time_seconds'),
            total_active=Sum('active_time_seconds'),
            total_interactions=Sum('total_interactions'),
            total_clicks=Sum('click_events'),
            total_scrolls=Sum('scroll_events')
        )
        
        # Usar 'or 0' para manejar casos donde la suma es None (sin sesiones)
        total_time = aggregates['total_time'] or 0
        total_active = aggregates['total_active'] or 0
        total_interactions = aggregates['total_interactions'] or 0
        total_clicks = aggregates['total_clicks'] or 0
        total_scrolls = aggregates['total_scrolls'] or 0
        
        # Calcular promedios y porcentajes
        avg_completion = 0
        avg_engagement = 0
        
        if total_sessions > 0:
            total_depth = sum((s.max_scroll_depth or 0) for s in sessions)
            avg_completion = total_depth / total_sessions
            
            total_engagement = sum(s.engagement_score() for s in sessions)
            avg_engagement = total_engagement / total_sessions
        
        # Colores para métricas
        engagement_color = '#28a745' if avg_completion > 70 else '#ffc107'
        score_color = '#28a745' if avg_engagement > 70 else '#ffc107' if avg_engagement > 40 else '#dc3545'
        
        html = f"""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #ddd;">
            
            <div style="display: flex; justify-content: space-between; margin-bottom: 20px; border-bottom: 2px solid #eee; padding-bottom: 10px;">
                <div>
                    <h2 style="margin:0; color: #333;">{obj.get_material_type_display()} de {obj.user.first_name} {obj.user.last_name}</h2>
                    <p style="margin:5px 0 0 0; color: #555; font-weight:bold;">
                        📚 Origen: {obj.text.title} (Quiz)
                    </p>
                    <p style="margin:0; color: #666; font-size: 0.9em;">
                        Creado el {obj.requested_at.strftime('%d/%m/%Y a las %H:%M')}
                    </p>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 3em;">📊</span>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #007bff;">{total_sessions}</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Sesiones Totales</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #17a2b8;">{total_time // 60}m {total_time % 60}s</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Tiempo Total</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #28a745;">{total_active // 60}m {total_active % 60}s</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Tiempo Activo</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #6c757d;">{total_interactions}</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Interacciones</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: {engagement_color};">{avg_completion:.1f}%</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Completitud Prom.</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: {score_color};">{avg_engagement:.1f}</div>
                    <div style="color: #666; text-transform: uppercase; font-size: 0.7em;">Engagement Prom.</div>
                </div>
            </div>
            
            <div style="background: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 25px; font-size: 0.9em; border-left: 5px solid #17a2b8;">
                <h4 style="margin-top: 0; color: #0c5460;">ℹ️ Guía de Métricas</h4>
                <ul style="margin-bottom: 0; padding-left: 20px;">
                    <li style="margin-bottom: 8px;"><strong>Interacciones:</strong> Suma total de eventos activos del usuario sobre el material, incluyendo clics, scrolls, movimientos de mouse (hovers) y cambios de foco en la ventana.</li>
                    <li style="margin-bottom: 8px;"><strong>Completado (100%):</strong> Se considera completado cuando se cumplen las siguientes reglas según el tipo de material:
                        <ul style="margin-top: 5px;">
                            <li><em>Resumen Estructurado:</em> El usuario ha llegado (scrolleado) hasta el final del texto generado.</li>
                            <li><em>Mapas Conceptuales / Árboles:</em> El usuario ha expandido todos los nodos interactivos hasta el último nivel.</li>
                            <li><em>Flashcards:</em> El usuario ha recorrido y volteado (flip) las 20 tarjetas del set.</li>
                        </ul>
                    </li>
                    <li><strong>Score de Engagement (0-100):</strong> Índice calculado combinando métricas ponderadas:
                        <br><code>Score = (TiempoActivo/5min * 40) + (Interacciones/50 * 30) + (ProfundidadScroll * 0.2) + (Si Completó * 10)</code>
                        <br><em>Nota: El tiempo activo se satura a los 5 minutos (300s) y las interacciones a 50 eventos.</em>
                    </li>
                </ul>
            </div>

            <h3 style="margin-bottom: 10px; color: #444;">Historial de Sesiones de Estudio</h3>
        """
        
        if sessions.exists():
            html += """
            <table style="width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <thead>
                    <tr style="background: #343a40; color: white;">
                        <th style="padding: 10px; text-align: left;">Fecha</th>
                        <th style="padding: 10px; text-align: center;">Duración</th>
                        <th style="padding: 10px; text-align: center;">Activo</th>
                        <th style="padding: 10px; text-align: center;">Interacciones</th>
                        <th style="padding: 10px; text-align: center;">Completado</th>
                        <th style="padding: 10px; text-align: center;">Engagement</th>
                        <th style="padding: 10px; text-align: right;">Acciones</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for sess in sessions:
                sess_date = sess.started_at.strftime('%d/%m/%Y %H:%M')
                sess_duration = f"{sess.total_time_seconds // 60}m {sess.total_time_seconds % 60}s"
                sess_active = f"{sess.active_time_seconds // 60}m {sess.active_time_seconds % 60}s"
                sess_interactions = sess.total_interactions
                scroll_depth = sess.max_scroll_depth or 0
                sess_score = sess.engagement_score()
                sess_score_color = '#28a745' if sess_score > 70 else '#ffc107' if sess_score > 40 else '#dc3545'
                
                sess_link = reverse('admin:pdi_texts_studysession_change', args=[sess.pk])
                
                # Enlace al heatmap si existe
                heatmap_link = ''
                if sess.heatmap_data.exists():
                    heatmap_url = reverse('admin:pdi_texts_studysession_heatmap', args=[sess.pk])
                    heatmap_link = f'<a href="{heatmap_url}" style="text-decoration: none;" title="Ver Heatmap">🔥</a>'
                
                html += f"""
                    <tr style="border-bottom: 1px solid #dee2e6;">
                        <td style="padding: 8px;">{sess_date}</td>
                        <td style="padding: 8px; text-align: center;">{sess_duration}</td>
                        <td style="padding: 8px; text-align: center;">{sess_active}</td>
                        <td style="padding: 8px; text-align: center;"><strong>{sess_interactions}</strong></td>
                        <td style="padding: 8px; text-align: center;">
                            <div style="background: #e9ecef; border-radius: 4px; height: 6px; width: 50px; display: inline-block; vertical-align: middle;">
                                <div style="background: #28a745; height: 100%; border-radius: 4px; width: {scroll_depth}%;"></div>
                            </div>
                            <span style="font-size:0.8em; margin-left:5px;">{scroll_depth:.0f}%</span>
                        </td>
                        <td style="padding: 8px; text-align: center;">
                            <span style="color: {sess_score_color}; font-weight: bold;">{sess_score:.1f}</span>
                        </td>
                        <td style="padding: 8px; text-align: right;">
                            {heatmap_link}
                            <a href="{sess_link}" style="text-decoration: none;">🔍</a>
                        </td>
                    </tr>
                """
        else:
            html += '<tr><td colspan="6" style="padding: 15px; text-align: center; color: #999;">El alumno aún no ha estudiado este material.</td></tr>'

        html += """
                </tbody>
            </table>
        </div>
        """
        return format_html(html)
    
    analytics_dashboard_panel.short_description = "Panel de Analítica"

    # --- CAMPOS READONLY AUXILIARES ---

    def associated_quiz_link_detailed(self, obj):
        url = reverse('admin:pdi_texts_quizattempt_change', args=[obj.attempt.pk])
        return format_html(
            '<div>'
            '<strong>Quiz Origen:</strong> {}<br>'
            '<a href="{}" class="button" style="margin-top:5px;">📄 Ver Intento ({:.1f}%)</a>'
            '</div>',
            obj.text.title,
            url, 
            obj.attempt.score
        )
    associated_quiz_link_detailed.short_description = "Quiz Origen"

    def html_content_preview(self, obj):
        return format_html(
            '<div style="border:1px solid #ccc; padding:10px; max-height:200px; overflow:auto;">{}</div>',
            obj.html_content
        )
    html_content_preview.short_description = "Preview HTML"

    # --- ACCIONES PERSONALIZADAS ---

    def delete_selected_materials_only(self, request, queryset):
        """
        Elimina el material didáctico seleccionado PERO preserva el QuizAttempt.
        """
        count = queryset.count()
        for material in queryset:
            material.delete()
        
        self.message_user(request, f"✅ Se eliminaron {count} materiales didácticos. Los intentos de quiz (QuizAttempt) permanecen intactos.", messages.SUCCESS)
    
    delete_selected_materials_only.short_description = "🗑️ Eliminar SOLO Material Didáctico (Preservar Quiz)"


# ==========================================================================
#  ADMIN DE STUDY SESSION (OCULTO DEL MENU PERO ACCESIBLE)
# ==========================================================================

@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        """
        Ocultar del menú principal del admin (pero mantener URLs accesibles).
        """
        return {}

    list_display = [
        'session_id_short',
        'user_link',
        'material_link',  # <--- Enlace corregido
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
        # Al haber registrado UserDidacticMaterialAdmin, este reverse ahora SÍ funciona
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
            '{} <span class="badge badge-{}">{:.1f}</span>',
            icon, color, score
        )
    engagement_badge.short_description = 'Engagement'
    
    def interactions_badge(self, obj):
        return format_html(
            '<span class="badge badge-primary">{}</span>',
            obj.total_interactions
        )
    interactions_badge.short_description = 'Interacciones'
    
    def completion_badge(self, obj):
        scroll_depth = obj.max_scroll_depth or 0
        
        if scroll_depth >= 90:
            icon = '✅'
            color = 'success'
        elif scroll_depth >= 70:
            icon = '🟡'
            color = 'warning'
        else:
            icon = '🔴'
            color = 'danger'
        
        return format_html(
            '{} <span class="badge badge-{}">{:.0f}%</span>',
            icon, color, scroll_depth
        )
    completion_badge.short_description = 'Completado'
    
    def actions_column(self, obj):
        """Botones de acción"""
        buttons = []
        
        # Botón para ver heatmap (si existe)
        if obj.heatmap_data.exists():
            heatmap_url = reverse('admin:pdi_texts_studysession_heatmap', args=[obj.pk])
            buttons.append(
                f'<a href="{heatmap_url}" class="btn btn-sm btn-danger" target="_blank" title="Ver Heatmap">'
                '🔥 Heatmap</a>'
            )
        
        return format_html(' '.join(buttons) if buttons else '—')
    actions_column.short_description = 'Acciones'
    
    # ============================================
    # READONLY FIELDS DETALLADOS
    # ============================================
    
    def engagement_score_display(self, obj):
        score = obj.engagement_score()
        
        if score >= 80:
            color = '#28a745'
            label = 'Excelente'
            icon = '🔥'
        elif score >= 60:
            color = '#17a2b8'
            label = 'Bueno'
            icon = '✅'
        elif score >= 40:
            color = '#ffc107'
            label = 'Regular'
            icon = '⚠️'
        else:
            color = '#dc3545'
            label = 'Bajo'
            icon = '❌'
        
        return format_html(
            '<div style="text-align: center; padding: 15px; background: {}20; border-radius: 8px;">'
            '<div style="font-size: 3em;">{}</div>'
            '<div style="font-size: 2em; font-weight: bold; color: {};">{:.1f}</div>'
            '<div style="color: #666;">{}</div>'
            '</div>',
            color, icon, color, score, label
        )
    engagement_score_display.short_description = 'Score de Engagement'
    
    def activity_chart(self, obj):
        """Gráfico simple de actividad"""
        html = '''
        <div class="card">
            <div class="card-body">
                <h5>Distribución de Tiempo</h5>
                <div class="progress" style="height: 30px;">
        '''
        
        total_time = obj.total_time_seconds if obj.total_time_seconds > 0 else 1
        active_pct = (obj.active_time_seconds / total_time) * 100
        idle_pct = (obj.idle_time_seconds / total_time) * 100
        
        html += f'''
                    <div class="progress-bar bg-success" role="progressbar" style="width: {active_pct}%" title="Activo: {obj.active_time_seconds}s">
                        Activo {active_pct:.1f}%
                    </div>
                    <div class="progress-bar bg-warning" role="progressbar" style="width: {idle_pct}%" title="Inactivo: {obj.idle_time_seconds}s">
                        Inactivo {idle_pct:.1f}%
                    </div>
        '''
        
        html += '''
                </div>
            </div>
        </div>
        '''
        
        return format_html(html)
    activity_chart.short_description = 'Gráfico de Actividad'
    
    def sections_breakdown(self, obj):
        """Desglose de tiempo por sección"""
        sections = obj.section_times.all().order_by('-total_time_seconds')[:10]
        
        if not sections:
            return format_html('<p class="text-muted">No hay datos de secciones</p>')
        
        total_time = sum(s.total_time_seconds for s in sections)
        
        html = '''
        <div class="card">
            <div class="card-body">
                <h5>Top 10 Secciones Más Visitadas</h5>
                <table class="table table-sm">
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
    heatmap_preview.short_description = 'Preview Heatmap'
    
    def event_timeline(self, obj):
        """Timeline de eventos"""
        events = obj.events.all().order_by('timestamp')[:50]  # Primeros 50
        
        if not events:
            return format_html('<p class="text-muted">No hay eventos registrados</p>')
        
        html = '''
        <div class="card">
            <div class="card-body">
                <h5>Timeline de Eventos (Primeros 50)</h5>
                <div style="max-height: 400px; overflow-y: auto;">
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th>Tiempo</th>
                                <th>Tipo</th>
                                <th>Elemento</th>
                            </tr>
                        </thead>
                        <tbody>
        '''
        
        event_icons = {
            'click': '🖱️',
            'scroll': '📜',
            'hover': '👆',
            'flashcard_flip': '🔄',
            'node_expand': '➕',
            'node_collapse': '➖'
        }
        
        for event in events:
            icon = event_icons.get(event.event_type, '•')
            time_display = f"{event.time_since_session_start:.1f}s"
            element_text = event.element_text[:50] if event.element_text else '—'
            
            html += f'''
                <tr>
                    <td><code>{time_display}</code></td>
                    <td>{icon} {event.event_type}</td>
                    <td><small>{element_text}</small></td>
                </tr>
            '''
        
        html += '''
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        '''
        
        return format_html(html)
    event_timeline.short_description = 'Timeline de Eventos'
    
    # ============================================
    # VISTAS PERSONALIZADAS
    # ============================================
    
    def analytics_dashboard_view(self, request):
        """Vista de dashboard general de analytics"""
        
        # Estadísticas generales
        total_sessions = StudySession.objects.filter(is_active=False).count()
        total_users = StudySession.objects.values('user').distinct().count()
        
        avg_duration = StudySession.objects.filter(is_active=False).aggregate(
            avg=Avg('total_time_seconds')
        )['avg'] or 0
        
        avg_engagement = StudySession.objects.filter(is_active=False).aggregate(
            avg=Avg(F('active_time_seconds') * 100.0 / F('total_time_seconds'))
        )['avg'] or 0
        
        # Top materiales
        top_materials = StudySession.objects.filter(is_active=False).values(
            'material__text__title',
            'material__material_type'
        ).annotate(
            total_sessions=Count('id'),
            avg_completion=Avg('max_scroll_depth')
        ).order_by('-total_sessions')[:10]
        
        context = {
            'title': 'Analytics Dashboard',
            'total_sessions': total_sessions,
            'total_users': total_users,
            'avg_duration': round(avg_duration, 2),
            'avg_engagement': round(avg_engagement, 2),
            'top_materials': top_materials,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/tracking/analytics_dashboard.html', context)
    
    def heatmap_view(self, request, session_id):
        """Vista personalizada para visualizar el heatmap"""
        session = get_object_or_404(StudySession, pk=session_id)
        heatmap = session.heatmap_data.first()
        
        # ✅ CORRECCIÓN PROBLEMA 4: Serializar correctamente los datos JSON
        import json
        
        if heatmap:
            # Convertir a JSON seguro para JavaScript
            heatmap_data = {
                'clicks': json.dumps(heatmap.clicks if heatmap.clicks else []),
                'mouse_movements': json.dumps(heatmap.mouse_movements if heatmap.mouse_movements else []),
                'scroll_points': json.dumps(heatmap.scroll_points if heatmap.scroll_points else []),
                'hot_zones': json.dumps(heatmap.hot_zones if heatmap.hot_zones else [])
            }
        else:
            heatmap_data = {
                'clicks': '[]',
                'mouse_movements': '[]',
                'scroll_points': '[]',
                'hot_zones': '[]'
            }
        
        context = {
            'session': session,
            'heatmap': heatmap,
            'heatmap_data': heatmap_data,  # ← Usar este dict en lugar de heatmap directo
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request, session)
        }
        
        return render(request, 'admin/tracking/heatmap_view.html', context)


@admin.register(InteractionEvent)
class InteractionEventAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        """
        Ocultar del menú principal del admin.
        """
        return {}

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
            return obj.element_text[:50]
        return '—'
    element_preview.short_description = 'Elemento'


@admin.register(SectionTimeTracking)
class SectionTimeTrackingAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        """
        Ocultar del menú principal del admin.
        """
        return {}

    list_display = [
        'section_id_short',
        'section_type_badge',
        'session_link',
        'time_display',
        'view_count_badge'
    ]
    
    list_filter = ['section_type', 'first_view_at']
    search_fields = ['section_id', 'session__session_id']
    readonly_fields = ['session', 'section_id', 'first_view_at', 'last_view_at']
    
    def section_id_short(self, obj):
        return obj.section_id[:30]
    section_id_short.short_description = 'Sección'
    
    def section_type_badge(self, obj):
        colors = {
            'weak_section': 'danger',
            'review_section': 'success',
            'flashcard': 'info',
            'tree_node': 'warning'
        }
        color = colors.get(obj.section_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_section_type_display()
        )
    section_type_badge.short_description = 'Tipo'
    
    def session_link(self, obj):
        url = reverse('admin:pdi_texts_studysession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">Ver Sesión</a>',
            url
        )
    session_link.short_description = 'Sesión'
    
    def time_display(self, obj):
        return f"{obj.total_time_seconds:.1f}s"
    time_display.short_description = 'Tiempo Total'
    
    def view_count_badge(self, obj):
        return format_html(
            '<span class="badge badge-primary">{}</span>',
            obj.view_count
        )
    view_count_badge.short_description = 'Vistas'


@admin.register(HeatmapData)
class HeatmapDataAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        """
        Ocultar del menú principal del admin.
        """
        return {}

    list_display = [
        'session_link',
        'clicks_count',
        'movements_count',
        'hot_zones_count',
        'captured_at'
    ]
    
    list_filter = ['captured_at']
    search_fields = ['session__session_id']
    readonly_fields = ['session', 'clicks', 'mouse_movements', 'scroll_points', 'hot_zones', 'captured_at']
    
    def session_link(self, obj):
        url = reverse('admin:pdi_texts_studysession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">Sesión {}</a>',
            url,
            str(obj.session.session_id)[:8]
        )
    session_link.short_description = 'Sesión'
    
    def clicks_count(self, obj):
        return format_html(
            '<span class="badge badge-danger">{}</span>',
            len(obj.clicks)
        )
    clicks_count.short_description = 'Clics'
    
    def movements_count(self, obj):
        return format_html(
            '<span class="badge badge-info">{}</span>',
            len(obj.mouse_movements)
        )
    movements_count.short_description = 'Movimientos'
    
    def hot_zones_count(self, obj):
        return format_html(
            '<span class="badge badge-warning">{}</span>',
            len(obj.hot_zones)
        )
    hot_zones_count.short_description = 'Zonas Calientes'


@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'text_title', 'material_type_badge', 'requested_at']
    list_filter = ['material_type', 'requested_at']
    search_fields = ['user__email', 'text__title']
    readonly_fields = ['user', 'text', 'attempt', 'requested_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Usuario'
    
    def text_title(self, obj):
        return obj.text.title
    text_title.short_description = 'Texto'
    
    def material_type_badge(self, obj):
        return format_html(
            '<span class="badge badge-info">{}</span>',
            obj.get_material_type_display()
        )
    material_type_badge.short_description = 'Tipo'


@admin.register(MaterialEffectiveness)
class MaterialEffectivenessAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'material_type_badge', 'was_effective_icon', 'created_at']
    list_filter = ['material_type', 'was_effective', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['user', 'material', 'created_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Usuario'
    
    def material_type_badge(self, obj):
        return format_html(
            '<span class="badge badge-info">{}</span>',
            obj.get_material_type_display()
        )
    material_type_badge.short_description = 'Tipo'
    
    def was_effective_icon(self, obj):
        if obj.was_effective:
            return format_html('<span style="font-size: 20px;">✅</span>')
        return format_html('<span style="font-size: 20px;">❌</span>')
    was_effective_icon.short_description = 'Efectivo'