from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from apps.pdi_texts.models import PDIText, InitialQuiz
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