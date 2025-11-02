"""
Tareas Celery para generación de material didáctico
"""

import time
import bleach
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import google.generativeai as genai

from apps.pdi_texts.models import (
    QuizAttempt,
    UserDidacticMaterial,
    MaterialRequest,
    PDIText
)
from apps.pdi_texts.prompts import (
    get_flashcard_prompt,
    get_decision_tree_prompt,
    get_mind_map_prompt,
    get_summary_prompt
)

import logging
logger = logging.getLogger(__name__)

# Configurar Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Tags HTML permitidos para sanitización
ALLOWED_TAGS = [
    'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 'br', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
    'code', 'pre', 'button', 'a',
    'header', 'footer', 'section', 'article', 'style', 'script'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style', 'id', 'onclick', 'onmouseover', 'onmouseout'],
    'a': ['href', 'title', 'target'],
    'button': ['onclick', 'type'],
}


@shared_task(bind=True, max_retries=3)
def generate_didactic_material(self, user_id, attempt_id, material_type):
    """
    Genera material didáctico personalizado usando Gemini Pro
    
    Args:
        user_id: ID del usuario
        attempt_id: ID del QuizAttempt
        material_type: 'flashcard', 'decision_tree', 'mind_map', 'summary'
    """
    
    try:
        # Obtener datos necesarios
        from apps.application_user.models import User
        user = User.objects.get(id=user_id)
        attempt = QuizAttempt.objects.get(id=attempt_id)
        text = attempt.quiz.text
        
        logger.info(f"Generando {material_type} para {user.email} en texto {text.id}")
        
        # Obtener temas débiles y preguntas incorrectas
        weak_topics = attempt.weak_topics
        answers = attempt.get_answers()
        quiz_questions = attempt.quiz.get_questions()
        
        # Construir texto de preguntas incorrectas
        incorrect_questions_text = ""
        for i, answer in enumerate(answers):
            if not answer.get('is_correct', False):
                question = quiz_questions[answer['question_index']]
                incorrect_questions_text += f"- {question['pregunta']}\n"
                incorrect_questions_text += f"  Tu respuesta: {answer['selected_answer']}\n"
                incorrect_questions_text += f"  Correcta: {question['respuesta_correcta']}\n\n"
        
        # Obtener preview del contenido
        text_content_preview = text.content[:3000] if text.content else ""
        
        # Seleccionar prompt según tipo
        start_time = time.time()
        
        if material_type == 'flashcard':
            prompt = get_flashcard_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                incorrect_questions_text=incorrect_questions_text,
                text_content_preview=text_content_preview
            )
        elif material_type == 'decision_tree':
            prompt = get_decision_tree_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                incorrect_questions_text=incorrect_questions_text,
                text_content_preview=text_content_preview
            )
        elif material_type == 'mind_map':
            prompt = get_mind_map_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                incorrect_questions_text=incorrect_questions_text,
                text_content_preview=text_content_preview
            )
        elif material_type == 'summary':
            prompt = get_summary_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                incorrect_questions_text=incorrect_questions_text,
                score=attempt.score,
                text_content_preview=text_content_preview
            )
        else:
            raise ValueError(f"Tipo de material inválido: {material_type}")
        
        # Llamar a Gemini Pro con MÁXIMO de tokens
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=16000,  # Máximo permitido
                top_p=0.95,
                top_k=40,
            )
        )
        
        # Extraer HTML
        html_content = response.text.strip()
        
        # Limpiar markdown si existe
        if html_content.startswith('```html'):
            html_content = html_content.replace('```html', '').replace('```', '').strip()
        elif html_content.startswith('```'):
            html_content = html_content.replace('```', '').strip()
        
        # Sanitizar HTML
        clean_html = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=False
        )
        
        # Calcular tiempo de generación
        generation_time = int(time.time() - start_time)
        
        # Guardar en base de datos
        material = UserDidacticMaterial.objects.create(
            user=user,
            text=text,
            attempt=attempt,
            material_type=material_type,
            html_content=clean_html,
            weak_topics=weak_topics,
            generated_at=timezone.now(),
            generation_time_seconds=generation_time
        )
        
        logger.info(f"Material {material_type} generado exitosamente (ID: {material.id}) en {generation_time}s")
        
        return {
            'status': 'success',
            'material_id': material.id,
            'material_type': material_type,
            'generation_time': generation_time,
            'message': f'Material {material_type} generado exitosamente'
        }
        
    except Exception as exc:
        logger.error(f"Error generando material: {str(exc)}")
        
        # Retry con backoff exponencial
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'message': f'Error: {str(exc)}'
        }