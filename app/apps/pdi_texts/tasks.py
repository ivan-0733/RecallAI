import time
import json
from celery import shared_task
from django.conf import settings
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List

from apps.pdi_texts.models import PDIText, InitialQuiz


# Configurar Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


class QuizQuestion(BaseModel):
    """Estructura de una pregunta del quiz"""
    pregunta: str = Field(description="La pregunta del quiz")
    opciones: List[str] = Field(description="Lista de 4 opciones de respuesta (A, B, C, D)")
    respuesta_correcta: str = Field(description="La letra de la respuesta correcta (A, B, C, o D)")
    tema: str = Field(description="Tema específico que evalúa esta pregunta")
    explicacion: str = Field(description="Explicación de por qué la respuesta es correcta")


class QuizStructure(BaseModel):
    """Estructura completa del quiz"""
    questions: List[QuizQuestion] = Field(description="Lista de 20 preguntas")


@shared_task(bind=True, max_retries=3)
def generate_initial_quiz(self, text_id):
    """
    Tarea asíncrona para generar cuestionario inicial usando Gemini Pro
    """
    
    try:
        # Obtener texto
        text = PDIText.objects.get(id=text_id)
        
        # Verificar si ya tiene quiz
        if hasattr(text, 'initial_quiz'):
            return {
                'status': 'already_exists',
                'text_id': text_id,
                'message': f'El texto "{text.title}" ya tiene un cuestionario'
            }
        
        start_time = time.time()
        
        # Construir prompt
        prompt = f"""
Eres un experto profesor de Procesamiento Digital de Imágenes con 15 años de experiencia.

TEXTO A EVALUAR:
Título: {text.title}
Tema: {text.topic}
Dificultad: {text.get_difficulty_display()}

CONTENIDO:
{text.content[:4000]}  

TAREA:
Genera un cuestionario de evaluación con EXACTAMENTE 20 preguntas de opción múltiple.

REQUISITOS:
1. Cada pregunta debe tener 4 opciones (A, B, C, D)
2. Solo UNA opción correcta por pregunta
3. Distribuye las preguntas así:
   - 40% (8 preguntas): Conceptos fundamentales y definiciones
   - 40% (8 preguntas): Aplicación práctica y casos de uso
   - 20% (4 preguntas): Comparación entre técnicas y análisis crítico
4. Dificultad: {text.difficulty}
5. Las preguntas deben cubrir TODO el contenido del texto
6. Cada pregunta debe tener un "tema" específico (ej: "Filtro Gaussiano", "Detección de bordes Canny")
7. Incluye explicación de por qué la respuesta es correcta

FORMATO DE SALIDA (JSON estricto):
{{
  "questions": [
    {{
      "pregunta": "¿Cuál es la principal ventaja del filtro Gaussiano sobre el filtro de media?",
      "opciones": [
        "A) Es más rápido de computar",
        "B) Preserva mejor los bordes al dar más peso al centro",
        "C) Utiliza menos memoria",
        "D) Funciona solo con imágenes en escala de grises"
      ],
      "respuesta_correcta": "B",
      "tema": "Filtros Gaussianos",
      "explicacion": "El filtro Gaussiano pondera los píxeles según su distancia al centro, dando más importancia a los píxeles cercanos, lo que permite suavizar ruido mientras preserva mejor los bordes que un filtro de media uniforme."
    }}
  ]
}}

IMPORTANTE: 
- Retorna SOLO el JSON, sin texto adicional
- Asegúrate de que sean EXACTAMENTE 20 preguntas
- Todas las opciones deben empezar con A), B), C), D)
- La respuesta_correcta debe ser solo la letra: "A", "B", "C" o "D"
"""
        
        # Llamar a Gemini Pro
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=16384,
            )
        )
        
        # Extraer texto de respuesta
        response_text = response.text.strip()
        
        # Limpiar markdown si existe
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '').strip()
        
        # Parsear JSON
        try:
            quiz_data = json.loads(response_text)
            questions = quiz_data.get('questions', [])
        except json.JSONDecodeError as e:
            raise Exception(f"Error al parsear JSON de Gemini: {str(e)}\n\nRespuesta recibida:\n{response_text}")
        
        # Validar que tenga 20 preguntas
        if len(questions) != 20:
            raise Exception(f"Se esperaban 20 preguntas, pero Gemini generó {len(questions)}")
        
        # Validar estructura de cada pregunta
        for i, q in enumerate(questions, 1):
            required_fields = ['pregunta', 'opciones', 'respuesta_correcta', 'tema', 'explicacion']
            for field in required_fields:
                if field not in q:
                    raise Exception(f"Pregunta {i} le falta el campo '{field}'")
            
            if len(q['opciones']) != 4:
                raise Exception(f"Pregunta {i} debe tener exactamente 4 opciones")
            
            if q['respuesta_correcta'] not in ['A', 'B', 'C', 'D']:
                raise Exception(f"Pregunta {i} tiene respuesta_correcta inválida: {q['respuesta_correcta']}")
        
        # Calcular tiempo de generación
        generation_time = int(time.time() - start_time)
        
        # Guardar en base de datos
        quiz = InitialQuiz.objects.create(
            text=text,
            questions_json=questions,
            total_questions=len(questions),
            generation_prompt=prompt[:1000],  # Guardar solo primeros 1000 chars
            generation_time_seconds=generation_time,
            model_used='gemini-2.5-pro'
        )
        
        # Actualizar flag en texto
        text.has_quiz = True
        text.save()
        
        return {
            'status': 'success',
            'text_id': text_id,
            'quiz_id': quiz.id,
            'total_questions': len(questions),
            'generation_time': generation_time,
            'message': f'✅ Cuestionario generado exitosamente para "{text.title}"'
        }
        
    except PDIText.DoesNotExist:
        return {
            'status': 'error',
            'text_id': text_id,
            'message': f'❌ No se encontró el texto con ID {text_id}'
        }
    
    except Exception as exc:
        # Retry con backoff exponencial
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'text_id': text_id,
            'message': f'❌ Error al generar cuestionario: {str(exc)}'
        }