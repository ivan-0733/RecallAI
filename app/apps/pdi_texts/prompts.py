import logging

logger = logging.getLogger(__name__)

def get_flashcard_prompt(weak_topics, subject="General", **kwargs):
    """
    Genera flashcards estilo Google Gemini - CON FORMATO MEJORADO
    """
    
    topics_str = ", ".join(weak_topics) if weak_topics else subject

    prompt = f"""Crea 20 flashcards interactivas sobre: {topics_str}

INSTRUCCIONES CRÍTICAS:
1. Responde SOLO con HTML completo (sin ```html, sin explicaciones)
2. Incluye TODO en un solo archivo: <style>, <script> y HTML
3. Usa clases CSS simples, sin complejidad
4. Basado ÚNICAMENTE en el contenido del PDF cargado

ESTRUCTURA HTML REQUERIDA:
- Div contenedor principal (width: 100%)
- Header con título "Conceptos Tarjetas" SOLAMENTE (sin mencionar fuentes)
- 20 divs de tarjetas, cada uno con clase "flashcard"
- Cada tarjeta tiene frente (fondo #3d3d3d) y reverso (fondo blanco)
- Controles de navegación abajo: reset, contador, flechas

DISTRIBUCIÓN DE CONTENIDO (20 tarjetas):
- 15 tarjetas: CONCEPTO (frente: término, reverso: definición 2-3 líneas)
- 3 tarjetas: PREGUNTA (frente: pregunta, reverso: respuesta)
- 2 tarjetas: COMPLETAR (frente: "_____ es...", reverso: palabra en AZUL + explicación)

FORMATO DE TARJETAS (MUY IMPORTANTE):

Para CONCEPTO:
- Arriba pequeño centrado: "CONCEPTO:" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: El término (tamaño 28px)
- Reverso: texto negro normal

Para PREGUNTA:
- Arriba pequeño centrado: "PREGUNTA:" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: La pregunta (tamaño 28px)
- Reverso: texto negro normal

Para COMPLETAR:
- Arriba pequeño centrado: "COMPLETAR:" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: La frase con _____ (tamaño 28px)
- Reverso: La palabra faltante en COLOR AZUL (#1976d2) + explicación en negro

CSS MINIMALISTA:
- Fondo oscuro (#3d3d3d) para frente de tarjeta
- Fondo blanco para reverso
- Una tarjeta visible a la vez (display: none en las demás)
- Botones con flechas grandes y visibles
- IMPORTANTE: .container con width: 100%
- IMPORTANTE: .flashcard con width: 100%
- IMPORTANTE: Respuestas de COMPLETAR en azul

JAVASCRIPT SIMPLE:
- Variable currentIndex para tarjeta actual
- Función mostrar/ocultar tarjetas
- Click en tarjeta para voltear
- Botones ← → para navegar

EJEMPLO DE ESTRUCTURA:

<html>
<head>
<style>
body {{ margin: 0; padding: 20px; font-family: Arial; background: #f8f9fa; }}
.container {{ width: 100%; max-width: 100%; margin: 0 auto; background: white; padding: 24px; border-radius: 16px; }}
.flashcard {{ display: none; width: 100%; height: 400px; border-radius: 12px; padding: 40px; text-align: center; cursor: pointer; }}
.flashcard.active {{ display: flex; flex-direction: column; justify-content: center; align-items: center; }}
.front {{ background: #3d3d3d; color: white; }}
.back {{ background: white; color: black; border: 1px solid #ddd; }}
.card-label {{ font-size: 14px; opacity: 0.7; margin-bottom: 20px; letter-spacing: 1px; font-weight: 500; }}
.card-content {{ font-size: 28px; font-weight: 400; line-height: 1.4; }}
.answer-word {{ color: #1976d2; font-weight: 600; font-size: 32px; }}
.controls {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }}
button {{ padding: 0; cursor: pointer; border: 2px solid #ddd; background: white; border-radius: 50%; width: 50px; height: 50px; font-size: 24px; display: flex; align-items: center; justify-content: center; }}
button:hover {{ background: #f0f0f0; border-color: #999; }}
</style>
</head>
<body>
<div class="container">
  <h1>Conceptos Tarjetas</h1>
  
  <!-- EJEMPLO CONCEPTO -->
  <div class="flashcard active front" id="card0" onclick="flip(0)">
    <div class="card-label">CONCEPTO:</div>
    <div class="card-content">Espacio de Color</div>
  </div>
  
  <!-- EJEMPLO PREGUNTA -->
  <div class="flashcard front" id="card1" onclick="flip(1)">
    <div class="card-label">PREGUNTA:</div>
    <div class="card-content">¿Qué diferencia hay entre RGB y HSV?</div>
  </div>
  
  <!-- EJEMPLO COMPLETAR (IMPORTANTE: respuesta en azul) -->
  <div class="flashcard front" id="card2" onclick="flip(2)">
    <div class="card-label">COMPLETAR:</div>
    <div class="card-content">El espacio _____ representa colores usando matiz, saturación y valor</div>
  </div>
  
  <!-- REVERSO de COMPLETAR debe tener la respuesta en azul -->
  <!-- Al voltear card2, debe verse así: -->
  <!-- <div class="answer-word">HSV</div> -->
  <!-- <p>Explicación del concepto...</p> -->
  
  <!-- ... 17 tarjetas más con el mismo formato ... -->
  
  <div class="controls">
    <button onclick="reset()">↻</button>
    <span id="counter">1 / 20</span>
    <div style="display: flex; gap: 10px;">
      <button onclick="prev()">←</button>
      <button onclick="next()">→</button>
    </div>
  </div>
</div>
<script>
let current = 0;
function show(i) {{
  document.querySelectorAll('.flashcard').forEach((c, idx) => c.classList.toggle('active', idx === i));
  document.getElementById('counter').textContent = (i + 1) + ' / 20';
}}
function next() {{ if (current < 19) show(++current); }}
function prev() {{ if (current > 0) show(--current); }}
function reset() {{ current = 0; show(0); }}
function flip(i) {{ 
  const card = document.getElementById('card' + i);
  card.classList.toggle('front'); 
  card.classList.toggle('back'); 
}}
</script>
</body>
</html>

REGLAS CRÍTICAS:
1. NO mencionar "Basado en X fuentes" - solo título "Conceptos Tarjetas"
2. TODAS las tarjetas deben tener card-label arriba ("CONCEPTO:", "PREGUNTA:" o "COMPLETAR:")
3. En tarjetas COMPLETAR: la palabra de respuesta debe estar en clase "answer-word" (color azul #1976d2)
4. Botones de flechas grandes y visibles (50x50px, font-size 24px)
5. container y flashcard: width 100%

GENERA AHORA las 20 tarjetas completas sobre: {topics_str}
Responde ÚNICAMENTE con el HTML completo y funcional.
IMPORTANTE: 
- NO incluir texto de "fuentes"
- Respuestas de COMPLETAR en color azul
- Flechas grandes y visibles"""

    return prompt


def get_decision_tree_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, text_content_preview):
    """Prompt para Árbol de Decisión"""
    
    weak_topics_str = ', '.join(weak_topics[:2]) if weak_topics else text_topic
    
    return f"""Crea un árbol de decisión interactivo en HTML sobre: {text_topic}

TEMAS DÉBILES: {weak_topics_str}

Genera HTML completo con:
- Nodos colapsables (botones con onclick)
- Colores: rojo para temas débiles, verde para dominados
- Código Python en nodos finales
- CSS inline
- JavaScript para colapsar/expandir

Responde SOLO con HTML completo, sin explicaciones."""


def get_mind_map_prompt(text_title, text_topic, weak_topics, text_content_preview):
    """Prompt para Mapa Mental"""
    
    weak_topics_str = ', '.join(weak_topics[:3]) if weak_topics else text_topic
    
    return f"""Crea un mapa mental interactivo en HTML sobre: {text_topic}

TEMAS DÉBILES: {weak_topics_str}

Genera HTML completo con:
- Nodo central con el tema principal
- Ramas principales (4-6)
- Sub-ramas (3-5 por rama)
- Colores: rojo para débiles, verde para dominados
- CSS inline
- Nodos expandibles

Responde SOLO con HTML completo, sin explicaciones."""


def get_summary_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, score, text_content_preview):
    """Prompt para Resumen Estructurado"""
    
    weak_topics_str = ', '.join(weak_topics[:3]) if weak_topics else text_topic
    
    return f"""Crea un resumen estructurado en HTML sobre: {text_title}

SCORE: {score}%
TEMAS DÉBILES: {weak_topics_str}

ESTRUCTURA (60% en temas débiles):

1. CONCEPTOS ESENCIALES (20%)
- Lista breve de 5-7 conceptos clave

2. DONDE NECESITAS REFORZAR (60%)
- Sección principal con explicaciones detalladas
- Código Python con comentarios
- Referencias a errores específicos del alumno
- Cómo evitarlo

3. REPASO RÁPIDO (20%)
- Bullet points de temas que sí domina

Genera HTML con:
- Header con gradiente morado
- Secciones con colores: azul (conceptos), rojo (débiles), verde (dominados)
- Tablas de referencia
- CSS inline

Responde SOLO con HTML completo, sin explicaciones."""