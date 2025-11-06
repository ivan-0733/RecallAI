def get_flashcard_prompt(text_title, text_topic, weak_topics, incorrect_questions_text, text_content_preview):
    """
    Prompt para Flashcards interactivas con estilo minimalista de élite y cabecera de temas.
    """
    
    # Preparamos los temas débiles para el prompt.
    # Usamos los 3 principales, o el tema general si no hay.
    topic_1 = weak_topics[0] if weak_topics else text_topic
    topic_2 = weak_topics[1] if len(weak_topics) > 1 else topic_1
    topic_3 = weak_topics[2] if len(weak_topics) > 2 else topic_2
    
    # Creamos un string con los temas débiles para el cabecero
    weak_topics_str_list = ', '.join([f"'{t}'" for t in weak_topics[:3]])

    # NOTA: El bloque <style> al final de este f-string tiene llaves dobles {{ }} para escapar el CSS.
    return f"""Eres un experto diseñador UI/UX y un pedagogo de élite especializado en Procesamiento Digital de Imágenes. Tu estándar de calidad es el más alto.

TAREA PRINCIPAL:
Tu tarea es generar un HTML completo para una sesión de estudio interactiva. Este HTML debe ser EXTREMADAMENTE bonito, elegante, limpio y minimalista, aunque requiera mucho HTML y CSS inline.

El HTML debe tener DOS (2) partes:
1. Un cabecero de 'Temas de Enfoque' (Weak Topics) con un diseño premium.
2. Un 'grid' de 15 flashcards minimalistas que se voltean suavemente.

CONTEXTO DEL ALUMNO:
- Texto Estudiado: "{text_title}"
- Tema Principal: {text_topic}
- Temas donde MÁS falló (Weak Topics): {weak_topics_str_list}
- Errores específicos: {incorrect_questions_text[:800]}

INSTRUCCIONES DE CALIDAD (CRÍTICO Y OBLIGATORIO):
- ¡NO TE LIMITES POR LA CANTIDAD DE TOKENS! La calidad del diseño, la precisión de la información y la estructura impecable son tu única prioridad. Puedes usar todos los tokens que necesites. No resumas si la explicación requiere detalle.
- ¡VALIDACIÓN MÚLTIPLE! Valida tu salida múltiples veces. El HTML y CSS no deben romperse, ni superponerse, ni salirse de los márgenes. El diseño debe ser perfecto y estable. La alineación y el espaciado deben ser impecables.
- REDACCIÓN: La redacción debe ser profesional, clara y experta.
- CSS: Usa CSS 100% inline, excepto la animación `.flipped` que irá en una etiqueta `<style>`.

---
PARTE 1: CABECERO DE TEMAS DE ENFOQUE (Weak Topics)
---
Primero, genera este cabecero. Debe ser elegante y destacar los temas a reforzar.

ESTRUCTURA DEL CABECERO (HTML):
```html
<div class="weak-topics-header" style="background: linear-gradient(135deg, #f5f7fa 0%, #eef2ff 100%); border: 1px solid #dcdfe6; padding: 25px 30px; border-radius: 18px; margin-bottom: 40px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); font-family: 'Segoe UI', sans-serif;">
    <h3 style="margin: 0 0 18px 0; font-size: 20px; font-weight: 600; color: #333d4b;">Tus Áreas de Enfoque Personalizadas</h3>
    <div class="topics-container" style="display: flex; flex-wrap: wrap; gap: 12px;">
        <span style="background: #ffffff; border: 1px solid #dcdfe6; color: #c53030; font-weight: 500; padding: 8px 16px; border-radius: 20px; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.03); display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 1.2em;">⚠️</span> {topic_1}
        </span>
        <span style="background: #ffffff; border: 1px solid #dcdfe6; color: #dd6b20; font-weight: 500; padding: 8px 16px; border-radius: 20px; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.03); display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 1.2em;">⚠️</span> {topic_2}
        </span>
        <span style="background: #ffffff; border: 1px solid #dcdfe6; color: #5a67d8; font-weight: 500; padding: 8px 16px; border-radius: 20px; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.03); display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 1.2em;">⚠️</span> {topic_3}
        </span>
        </div>
</div>
PARTE 2: GRID DE FLASHCARDS MINIMALISTAS (15 tarjetas)
Segundo, después del cabecero, genera un grid con 15 flashcards.
DISTRIBUCIÓN DE TEMAS (OBLIGATORIA):

9 flashcards sobre: "{topic_1}" (El tema MÁS débil)
4 flashcards sobre: "{topic_2}"
2 flashcards sobre: "{topic_3}"
ESTRUCTURA DEL GRID (HTML):
HTML

<div class="flashcard-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; perspective: 1800px;">
ESTRUCTURA DE CADA FLASHCARD (HTML):
Usa esta plantilla exacta para CADA una de las 15 flashcards. ¡El diseño es crucial!
HTML

    <div class="flashcard" onclick="this.classList.toggle('flipped')" style="width: 100%; height: 380px; cursor: pointer; font-family: 'Segoe UI', sans-serif;">
        <div class="flashcard-inner" style="position: relative; width: 100%; height: 100%; transition: transform 0.7s cubic-bezier(0.22, 1, 0.36, 1); transform-style: preserve-3d;">
            
            <div class="flashcard-front" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 18px; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.07), 0 2px 6px rgba(0,0,0,0.03); display: flex; flex-direction: column; justify-content: space-between; padding: 25px 30px;">
                <div>
                    <span style="font-size: 13px; font-weight: 600; color: #667eea; background: #eef2ff; padding: 6px 12px; border-radius: 15px; display: inline-block;">
                        [TEMA DE LA TARJETA (Ej: {topic_1})]
                    </span>
                </div>
                <h3 style="font-size: 22px; font-weight: 600; color: #2d3748; text-align: left; margin: 20px 0; line-height: 1.4;">
                    [CONCEPTO, TÉRMINO o PREGUNTA CLAVE. Debe ser conciso pero claro.]
                </h3>
                <p style="font-size: 13px; color: #a0aec0; text-align: left; margin-top: auto; font-weight: 500;">
                    Haz clic para ver la explicación
                </p>
            </div>
            
            <div class="flashcard-back" style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 18px; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.07); padding: 25px 30px; transform: rotateY(180deg); overflow-y: auto; color: #4a5568; line-height: 1.7;">
                <h4 style="color: #667eea; margin: 0 0 10px 0; font-size: 16px; border-bottom: 2px solid #eef2ff; padding-bottom: 8px; font-weight: 600;">
                    Explicación Detallada
                </h4>
                <p style="font-size: 16px;">
                    [EXPLICACIÓN CLARA, PRECISA Y BIEN REDACTADA. Usa 2-3 párrafos si es necesario. NO TE LIMITES. La calidad y profundidad importan más que la brevedad.]
                </p>
                
                <div style="background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 10px; margin-top: 15px; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.5;">
                    <code style="white-space: pre-wrap;">[EJEMPLO DE CÓDIGO (si aplica)]</code>
                </div>
                
                <div style="background: #fff5f5; border-left: 4px solid #fc8181; padding: 12px 15px; margin-top: 15px; font-size: 14px; line-height: 1.6;">
                    <strong>Punto clave (Error Común):</strong> [Relaciona esto con los errores del alumno o un error común, basado en: {incorrect_questions_text}]
                </div>
            </div>
        </div>
    </div>
CIERRE DEL HTML
Cierra el grid y añade la etiqueta <style> para la animación.
HTML

</div> <style>
    /* Animación de volteo */
    .flashcard.flipped .flashcard-inner {{
        transform: rotateY(180deg);
    }}
    /* Para mejorar el scroll en la cara trasera */
    .flashcard-back {{
        scrollbar-width: thin;
        scrollbar-color: #a0aec0 #f7fafc;
    }}
    .flashcard-back::-webkit-scrollbar {{
        width: 6px;
    }}
    .flashcard-back::-webkit-scrollbar-thumb {{
        background-color: #a0aec0;
        border-radius: 10px;
    }}</style>
REQUISITOS FINALES:

Retorna un SOLO bloque de HTML.
El HTML debe empezar con el <div class="weak-topics-header">...</div>.
Seguido por <div class="flashcard-grid">... conteniendo EXACTAMENTE 15 flashcards.
Termina con la etiqueta <style>.
No incluyas markdown (```html) en la salida final.
Valida la estructura 100%. No falles. El diseño debe ser perfecto.
"""

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