"""
Tareas Celery para generación de material didáctico
"""

import time
import bleach
import random # Se importa random para la selección
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import google.generativeai as genai

from apps.pdi_texts.models import (
    QuizAttempt,
    UserDidacticMaterial,
    MaterialRequest,
    PDIText,
    InitialQuiz # Se importa InitialQuiz para leer temas
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

# Tags HTML permitidos para sanitización - VERSIÓN AMPLIADA
ALLOWED_TAGS = [
    'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 'br', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
    'code', 'pre', 'button', 'a',
    'header', 'footer', 'section', 'article', 
    'style', 'script',  # PERMITIR style y script
    'html', 'head', 'body', 'meta', 'title', 'link',  # Tags de documento
    'svg', 'path'  # Para iconos
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style', 'id', 'onclick', 'onmouseover', 'onmouseout', 'onload'],
    'a': ['href', 'title', 'target'],
    'button': ['onclick', 'type'],
    'meta': ['charset', 'name', 'content'],
    'link': ['rel', 'href'],
    'svg': ['viewBox', 'width', 'height', 'fill'],
    'path': ['d', 'fill'],
    'script': ['type'],  # Permitir scripts
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
        # Se obtienen los datos necesarios
        from apps.application_user.models import User
        user = User.objects.get(id=user_id)
        attempt = QuizAttempt.objects.get(id=attempt_id)
        text = attempt.quiz.text
        initial_quiz = attempt.quiz # El 'quiz' del intento ES el InitialQuiz
        
        logger.info(f"Generando {material_type} para {user.email} en texto {text.id}")
        
        # --- Inicia la lógica 75/25 ---
        
        # 1. Componente de Refuerzo (75%)
        # Se obtienen los temas de las preguntas incorrectas en este intento
        weak_topics = attempt.weak_topics
        weak_topics_set = set(weak_topics)
        
        # 2. Componente de Repaso (25%)
        # Se obtienen los temas del Cuestionario Inicial
        initial_questions = initial_quiz.get_questions()
        all_initial_topics = list(set(q.get('tema', 'General') for q in initial_questions if q.get('tema')))
        
        all_initial_topics_set = set(all_initial_topics)
        
        # Se excluyen los temas débiles del pool de repaso
        review_topics_pool = list(all_initial_topics_set - weak_topics_set)

        # Se asigna la lista completa de temas de repaso (complemento de temas débiles)
        review_topics = review_topics_pool
            
        logger.info(f"Lógica 75/25 - Temas Débiles (75%): {weak_topics}")
        logger.info(f"Lógica 75/25 - Temas Repaso (COMPLEMENTO): {review_topics}")
        
        # --- Fin de la lógica 75/25 ---

        # Se construye el texto de preguntas incorrectas (para prompts de resumen)
        answers = attempt.get_answers()
        quiz_questions = initial_quiz.get_questions()
        
        incorrect_questions_text = ""
        for i, answer in enumerate(answers):
            if not answer.get('is_correct', False):
                # Se asegura que el índice es válido
                if 'question_index' in answer and 0 <= answer['question_index'] < len(quiz_questions):
                    question = quiz_questions[answer['question_index']]
                    incorrect_questions_text += f"- {question['pregunta']}\n"
                    incorrect_questions_text += f"  Tu respuesta: {answer['selected_answer']}\n"
                    incorrect_questions_text += f"  Correcta: {question['respuesta_correcta']}\n\n"
        
        # Se obtiene una vista previa del contenido
        text_content_preview = text.content[:3000] if text.content else ""
        
        # Se selecciona el prompt según el tipo
        start_time = time.time()
        
        # Se pasan ambas listas (weak_topics y review_topics) a los prompts
        
        if material_type == 'flashcard':
            prompt = get_flashcard_prompt(
                weak_topics=weak_topics,
                review_topics=review_topics, # Se añade la lista de repaso
                subject=text.topic
            )
        elif material_type == 'decision_tree':
            prompt = get_decision_tree_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics, # Se añade la lista de repaso
                incorrect_questions_text=incorrect_questions_text,
                text_content_preview=text_content_preview
            )
        elif material_type == 'mind_map':
            prompt = get_mind_map_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics, # Se añade la lista de repaso
                text_content_preview=text_content_preview
            )
        elif material_type == 'summary':
            prompt = get_summary_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics, # Se añade la lista de repaso
                incorrect_questions_text=incorrect_questions_text,
                score=attempt.score,
                text_content_preview=text_content_preview
            )
        else:
            raise ValueError(f"Tipo de material inválido: {material_type}")
        
        # Se llama al modelo de IA (se mantiene el modelo y config originales)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=16000,
                top_p=0.95,
                top_k=40,
            )
        )
        
        # Se extrae el contenido HTML
        html_content = response.text.strip()
        
        # NUEVO: Limpieza especial para árboles de decisión (JSON)
        if material_type == 'decision_tree':
            # Limpiar markdown JSON
            if html_content.startswith('```json'):
                html_content = html_content.replace('```json', '').replace('```', '').strip()
            elif html_content.startswith('```'):
                html_content = html_content.replace('```', '').strip()
            
            # Validar que sea JSON válido
            import json
            try:
                # Intentar parsear para validar
                parsed_json = json.loads(html_content)
                # Re-serializar limpio (sin escapes innecesarios)
                html_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                logger.info(f"✅ JSON del árbol validado y limpiado ({len(parsed_json.get('datos', {}).get('nodos', []))} nodos)")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error validando JSON del árbol: {e}")
                # Si falla, intentar extraer JSON del texto
                import re
                json_match = re.search(r'\{.*\}', html_content, re.DOTALL)
                if json_match:
                    html_content = json_match.group(0)
                    try:
                        parsed_json = json.loads(html_content)
                        html_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                        logger.info("✅ JSON extraído y validado mediante regex")
                    except:
                        logger.error("❌ No se pudo validar el JSON del árbol")
        
        # Limpieza para otros tipos (HTML)
        elif html_content.startswith('```html'):
            html_content = html_content.replace('```html', '').replace('```', '').strip()
        elif html_content.startswith('```'):
            html_content = html_content.replace('```', '').strip()
        
        # CRÍTICO: NO se sanitizan las flashcards
        # Las flashcards generadas por IA son seguras y necesitan scripts
        if material_type == 'flashcard':
            clean_html = html_content  # NO sanitizar flashcards
            logger.info("⚠️ Flashcard HTML NO sanitizado (scripts permitidos)")
        else:
            # Se sanitizan otros tipos de material
            clean_html = bleach.clean(
                html_content,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                strip=False
            )
            logger.info(f"✅ {material_type} HTML sanitizado")
        
        # Se calcula el tiempo de generación
        generation_time = int(time.time() - start_time)
        
        # Se guarda el material en la base de datos
        material = UserDidacticMaterial.objects.create(
            user=user,
            text=text,
            attempt=attempt,
            material_type=material_type,
            html_content=clean_html,
            weak_topics=weak_topics, # Se guardan los temas débiles para referencia
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
        
        # Se configura el reintento con backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'message': f'Error: {str(exc)}'
        }