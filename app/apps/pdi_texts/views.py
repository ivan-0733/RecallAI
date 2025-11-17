from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg
from collections import Counter
from django.utils import timezone
from datetime import timedelta
from bs4 import BeautifulSoup  # Si no está ya importada
import re  # Si no está ya importada

from apps.pdi_texts.recommendation import get_recommended_material
from apps.pdi_texts.tasks_material import generate_didactic_material
from apps.pdi_texts.models import MaterialRequest, UserDidacticMaterial

from apps.pdi_texts.models import PDIText, InitialQuiz, QuizAttempt, UserProfile
from apps.pdi_texts.serializers import (
    PDITextListSerializer,
    PDITextDetailSerializer,
    InitialQuizSerializer,
    QuizSubmissionSerializer,
    QuizAttemptSerializer,
    UserProfileSerializer,
    MaterialRecommendationSerializer,
    MaterialGenerateRequestSerializer,
    UserDidacticMaterialSerializer
)


class PDITextViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para que los alumnos vean y lean textos
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Solo textos activos con cuestionario"""
        return PDIText.objects.filter(
            status='active',
            has_quiz=True
        ).order_by('order', '-created_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PDITextListSerializer
        return PDITextDetailSerializer
    
    def get_serializer_context(self):
        """Pasar request al serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['get'], url_path='quiz')
    def get_quiz(self, request, pk=None):
        """
        Obtener cuestionario inicial de un texto
        GET /api/texts/{id}/quiz/
        """
        text = self.get_object()
        
        if not text.has_quiz:
            return Response(
                {'error': 'Este texto no tiene cuestionario disponible'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            quiz = text.initial_quiz
            
            # Contar intentos previos del usuario
            previous_attempts = QuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz
            ).count()
            
            # ✅ NUEVO: Si ya tomó el cuestionario inicial, no permitir más intentos
            # Se permite GET para que el visor de material pueda cargar los temas dominados
            if previous_attempts >= 1 and request.method != 'GET':
                return Response({
                    'error': 'Ya completaste el cuestionario inicial de este texto',
                    'message': 'Solo puedes tomar el cuestionario inicial una vez',
                    'previous_attempts': previous_attempts,
                    'already_taken': True
                }, status=status.HTTP_403_FORBIDDEN)

            serializer = InitialQuizSerializer(quiz)
            
            return Response({
                'quiz': serializer.data,
                'previous_attempts': previous_attempts,
                'next_attempt_number': previous_attempts + 1,
                'already_taken': False
            })
        
        except InitialQuiz.DoesNotExist:
            return Response(
                {'error': 'Cuestionario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    @action(detail=True, methods=['get'], url_path='last-attempt')
    def get_last_attempt(self, request, pk=None):
        """
        Obtener el último intento del usuario en este texto
        GET /api/texts/{id}/last-attempt/
        """
        text = self.get_object()
        
        if not text.has_quiz:
            return Response(
                {'error': 'Este texto no tiene cuestionario'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        quiz = text.initial_quiz
        
        # Buscar último intento
        last_attempt = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz
        ).order_by('-created_at').first()
        
        if not last_attempt:
            return Response(
                {'error': 'No has tomado este cuestionario aún'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener preguntas del quiz
        questions = quiz.get_questions()
        
        # Reconstruir el resultado completo
        detailed_answers = last_attempt.answers_json

        for answer_detail in detailed_answers:
                if 'opciones' not in answer_detail:
                    try:
                        question_index = answer_detail['question_index']
                        if 0 <= question_index < len(questions):
                            original_question = questions[question_index]
                            answer_detail['opciones'] = original_question.get('opciones', [])
                    except (KeyError, IndexError, TypeError):
                        # Si algo falla, solo añade una lista vacía
                        answer_detail['opciones'] = []
        
        # Agrupar errores por tema
        from collections import Counter
        incorrect_topics = [
            ans['topic'] for ans in detailed_answers if not ans.get('is_correct', False)
        ]
        topic_counter = Counter(incorrect_topics)
        
        return Response({
            'attempt': QuizAttemptSerializer(last_attempt).data,
            'score': last_attempt.score,
            'correct_count': sum(1 for ans in detailed_answers if ans.get('is_correct', False)),
            'total_questions': quiz.total_questions,
            'passed': last_attempt.passed(),
            'weak_topics': last_attempt.weak_topics,
            'topic_errors': dict(topic_counter),
            'detailed_answers': detailed_answers,
            'message': '¡Excelente! Has aprobado' if last_attempt.passed() else 'Necesitas reforzar algunos temas'
        })
    
    @action(detail=True, methods=['post'], url_path='submit-quiz')
    def submit_quiz(self, request, pk=None):
        """
        Evaluar respuestas del cuestionario
        POST /api/texts/{id}/submit-quiz/
        Body: {
            "answers": [{"question_index": 0, "selected_answer": "A"}, ...],
            "time_spent_seconds": 600
        }
        """
        text = self.get_object()
        
        if not text.has_quiz:
            return Response(
                {'error': 'Este texto no tiene cuestionario'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quiz = text.initial_quiz
        
        # Validar datos de entrada
        answers = request.data.get('answers', [])
        time_spent = request.data.get('time_spent_seconds', 0)
        
        if not answers:
            return Response(
                {'error': 'Debes proporcionar respuestas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(answers) != quiz.total_questions:
            return Response(
                {'error': f'Se esperaban {quiz.total_questions} respuestas, recibidas: {len(answers)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener preguntas del quiz
        questions = quiz.get_questions()
        
        # Evaluar respuestas
        correct_count = 0
        detailed_answers = []
        incorrect_topics = []
        
        for answer in answers:
            question_index = answer.get('question_index')
            selected_answer = answer.get('selected_answer', '').upper()
            
            if question_index is None or question_index >= len(questions):
                continue
            
            question = questions[question_index]
            correct_answer = question.get('respuesta_correcta', '').upper()
            
            is_correct = selected_answer == correct_answer
            
            if is_correct:
                correct_count += 1
            else:
                # Agregar tema a lista de temas débiles
                topic = question.get('tema', 'Desconocido')
                incorrect_topics.append(topic)
            
            detailed_answers.append({
                'question_index': question_index,
                'question': question.get('pregunta'),
                'opciones': question.get('opciones', []),
                'selected_answer': selected_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'topic': question.get('tema'),
                'explanation': question.get('explicacion') if not is_correct else None
            })
        
        # Calcular score
        score = (correct_count / quiz.total_questions) * 100
        
        # Agrupar temas débiles por frecuencia
        topic_counter = Counter(incorrect_topics)
        weak_topics_sorted = [topic for topic, count in topic_counter.most_common()]
        
        # Calcular número de intento
        previous_attempts = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz
        ).count()
        
        attempt_number = previous_attempts + 1
        
        # Guardar intento
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            attempt_number=attempt_number,
            score=score,
            answers_json=detailed_answers,
            weak_topics=weak_topics_sorted,
            time_spent_seconds=time_spent
        )
        
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.update_weak_topics(weak_topics_sorted)
        profile.add_study_time(time_spent // 60)  # convertir a minutos
        
        # Actualizar last_study_date y study_streak
        today = timezone.now().date()
        
        if profile.last_study_date:
            # Calcular días desde último estudio
            days_since_last_study = (today - profile.last_study_date).days
            
            if days_since_last_study == 0:
                # Mismo día, no hacer nada con el streak
                pass
            elif days_since_last_study == 1:
                # Día consecutivo, incrementar racha
                profile.study_streak += 1
            else:
                # Rompió la racha, reiniciar a 1
                profile.study_streak = 1
        else:
            # Primera vez que estudia
            profile.study_streak = 1
        
        profile.last_study_date = today
        profile.save()      
        
        # Preparar respuesta
        return Response({
            'attempt': QuizAttemptSerializer(attempt).data,
            'score': score,
            'correct_count': correct_count,
            'total_questions': quiz.total_questions,
            'passed': attempt.passed(),
            'weak_topics': weak_topics_sorted,
            'topic_errors': dict(topic_counter),
            'detailed_answers': detailed_answers,
            'message': '¡Excelente! Has aprobado' if attempt.passed() else 'Necesitas reforzar algunos temas'
        })
    
    @action(detail=False, methods=['post'], url_path='generate-material')
    def generate_material(self, request):
        """
        Genera material didáctico del tipo seleccionado
        POST /api/texts/generate-material/
        Body: {
            "material_type": "flashcard",
            "attempt_id": 123,
            "was_recommended": true,
            "followed_recommendation": true
        }
        """
        serializer = MaterialGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        material_type = serializer.validated_data['material_type']
        attempt_id = serializer.validated_data['attempt_id']
        was_recommended = serializer.validated_data.get('was_recommended', False)
        followed_recommendation = serializer.validated_data.get('followed_recommendation', None)
        
        # Validar que el intento existe y pertenece al usuario
        try:
            attempt = QuizAttempt.objects.get(id=attempt_id, user=request.user)
        except QuizAttempt.DoesNotExist:
            return Response(
                {'error': 'Intento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Registrar solicitud
        MaterialRequest.objects.create(
            user=request.user,
            text=attempt.quiz.text,
            attempt=attempt,
            material_type=material_type,
            was_recommended=was_recommended,
            followed_recommendation=followed_recommendation
        )
        
        # Encolar tarea Celery
        task = generate_didactic_material.delay(
            user_id=request.user.id,
            attempt_id=attempt_id,
            material_type=material_type
        )
        
        return Response({
            'task_id': str(task.id),
            'status': 'pending',
            'message': f'Generando {material_type}... Esto puede tomar 1-2 minutos.',
            'material_type': material_type
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['get'], url_path='recommendation')
    def get_recommendation(self, request, pk=None):
        """
        Obtiene recomendación de material basada en historial
        GET /api/texts/{id}/recommendation/?attempt_id=123
        """
        text = self.get_object()
        attempt_id = request.query_params.get('attempt_id')
        
        if not attempt_id:
            return Response(
                {'error': 'Se requiere attempt_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que el intento existe
        try:
            attempt = QuizAttempt.objects.get(id=attempt_id, user=request.user)
        except QuizAttempt.DoesNotExist:
            return Response(
                {'error': 'Intento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener recomendación
        recommendation = get_recommended_material(request.user, text)
        
        serializer = MaterialRecommendationSerializer(recommendation)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='my-materials')
    def my_materials(self, request):
        """
        Lista todos los materiales generados del usuario
        GET /api/texts/my-materials/
        """
        materials = UserDidacticMaterial.objects.filter(
            user=request.user
        ).select_related('text', 'attempt').order_by('-requested_at')
        
        serializer = UserDidacticMaterialSerializer(materials, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='material-status')
    def get_material_status(self, request):
        """
        Consulta el estado de una solicitud de material.
        Usado por el frontend para sondear (polling).
        GET /api/texts/material-status/?request_id=123
        """
        request_id = request.query_params.get('request_id')
        if not request_id:
            return Response(
                {'error': 'Se requiere request_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Usar get_object_or_404 para manejar el 'No Encontrado'
            material_request = get_object_or_404(
                MaterialRequest, 
                id=request_id, 
                user=request.user
            )
            
            if material_request.status == 'completed':
                # ¡Material listo! Serializar y devolver el UserDidacticMaterial
                material = material_request.generated_material
                
                if not material:
                    # Esto no debería pasar si el estado es 'completado', pero por si acaso
                    return Response({
                        'status': 'failed', 
                        'error': 'El servidor completó la tarea pero no pudo enlazar el material.'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Usamos el serializer que ya tienes
                serializer = UserDidacticMaterialSerializer(material)
                return Response({
                    'status': 'completed',
                    'material': serializer.data
                })
            
            elif material_request.status == 'failed':
                return Response({'status': 'failed'})
            
            else:
                # Sigue en 'pending' o 'processing'
                return Response({'status': 'processing'})
                
        except MaterialRequest.DoesNotExist:
            # Esto pasa si el frontend carga antes que la BD cree el registro
            # El frontend lo interpretará como 'processing'
            return Response(
                {'status': 'processing', 'detail': 'Request not found yet, still processing.'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver historial de intentos del usuario
    """
    permission_classes = [IsAuthenticated]
    serializer_class = QuizAttemptSerializer
    
    def get_queryset(self):
        """Solo intentos del usuario actual"""
        return QuizAttempt.objects.filter(
            user=self.request.user
        ).select_related('quiz__text')
    
    @action(detail=False, methods=['get'], url_path='stats')
    def get_stats(self, request):
        """
        Obtener estadísticas generales del usuario
        GET /api/attempts/stats/
        """
        attempts = self.get_queryset()
        
        if not attempts.exists():
            return Response({
                'total_attempts': 0,
                'texts_studied': 0,
                'average_score': 0,
                'texts_passed': 0,
                'total_time_minutes': 0
            })
        
        stats = attempts.aggregate(
            total_attempts=Count('id'),
            average_score=Avg('score'),
            total_time_seconds=Count('time_spent_seconds')
        )
        
        # Textos únicos estudiados
        texts_studied = attempts.values('quiz__text').distinct().count()
        
        # Textos aprobados (score >= 80%)
        texts_passed = attempts.filter(score__gte=80).values('quiz__text').distinct().count()
        
        # Tiempo total en minutos
        total_time = sum(a.time_spent_seconds for a in attempts) // 60
        
        return Response({
            'total_attempts': stats['total_attempts'],
            'texts_studied': texts_studied,
            'average_score': round(stats['average_score'] or 0, 2),
            'texts_passed': texts_passed,
            'total_time_minutes': total_time
        })


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver perfil del usuario
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get_queryset(self):
        """Solo perfil del usuario actual"""
        return UserProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'], url_path='me')
    def get_my_profile(self, request):
        """
        Obtener perfil del usuario autenticado
        GET /api/profile/me/
        """
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

class UserDidacticMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver y obtener materiales didácticos generados
    GET /api/materials/{id}/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserDidacticMaterialSerializer
    
    def get_queryset(self):
        """Solo materiales del usuario actual"""
        return UserDidacticMaterial.objects.filter(user=self.request.user)
    

# ========================================
# VISTAS PARA TRACKING
# Agregar a app/apps/pdi_texts/views.py
# ========================================

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Avg, Count, F
from datetime import timedelta

from apps.pdi_texts.models import (
    StudySession,
    InteractionEvent,
    SectionTimeTracking,
    HeatmapData,
    UserDidacticMaterial
)


class TrackingViewSet(viewsets.ViewSet):
    """
    ViewSet para gestionar el tracking de estudio
    """
    permission_classes = [IsAuthenticated]
    
    # URL Final: /api/tracking/session/start/
    @action(detail=False, methods=['post'], url_path='start')
    def start_session(self, request):
        """
        Inicia una nueva sesión de estudio
        """
        data = request.data
        
        try:
            material = UserDidacticMaterial.objects.get(
                id=data['material_id'],
                user=request.user
            )
            
            session = StudySession.objects.create(
                session_id=data['session_id'],
                user=request.user,
                material=material,
                device_type=data.get('device_type'),
                browser=data.get('browser'),
                screen_resolution=data.get('screen_resolution'),
                started_at=timezone.now()
            )
            
            return Response({
                'status': 'success',
                'session_id': str(session.session_id),
                'message': 'Sesión iniciada correctamente'
            }, status=status.HTTP_201_CREATED)
            
        except UserDidacticMaterial.DoesNotExist:
            return Response({
                'error': 'Material no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # URL Final: /api/tracking/session/sync/
    @action(detail=False, methods=['post'], url_path='sync')
    def sync_session(self, request):
        """
        Sincroniza datos de la sesión activa
        """
        data = request.data
        session_id = data.get('session_id')
        
        try:
            session = StudySession.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )
            
            # 1. Guardar eventos
            events_data = data.get('events', [])
            events_to_create = []
            
            for event_data in events_data:
                events_to_create.append(InteractionEvent(
                    session=session,
                    event_type=event_data.get('event_type'),
                    element_id=event_data.get('element_id'),
                    element_type=event_data.get('element_type'),
                    element_text=event_data.get('element_text', '')[:500],
                    x_position=event_data.get('x_position'),
                    y_position=event_data.get('y_position'),
                    scroll_position=event_data.get('scroll_position'),
                    viewport_height=event_data.get('viewport_height'),
                    time_since_session_start=event_data.get('time_since_session_start'),
                    metadata=event_data.get('metadata', {})
                ))
            
            if events_to_create:
                InteractionEvent.objects.bulk_create(events_to_create)
            
            # 2. Actualizar o crear section times
            section_times_data = data.get('section_times', [])
            
            for section_data in section_times_data:
                section, created = SectionTimeTracking.objects.get_or_create(
                    session=session,
                    section_id=section_data['section_id'],
                    defaults={
                        'section_type': section_data.get('section_type', 'unknown'),
                        'section_content_preview': section_data.get('section_content_preview', '')[:500],
                        'first_view_at': timezone.now(),
                        'last_view_at': timezone.now()
                    }
                )
                
                if not created:
                    # Actualizar tiempos
                    section.total_time_seconds += section_data.get('total_time_seconds', 0)
                    section.view_count += section_data.get('view_count', 1)
                    section.last_view_at = timezone.now()
                    section.save()
            
            # 3. Guardar o actualizar heatmap data
            heatmap_data = data.get('heatmap_data', {})
            if heatmap_data:
                heatmap, created = HeatmapData.objects.get_or_create(
                    session=session,
                    defaults={
                        'clicks': heatmap_data.get('clicks', []),
                        'mouse_movements': heatmap_data.get('mouse_movements', []),
                        'scroll_points': heatmap_data.get('scroll_points', [])
                    }
                )
                
                if not created:
                    # Agregar nuevos datos
                    heatmap.clicks.extend(heatmap_data.get('clicks', []))
                    heatmap.mouse_movements.extend(heatmap_data.get('mouse_movements', []))
                    heatmap.scroll_points.extend(heatmap_data.get('scroll_points', []))
                    heatmap.data_points_count = len(heatmap.clicks) + len(heatmap.mouse_movements)
                    
                    # Calcular hot zones
                    heatmap.hot_zones = heatmap.calculate_hot_zones()
                    heatmap.save()
            
            # 4. Actualizar métricas de sesión
            metrics = data.get('metrics', {})
            if metrics:
                session.total_interactions = metrics.get('total_interactions', 0)
                session.scroll_events = metrics.get('scroll_events', 0)
                session.click_events = metrics.get('click_events', 0)
                session.hover_events = metrics.get('hover_events', 0)
                session.focus_changes = metrics.get('focus_changes', 0)
                session.sections_visited = metrics.get('sections_visited', [])
                session.max_scroll_depth = metrics.get('max_scroll_depth', 0)
                
                # ✅ CORRECCIÓN PROBLEMA 1: Actualizar tiempos en tiempo real
                session.total_time_seconds = metrics.get('total_time_seconds', 0)
                session.active_time_seconds = metrics.get('active_time_seconds', 0)
                session.idle_time_seconds = session.total_time_seconds - session.active_time_seconds
                
                session.save()
            
            return Response({
                'status': 'success',
                'synced_events': len(events_data),
                'synced_sections': len(section_times_data)
            })
            
        except StudySession.DoesNotExist:
            return Response({
                'error': 'Sesión no encontrada o inactiva'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # URL Final: /api/tracking/session/end/
    @action(detail=False, methods=['post'], url_path='end')
    def end_session(self, request):
        """
        Finaliza una sesión de estudio
        """
        data = request.data
        session_id = data.get('session_id')
        
        try:
            session = StudySession.objects.get(
                session_id=session_id,
                user=request.user
            )
            
            # Actualizar sesión
            session.ended_at = timezone.now()
            session.total_time_seconds = data.get('total_time_seconds', 0)
            session.active_time_seconds = data.get('active_time_seconds', 0)
            session.idle_time_seconds = session.total_time_seconds - session.active_time_seconds
            session.exit_type = data.get('exit_type', 'normal')
            session.is_active = False
            
            # Métricas finales
            metrics = data.get('metrics', {})
            if metrics:
                session.total_interactions = metrics.get('total_interactions', 0)
                session.max_scroll_depth = metrics.get('max_scroll_depth', 0)
            
            # Determinar si completó el material
            session.completed = session.max_scroll_depth >= 90
            
            session.save()
            
            # Actualizar estadísticas del material
            material = session.material
            material.total_study_time_seconds += session.total_time_seconds
            material.active_study_time_seconds += session.active_time_seconds
            material.total_interactions += session.total_interactions
            material.sessions_count += 1
            material.last_studied_at = timezone.now()

            # ✅ CORRECCIÓN PROBLEMA 2 y 3: Calcular completion_percentage según tipo de material
            if material.material_type == 'flashcard':
                # Para flashcards: contar cuántas se voltearon
                flashcard_flip_count = session.events.filter(event_type='flashcard_flip').count()
                total_flashcards = 20  # Siempre son 20 flashcards
                material.completion_percentage = min(100, (flashcard_flip_count / total_flashcards) * 100)
                session.completed = flashcard_flip_count >= total_flashcards
                
            elif material.material_type in ['decision_tree', 'mind_map']:
                # Para árboles/mapas: contar cuántos nodos se expandieron
                node_expand_count = session.events.filter(event_type='node_expand').count()
                
                # Extraer el número total de nodos del HTML (buscar atributos data-node)
                import re
                from bs4 import BeautifulSoup
                
                try:
                    soup = BeautifulSoup(material.html_content, 'html.parser')
                    # Buscar todos los elementos con data-node o clase 'node'
                    total_nodes = len(soup.find_all(attrs={'data-node': True}))
                    if total_nodes == 0:
                        total_nodes = len(soup.find_all(class_='node'))
                    
                    if total_nodes > 0:
                        material.completion_percentage = min(100, (node_expand_count / total_nodes) * 100)
                        session.completed = node_expand_count >= total_nodes
                    else:
                        # Fallback si no se puede determinar
                        material.completion_percentage = session.max_scroll_depth
                        session.completed = session.max_scroll_depth >= 90
                except Exception as e:
                    # Si falla el parsing, usar scroll depth como fallback
                    material.completion_percentage = session.max_scroll_depth
                    session.completed = session.max_scroll_depth >= 90
                    
            elif material.material_type == 'summary':
                # Para resúmenes: usar scroll depth (ya funciona bien)
                material.completion_percentage = session.max_scroll_depth
                session.completed = session.max_scroll_depth >= 90
            else:
                # Por defecto: usar scroll depth
                material.completion_percentage = session.max_scroll_depth
                session.completed = session.max_scroll_depth >= 90

            # Calcular engagement score
            material.engagement_score = session.engagement_score()
            material.save()
            session.save()  # Guardar session.completed
            
            return Response({
                'status': 'success',
                'session_summary': {
                    'duration_seconds': session.total_time_seconds,
                    'active_time_seconds': session.active_time_seconds,
                    'active_percentage': session.active_percentage(),
                    'engagement_score': session.engagement_score(),
                    'interactions': session.total_interactions,
                    'scroll_depth': session.max_scroll_depth,
                    'completed': session.completed
                }
            })
            
        except StudySession.DoesNotExist:
            return Response({
                'error': 'Sesión no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # URL Final: /api/tracking/session/{uuid}/
    @action(detail=False, methods=['get'], url_path='(?P<session_id>[^/.]+)')
    def get_session_details(self, request, session_id=None):
        """
        Obtiene detalles completos de una sesión
        """
        try:
            session = StudySession.objects.get(
                session_id=session_id,
                user=request.user
            )
            
            # Obtener eventos de la sesión
            events = session.events.all().order_by('timestamp')
            event_timeline = [
                {
                    'type': e.event_type,
                    'time': e.time_since_session_start,
                    'element': e.element_text[:50] if e.element_text else None
                }
                for e in events[:100]  # Limitar a 100 eventos
            ]
            
            # Obtener section times
            section_times = session.section_times.all().order_by('-total_time_seconds')
            sections_summary = [
                {
                    'section_id': s.section_id,
                    'type': s.section_type,
                    'time_seconds': round(s.total_time_seconds, 2),
                    'views': s.view_count
                }
                for s in section_times
            ]
            
            # Obtener heatmap
            heatmap = session.heatmap_data.first()
            hot_zones = heatmap.hot_zones if heatmap else []
            
            return Response({
                'session_id': str(session.session_id),
                'material_title': session.material.text.title,
                'started_at': session.started_at,
                'ended_at': session.ended_at,
                'duration_formatted': session.duration_formatted(),
                'active_percentage': round(session.active_percentage(), 2),
                'engagement_score': session.engagement_score(),
                'metrics': {
                    'interactions': session.total_interactions,
                    'clicks': session.click_events,
                    'scrolls': session.scroll_events,
                    'hovers': session.hover_events,
                    'max_scroll_depth': session.max_scroll_depth,
                    'sections_visited': len(session.sections_visited)
                },
                'event_timeline': event_timeline,
                'sections_summary': sections_summary,
                'hot_zones': hot_zones[:10]  # Top 10 zonas calientes
            })
            
        except StudySession.DoesNotExist:
            return Response({
                'error': 'Sesión no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)


class AnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet para analytics y estadísticas del admin
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_analytics(self, request, user_id=None):
        """
        Analytics completos de un usuario
        GET /api/analytics/user/{user_id}/
        """
        from apps.application_user.models import User
        
        try:
            user = User.objects.get(id=user_id)
            
            # Sesiones del usuario
            sessions = StudySession.objects.filter(user=user, is_active=False)
            
            # Métricas generales
            total_sessions = sessions.count()
            total_study_time = sessions.aggregate(
                total=Sum('total_time_seconds')
            )['total'] or 0
            
            avg_session_duration = sessions.aggregate(
                avg=Avg('total_time_seconds')
            )['avg'] or 0
            
            avg_engagement = sessions.aggregate(
                avg=Avg(F('active_time_seconds') * 100.0 / F('total_time_seconds'))
            )['avg'] or 0
            
            # Interacciones totales
            total_interactions = sessions.aggregate(
                total=Sum('total_interactions')
            )['total'] or 0
            
            # Materiales estudiados
            materials = UserDidacticMaterial.objects.filter(user=user)
            materials_by_type = materials.values('material_type').annotate(
                count=Count('id'),
                avg_engagement=Avg('engagement_score')
            )
            
            # Sesiones por día (últimos 30 días)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            sessions_by_day = sessions.filter(
                started_at__gte=thirty_days_ago
            ).extra(
                select={'day': 'DATE(started_at)'}
            ).values('day').annotate(
                count=Count('id'),
                total_time=Sum('total_time_seconds')
            ).order_by('day')
            
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}"
                },
                'summary': {
                    'total_sessions': total_sessions,
                    'total_study_time_hours': round(total_study_time / 3600, 2),
                    'avg_session_duration_minutes': round(avg_session_duration / 60, 2),
                    'avg_engagement_percentage': round(avg_engagement, 2),
                    'total_interactions': total_interactions
                },
                'materials_by_type': list(materials_by_type),
                'sessions_by_day': list(sessions_by_day)
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'Usuario no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'], url_path='material/(?P<material_id>[^/.]+)/heatmap')
    def material_heatmap(self, request, material_id=None):
        """
        Obtiene el heatmap agregado de un material
        GET /api/analytics/material/{material_id}/heatmap/
        """
        try:
            material = UserDidacticMaterial.objects.get(id=material_id)
            
            # Obtener todas las sesiones del material
            sessions = StudySession.objects.filter(material=material, is_active=False)
            
            # Agregar todos los clicks
            all_clicks = []
            for session in sessions:
                heatmap = session.heatmap_data.first()
                if heatmap:
                    all_clicks.extend(heatmap.clicks)
            
            # Calcular zonas calientes agregadas
            # (usar el mismo algoritmo que HeatmapData.calculate_hot_zones)
            
            return Response({
                'material_id': material.id,
                'total_sessions': sessions.count(),
                'total_clicks': len(all_clicks),
                'clicks': all_clicks  # O las hot_zones calculadas
            })
            
        except UserDidacticMaterial.DoesNotExist:
            return Response({
                'error': 'Material no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)