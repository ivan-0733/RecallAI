import logging

logger = logging.getLogger(__name__)

# --- INICIA LA FUNCIÓN MODIFICADA ---

# (El resto de prompts.py... logging, get_decision_tree_prompt, etc.)

# --- INICIA LA FUNCIÓN MODIFICADA Y CORREGIDA ---

def get_flashcard_prompt(weak_topics, subject="General", **kwargs):
    """
    Genera un prompt para crear un carrusel de 20 flashcards interactivas.
    El prompt le pide a la IA que genere un bloque HTML/CSS/JS auto-contenido
    que muestra una tarjeta a la vez, con navegación y animación de volteo al hacer clic.
    
    El **kwargs se añade para aceptar y descartar argumentos adicionales 
    (como text_title, text_topic, etc.) que la tarea de Celery envía.
    """
    
    # Convierte la lista de temas en un string legible
    topics_str = ", ".join(weak_topics)

    # El prompt ahora es extremadamente específico y provee todo el "boilerplate".
    # La IA solo debe rellenar el contenido de [CONCEPTO] y [DEFINICIÓN].
    prompt = f"""
    Actúa como un desarrollador frontend senior y diseñador instruccional experto.
    Tu tarea es generar un (1) bloque de código HTML auto-contenido para un
    CARROUSEL de 20 FLASHCARDS interactivas.

    El objetivo es reforzar los siguientes temas débiles: **{topics_str}**
    de la materia de **{subject}**.

    **REQUERIMIENTOS ESTRICTOS DE DISEÑO Y FUNCIONALIDAD:**

    1.  **Total de Tarjetas:** Genera **exactamente 20 tarjetas**. Si los temas débiles son pocos (ej. 4), debes crear 5 tarjetas para cada tema. Si son muchos (ej. 20), crea 1 tarjeta por tema. El total debe ser 20.
    2.  **Formato de Contenido:** El formato NO debe ser pregunta-respuesta. Debe ser **"Concepto"** en el frente y **"Definición"** en el reverso.
    3.  **Funcionalidad del Carrusel:**
        * Solo se debe ver **una (1) tarjeta a la vez**.
        * Debe haber un **contador** en la esquina inferior izquierda (ej: "1 / 20").
        * Debe haber **flechas de navegación** (Siguiente/Anterior) en la esquina inferior derecha.
    4.  **Funcionalidad de Volteo:**
        * La tarjeta se voltea al **hacer clic sobre ella** (sobre la tarjeta, no un botón).
        * La tarjeta debe volver a su estado original (sin voltear) cuando se navega a la siguiente o anterior.
    5.  **Código Auto-contenido:** El bloque HTML final debe incluir:
        * Una (1) etiqueta `<style>` con TODO el CSS.
        * Una (1) etiqueta `<script>` con TODO el JavaScript.
        * El HTML para el mazo, las 20 tarjetas, el contador y la navegación.
    6.  **Estilo:** Profesional, centrado, modo oscuro (dark-mode), legible y pulido.

    **UTILIZA ESTE CÓDIGO HTML, CSS Y JS EXACTO COMO PLANTILLA:**
    Asegúrate de que la IA llene los 20 bloques `flashcard-container`.

    ```html
    <style>
    /* Contenedor principal del mazo de tarjetas */
    .flashcard-deck {{
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        position: relative;
        width: 100%;
        max-width: 500px; /* Ancho máximo del carrusel */
        height: 350px;     /* Alto fijo para el carrusel */
        margin: 20px auto; /* Centrado en la página */
    }}

    /* Contenedor de una sola tarjeta (para posicionamiento y perspectiva) */
    .flashcard-container {{
        width: 100%;
        height: 100%;
        perspective: 1200px;
        position: absolute;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.4s ease-in-out;
        display: flex; /* Para centrar la tarjeta interna */
        justify-content: center;
        align-items: center;
    }}

    /* Tarjeta activa (visible) */
    .flashcard-container.is-active {{
        opacity: 1;
        pointer-events: all;
    }}

    /* La tarjeta interna que gira */
    .flashcard {{
        width: 90%; /* Un poco más pequeña que el contenedor */
        height: 90%;
        position: relative;
        transform-style: preserve-3d;
        transition: transform 0.7s cubic-bezier(0.4, 0.0, 0.2, 1);
        cursor: pointer;
    }}

    /* Clase que se añade con JS para activar el giro */
    .flashcard.is-flipped {{
        transform: rotateY(180deg);
    }}

    /* Estilo común para ambas caras */
    .card-face {{
        position: absolute;
        width: 100%;
        height: 100%;
        -webkit-backface-visibility: hidden;
        backface-visibility: hidden;
        
        border-radius: 16px;
        background-color: #2d2d2d; /* Fondo oscuro */
        color: #e0e0e0; /* Texto claro */
        border: 1px solid #444;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5);
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
    }}

    /* Cara frontal: CONCEPTO */
    .card-face.card-front {{
        justify-content: center;
        align-items: center;
        padding: 25px;
        font-size: 1.8em;
        font-weight: 600;
        text-align: center;
    }}

    /* Cara trasera: DEFINICIÓN */
    .card-face.card-back {{
        transform: rotateY(180deg);
        justify-content: flex-start;
        align-items: flex-start;
        padding: 30px;
    }}

    .card-back h4 {{
        margin: 0 0 15px 0;
        color: #58a6ff; /* Acento azul */
        font-size: 1.2em;
        font-weight: 600;
        border-bottom: 1px solid #444;
        padding-bottom: 8px;
        width: 100%;
    }}

    .card-back p {{
        margin: 0;
        font-size: 1em;
        line-height: 1.6;
        overflow-y: auto;
        max-height: calc(100% - 60px); /* Límite de altura */
    }}
    
    /* Contenedor de Navegación */
    .card-navigation {{
        position: absolute;
        bottom: 25px;
        right: 25px;
        display: flex;
        gap: 10px;
    }}

    .nav-btn {{
        background-color: #3f3f3f;
        color: #e0e0e0;
        border: 1px solid #555;
        border-radius: 50%; /* Botones redondos */
        width: 40px;
        height: 40px;
        font-size: 20px;
        cursor: pointer;
        display: flex;
        justify-content: center;
        align-items: center;
        transition: background-color 0.3s, color 0.3s;
    }}

    .nav-btn:hover {{
        background-color: #58a6ff;
        color: #111;
    }}
    
    /* Contador de tarjetas */
    .card-counter {{
        position: absolute;
        bottom: 35px;
        left: 35px;
        font-size: 1em;
        color: #888;
        font-weight: 500;
    }}
    </style>

    <div class="flashcard-deck">
    
      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 1]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 1]</h4>
            <p>[Definición concisa y clara del concepto 1]</p>
          </div>
        </div>
      </div>
      
      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 2]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 2]</h4>
            <p>[Definición concisa y clara del concepto 2]</p>
          </div>
        </div>
      </div>
      
      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 3]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 3]</h4>
            <p>[Definición concisa y clara del concepto 3]</p>
          </div>
        </div>
      </div>
      
      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 4]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 4]</h4>
            <p>[Definición concisa y clara del concepto 4]</p>
          </div>
        </div>
      </div>
      
      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 5]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 5]</h4>
            <p>[Definición concisa y clara del concepto 5]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 6]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 6]</h4>
            <p>[Definición concisa y clara del concepto 6]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 7]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 7]</h4>
            <p>[Definición concisa y clara del concepto 7]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 8]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 8]</h4>
            <p>[Definición concisa y clara del concepto 8]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 9]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 9]</h4>
            <p>[Definición concisa y clara del concepto 9]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 10]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 10]</h4>
            <p>[Definición concisa y clara del concepto 10]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 11]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 11]</h4>
            <p>[Definición concisa y clara del concepto 11]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 12]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 12]</h4>
            <p>[Definición concisa y clara del concepto 12]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 13]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 13]</h4>
            <p>[Definición concisa y clara del concepto 13]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 14]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 14]</h4>
            <p>[Definición concisa y clara del concepto 14]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 15]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 15]</h4>
            <p>[Definición concisa y clara del concepto 15]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 16]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 16]</h4>
            <p>[Definición concisa y clara del concepto 16]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 17]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 17]</h4>
            <p>[Definición concisa y clara del concepto 17]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 18]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 18]</h4>
            <p>[Definición concisa y clara del concepto 18]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 19]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 19]</h4>
            <p>[Definición concisa y clara del concepto 19]</p>
          </div>
        </div>
      </div>

      <div class="flashcard-container">
        <div class="flashcard" onclick="flipCard(this)">
          <div class="card-face card-front">
            <h3>[CONCEPTO 20]</h3>
          </div>
          <div class="card-face card-back">
            <h4>[CONCEPTO 20]</h4>
            <p>[Definición concisa y clara del concepto 20]</p>
          </div>
        </div>
      </div>
      <div class="card-counter" id="deck-counter">1 / 20</div>
      
      <div class="card-navigation">
        <button class="nav-btn" id="prev-card" onclick="prevCard()">&#x2190;</button>
        <button class="nav-btn" id="next-card" onclick="nextCard()">&#x2192;</button>
      </div>

    </div>

    <script>
    // Se encapsula el script para evitar colisiones de variables
    (function() {{
        let currentCardIndex = 0;
        let cards = [];
        let counterElement = null;

        // Función para mostrar una tarjeta específica
        function showCard(index) {{
            if (!cards || cards.length === 0) return;

            // Ocultar todas las tarjetas y quitar 'is-flipped'
            cards.forEach((cardContainer, i) => {{
                cardContainer.classList.remove('is-active');
                const flashcard = cardContainer.querySelector('.flashcard');
                if (flashcard) {{
                    flashcard.classList.remove('is-flipped');
                }}
            }});

            // Mostrar la tarjeta en el índice dado
            if (cards[index]) {{
                cards[index].classList.add('is-active');
            }}

            // Actualizar contador
            if (counterElement) {{
                // --- LÍNEA CORREGIDA ---
                // Se cambió de JS template literal (`${...}`) a concatenación
                // simple para evitar conflictos con el f-string de Python.
                counterElement.textContent = (index + 1) + " / " + cards.length;
                // --- FIN DE LA CORRECCIÓN ---
            }}
        }}

        // Función para la tarjeta siguiente
        window.nextCard = function() {{
            currentCardIndex = (currentCardIndex + 1) % cards.length;
            showCard(currentCardIndex);
        }}

        // Función para la tarjeta anterior
        window.prevCard = function() {{
            currentCardIndex = (currentCardIndex - 1 + cards.length) % cards.length;
            showCard(currentCardIndex);
        }}

        // Función para voltear la tarjeta actual
        window.flipCard = function(cardElement) {{
            // 'cardElement' es el div .flashcard que se clickeó
            cardElement.classList.toggle('is-flipped');
        }}

        // Inicializar el carrusel cuando el DOM esté listo
        // Se usa un pequeño timeout para asegurar que el HTML se haya renderizado
        setTimeout(function() {{
            // Buscar elementos dentro del scope del .flashcard-deck
            const deck = document.querySelector('.flashcard-deck');
            if (deck) {{
                cards = deck.querySelectorAll('.flashcard-container');
                counterElement = deck.querySelector('#deck-counter');
                
                if(cards.length > 0) {{
                    showCard(currentCardIndex);
                }} else {{
                    console.error("No se encontraron tarjetas ('.flashcard-container')");
                }}
            }} else {{
                console.error("No se encontró el contenedor ('.flashcard-deck')");
            }}
        }}, 100); // 100ms de espera
    }})();
    </script>
    ```

    Por favor, genera el bloque HTML completo **llenando los 20 contenedores de tarjetas** (`.flashcard-container`) con un **Concepto** y una **Definición** para cada uno, basándote en los temas débiles **{topics_str}**.
    Asegúrate de que el bloque de CÓDIGO HTML que generes sea único, completo (con style, script y divs) y siga la plantilla al pie de la letra.
    **NO OMITAS NI UNA SOLA TARJETA. DEBEN SER 20.**
    """
    
    logger.debug(f"Generando prompt de carrusel de 20 flashcards para los temas: {topics_str}")
    return prompt

# --- FIN DE LA FUNCIÓN ---

def get_decision_tree_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, text_content_preview):
    """Prompt para Árbol de Decisión"""
    
    weak_topics_str = ', '.join(weak_topics[:2]) if weak_topics else text_topic
    
    return f"""Eres un experto en diseño instruccional para PDI.

CONTEXTO:
- Texto: "{text_title}"
- Tema: {text_topic}
- Temas donde falló: {weak_topics_str}
- Eligió: Árbol de Decisión

CONTENIDO:
{text_content_preview[:2000]}

ERRORES:
{incorrect_questions_text[:800]}

TAREA:
Genera un árbol de decisión interactivo en HTML puro para ayudar a elegir técnicas de PDI.

ENFOQUE:
- 70% enfocado en: {weak_topics_str}
- Las ramas llevan a técnicas que el alumno NO usó correctamente

ESTRUCTURA COMPLETA:
```html
<div class="decision-tree" style="font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px;">
    
    <div class="tree-node" id="node-start" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 30px; box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);">
        <h2 style="margin: 0 0 20px 0;">🤔 ¿Qué problema estás resolviendo?</h2>
        <p style="opacity: 0.9; margin-bottom: 25px;">Selecciona el escenario:</p>
        
        <button onclick="showNode('noise')" style="display: block; width: 100%; padding: 15px; margin: 10px 0; background: white; color: #667eea; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            [PROBLEMA 1 RELACIONADO CON TEMA DÉBIL]
        </button>
        
        <button onclick="showNode('option2')" style="display: block; width: 100%; padding: 15px; margin: 10px 0; background: white; color: #667eea; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            [PROBLEMA 2]
        </button>
        
        <button onclick="showNode('option3')" style="display: block; width: 100%; padding: 15px; margin: 10px 0; background: white; color: #667eea; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            [PROBLEMA 3]
        </button>
    </div>
    
    <!-- NODO PRINCIPAL (tema débil) -->
    <div class="tree-node hidden" id="node-noise" style="background: white; border: 3px solid #667eea; border-radius: 15px; padding: 30px; margin-bottom: 30px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); display: none;">
        <button onclick="showNode('start')" style="background: #e2e8f0; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin-bottom: 20px;">← Volver</button>
        
        <h3 style="color: #667eea; margin-bottom: 20px;">[TÍTULO DEL PROBLEMA]</h3>
        <p style="margin-bottom: 20px;">[PREGUNTA DE REFINAMIENTO]</p>
        
        <!-- OPCIÓN CORRECTA QUE NO ELIGIÓ -->
        <div class="decision-option" style="background: #f0fff4; border: 3px solid #48bb78; border-radius: 10px; padding: 20px; margin: 15px 0; position: relative;">
            <span style="position: absolute; top: -15px; right: 20px; background: #48bb78; color: white; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold;">⭐ LO QUE DEBISTE USAR</span>
            
            <h4 style="color: #2f855a; margin-top: 0;">✅ [TÉCNICA CORRECTA]</h4>
            <p style="line-height: 1.6;">[EXPLICACIÓN]</p>
            
            <div style="background: #2d3748; color: #68d391; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <code style="font-size: 13px;">[CÓDIGO PYTHON]</code>
            </div>
            
            <div style="background: #fff5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #fc8181;">
                <p style="margin: 0;"><strong>❌ TÚ ELEGISTE:</strong> [TÉCNICA INCORRECTA]</p>
                <p style="margin: 10px 0 0 0; color: #c53030;"><strong>Problema:</strong> [POR QUÉ ESTÁ MAL]</p>
            </div>
            
            <div style="background: #ebf8ff; padding: 15px; border-radius: 8px; margin-top: 15px;">
                <p style="margin: 0;"><strong>📊 Cuándo usar:</strong></p>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>[CONDICIÓN 1]</li>
                    <li>[CONDICIÓN 2]</li>
                </ul>
            </div>
        </div>
        
        <!-- ALTERNATIVA -->
        <div class="decision-option" style="background: #f7fafc; border: 2px solid #cbd5e0; border-radius: 10px; padding: 20px; margin: 15px 0;">
            <h4 style="color: #4a5568; margin-top: 0;">[ALTERNATIVA]</h4>
            <p>[CUÁNDO USARLA]</p>
            
            <div style="background: #2d3748; color: #68d391; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <code style="font-size: 13px;">[CÓDIGO]</code>
            </div>
        </div>
    </div>
    
    <!-- MÁS NODOS (crea 2-3 nodos adicionales similares) -->
    
</div>

<script>
function showNode(nodeId) {{
    // Ocultar todos
    var nodes = document.querySelectorAll('.tree-node');
    nodes.forEach(function(node) {{
        node.style.display = 'none';
    }});
    
    // Mostrar el seleccionado
    var targetNode = document.getElementById('node-' + nodeId);
    if (targetNode) {{
        targetNode.style.display = 'block';
    }}
}}

// Mostrar nodo inicial
document.getElementById('node-start').style.display = 'block';
</script>
```

REQUISITOS:
- HTML válido
- 3-4 nodos totales
- 70% enfocado en temas débiles
- JS inline para navegación
- Comparar con errores del alumno
- Máximo 5 niveles

RETORNA:
- SOLO HTML completo + script
- Sin markdown
- Sin explicaciones"""


def get_mind_map_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, text_content_preview):
    """Prompt para Mapa Mental"""
    
    weak_topics_str = ', '.join(weak_topics[:3]) if weak_topics else text_topic
    
    return f"""Eres un experto en mapas conceptuales para PDI.

CONTEXTO:
- Texto: "{text_title}"
- Tema: {text_topic}
- Temas débiles: {weak_topics_str}
- Eligió: Mapa Mental

CONTENIDO:
{text_content_preview[:2000]}

ERRORES:
{incorrect_questions_text[:800]}

TAREA:
Genera un mapa mental interactivo y colapsable en HTML.

REGLAS DE ÉNFASIS:
- Nodos de temas débiles: clase "weak-topic" + badge "⚠️ Reforzar"
- {weak_topics[0] if weak_topics else text_topic}: 5 sub-nodos MUY detallados
- {weak_topics[1] if len(weak_topics) > 1 else text_topic}: 3 sub-nodos
- Otros temas: 1-2 sub-nodos (overview)

ESTRUCTURA COMPLETA:
```html
<div class="mind-map" style="font-family: 'Segoe UI', sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px;">
    
    <!-- NODO CENTRAL -->
    <div class="central-node" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 20px; text-align: center; margin-bottom: 40px; box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);">
        <h2 style="margin: 0; font-size: 28px;">🖼️ {text_title}</h2>
        <p style="opacity: 0.9; margin: 10px 0 0 0;">Mapa conceptual personalizado</p>
    </div>
    
    <!-- RAMA 1: TEMA MÁS DÉBIL (60%) -->
    <div class="branch" style="margin-bottom: 30px;">
        <button class="node weak-topic" onclick="toggleBranch(this)" style="display: block; width: 100%; padding: 20px; background: #fff5f5; border: 3px solid #fc8181; border-radius: 12px; cursor: pointer; text-align: left; font-size: 18px; font-weight: 600; color: #c53030; position: relative; transition: all 0.3s;" onmouseover="this.style.transform='translateX(5px)'" onmouseout="this.style.transform='translateX(0)'">
            🌫️ {weak_topics[0] if weak_topics else text_topic}
            <span style="position: absolute; right: 20px; top: 50%; transform: translateY(-50%); background: #fc8181; color: white; padding: 5px 12px; border-radius: 15px; font-size: 12px;">⚠️ Reforzar</span>
        </button>
        
        <div class="sub-nodes" style="margin-left: 30px; margin-top: 15px; display: none; padding-left: 20px; border-left: 3px solid #fc8181;">
            
            <!-- SUB-NODO 1 -->
            <div class="sub-node" style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 3px 10px rgba(0,0,0,0.1); border-left: 5px solid #fc8181;">
                <strong style="color: #c53030; font-size: 16px;">[CONCEPTO 1]</strong>
                <p style="margin: 10px 0; line-height: 1.6;">[EXPLICACIÓN DETALLADA]</p>
                
                <div style="background: #2d3748; color: #68d391; padding: 12px; border-radius: 8px; margin: 10px 0;">
                    <code style="font-size: 13px;">[CÓDIGO PYTHON]</code>
                </div>
                
                <div style="background: #fff5f5; padding: 12px; border-radius: 8px; border-left: 4px solid #fc8181; margin-top: 10px;">
                    <p style="margin: 0; font-size: 14px;"><strong>❌ Tu error:</strong> [REFERENCIA A ERROR DEL ALUMNO]</p>
                    <p style="margin: 8px 0 0 0; color: #38a169;"><strong>✅ Lo correcto:</strong> [EXPLICACIÓN]</p>
                </div>
            </div>
            
            <!-- SUB-NODOS 2-5 (repetir estructura similar) -->
            
        </div>
    </div>
    
    <!-- RAMA 2: SEGUNDO TEMA DÉBIL (25%) -->
    <div class="branch" style="margin-bottom: 30px;">
        <button class="node weak-topic" onclick="toggleBranch(this)" style="display: block; width: 100%; padding: 20px; background: #fffaf0; border: 3px solid #ed8936; border-radius: 12px; cursor: pointer; text-align: left; font-size: 18px; font-weight: 600; color: #dd6b20;" onmouseover="this.style.transform='translateX(5px)'" onmouseout="this.style.transform='translateX(0)'">
            {weak_topics[1] if len(weak_topics) > 1 else 'Otro Tema'}
            <span style="position: absolute; right: 20px; top: 50%; transform: translateY(-50%); background: #ed8936; color: white; padding: 5px 12px; border-radius: 15px; font-size: 12px;">⚠️ Reforzar</span>
        </button>
        
        <div class="sub-nodes" style="margin-left: 30px; margin-top: 15px; display: none; padding-left: 20px; border-left: 3px solid #ed8936;">
            <!-- 3 SUB-NODOS (estructura similar) -->
        </div>
    </div>
    
    <!-- RAMA 3: OTROS TEMAS (15%) -->
    <div class="branch" style="margin-bottom: 30px;">
        <button class="node" onclick="toggleBranch(this)" style="display: block; width: 100%; padding: 20px; background: #f0fff4; border: 2px solid #48bb78; border-radius: 12px; cursor: pointer; text-align: left; font-size: 18px; font-weight: 600; color: #2f855a;" onmouseover="this.style.transform='translateX(5px)'" onmouseout="this.style.transform='translateX(0)'">
            [TEMA QUE SÍ DOMINA] ✅
        </button>
        
        <div class="sub-nodes" style="margin-left: 30px; margin-top: 15px; display: none; padding-left: 20px; border-left: 3px solid #48bb78;">
            <!-- 1-2 SUB-NODOS BREVES -->
        </div>
    </div>
    
</div>

<script>
function toggleBranch(button) {{
    var subNodes = button.nextElementSibling;
    if (subNodes && subNodes.classList.contains('sub-nodes')) {{
        if (subNodes.style.display === 'none' || subNodes.style.display === '') {{
            subNodes.style.display = 'block';
        }} else {{
            subNodes.style.display = 'none';
        }}
    }}
}}
</script>
```

REQUISITOS:
- HTML válido
- Nodos colapsables
- 60% en tema más débil (5 sub-nodos)
- 25% en segundo tema (3 sub-nodos)
- Referencias a errores específicos
- Código Python en sub-nodos principales
- CSS inline rojo para weak-topics

RETORNA:
- SOLO HTML + script
- Sin markdown
- Sin explicaciones"""


def get_summary_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, score, text_content_preview):
    """Prompt para Resumen Estructurado"""
    
    weak_topics_str = ', '.join(weak_topics[:3]) if weak_topics else text_topic
    
    return f"""Eres un experto en síntesis pedagógica para PDI.

CONTEXTO:
- Texto: "{text_title}"
- Score actual: {score}%
- Temas donde MÁS falló: {weak_topics_str}
- Eligió: Resumen Estructurado

CONTENIDO:
{text_content_preview[:2500]}

ERRORES:
{incorrect_questions_text[:1000]}

TAREA:
Genera un resumen estructurado en HTML del texto completo.

ESTRUCTURA DEL RESUMEN:

1. **Conceptos Esenciales** (20%)
   - Definiciones clave de TODO el texto
   - Muy breve

2. **SECCIÓN AMPLIADA: Temas donde Fallaste** (60%)
   - Explicación DETALLADA de cada tema débil
   - Por qué es importante
   - Código de ejemplo
   - ERROR COMÚN: El error que cometió
   - CÓMO EVITARLO

3. **Repaso Rápido** (20%)
   - Bullet points de temas que dominó

HTML COMPLETO:
```html
<div class="summary-document" style="font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: white;">
    
    <!-- HEADER -->
    <header style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0 0 10px 0; font-size: 28px;">{text_title}</h1>
        <p style="margin: 0; opacity: 0.9; font-size: 16px;">Resumen Personalizado</p>
        <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 8px; margin-top: 15px;">
            <p style="margin: 0; font-size: 14px;">📊 Enfocado en tus áreas de oportunidad detectadas</p>
        </div>
    </header>
    
    <!-- SECCIÓN 1: CONCEPTOS ESENCIALES (20%) -->
    <section style="margin-bottom: 30px; padding: 20px; background: #f7fafc; border-radius: 10px;">
        <h2 style="color: #667eea; margin-top: 0; border-bottom: 3px solid #667eea; padding-bottom: 10px;">📌 Conceptos Esenciales</h2>
        <ul style="line-height: 1.8; color: #2d3748;">
            <li><strong>[Concepto 1]:</strong> [Definición breve en 1 línea]</li>
            <li><strong>[Concepto 2]:</strong> [Definición breve]</li>
            <!-- 5-7 conceptos clave del texto completo -->
        </ul>
    </section>
    
    <!-- SECCIÓN 2: DONDE NECESITAS REFORZAR (60%) -->
    <section style="margin-bottom: 30px;">
        <h2 style="color: #fc8181; margin-top: 0; border-bottom: 3px solid #fc8181; padding-bottom: 10px;">🎯 Donde Necesitas Reforzar (60% del resumen)</h2>
        
        <!-- TEMA DÉBIL 1 -->
        <article style="background: #fff5f5; border: 3px solid #fc8181; border-radius: 12px; padding: 25px; margin-bottom: 25px;">
            <h3 style="color: #c53030; margin-top: 0;">🔴 {weak_topics[0] if weak_topics else text_topic}</h3>
            
            <div style="margin-bottom: 20px;">
                <h4 style="color: #667eea;">¿Qué es?</h4>
                <p style="line-height: 1.8; color: #2d3748;">[EXPLICACIÓN DETALLADA EN 4-5 LÍNEAS CON PROFUNDIDAD]</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h4 style="color: #667eea;">¿Por qué importa?</h4>
                <p style="line-height: 1.8; color: #2d3748;">[APLICACIONES PRÁCTICAS Y RELEVANCIA]</p>
            </div>
            
            <div style="background: #2d3748; color: #68d391; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h4 style="color: #68d391; margin-top: 0;">💻 Ejemplo de código:</h4>
                <code style="font-size: 14px; display: block; white-space: pre-wrap;">[CÓDIGO PYTHON CON COMENTARIOS PASO A PASO]</code>
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 8px; border-left: 5px solid #fc8181; margin: 20px 0;">
                <h4 style="color: #c53030; margin-top: 0;">❌ Tu Error Específico:</h4>
                <p style="margin: 0;">En la pregunta "[PREGUNTA QUE FALLÓ]", elegiste [OPCIÓN INCORRECTA].</p>
                <p style="margin: 10px 0 0 0;"><strong>El problema:</strong> [EXPLICACIÓN DEL ERROR]</p>
            </div>
            
            <div style="background: #f0fff4; padding: 15px; border-radius: 8px; border-left: 5px solid #48bb78; margin: 20px 0;">
                <h4 style="color: #2f855a; margin-top: 0;">💡 Cómo Recordarlo:</h4>
                <ul style="margin: 10px 0; padding-left: 20px; line-height: 1.8;">
                    <li>[TÉCNICA MNEMOTÉCNICA 1]</li>
                    <li>[ANALOGÍA VISUAL]</li>
                    <li>[COMPARACIÓN: X vs Y]</li>
                </ul>
            </div>
            
            <div style="margin: 20px 0;">
                <h4 style="color: #667eea;">📋 Referencia Rápida:</h4>
                <table style="width: 100%; border-collapse: collapse; border: 1px solid #e2e8f0;">
                    <tr style="background: #f7fafc;">
                        <td style="padding: 12px; border: 1px solid #e2e8f0; font-weight: bold;">Cuándo usar</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0;">[ESCENARIOS]</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; font-weight: bold;">Cuándo NO usar</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0;">[ANTIPATRONES]</td>
                    </tr>
                    <tr style="background: #f7fafc;">
                        <td style="padding: 12px; border: 1px solid #e2e8f0; font-weight: bold;">Alternativas</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0;">[OTRAS TÉCNICAS]</td>
                    </tr>
                </table>
            </div>
        </article>
        
        <!-- TEMA DÉBIL 2 (estructura similar pero más breve) -->
        
        <!-- TEMA DÉBIL 3 (aún más breve) -->
        
    </section>
    
    <!-- SECCIÓN 3: REPASO RÁPIDO (20%) -->
    <section style="background: #f0fff4; padding: 20px; border-radius: 10px; border: 2px solid #48bb78;">
        <h2 style="color: #2f855a; margin-top: 0;">✅ Repaso Rápido de Temas que Dominas</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
            <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #48bb78;">
                <h4 style="color: #2f855a; margin: 0 0 8px 0;">[Tema dominado 1]</h4>
                <p style="margin: 0; font-size: 14px; color: #4a5568;">[Recordatorio de 1 línea]</p>
            </div>
            <!-- 3-4 mini-topics más -->
        </div>
    </section>
    
    <!-- FOOTER: TIPS -->
    <footer style="background: #ebf8ff; padding: 20px; border-radius: 10px; margin-top: 30px; border-left: 5px solid #4299e1;">
        <h3 style="color: #2c5282; margin-top: 0;">📚 Tips de Estudio para Este Texto:</h3>
        <ul style="line-height: 1.8; color: #2d3748;">
            <li>Dedica más tiempo a: <strong>{weak_topics[0] if weak_topics else text_topic}</strong></li>
            <li>Práctica recomendada: [EJERCICIO ESPECÍFICO]</li>
            <li>Compara siempre: {weak_topics[0] if weak_topics else 'conceptos'} vs {weak_topics[1] if len(weak_topics) > 1 else 'alternativas'}</li>
        </ul>
    </footer>
    
</div>
```

REQUISITOS CRÍTICOS:
- 60% del contenido en "Temas donde Fallaste"
- Referencias EXPLÍCITAS a errores del alumno
- Código Python comentado paso a paso
- Tablas de referencia rápida
- Tono: tutorial personalizado

RETORNA:
- SOLO HTML completo
- Sin markdown
- Sin explicaciones"""