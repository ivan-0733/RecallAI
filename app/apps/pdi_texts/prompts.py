import logging

logger = logging.getLogger(__name__)

def get_flashcard_prompt(weak_topics, review_topics, subject="General", **kwargs):
    """
    Genera flashcards estilo Google Gemini - CON FORMATO MEJORADO
    """
    
    # Se definen los strings de temas
    weak_topics_str = ", ".join(weak_topics) if weak_topics else "Ninguno"
    review_topics_str = ", ".join(review_topics) if review_topics else "Ninguno"

    prompt = f"""Crea 20 flashcards interactivas.

INSTRUCCIONES CRÍTICAS DE ENFOQUE (LÓGICA 75/25):
1.  **ENFOQUE PRINCIPAL (75% del material, 15 tarjetas):** Deben ser sobre los temas débiles del alumno. Enfócate en: {weak_topics_str}
2.  **ENFOQUE DE REPASO (25% del material, 5 tarjetas):** Deben ser un repaso de conceptos generales. Enfócate en: {review_topics_str}

NUEVA INSTRUCCIÓN DE ETIQUETADO (MUY IMPORTANTE):
- Para las 15 tarjetas de TEMAS DÉBILES, la etiqueta DEBE ser: "CONCEPTO (TEMA DÉBIL):", "PREGUNTA (TEMA DÉBIL):" o "COMPLETAR (TEMA DÉBIL):"
- Para las 5 tarjetas de TEMAS GENERALES, la etiqueta DEBE ser: "CONCEPTO (TEMA GENERAL):", "PREGUNTA (TEMA GENERAL):" o "COMPLETAR (TEMA GENERAL):"

INSTRUCCIONES DE FORMATO:
1. Responde SOLO con HTML completo (sin ```html, sin explicaciones)
2. Incluye TODO en un solo archivo: <style>, <script> y HTML
3. Usa clases CSS simples, sin complejidad
4. Basado ÚNICAMENTE en el contenido del PDF cargado
5. CRÍTICO: Dentro de CADA tarjeta (ej: id='card0'), crea DOS divs: uno con class='content-front' (para el frente) y otro con class='content-back' (para el reverso). El CSS se encargará de ocultar el que no corresponda.

ESTRUCTURA HTML REQUERIDA:
- Div contenedor principal (width: 100%)
- Header con título "Conceptos Tarjetas" SOLAMENTE (sin mencionar fuentes)
- 20 divs de tarjetas, cada uno con clase "flashcard" (ej: id="card0", id="card1", etc.)
- CADA flashcard debe tener un div hijo class="content-front" y un div hijo class="content-back"
- Controles de navegación abajo: reset, contador, flechas

DISTRIBUCIÓN DE CONTENIDO (20 tarjetas):
- 15 tarjetas: CONCEPTO (frente: término, reverso: definición 2-3 líneas)
- 3 tarjetas: PREGUNTA (frente: pregunta, reverso: respuesta)
- 2 tarjetas: COMPLETAR (frente: "_____ es...", reverso: palabra en AZUL + explicación)
(La distribución 15/3/2 se refiere al TIPO de tarjeta, el contenido de estas 20 tarjetas debe seguir la proporción 75/25 de TEMAS)

FORMATO DE TARJETAS (MUY IMPORTANTE):
(Se aplica a los divs .content-front y .content-back)

Para CONCEPTO (TEMA DÉBIL):
- Arriba pequeño centrado: "CONCEPTO (TEMA DÉBIL):" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: El término (tamaño 28px)
- Reverso: texto negro normal

Para PREGUNTA (TEMA GENERAL):
- Arriba pequeño centrado: "PREGUNTA (TEMA GENERAL):" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: La pregunta (tamaño 28px)
- Reverso: texto negro normal

Para COMPLETAR (TEMA DÉBIL):
- Arriba pequeño centrado: "COMPLETAR (TEMA DÉBIL):" (tamaño 14px, opacidad 0.7)
- Abajo grande centrado: La frase con _____ (tamaño 28px)
- Reverso: La palabra faltante en COLOR AZUL (#1976d2) + explicación en negro

CSS MINIMALISTA:
- Fondo oscuro (#3d3d3d) para frente de tarjeta (clase .front)
- Fondo blanco para reverso (clase .back)
- Una tarjeta visible a la vez (display: none en las demás)
- Botones con flechas grandes y visibles
- IMPORTANTE: .container con width: 100%
- IMPORTANTE: .flashcard con width: 100%
- IMPORTANTE: Respuestas de COMPLETAR en azul
- **CORRECCIÓN CLAVE DE CSS:**
- .front .content-back {{ display: none; }}
- .back .content-front {{ display: none; }}
- .front .content-front, .back .content-back {{ display: flex; flex-direction: column; justify-content: center; align-items: center; width: 100%; height: 100%; }}

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
/* No se usa 'display: flex' en .flashcard.active, se usa en los hijos */
.flashcard.active {{ display: block; }} 
.front {{ background: #3d3d3d; color: white; }}
.back {{ background: white; color: black; border: 1px solid #ddd; }}

/* --- INICIO CORRECCIÓN CSS --- */
/* Oculta el contenido del reverso cuando la tarjeta tiene clase .front */
.front .content-back {{ display: none; }}
/* Oculta el contenido del frente cuando la tarjeta tiene clase .back */
.back .content-front {{ display: none; }}

/* Asegura que el contenido visible ocupe todo el espacio */
.front .content-front, .back .content-back {{ 
    display: flex; 
    flex-direction: column; 
    justify-content: center; 
    align-items: center; 
    width: 100%; 
    height: 100%; 
    padding: 40px; /* Padding movido aquí desde .flashcard */
    box-sizing: border-box; /* Importante */
}}
/* Ajuste: el padding se aplica al contenido, no al contenedor de la tarjeta */
.flashcard {{ padding: 0; }} 
/* --- FIN CORRECCIÓN CSS --- */

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
  
  <div class="flashcard active front" id="card0" onclick="flip(0)">
    <div class="content-front">
      <div class="card-label">CONCEPTO (TEMA DÉBIL):</div>
      <div class="card-content">Espacio de Color</div>
    </div>
    <div class="content-back">
      <div class="card-label">CONCEPTO (TEMA DÉBIL):</div>
      <div class="card-content">Un modelo matemático que describe cómo los colores pueden ser representados.</div>
    </div>
  </div>
  
  <div class="flashcard front" id="card1" onclick="flip(1)">
    <div class="content-front">
      <div class="card-label">PREGUNTA (TEMA GENERAL):</div>
      <div class="card-content">¿Qué diferencia hay entre RGB y HSV?</div>
    </div>
    <div class="content-back">
      <div class="card-label">PREGUNTA (TEMA GENERAL):</div>
      <div class="card-content">RGB se basa en componentes de luz (Rojo, Verde, Azul), mientras que HSV se basa en Tono, Saturación y Valor.</div>
    </div>
  </div>
  
  <div class="flashcard front" id="card2" onclick="flip(2)">
    <div class="content-front">
      <div class="card-label">COMPLETAR (TEMA DÉBIL):</div>
      <div class="card-content">El espacio _____ representa colores usando matiz, saturación y valor</div>
    </div>
    <div class="content-back">
      <div class="card-label">COMPLETAR (TEMA DÉBIL):</div>
      <div class="card-content">
        <span class="answer-word">HSV</span>
        <p style="font-size: 18px; margin-top: 15px;">Este modelo es más intuitivo para la percepción humana.</p>
      </div>
    </div>
  </div>

  <div class="controls">
    <button onclick="reset()">↻</button>
    
    <div style="display: flex; align-items: center; gap: 10px;">
      <span id="counter">1 / 20</span>
      <button onclick="prev()">←</button>
      <button onclick="next()">→</button>
    </div>
  </div>
  </div>
<script>
/* Se adjuntan las funciones a 'window' para hacerlas globales.
   Esto asegura que los atributos 'onclick=""' en el HTML 
   puedan encontrarlas después de ser cargadas dinámicamente.
*/
let current = 0;
window.show = function(i) {{
  // 1. Resetea TODAS las tarjetas a su estado 'front' (gris)
  document.querySelectorAll('.flashcard').forEach(c => {{
    c.classList.remove('back');
    c.classList.add('front');
  }});

  // 2. Muestra/oculta la tarjeta correcta
  document.querySelectorAll('.flashcard').forEach((c, idx) => {{
    c.classList.toggle('active', idx === i);
  }});
  
  // 3. Actualiza el contador y el índice
  document.getElementById('counter').textContent = (i + 1) + ' / 20';
  current = i; // Se actualiza el índice actual
}}
// La lógica 'if (current < 19)' y 'if (current > 0)' YA DETIENE la navegación en los extremos.
window.next = function() {{ if (current < 19) window.show(++current); }}
window.prev = function() {{ if (current > 0) window.show(--current); }}
window.reset = function() {{ 
  current = 0; 
  window.show(0); 
}}
window.flip = function(i) {{ 
  const card = document.getElementById('card' + i);
  card.classList.toggle('front'); 
  card.classList.toggle('back'); 
}}
</script>
</body>
</html>

REGLAS CRÍTICAS:
1. NO mencionar "Basado en X fuentes" - solo título "Conceptos Tarjetas"
2. TODAS las tarjetas deben tener card-label arriba (ej: "CONCEPTO (TEMA DÉBIL):" o "CONCEPTO (TEMA GENERAL):")
3. En tarjetas COMPLETAR: la palabra de respuesta debe estar en clase "answer-word" (color azul #1976d2)
4. Botones de flechas grandes y visibles (50x50px, font-size 24px)
5. container y flashcard: width 100%
6. **CRÍTICO: Usar la estructura .content-front y .content-back dentro de cada flashcard, como en el ejemplo.**

GENERA AHORA las 20 tarjetas completas sobre: {weak_topics_str} (75%) y {review_topics_str} (25%)
Responde ÚNICAMENTE con el HTML completo y funcional.
IMPORTANTE: 
- NO incluir texto de "fuentes"
- Respuestas de COMPLETAR en color azul
- Flechas grandes y visibles
- Aplicar las etiquetas (TEMA DÉBIL) y (TEMA GENERAL) a CADA tarjeta.
"""

    return prompt


def get_decision_tree_prompt(text_title, text_topic, weak_topics, review_topics, incorrect_questions_text, text_content_preview):
    """Prompt para Árbol de Decisión"""
    
    # Se definen los strings de temas
    weak_topics_str = ", ".join(weak_topics) if weak_topics else "Ninguno"
    review_topics_str = ", ".join(review_topics) if review_topics else "Ninguno"
    
    return f"""Crea un árbol de decisión interactivo en HTML sobre: {text_topic}

INSTRUCCIONES CRÍTICAS DE ENFOQUE (LÓGICA 75/25):
El árbol debe reflejar esta proporción de contenido:
1.  **ENFOQUE PRINCIPAL (75% del árbol):** Las ramas principales deben enfocarse en los temas débiles del alumno. Usa COLOR ROJO para estos nodos. Temas: {weak_topics_str}
2.  **ENFOQUE DE REPASO (25% del árbol):** Incluye ramas secundarias o nodos de repaso sobre temas generales. Usa COLOR VERDE para estos. Temas: {review_topics_str}

TEMAS DÉBILES: {weak_topics_str}

Genera HTML completo con:
- Nodos colapsables (botones con onclick)
- Colores: rojo para temas débiles, verde para dominados (repaso)
- Código Python en nodos finales
- CSS inline
- JavaScript para colapsar/expandir

Responde SOLO con HTML completo, sin explicaciones."""


def get_mind_map_prompt(text_title, text_topic, weak_topics, review_topics, text_content_preview):
    """Prompt para Mapa Mental"""
    
    # Se definen los strings de temas
    weak_topics_str = ", ".join(weak_topics) if weak_topics else "Ninguno"
    review_topics_str = ", ".join(review_topics) if review_topics else "Ninguno"
    
    return f"""Crea un mapa mental interactivo en HTML sobre: {text_topic}

INSTRUCCIONES CRÍTICAS DE ENFOQUE (LÓGICA 75/25):
El mapa debe reflejar esta proporción de contenido:
1.  **ENFOQUE PRINCIPAL (75% del mapa):** Las ramas principales y más detalladas deben ser sobre los temas débiles. Usa COLOR ROJO para estos nodos. Temas: {weak_topics_str}
2.  **ENFOQUE DE REPASO (25% del mapa):** Incluye ramas secundarias para repasar conceptos generales. Usa COLOR VERDE para estos. Temas: {review_topics_str}

TEMAS DÉBILES: {weak_topics_str}

Genera HTML completo con:
- Nodo central con el tema principal
- Ramas principales (4-6) (priorizando {weak_topics_str})
- Sub-ramas (3-5 por rama)
- Colores: rojo para débiles, verde para dominados (repaso)
- CSS inline
- Nodos expandibles

Responde SOLO con HTML completo, sin explicaciones."""


def get_summary_prompt(text_title, text_topic, weak_topics, review_topics, incorrect_questions_text, score, text_content_preview):
    """Prompt para Resumen Estructurado"""
    
    # Se definen los strings de temas
    weak_topics_str = ", ".join(weak_topics) if weak_topics else "Ninguno"
    review_topics_str = ", ".join(review_topics) if review_topics else "Ninguno"
    
    return f"""Crea un resumen estructurado en HTML sobre: {text_title}

SCORE: {score}%
TEMAS DÉBILES (ERRORES): {weak_topics_str}
TEMAS DE REPASO (GENERALES): {review_topics_str}

INSTRUCCIONES CRÍTICAS DE ESTRUCTURA (LÓGICA 75/25):
El resumen debe tener las siguientes secciones, respetando la proporción de contenido:

1.  **DONDE NECESITAS REFORZAR (75% del contenido)**
    * Esta es la sección principal. Enfócate en explicar detalladamente los temas débiles: {weak_topics_str}
    * Usa los errores específicos del alumno como contexto:
        {incorrect_questions_text}
    * Proporciona explicaciones claras, ejemplos de código Python comentados y cómo evitar esos errores.
    * Usa un fondo o borde ROJO/ROSADO para esta sección.

2.  **REPASO RÁPIDO DE CONCEPTOS (25% del contenido)**
    * Esta sección es para repasar temas generales y mantenerlos frescos.
    * Enfócate en: {review_topics_str}
    * Usa bullet points o listas breves. No necesita ser tan detallado como la sección de refuerzo.
    * Usa un fondo o borde VERDE/AZULADO para esta sección.

(El resumen debe mezclar estas dos secciones, pero manteniendo la proporción 75/25. El formato original 60/20/20 de abajo ya no aplica, usa el 75/25 de arriba)


ESTRUCTURA (60% en temas débiles): (Esta línea se ignora, se prioriza el 75/25)

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