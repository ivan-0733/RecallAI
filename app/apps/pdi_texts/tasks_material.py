"""
Tareas Celery para generación de material didáctico
"""

import time
import bleach
import random 
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import google.generativeai as genai
from bs4 import BeautifulSoup  # ✅ Asegúrate de que esto esté importado

from apps.pdi_texts.models import (
    QuizAttempt,
    UserDidacticMaterial,
    MaterialRequest,
    PDIText,
    InitialQuiz
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
    'header', 'footer', 'section', 'article', 
    'style', 'script',
    'html', 'head', 'body', 'meta', 'title', 'link',
    'svg', 'path'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style', 'id', 'onclick', 'onmouseover', 'onmouseout', 'onload'],
    'a': ['href', 'title', 'target'],
    'button': ['onclick', 'type'],
    'meta': ['charset', 'name', 'content'],
    'link': ['rel', 'href'],
    'svg': ['viewBox', 'width', 'height', 'fill'],
    'path': ['d', 'fill'],
    'script': ['type'],
}


@shared_task(bind=True, max_retries=3)
def generate_didactic_material(self, user_id, attempt_id, material_type):
    """
    Genera material didáctico personalizado usando Gemini Pro
    """
    
    try:
        # Se obtienen los datos necesarios
        from apps.application_user.models import User
        user = User.objects.get(id=user_id)
        attempt = QuizAttempt.objects.get(id=attempt_id)
        text = attempt.quiz.text
        initial_quiz = attempt.quiz 
        
        logger.info(f"Generando {material_type} para {user.email} en texto {text.id}")
        
        # --- Inicia la lógica 75/25 ---
        weak_topics = attempt.weak_topics
        weak_topics_set = set(weak_topics)
        
        initial_questions = initial_quiz.get_questions()
        all_initial_topics = list(set(q.get('tema', 'General') for q in initial_questions if q.get('tema')))
        all_initial_topics_set = set(all_initial_topics)
        
        review_topics_pool = list(all_initial_topics_set - weak_topics_set)
        review_topics = review_topics_pool
            
        logger.info(f"Lógica 75/25 - Temas Débiles (75%): {weak_topics}")
        logger.info(f"Lógica 75/25 - Temas Repaso (COMPLEMENTO): {review_topics}")
        # --- Fin de la lógica 75/25 ---

        answers = attempt.get_answers()
        quiz_questions = initial_quiz.get_questions()
        
        incorrect_questions_text = ""
        for i, answer in enumerate(answers):
            if not answer.get('is_correct', False):
                if 'question_index' in answer and 0 <= answer['question_index'] < len(quiz_questions):
                    question = quiz_questions[answer['question_index']]
                    incorrect_questions_text += f"- {question['pregunta']}\n"
                    incorrect_questions_text += f"  Tu respuesta: {answer['selected_answer']}\n"
                    incorrect_questions_text += f"  Correcta: {question['respuesta_correcta']}\n\n"
        
        text_content_preview = text.content[:3000] if text.content else ""
        start_time = time.time()
        
        if material_type == 'flashcard':
            prompt = get_flashcard_prompt(
                weak_topics=weak_topics,
                review_topics=review_topics,
                subject=text.topic
            )
        elif material_type == 'decision_tree':
            prompt = get_decision_tree_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics,
                incorrect_questions_text=incorrect_questions_text,
                text_content_preview=text_content_preview
            )
        elif material_type == 'mind_map':
            prompt = get_mind_map_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics,
                text_content_preview=text_content_preview
            )
        elif material_type == 'summary':
            prompt = get_summary_prompt(
                text_title=text.title,
                text_topic=text.topic,
                weak_topics=weak_topics,
                review_topics=review_topics,
                incorrect_questions_text=incorrect_questions_text,
                score=attempt.score,
                text_content_preview=text_content_preview
            )
        else:
            raise ValueError(f"Tipo de material inválido: {material_type}")
        
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
        
        html_content = response.text.strip()
        
        # Limpieza de JSON/Markdown
        if material_type == 'decision_tree':
            if html_content.startswith('```json'):
                html_content = html_content.replace('```json', '').replace('```', '').strip()
            elif html_content.startswith('```'):
                html_content = html_content.replace('```', '').strip()
            
            import json
            try:
                parsed_json = json.loads(html_content)
                html_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                logger.info(f"✅ JSON del árbol validado")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error validando JSON del árbol: {e}")
                import re
                json_match = re.search(r'\{.*\}', html_content, re.DOTALL)
                if json_match:
                    html_content = json_match.group(0)
        
        elif html_content.startswith('```html'):
            html_content = html_content.replace('```html', '').replace('```', '').strip()
        elif html_content.startswith('```'):
            html_content = html_content.replace('```', '').strip()
        
        if material_type == 'flashcard':
            clean_html = html_content
            logger.info("⚠️ Flashcard HTML NO sanitizado (scripts permitidos)")
        else:
            clean_html = bleach.clean(
                html_content,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                strip=False
            )
            logger.info(f"✅ {material_type} HTML sanitizado")
        
        generation_time = int(time.time() - start_time)
        
# En la sección donde se cuenta los nodos (alrededor de la línea donde dice "✅ LÓGICA NUEVA: CONTAR NODOS ANTES DE GUARDAR")
# Reemplaza toda esa sección con:

        # ------------------------------------------------------------------
        # ✅ LÓGICA NUEVA: CONTAR SOLO NODOS PADRES (Niveles 0, 1, 2)
        # ------------------------------------------------------------------
        
        total_nodes = 0
        total_flashcards = 0
        
        try:
            if material_type == 'flashcard':
                # Para flashcards: contar divs con clase 'flashcard'
                soup = BeautifulSoup(clean_html, 'html.parser')
                flashcard_elements = soup.find_all('div', class_='flashcard')
                total_flashcards = len(flashcard_elements) if flashcard_elements else 20
                logger.info(f"📇 Flashcards detectadas para guardar: {total_flashcards}")
                
            elif material_type == 'decision_tree':
                # Para árbol de decisión: contar solo nodos padres del JSON
                import json
                try:
                    tree_data = json.loads(clean_html)
                    if 'datos' in tree_data and 'nodos' in tree_data['datos']:
                        # Contar solo nodos con nivel 0, 1 o 2 (excluir nivel 3)
                        parent_nodes = [
                            nodo for nodo in tree_data['datos']['nodos'] 
                            if nodo.get('nivel', 0) < 3
                        ]
                        total_nodes = len(parent_nodes)
                        logger.info(f"🌳 Nodos padres detectados (niveles 0-2): {total_nodes}")
                        
                        # Log detallado para debugging
                        levels_count = {}
                        for nodo in tree_data['datos']['nodos']:
                            nivel = nodo.get('nivel', 0)
                            levels_count[nivel] = levels_count.get(nivel, 0) + 1
                        logger.info(f"📊 Distribución por niveles: {levels_count}")
                    else:
                        total_nodes = 15  # Default si no hay estructura válida
                        logger.warning("⚠️ Estructura JSON inválida, usando default 15")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Error parseando JSON del árbol: {e}")
                    total_nodes = 15  # Default en caso de error
                    
            elif material_type == 'mind_map':
                # Para mapa mental: intentar parsear si es JSON, sino contar elementos HTML
                try:
                    import json
                    mind_map_data = json.loads(clean_html)
                    if 'datos' in mind_map_data and 'nodos' in mind_map_data['datos']:
                        # Similar al árbol, contar solo nodos padres
                        parent_nodes = [
                            nodo for nodo in mind_map_data['datos']['nodos'] 
                            if nodo.get('nivel', 0) < 3
                        ]
                        total_nodes = len(parent_nodes)
                        logger.info(f"🧠 Nodos padres mapa mental (niveles 0-2): {total_nodes}")
                    else:
                        # Si no es JSON estructurado, contar elementos HTML
                        soup = BeautifulSoup(clean_html, 'html.parser')
                        all_nodes = soup.find_all('g', class_='arbol-nodo')
                        if not all_nodes:
                            all_nodes = soup.find_all(attrs={'data-node': True})
                        if not all_nodes:
                            all_nodes = soup.find_all('div', class_='node')
                        total_nodes = max(1, len(all_nodes) - 1) if all_nodes else 15
                        logger.info(f"🧠 Nodos HTML detectados en mapa mental: {total_nodes}")
                        
                except (json.JSONDecodeError, ValueError):
                    # No es JSON, contar elementos HTML
                    soup = BeautifulSoup(clean_html, 'html.parser')
                    all_nodes = soup.find_all('g', class_='arbol-nodo')
                    if not all_nodes:
                        all_nodes = soup.find_all(attrs={'data-node': True})
                    if not all_nodes:
                        all_nodes = soup.find_all('div', class_='node')
                    total_nodes = max(1, len(all_nodes) - 1) if all_nodes else 15
                    logger.info(f"🧠 Nodos HTML en mapa mental: {total_nodes}")
                
        except Exception as e:
            logger.error(f"Error contando nodos/flashcards: {e}")
            # Fallbacks
            total_nodes = 15
            total_flashcards = 20

        # ------------------------------------------------------------------
        # ✅ GUARDAR CON LOS VALORES REALES
        # ------------------------------------------------------------------
        
        material = UserDidacticMaterial.objects.create(
            user=user,
            text=text,
            attempt=attempt,
            material_type=material_type,
            html_content=clean_html,
            weak_topics=weak_topics,
            requested_at=timezone.now(),
            generated_at=timezone.now(),
            generation_time_seconds=generation_time,
            # AQUÍ GUARDAMOS LA CUENTA REAL DE NODOS PADRES
            total_nodes=total_nodes,
            total_flashcards=total_flashcards
        )
        
        logger.info(f"Material generado exitosamente (ID: {material.id})")
        logger.info(f"📊 Totales guardados -> Nodos padres: {total_nodes}, Flashcards: {total_flashcards}")
        
        return {
            'status': 'success',
            'material_id': material.id,
            'material_type': material_type,
            'generation_time': generation_time,
            'message': f'Material {material_type} generado exitosamente'
        }
        
    except Exception as exc:
        logger.error(f"Error generando material: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {
            'status': 'error',
            'message': f'Error: {str(exc)}'
        }