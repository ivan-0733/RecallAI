from rest_framework import viewsets, status
from rest_framework.views import APIView # <--- NUEVO IMPORT
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

from collections import Counter

from apps.pdi_texts.recommendation import get_recommended_material
from apps.pdi_texts.tasks_material import generate_didactic_material
from apps.pdi_texts.models import MaterialRequest, UserDidacticMaterial

from apps.pdi_texts.utils import log_session_summary, log_quiz_items
from apps.pdi_texts.models import StudentLearningPath, AdaptiveQuiz

from django.utils import timezone
from apps.pdi_texts.models import StudentLearningPath, AdaptiveQuiz, QuizAttempt, UserDidacticMaterial
from apps.pdi_texts.utils import log_session_summary, log_quiz_items
from apps.pdi_texts.tasks_material import generate_didactic_material

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
            
            # Contar intentos previos del usuario para este quiz específico
            previous_attempts = QuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz
            ).count()

            # --- CAMBIO AQUÍ: Verificar si es Post-Test ---
            path = StudentLearningPath.objects.filter(user=request.user, text=text).first()
            is_post_test_ready = path and path.is_completed

            # Definir límite de intentos: 
            # 1 si es Pre-Test (apenas empieza)
            # 2 si es Post-Test (1 del Pre + 1 del Post)
            allowed_attempts = 2 if is_post_test_ready else 1
            
            if previous_attempts >= allowed_attempts and request.method != 'GET':
                 return Response({
                    'error': 'Ya has completado los intentos permitidos para este cuestionario',
                    'message': 'No puedes realizar más intentos.',
                    'previous_attempts': previous_attempts,
                    'already_taken': True
                }, status=status.HTTP_403_FORBIDDEN)

            serializer = InitialQuizSerializer(quiz)
            
            return Response({
                'quiz': serializer.data,
                'previous_attempts': previous_attempts,
                'next_attempt_number': previous_attempts + 1,
                'already_taken': False,
                'is_post_test': is_post_test_ready  # Flag para el frontend
            })
        
        except InitialQuiz.DoesNotExist:
            return Response(
                {'error': 'Cuestionario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    @action(detail=True, methods=['get'], url_path='adaptive-quiz/(?P<quiz_id>[^/.]+)')
    def get_adaptive_details(self, request, pk=None, quiz_id=None):
        """
        Obtener preguntas de un quiz adaptativo específico
        GET /api/texts/{id}/adaptive-quiz/{quiz_id}/
        """
        try:
            adaptive_quiz = AdaptiveQuiz.objects.get(id=quiz_id, user=request.user)
            
            # Construir estructura similar al InitialQuiz para reutilizar el frontend
            return Response({
                'quiz': {
                    'text_title': adaptive_quiz.text.title,
                    'total_questions': len(adaptive_quiz.questions_json),
                    'questions_json': adaptive_quiz.questions_json,
                    'is_adaptive': True,
                    'session_number': adaptive_quiz.session_number
                },
                'attempt_number': 1,
                'next_attempt_number': 1
            })
        except AdaptiveQuiz.DoesNotExist:
            return Response(
                {'error': 'Quiz adaptativo no encontrado o no te pertenece'},
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
            pdi_text=text  # ← CAMBIO AQUÍ
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

        # ✅ CORRECCIÓN ROBUSTA: Asegurar que cada respuesta tenga opciones
        for idx, answer_detail in enumerate(detailed_answers):
            if 'opciones' not in answer_detail or not answer_detail['opciones']:
                try:
                    # Intentar recuperar opciones usando el índice guardado o el índice del loop
                    q_idx = answer_detail.get('question_index', idx)
                    if 0 <= q_idx < len(questions):
                        original_question = questions[q_idx]
                        answer_detail['opciones'] = original_question.get('opciones', [])
                        # También recuperar la pregunta si faltara
                        if 'question' not in answer_detail:
                            answer_detail['question'] = original_question.get('pregunta', '')
                except (KeyError, IndexError, TypeError):
                    answer_detail['opciones'] = []
        
        # Agrupar errores por tema
        from collections import Counter
        incorrect_topics = [
            ans['topic'] for ans in detailed_answers if not ans.get('is_correct', False)
        ]
        topic_counter = Counter(incorrect_topics)
        
        # Calcular si aprobó (score >= 80)
        passed = last_attempt.score >= 80
        
        return Response({
            'attempt': QuizAttemptSerializer(last_attempt).data,
            'score': last_attempt.score,
            'correct_count': sum(1 for ans in detailed_answers if ans.get('is_correct', False)),
            'total_questions': quiz.total_questions,
            'passed': passed,
            'weak_topics': last_attempt.weak_topics,
            'topic_errors': dict(topic_counter),
            'detailed_answers': detailed_answers,
            'message': '¡Excelente! Has aprobado' if passed else 'Necesitas reforzar algunos temas'
        })
    
    @action(detail=True, methods=['get'], url_path='flow-status')
    def get_flow_status(self, request, pk=None):
        """
        Obtener el estado actual del flujo de aprendizaje del usuario
        GET /api/texts/{id}/flow-status/
        """
        text = self.get_object()
        user = request.user
        
        try:
            path = StudentLearningPath.objects.get(user=user, text=text)
            
            # Material más reciente
            latest_material = UserDidacticMaterial.objects.filter(
                user=user,
                text=text
            ).order_by('-requested_at').first()
            
            # Quiz adaptativo pendiente
            pending_quiz = AdaptiveQuiz.objects.filter(
                user=user,
                text=text,
                learning_path=path
            ).order_by('-created_at').first()
            
            # Verificar si el quiz ya fue respondido
            quiz_already_taken = False
            if pending_quiz:
                quiz_already_taken = QuizAttempt.objects.filter(
                    user=user,
                    pdi_text=text,
                    quiz_type='adaptive'
                ).filter(
                    created_at__gte=pending_quiz.created_at
                ).exists()
            
            # Verificar si hay un intento de quiz adaptativo más reciente que el material
            latest_adaptive_attempt = QuizAttempt.objects.filter(
                user=user,
                pdi_text=text,
                quiz_type='adaptive'
            ).order_by('-created_at').first()
            
            # Determinar si necesita generar nuevo material
            needs_new_material = False
            if latest_adaptive_attempt and latest_material:
                # Si el último quiz adaptativo es más reciente que el último material
                needs_new_material = latest_adaptive_attempt.created_at > latest_material.requested_at
            elif latest_adaptive_attempt and not latest_material:
                needs_new_material = True
            
            return Response({
                'has_path': True,
                'current_session': path.current_session,
                'is_completed': path.is_completed,
                'has_material': latest_material is not None,
                'material_id': latest_material.id if latest_material else None,
                'material_type': latest_material.material_type if latest_material else None,
                'has_pending_quiz': pending_quiz is not None and not quiz_already_taken,
                'adaptive_quiz_id': pending_quiz.id if pending_quiz and not quiz_already_taken else None,
                'session_label': f"Sesión {path.current_session + 1}",
                'needs_new_material': needs_new_material,
                'last_attempt_id': latest_adaptive_attempt.id if latest_adaptive_attempt else None
            })
            
        except StudentLearningPath.DoesNotExist:
            return Response({
                'has_path': False,
                'current_session': 0,
                'is_completed': False,
                'has_material': False,
                'material_id': None,
                'material_type': None,
                'has_pending_quiz': False,
                'adaptive_quiz_id': None,
                'session_label': 'Pre-Test'
            })
    
    @action(detail=True, methods=['post'], url_path='submit-quiz')
    def submit_quiz(self, request, pk=None):
        text = self.get_object()
        user = request.user
        answers = request.data.get('answers', [])
        time_spent = request.data.get('time_spent', 0)
        quiz_type = request.data.get('quiz_type', 'initial')
        adaptive_quiz_id = request.data.get('quiz_id')

        # --- CAMBIO 1: Detección Automática de Post-Test ---
        path = StudentLearningPath.objects.filter(user=user, text=text).first()
        
        if quiz_type == 'initial' and path and path.is_completed:
            print("🔄 CAMBIO DE TIPO: Detectado path completado, cambiando 'initial' a 'post_test'")
            quiz_type = 'post_test'

        # --- Carga de preguntas (Soporta post_test) ---
        questions_data = []
        quiz_instance = None
        
        if quiz_type in ['initial', 'post_test']: # <--- Aceptamos post_test aquí
            if not hasattr(text, 'initial_quiz'):
                return Response({'error': 'No hay quiz inicial'}, status=404)
            quiz_instance = text.initial_quiz
            questions_data = text.initial_quiz.get_questions() 
        elif quiz_type == 'adaptive':
            quiz_obj = get_object_or_404(AdaptiveQuiz, id=adaptive_quiz_id, user=user)
            questions_data = quiz_obj.questions_json 

        # ... (Cálculo de Score y weak_topics IDÉNTICO al anterior) ...
        # (Aquí va el bucle for que calcula el score, no cambia)
        score = 0
        correct_count = 0
        detailed_answers = []
        weak_topics = []
        binary_results = []

        for i, question in enumerate(questions_data):
            # ... Lógica de evaluación ...
            user_ans_obj = next((a for a in answers if int(a.get('question_index', -1)) == i), None)
            user_response = user_ans_obj.get('selected_answer') if user_ans_obj else None
            correct_option = question.get('respuesta_correcta')
            is_correct = (user_response == correct_option)

            if is_correct:
                correct_count += 1
                binary_results.append(1)
            else:
                binary_results.append(0)
                if 'tema' in question:
                    weak_topics.append(question['tema'])

            detailed_answers.append({
                # ... datos detallados ...
                'question_index': i,
                'user_answer': user_response,
                'correct_answer': correct_option,
                'is_correct': is_correct,
                'topic': question.get('tema'),
                'opciones': question.get('opciones', [])
            })

        final_score = (correct_count / len(questions_data)) * 100 if questions_data else 0

        # --- CAMBIO 2: Guardado con el tipo correcto ('post_test') ---
        attempt = QuizAttempt.objects.create(
            user=user,
            pdi_text=text,
            quiz_type=quiz_type, # <--- Ahora valdrá 'post_test' si aplica
            quiz=quiz_instance,
            score=final_score,
            answers_json=detailed_answers,
            weak_topics=weak_topics,
            time_spent_seconds=time_spent,
            created_at=timezone.now()
        )

        next_action = 'none'
        message = ''

        # --- Flujo PRE-TEST ---
        if quiz_type == 'initial':
            fixed_topics = [q.get('tema', f'Tema {idx+1}') for idx, q in enumerate(questions_data)]
            path, created = StudentLearningPath.objects.get_or_create(
                user=user, text=text,
                defaults={'fixed_topics_order': fixed_topics, 'current_session': 0}
            )
            log_quiz_items(user.id, text.id, 'PRE_TEST', 0, final_score, binary_results)
            log_session_summary(user.id, text.id, 0, final_score, weak_topics)
            next_action = 'show_results'
            message = 'Diagnóstico completado.'

        # --- Flujo ADAPTATIVO (Igual) ---
        elif quiz_type == 'adaptive':
            current_session = path.current_session
            log_quiz_items(user.id, text.id, 'ADAPTIVE', current_session, final_score, binary_results)
            log_session_summary(user.id, text.id, current_session, final_score, weak_topics)
            path.current_session += 1
            path.save()
            
            MAX_SESSIONS = 2 
            if path.current_session >= MAX_SESSIONS:
                path.is_completed = True
                path.save()
                next_action = 'go_to_post_test'
                message = 'Ciclo finalizado. Realiza el Examen Final.'
            else:
                next_action = 'show_results'
                message = f'Sesión {current_session} finalizada.'

        # --- CAMBIO 3: Nuevo Bloque POST-TEST ---
        elif quiz_type == 'post_test':
            current_session = path.current_session if path else 99
            # Se registra explícitamente como POST_TEST para el CSV
            log_quiz_items(user.id, text.id, 'POST_TEST', current_session, final_score, binary_results)
            log_session_summary(user.id, text.id, current_session, final_score, weak_topics)
            
            next_action = 'finished_course'
            message = '¡Felicidades! Has completado el curso.'

        topic_counter = Counter(weak_topics)

        return Response({
            'status': 'success',
            'score': final_score,
            'passed': final_score >= 80,
            'attempt': {
                'id': attempt.id, 
                'quiz_type': attempt.quiz_type 
            },
            'next_action': next_action,
            'message': message,
            'weak_topics': list(set(weak_topics)),
            'detailed_answers': detailed_answers
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
        # ✅ CORREGIDO: Usar pdi_text en lugar de quiz.text
        MaterialRequest.objects.create(
            user=request.user,
            text=attempt.pdi_text,
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
        Finaliza una sesión de estudio.
        Calcula el porcentaje usando el total REAL guardado en la BD.
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
            
            # Métricas
            metrics = data.get('metrics', {})
            if metrics:
                session.total_interactions = metrics.get('total_interactions', 0)
                session.max_scroll_depth = metrics.get('max_scroll_depth', 0)
            
            material = session.material
            completion_percentage = 0
            
            # ------------------------------------------------
            # ✅ CÁLCULO PRECISO (USANDO VALORES DE BD)
            # ------------------------------------------------
            
            if material.material_type == 'flashcard':
                flashcard_events = session.events.filter(event_type='flashcard_flip')
                unique_flashcards = set()
                for event in flashcard_events:
                    if event.element_id:
                        unique_flashcards.add(event.element_id)
                
                flashcard_flip_count = len(unique_flashcards)
                
                # Usar el total guardado al generar
                total = material.total_flashcards if material.total_flashcards > 0 else 20
                
                completion_percentage = (flashcard_flip_count / total) * 100
                session.completed = flashcard_flip_count >= total
                
                print(f"📇 Flashcards: {flashcard_flip_count}/{total} ({completion_percentage:.1f}%)")
                
            elif material.material_type in ['decision_tree', 'mind_map']:
                node_events = session.events.filter(event_type='node_expand')
                unique_nodes_expanded = set()
                for event in node_events:
                    if event.element_id:
                        unique_nodes_expanded.add(event.element_id)
                
                node_expand_count = len(unique_nodes_expanded)
                
                # Usar el total guardado al generar
                total = material.total_nodes if material.total_nodes > 0 else 15
                
                completion_percentage = (node_expand_count / total) * 100
                session.completed = node_expand_count >= total
                
                print(f"🌳 Nodos: {node_expand_count}/{total} ({completion_percentage:.1f}%)")
                    
            else:
                # Resúmenes
                completion_percentage = session.max_scroll_depth
                session.completed = session.max_scroll_depth >= 90

            # Limitar y guardar
            completion_percentage = min(100.0, completion_percentage)
            session.save()
            
            return Response({
                'status': 'success',
                'session_summary': {
                    'duration_seconds': session.total_time_seconds,
                    'active_time_seconds': session.active_time_seconds,
                    'interactions': session.total_interactions,
                    'completed': session.completed,
                    'completion_percentage': round(completion_percentage, 2)
                }
            })
            
        except StudySession.DoesNotExist:
            return Response({'error': 'Sesión no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
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
        
# ========================================
# NUEVO ENDPOINT: Generar Material + Quiz Adaptativo
# ========================================

class GenerateMaterialAndQuizView(APIView):
    """
    Genera Material Didáctico Y Quiz Adaptativo de forma síncrona.
    Espera a que ambos estén listos antes de retornar.
    POST /api/texts/generate-material-and-quiz/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        import time
        from apps.pdi_texts.tasks import generate_adaptive_quiz_task
        
        user = request.user
        material_type = request.data.get('material_type')
        attempt_id = request.data.get('attempt_id')
        was_recommended = request.data.get('was_recommended', False)
        followed_recommendation = request.data.get('followed_recommendation', False)
        
        if not material_type or not attempt_id:
            return Response(
                {'error': 'material_type y attempt_id son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            attempt = QuizAttempt.objects.get(id=attempt_id, user=user)
            text = attempt.pdi_text
            
            # Obtener o crear el Learning Path
            path = StudentLearningPath.objects.filter(user=user, text=text).first()
            if not path:
                return Response(
                    {'error': 'No existe un Learning Path para este texto'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Registrar solicitud de material
            MaterialRequest.objects.create(
                user=user,
                text=text,
                attempt=attempt,
                material_type=material_type,
                was_recommended=was_recommended,
                followed_recommendation=followed_recommendation
            )
            
            # PASO 1: Generar Material Didáctico (SÍNCRONO - sin .delay())
            print(f"🎯 PASO 1: Generando material {material_type}...")
            material_result = generate_didactic_material(
                user_id=user.id,
                attempt_id=attempt_id,
                material_type=material_type
            )
            
            # Obtener el material recién creado
            material = UserDidacticMaterial.objects.filter(
                user=user,
                text=text
            ).order_by('-generated_at').first() 
            
            if not material:
                return Response(
                    {'error': 'Error al generar el material'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            print(f"✅ Material generado: ID {material.id}")
            
            # PASO 2: Esperar 2 minutos antes de generar el quiz (delay para API)
            print(f"⏳ PASO 2: Esperando 120 segundos antes de generar quiz...")
            time.sleep(120)  # 2 minutos de delay
            
            # PASO 3: Generar Quiz Adaptativo (SÍNCRONO - sin .delay())
            print(f"🎯 PASO 3: Generando Quiz Adaptativo...")
            quiz_result = generate_adaptive_quiz_task(
                learning_path_id=path.id,
                material_id=material.id
            )
            
            print(f"✅ Quiz generado exitosamente")
            
            return Response({
                'status': 'success',
                'material_id': material.id,
                'material_type': material_type,
                'quiz_generated': True,
                'message': 'Material y Quiz generados exitosamente'
            })
            
        except QuizAttempt.DoesNotExist:
            return Response(
                {'error': 'Intento de quiz no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            print(f"❌ Error: {str(e)}")
            traceback.print_exc()
            return Response(
                {'error': f'Error al generar: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class MaterialsHistoryAPIView(APIView):
    """
    Devuelve el historial de materiales del usuario con estado activo/inactivo
    y si necesita generar nuevo material.
    GET /api/texts/{text_id}/materials-history/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, text_id):
        user = request.user
        
        try:
            text = PDIText.objects.get(id=text_id)
        except PDIText.DoesNotExist:
            return Response({'error': 'Texto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener el Learning Path para saber si está completado
        path = StudentLearningPath.objects.filter(user=user, text=text).first()
        path_is_completed = path.is_completed if path else False
        current_session = path.current_session if path else 0
        
        # Obtener todos los materiales del usuario para este texto
        materials = UserDidacticMaterial.objects.filter(
            user=user,
            text=text
        ).order_by('-generated_at')
        
        # Obtener el último quiz adaptativo contestado
        last_adaptive_attempt = QuizAttempt.objects.filter(
            user=user,
            pdi_text=text,
            quiz_type='adaptive'
        ).order_by('-created_at').first()
        
        # Obtener el último material generado
        last_material = materials.first()
        
        # Determinar si necesita generar nuevo material
        # (hay quiz contestado más reciente que el último material)
        # PERO si el path está completado, NO necesita nuevo material
        needs_new_material = False
        last_attempt_id = None
        last_attempt_data = None
        
        if not path_is_completed and last_adaptive_attempt:
            last_attempt_id = last_adaptive_attempt.id
            if last_material:
                needs_new_material = last_adaptive_attempt.created_at > last_material.generated_at
            else:
                needs_new_material = True
            
            # Si necesita nuevo material, incluir datos del último quiz
            if needs_new_material:
                last_attempt_data = {
                    'id': last_adaptive_attempt.id,
                    'score': last_adaptive_attempt.score,
                    'weak_topics': last_adaptive_attempt.weak_topics,
                    'created_at': last_adaptive_attempt.created_at,
                    'answers_json': last_adaptive_attempt.answers_json,
                    'time_spent_seconds': last_adaptive_attempt.time_spent_seconds
                }
        
        # Construir lista de materiales con estado
        materials_data = []
        for idx, material in enumerate(materials):
            # Si el path está completado, TODOS los materiales están inactivos
            # Si no está completado, solo el más reciente puede estar activo
            is_active = False
            
            if not path_is_completed and idx == 0:  # Es el material más reciente
                if last_adaptive_attempt:
                    # Activo si el material fue generado DESPUÉS del último quiz
                    is_active = material.generated_at > last_adaptive_attempt.created_at
                else:
                    # Si no hay quiz adaptativo, el primer material siempre está activo
                    is_active = True
            
            materials_data.append({
                'id': material.id,
                'material_type': material.material_type,
                'generated_at': material.generated_at,
                'weak_topics': material.weak_topics,
                'total_flashcards': material.total_flashcards,
                'total_nodes': material.total_nodes,
                'is_active': is_active
            })
        
        return Response({
            'materials': materials_data,
            'needs_new_material': needs_new_material,
            'last_attempt_id': last_attempt_id,
            'last_attempt_data': last_attempt_data,
            'total_materials': len(materials_data),
            'path_is_completed': path_is_completed,  # ← NUEVO CAMPO
            'current_session': current_session  # ← NUEVO CAMPO
        })
        
class UserActivePathsView(APIView):
    """
    Vista para el Dashboard: Devuelve Paths activos Y completados,
    incluyendo resumen de resultados (Pre vs Post) para el dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # CORRECCIÓN: Usamos '-created_at' ya que 'updated_at' no existe en este modelo.
        active_paths = StudentLearningPath.objects.filter(
            user=request.user
        ).select_related('text').order_by('-created_at')

        data = []
        for path in active_paths:
            user = request.user
            text = path.text
            
            # --- Lógica existente de Material y Quiz Adaptativo ---
            has_material = UserDidacticMaterial.objects.filter(user=user, text=text).exists()
            
            pending_quiz = AdaptiveQuiz.objects.filter(
                learning_path=path, user=user
            ).order_by('-created_at').first()

            has_pending_quiz = False
            adaptive_quiz_id = None
            
            if pending_quiz:
                already_taken = QuizAttempt.objects.filter(
                    user=user, pdi_text=text, quiz_type='adaptive',
                    created_at__gte=pending_quiz.created_at
                ).exists()
                if not already_taken:
                    has_pending_quiz = True
                    adaptive_quiz_id = pending_quiz.id

            # --- NUEVA LÓGICA: Obtener datos de Pre y Post Test ---
            def get_quiz_data(q_type):
                attempt = QuizAttempt.objects.filter(
                    user=user, pdi_text=text, quiz_type=q_type
                ).order_by('-created_at').first()
                
                if not attempt:
                    return None
                
                # Calcular temas fuertes (respuestas correctas)
                strong_topics = set()
                if attempt.answers_json:
                    for ans in attempt.answers_json:
                        if ans.get('is_correct') and ans.get('topic'):
                            strong_topics.add(ans['topic'])
                
                return {
                    'score': attempt.score,
                    'weak_topics': attempt.weak_topics[:3], # Top 3 débiles
                    'strong_topics': list(strong_topics)[:3] # Top 3 fuertes
                }

            pre_test_summary = get_quiz_data('initial')
            post_test_summary = get_quiz_data('post_test')
            has_post_test = post_test_summary is not None

            # Determinar etiqueta de estado
            status_label = f"Sesión {path.current_session}"
            if path.is_completed:
                if has_post_test:
                    status_label = "Curso Finalizado"
                else:
                    status_label = "Listo para Post-Test"
            elif has_pending_quiz:
                status_label = "Quiz Pendiente"

            data.append({
                'text_id': text.id,
                'text_title': text.title,
                'current_session': path.current_session,
                'is_completed': path.is_completed,
                'status_label': status_label,
                'has_material': has_material,
                'has_pending_quiz': has_pending_quiz,
                'adaptive_quiz_id': adaptive_quiz_id,
                'started_at': path.created_at,
                # Datos nuevos para el frontend
                'has_post_test': has_post_test,
                'pre_test_summary': pre_test_summary,
                'post_test_summary': post_test_summary
            })
        
        return Response(data)