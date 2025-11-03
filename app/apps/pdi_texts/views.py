from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg
from collections import Counter
from django.utils import timezone
from datetime import timedelta

from apps.pdi_texts.recommendation import get_recommended_material
from apps.pdi_texts.tasks_material import generate_didactic_material
from apps.pdi_texts.models import MaterialRequest, UserDidacticMaterial
from apps.pdi_texts.serializers import (
    MaterialRecommendationSerializer,
    MaterialGenerateRequestSerializer,
    UserDidacticMaterialSerializer
)

from apps.pdi_texts.models import PDIText, InitialQuiz, QuizAttempt, UserProfile
from apps.pdi_texts.serializers import (
    PDITextListSerializer,
    PDITextDetailSerializer,
    InitialQuizSerializer,
    QuizSubmissionSerializer,
    QuizAttemptSerializer,
    UserProfileSerializer
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
            if previous_attempts >= 1:
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