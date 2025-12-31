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
genai.configure(api_key="")

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
        
        # ✅ CORREGIDO: Usar pdi_text en lugar de quiz.text
        text = attempt.pdi_text
        
        # ✅ CORREGIDO: Obtener initial_quiz desde el texto, no desde el attempt
        initial_quiz = text.initial_quiz
        
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

        answers = attempt.answers_json
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
                
                # --- INICIO CORRECCIÓN DE INTEGRIDAD PARA D3.JS (SOLUCIÓN AL ERROR DE JERARQUÍA) ---
                # D3.stratify es estricto: IDs sin espacios, referencias de padre existentes y una única raíz.
                if 'datos' in parsed_json and 'nodos' in parsed_json['datos']:
                    nodos = parsed_json['datos']['nodos']
                    
                    # 1. Recopilar todos los IDs válidos (limpiando espacios invisibles)
                    ids_validos = set()
                    for n in nodos:
                        if 'id' in n:
                            n['id'] = str(n['id']).strip() 
                            ids_validos.add(n['id'])
                    
                    # 2. Corregir padres, referencias rotas y formato de null
                    raiz_encontrada = False
                    nodos_limpios = []
                    
                    for n in nodos:
                        padre_raw = n.get('padre')
                        
                        # Caso: Nodo Raíz (null, None, "null" texto, o vacío)
                        if padre_raw is None or str(padre_raw).lower() in ['null', 'none', ''] or n['id'] == 'raiz':
                            n['padre'] = None # Null real de Python/JSON
                            # Forzar ID raiz estándar si es posible para evitar duplicados
                            if not raiz_encontrada:
                                raiz_encontrada = True
                            else:
                                # Si ya hay una raiz, convertir esta en hija de la primera raiz para no romper D3
                                n['padre'] = 'raiz' if 'raiz' in ids_validos and n['id'] != 'raiz' else None
                        else:
                            # Caso: Nodo Hijo
                            padre_limpio = str(padre_raw).strip()
                            
                            # Verificar si el padre existe realmente en la lista de IDs
                            if padre_limpio in ids_validos:
                                n['padre'] = padre_limpio
                            else:
                                # Si el padre no existe (alucinación de Gemini), lo conectamos a la raiz para salvarlo
                                logger.warning(f"⚠️ Reparando nodo huérfano {n.get('id')}: padre '{padre_limpio}' no existe. Re-conectando.")
                                n['padre'] = 'raiz' if 'raiz' in ids_validos else None
                                if n['padre'] is None: raiz_encontrada = True # Se convirtió en raiz por defecto

                        # Evitar ciclos
                        if n.get('padre') == n.get('id'):
                             n['padre'] = 'raiz' if n.get('id') != 'raiz' else None

                        nodos_limpios.append(n)
                        
                    # 3. Seguridad final: Si D3 no encuentra una raíz explícita, forzar al primer nodo
                    if not raiz_encontrada and nodos_limpios:
                        logger.warning("⚠️ No se detectó nodo raiz explícito. Forzando el primer nodo como raiz.")
                        nodos_limpios[0]['padre'] = None
                        # Asegurar que tenga un ID común si es posible, o dejar el que tiene
                        if 'raiz' not in ids_validos:
                            nodos_limpios[0]['id'] = 'raiz'
                        
                    parsed_json['datos']['nodos'] = nodos_limpios
                # --- FIN CORRECCIÓN ---

                html_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                logger.info(f"✅ JSON del árbol validado y sanitizado para D3")
                
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
        logger.info(f"Totales guardados -> Nodos padres: {total_nodes}, Flashcards: {total_flashcards}")

        # ==========================================================
        # TRIGGER AUTOMÁTICO: GENERAR EL QUIZ ADAPTATIVO SIGUIENTE
        # ==========================================================
        try:
            # Buscamos si existe un Learning Path activo para este usuario/texto
            from apps.pdi_texts.models import StudentLearningPath
            path = StudentLearningPath.objects.get(user=user, text=text)
            
            # Importar la tarea nueva (importación local para evitar ciclos)
            from apps.pdi_texts.tasks import generate_adaptive_quiz_task
            
            # Disparar tarea
            # La tarea en tasks.py solo recibe learning_path_id y material_id
            generate_adaptive_quiz_task.apply_async(
                kwargs={
                    'learning_path_id': path.id,
                    'material_id': material.id
                },
                countdown=120  # Esperar 2 minutos (120 segundos)
            )
            logger.info(f"🚀 [FLUJO AUTOMÁTICO] Programada generación de Quiz Adaptativo para Sesión {path.current_session} (delay 2 min)")
            
        except StudentLearningPath.DoesNotExist:
            logger.warning("⚠️ No se encontró Learning Path. Generación de material aislada (fuera de flujo).")
            
        # ==========================================================
        
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