# Generated manually for tracking system

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdi_texts', '0004_materialeffectiveness_materialrequest_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ============================================
        # MODELO 1: StudySession - Sesión de estudio completa
        # ============================================
        migrations.CreateModel(
            name='StudySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.UUIDField(unique=True, verbose_name='ID de Sesión')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='study_sessions', to='pdi_texts.userdidacticmaterial', verbose_name='Material')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='study_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
                
                # Tiempos
                ('started_at', models.DateTimeField(verbose_name='Inicio')),
                ('ended_at', models.DateTimeField(null=True, blank=True, verbose_name='Fin')),
                ('total_time_seconds', models.IntegerField(default=0, verbose_name='Tiempo Total (segundos)')),
                ('active_time_seconds', models.IntegerField(default=0, verbose_name='Tiempo Activo (segundos)', help_text='Tiempo real de interacción (sin idle)')),
                ('idle_time_seconds', models.IntegerField(default=0, verbose_name='Tiempo Inactivo (segundos)')),
                
                # Métricas de actividad
                ('total_interactions', models.IntegerField(default=0, verbose_name='Total de Interacciones')),
                ('scroll_events', models.IntegerField(default=0, verbose_name='Eventos de Scroll')),
                ('click_events', models.IntegerField(default=0, verbose_name='Eventos de Click')),
                ('hover_events', models.IntegerField(default=0, verbose_name='Eventos de Hover')),
                ('focus_changes', models.IntegerField(default=0, verbose_name='Cambios de Foco')),
                
                # Métricas de contenido
                ('sections_visited', models.JSONField(default=list, verbose_name='Secciones Visitadas')),
                ('max_scroll_depth', models.FloatField(default=0, verbose_name='Profundidad Máxima de Scroll (%)')),
                ('revisits_count', models.IntegerField(default=0, verbose_name='Número de Revisitas')),
                
                # Estado
                ('is_active', models.BooleanField(default=True, verbose_name='Sesión Activa')),
                ('completed', models.BooleanField(default=False, verbose_name='Completó el Material')),
                ('exit_type', models.CharField(max_length=20, choices=[
                    ('normal', 'Salida Normal'),
                    ('timeout', 'Timeout por Inactividad'),
                    ('browser_close', 'Cerró Navegador'),
                    ('navigation', 'Navegó a otra página'),
                ], null=True, blank=True, verbose_name='Tipo de Salida')),
                
                # Metadata del dispositivo
                ('device_type', models.CharField(max_length=20, null=True, verbose_name='Tipo de Dispositivo')),
                ('browser', models.CharField(max_length=50, null=True, verbose_name='Navegador')),
                ('screen_resolution', models.CharField(max_length=20, null=True, verbose_name='Resolución')),
                
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Actualización')),
            ],
            options={
                'verbose_name': 'Sesión de Estudio',
                'verbose_name_plural': 'Sesiones de Estudio',
                'db_table': 'study_session',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['user', '-started_at']),
                    models.Index(fields=['material', '-started_at']),
                    models.Index(fields=['session_id']),
                    models.Index(fields=['is_active']),
                ],
            },
        ),
        
        # ============================================
        # MODELO 2: InteractionEvent - Eventos granulares
        # ============================================
        migrations.CreateModel(
            name='InteractionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='pdi_texts.studysession', verbose_name='Sesión')),
                
                # Tipo de evento
                ('event_type', models.CharField(max_length=30, choices=[
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
                ], verbose_name='Tipo de Evento')),
                
                # Datos del evento
                ('element_id', models.CharField(max_length=255, null=True, blank=True, verbose_name='ID del Elemento')),
                ('element_type', models.CharField(max_length=50, null=True, blank=True, verbose_name='Tipo de Elemento')),
                ('element_text', models.TextField(null=True, blank=True, verbose_name='Texto del Elemento')),
                
                # Posición
                ('x_position', models.IntegerField(null=True, blank=True, verbose_name='Posición X')),
                ('y_position', models.IntegerField(null=True, blank=True, verbose_name='Posición Y')),
                ('scroll_position', models.IntegerField(null=True, blank=True, verbose_name='Posición de Scroll')),
                ('viewport_height', models.IntegerField(null=True, blank=True, verbose_name='Alto del Viewport')),
                
                # Timing
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')),
                ('time_since_session_start', models.FloatField(verbose_name='Tiempo desde Inicio (segundos)')),
                
                # Contexto adicional
                ('metadata', models.JSONField(default=dict, verbose_name='Metadata Adicional')),
            ],
            options={
                'verbose_name': 'Evento de Interacción',
                'verbose_name_plural': 'Eventos de Interacción',
                'db_table': 'interaction_event',
                'ordering': ['timestamp'],
                'indexes': [
                    models.Index(fields=['session', 'timestamp']),
                    models.Index(fields=['event_type']),
                ],
            },
        ),
        
        # ============================================
        # MODELO 3: SectionTimeTracking - Tiempo por sección
        # ============================================
        migrations.CreateModel(
            name='SectionTimeTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_times', to='pdi_texts.studysession', verbose_name='Sesión')),
                
                # Identificación de sección
                ('section_id', models.CharField(max_length=255, verbose_name='ID de Sección')),
                ('section_type', models.CharField(max_length=50, choices=[
                    ('weak_section', 'Sección de Temas Débiles'),
                    ('review_section', 'Sección de Repaso'),
                    ('flashcard', 'Flashcard'),
                    ('tree_node', 'Nodo del Árbol'),
                    ('summary_block', 'Bloque de Resumen'),
                    ('comparison_table', 'Tabla Comparativa'),
                    ('code_block', 'Bloque de Código'),
                ], verbose_name='Tipo de Sección')),
                ('section_content_preview', models.TextField(max_length=500, verbose_name='Preview del Contenido')),
                
                # Métricas de tiempo
                ('first_view_at', models.DateTimeField(verbose_name='Primera Vista')),
                ('last_view_at', models.DateTimeField(verbose_name='Última Vista')),
                ('total_time_seconds', models.FloatField(default=0, verbose_name='Tiempo Total (segundos)')),
                ('view_count', models.IntegerField(default=0, verbose_name='Número de Vistas')),
                
                # Interacciones específicas
                ('interaction_count', models.IntegerField(default=0, verbose_name='Interacciones en Sección')),
                ('scroll_depth_percent', models.FloatField(default=0, verbose_name='Profundidad de Scroll (%)')),
                
                # Flags
                ('fully_read', models.BooleanField(default=False, verbose_name='Leído Completamente')),
                ('interacted_with', models.BooleanField(default=False, verbose_name='Interactuó con la Sección')),
            ],
            options={
                'verbose_name': 'Tracking de Tiempo por Sección',
                'verbose_name_plural': 'Tracking de Tiempo por Sección',
                'db_table': 'section_time_tracking',
                'ordering': ['-total_time_seconds'],
                'indexes': [
                    models.Index(fields=['session', 'section_id']),
                    models.Index(fields=['section_type']),
                ],
            },
        ),
        
        # ============================================
        # MODELO 4: HeatmapData - Datos para heatmap
        # ============================================
        migrations.CreateModel(
            name='HeatmapData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='heatmap_data', to='pdi_texts.studysession', verbose_name='Sesión')),
                
                # Datos de clics
                ('clicks', models.JSONField(default=list, verbose_name='Clics', help_text='Array de {x, y, timestamp}')),
                
                # Datos de movimiento del mouse
                ('mouse_movements', models.JSONField(default=list, verbose_name='Movimientos del Mouse', help_text='Array de {x, y, timestamp} (sample rate: cada 100ms)')),
                
                # Datos de scroll
                ('scroll_points', models.JSONField(default=list, verbose_name='Puntos de Scroll', help_text='Array de {position, timestamp}')),
                
                # Zonas calientes (agregado)
                ('hot_zones', models.JSONField(default=list, verbose_name='Zonas Calientes', help_text='Áreas con más actividad: [{x, y, width, height, intensity}]')),
                
                # Metadata
                ('captured_at', models.DateTimeField(auto_now_add=True, verbose_name='Capturado')),
                ('data_points_count', models.IntegerField(default=0, verbose_name='Número de Puntos de Datos')),
            ],
            options={
                'verbose_name': 'Datos de Heatmap',
                'verbose_name_plural': 'Datos de Heatmap',
                'db_table': 'heatmap_data',
                'ordering': ['-captured_at'],
            },
        ),
        
        # ============================================
        # EXTENSIONES A MODELOS EXISTENTES
        # ============================================
        
        # Agregar campos de tracking a UserDidacticMaterial
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='total_study_time_seconds',
            field=models.IntegerField(default=0, verbose_name='Tiempo Total de Estudio (segundos)'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='active_study_time_seconds',
            field=models.IntegerField(default=0, verbose_name='Tiempo Activo de Estudio (segundos)'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='total_interactions',
            field=models.IntegerField(default=0, verbose_name='Total de Interacciones'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='completion_percentage',
            field=models.FloatField(default=0, verbose_name='Porcentaje de Completitud'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='sessions_count',
            field=models.IntegerField(default=0, verbose_name='Número de Sesiones'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='last_studied_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Última Vez Estudiado'),
        ),
        migrations.AddField(
            model_name='userdidacticmaterial',
            name='engagement_score',
            field=models.FloatField(default=0, verbose_name='Score de Engagement', help_text='0-100, calculado por algoritmo'),
        ),
    ]