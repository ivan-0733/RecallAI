/**
 * ========================================
 * SISTEMA DE TRACKING ROBUSTO - RecallAI
 * ✅ CORRECCIONES APLICADAS:
 * - Problema 1: Detección precisa de tiempo inactivo
 * - Problema 2: Event listeners dinámicos para flashcards/mapas
 * - Problema 3: Datos de heatmap correctamente formateados
 * ========================================
 */

class StudyTracker {
    constructor(materialId, userId) {
        this.materialId = materialId;
        this.userId = userId;
        this.sessionId = this.generateUUID();
        this.sessionStartTime = Date.now();
        this.lastActivityTime = Date.now();
        this.isActive = true;
        this.tabVisible = true;
        
        // ✅ CORRECCIÓN PROBLEMA 1: Acumuladores de tiempo
        this.totalIdleTime = 0; // Acumulador de tiempo inactivo
        this.lastIdleCheck = Date.now(); // Última vez que chequeamos idle
        this.currentlyIdle = false; // Estado actual
        
        // Contadores
        this.metrics = {
            totalInteractions: 0,
            scrollEvents: 0,
            clickEvents: 0,
            hoverEvents: 0,
            focusChanges: 0,
            sectionsVisited: new Set(),
            maxScrollDepth: 0
        };
        
        // Buffers de eventos
        this.events = [];
        this.sectionTimes = new Map();
        this.heatmapData = {
            clicks: [],
            mouseMovements: [],
            scrollPoints: []
        };
        
        // Configuración
        this.idleThreshold = 30000; // 30 segundos sin actividad = idle
        this.batchSize = 50; // Enviar datos cada 50 eventos
        this.mouseSampleRate = 100; // Samplear mouse cada 100ms
        
        // Estado
        this.currentSection = null;
        this.sectionStartTime = null;
        
        this.init();
    }
    
    // ============================================
    // INICIALIZACIÓN
    // ============================================
    
    init() {
        console.log(`🎯 StudyTracker iniciado - Sesión: ${this.sessionId}`);
        
        // Crear sesión en backend
        this.createSession();
        
        // Inicializar listeners
        this.initEventListeners();
        
        // Iniciar timers
        this.startIdleDetection();
        this.startPeriodicSync();
        this.startMouseTracking();
        
        // Marcar secciones del DOM
        this.markSections();
        
        // Guardar sesión al salir
        window.addEventListener('beforeunload', () => this.endSession('browser_close'));
        
        console.log('✅ Tracking activado completamente');
    }
    
    // ============================================
    // GESTIÓN DE SESIÓN
    // ============================================
    
    async createSession() {
        const sessionData = {
            session_id: this.sessionId,
            material_id: this.materialId,
            device_type: this.getDeviceType(),
            browser: this.getBrowser(),
            screen_resolution: `${window.screen.width}x${window.screen.height}`,
            started_at: new Date().toISOString()
        };
        
        try {
            const response = await fetch('/api/tracking/session/start/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(sessionData)
            });
            
            if (response.ok) {
                console.log('✅ Sesión creada en backend');
            }
        } catch (error) {
            console.error('❌ Error creando sesión:', error);
        }
    }
    
    async endSession(exitType = 'normal') {
        this.isActive = false;
        
        // ✅ CORRECCIÓN PROBLEMA 1: Calcular tiempo activo final correctamente
        this.updateIdleAccumulator(); // Actualizar una última vez antes de finalizar
        
        const duration = this.getSessionDuration();
        const activeTime = this.calculateActiveTime();
        
        const endData = {
            session_id: this.sessionId,
            ended_at: new Date().toISOString(),
            total_time_seconds: Math.floor(duration / 1000),
            active_time_seconds: Math.floor(activeTime / 1000),
            exit_type: exitType,
            metrics: this.getMetricsSummary()
        };
        
        console.log('📊 Resumen final de sesión:', {
            total: `${Math.floor(duration / 1000)}s`,
            active: `${Math.floor(activeTime / 1000)}s`,
            idle: `${Math.floor(this.totalIdleTime / 1000)}s`
        });
        
        // Enviar todos los datos pendientes
        await this.syncData(true);
        
        // Finalizar sesión
        try {
            await fetch('/api/tracking/session/end/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(endData),
                keepalive: true // Importante para beforeunload
            });
            
            console.log('✅ Sesión finalizada:', endData);
        } catch (error) {
            console.error('❌ Error finalizando sesión:', error);
        }
    }
    
    // ============================================
    // EVENT LISTENERS
    // ============================================
    
    initEventListeners() {
        // CLICKS
        document.addEventListener('click', (e) => this.handleClick(e));
        
        // SCROLL
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => this.handleScroll(), 150);
        });
        
        // HOVER (throttled)
        let hoverTimeout;
        document.addEventListener('mouseover', (e) => {
            clearTimeout(hoverTimeout);
            hoverTimeout = setTimeout(() => this.handleHover(e), 200);
        });
        
        // FOCUS (tab change detection)
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        
        // COPY TEXT
        document.addEventListener('copy', (e) => this.handleCopy(e));
        
        // ✅ CORRECCIÓN PROBLEMA 2: NO inicializar listeners específicos aquí
        // Los inicializaremos después de cargar el contenido dinámico
        
        // KEYBOARD
        document.addEventListener('keydown', (e) => this.handleKeyPress(e));
    }
    
    // ✅ CORRECCIÓN PROBLEMA 2: Nueva función para inicializar listeners después de cargar contenido
    initMaterialSpecificListeners() {
        console.log('🔧 Inicializando listeners específicos del material...');
        
        // Esperar un momento para que el DOM se actualice completamente
        setTimeout(() => {
            // ============================================
            // FLASHCARD FLIPS - Usar event delegation
            // ============================================
            document.body.addEventListener('click', (e) => {
                const flashcard = e.target.closest('.flashcard');
                if (flashcard) {
                    const cardId = flashcard.id || flashcard.getAttribute('data-card-id');
                    console.log('🎴 Flashcard flip detectado:', cardId);
                    
                    this.trackEvent('flashcard_flip', {
                        element_id: cardId,
                        element_text: flashcard.querySelector('.front, .content-front')?.textContent.substring(0, 100)
                    });
                }
            });
            
            // ============================================
            // ÁRBOL DE DECISIÓN - Mejorar detección de nodos
            // ============================================
            document.body.addEventListener('click', (e) => {
                // Buscar el nodo más cercano con múltiples selectores
                const node = e.target.closest('.arbol-nodo') || 
                            e.target.closest('[data-node]') || 
                            e.target.closest('.node') ||
                            e.target.closest('g.arbol-nodo');
                
                if (node && !e.target.closest('.flashcard')) { // Evitar conflicto con flashcards
                    // Obtener el ID del nodo de múltiples fuentes posibles
                                        // ✅ CORRECCIÓN: Generar ID único y persistente
                    let nodeId = node.getAttribute('data-node-id'); // Primero intentar recuperar ID asignado

                    if (!nodeId) {
                        // Si no tiene ID asignado, generarlo
                        nodeId = node.id || 
                                node.getAttribute('data-node') || 
                                node.getAttribute('data-id');
                        
                        // Si aún no hay ID, usar una combinación de propiedades únicas
                        if (!nodeId) {
                            const textElement = node.querySelector('text') || 
                                            node.querySelector('.node-text') ||
                                            node.querySelector('foreignObject div') ||
                                            node.querySelector('span') ||
                                            node.querySelector('p');
                            
                            if (textElement) {
                                const nodeText = textElement.textContent.trim();
                                
                                // Usar hash simple del texto para ID único
                                const hash = Array.from(nodeText).reduce((s, c) => Math.imul(31, s) + c.charCodeAt(0) | 0, 0);
                                
                                // Combinar: posición en el DOM + hash del texto
                                const siblings = Array.from(node.parentElement?.children || []);
                                const position = siblings.indexOf(node);
                                
                                nodeId = `node_${position}_${Math.abs(hash)}`;
                            } else {
                                // Último recurso: usar índice en el árbol SVG
                                const allNodes = document.querySelectorAll('.arbol-nodo, [data-node], g.arbol-nodo');
                                const index = Array.from(allNodes).indexOf(node);
                                nodeId = `node_index_${index}_${Date.now()}`;
                            }
                        }
                        
                        // Asignar el ID al nodo para futuras referencias
                        node.setAttribute('data-node-id', nodeId);
                        console.log(`🆔 ID asignado al nodo: ${nodeId}`);
                    }
                    
                    // Determinar si está expandiendo o colapsando
                    const isExpanding = node.classList.contains('collapsed') || 
                                       !node.classList.contains('expanded') ||
                                       node.getAttribute('data-expanded') !== 'true';
                    
                    if (isExpanding) {
                        node.classList.add('expanded');
                        node.classList.remove('collapsed');
                        node.setAttribute('data-expanded', 'true');
                    } else {
                        node.classList.add('collapsed');
                        node.classList.remove('expanded');
                        node.setAttribute('data-expanded', 'false');
                    }
                    
                    // ✅ CORRECCIÓN: Solo trackear cuando hay un cambio real
                    const wasExpanded = node.getAttribute('data-was-expanded') === 'true';

                    if (isExpanding && !wasExpanded) {
                        // Primera vez que se expande este nodo
                        node.setAttribute('data-was-expanded', 'true');
                        console.log(`🌳 Nodo expandido (primera vez): ${nodeId}`);
                        
                        this.trackEvent('node_expand', {
                            element_id: nodeId,
                            element_text: node.textContent.substring(0, 100)
                        });
                    } else if (isExpanding) {
                        console.log(`🔄 Nodo ya expandido antes: ${nodeId} (no contabilizado)`);
                    } else {
                        console.log(`🔽 Nodo colapsado: ${nodeId} (no contabilizado)`);
                    }

                    // Actualizar estado visual
                    if (isExpanding) {
                        node.classList.add('expanded');
                        node.classList.remove('collapsed');
                        node.setAttribute('data-expanded', 'true');
                    } else {
                        node.classList.add('collapsed');
                        node.classList.remove('expanded');
                        node.setAttribute('data-expanded', 'false');
                    }
                }
            });
            
            // ============================================
            // TABS DE RESUMEN (mantener sin cambios)
            // ============================================
            document.body.addEventListener('click', (e) => {
                const tab = e.target.closest('.tab-button, [role="tab"]');
                if (tab) {
                    console.log('📑 Tab change:', tab.id);
                    this.trackEvent('tab_change', {
                        element_id: tab.id,
                        tab_name: tab.textContent
                    });
                }
            });
            
            console.log('✅ Listeners específicos inicializados con event delegation');
        }, 500); // Dar tiempo para que el contenido HTML se cargue completamente
    }
    
    // ============================================
    // HANDLERS DE EVENTOS
    // ============================================
    
    handleClick(event) {
        this.updateActivity();
        this.metrics.clickEvents++;
        
        const clickData = {
            x: event.clientX,
            y: event.clientY,
            timestamp: Date.now()
        };
        
        this.heatmapData.clicks.push(clickData);
        
        // Registrar evento detallado
        this.trackEvent('click', {
            element_id: event.target.id || null,
            element_type: event.target.tagName,
            element_text: event.target.textContent?.substring(0, 100),
            x_position: event.clientX,
            y_position: event.clientY
        });
    }
    
    handleScroll() {
        this.updateActivity();
        this.metrics.scrollEvents++;
        
        const scrollDepth = this.calculateScrollDepth();
        if (scrollDepth > this.metrics.maxScrollDepth) {
            this.metrics.maxScrollDepth = scrollDepth;
        }
        
        this.heatmapData.scrollPoints.push({
            position: window.scrollY,
            timestamp: Date.now()
        });
        
        this.trackEvent('scroll', {
            scroll_position: window.scrollY,
            viewport_height: window.innerHeight,
            metadata: { scroll_depth: scrollDepth }
        });
        
        // Detectar sección visible
        this.detectVisibleSection();
    }
    
    handleHover(event) {
        this.updateActivity();
        this.metrics.hoverEvents++;
        
        // Solo trackear hovers sobre elementos importantes
        const target = event.target;
        if (this.isImportantElement(target)) {
            this.trackEvent('hover', {
                element_id: target.id || null,
                element_type: target.tagName,
                element_text: target.textContent?.substring(0, 100)
            });
        }
    }
    
    handleVisibilityChange() {
        if (document.hidden) {
            this.tabVisible = false;
            this.trackEvent('tab_hidden', {});
            
            // Pausar tiempo de sección actual
            if (this.currentSection && this.sectionStartTime) {
                this.updateSectionTime(this.currentSection);
                this.sectionStartTime = null;
            }
        } else {
            this.tabVisible = true;
            this.trackEvent('tab_visible', {});
            this.updateActivity();
            
            // Reanudar tiempo de sección
            if (this.currentSection) {
                this.sectionStartTime = Date.now();
            }
        }
        
        this.metrics.focusChanges++;
    }
    
    handleCopy(event) {
        this.updateActivity();
        
        const copiedText = window.getSelection().toString();
        this.trackEvent('copy_text', {
            element_text: copiedText.substring(0, 500),
            metadata: { text_length: copiedText.length }
        });
    }
    
    handleKeyPress(event) {
        this.updateActivity();
        
        // Trackear atajos útiles
        const shortcuts = {
            'ctrl+f': 'search',
            'ctrl+c': 'copy',
            'f11': 'fullscreen'
        };
        
        const key = event.ctrlKey ? `ctrl+${event.key.toLowerCase()}` : event.key;
        if (shortcuts[key]) {
            this.trackEvent('keyboard_shortcut', {
                metadata: { shortcut: key, action: shortcuts[key] }
            });
        }
    }
    
    // ============================================
    // TRACKING DE SECCIONES
    // ============================================
    
    markSections() {
        // Marcar todas las secciones importantes del DOM
        const sectionSelectors = [
            '.weak-section',
            '.review-section',
            '.flashcard',
            '.arbol-nodo',
            '.summary-block',
            '.comparison-table',
            '.code-block'
        ];
        
        sectionSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach((element, index) => {
                if (!element.id) {
                    element.id = `${selector.replace('.', '')}-${index}`;
                }
                element.dataset.trackedSection = 'true';
                element.dataset.sectionType = selector.replace('.', '');
            });
        });
    }
    
    detectVisibleSection() {
        const viewportHeight = window.innerHeight;
        const scrollTop = window.scrollY;
        const viewportMiddle = scrollTop + (viewportHeight / 2);
        
        let closestSection = null;
        let closestDistance = Infinity;
        
        // Encontrar sección más cercana al centro del viewport
        document.querySelectorAll('[data-tracked-section="true"]').forEach(section => {
            const rect = section.getBoundingClientRect();
            const sectionMiddle = scrollTop + rect.top + (rect.height / 2);
            const distance = Math.abs(viewportMiddle - sectionMiddle);
            
            if (distance < closestDistance && rect.top < viewportHeight && rect.bottom > 0) {
                closestDistance = distance;
                closestSection = section;
            }
        });
        
        if (closestSection && closestSection.id !== this.currentSection) {
            // Cambió de sección
            if (this.currentSection) {
                this.updateSectionTime(this.currentSection);
            }
            
            this.currentSection = closestSection.id;
            this.sectionStartTime = Date.now();
            this.metrics.sectionsVisited.add(this.currentSection);
            
            this.trackEvent('section_view', {
                element_id: this.currentSection,
                element_type: closestSection.dataset.sectionType,
                element_text: closestSection.textContent.substring(0, 100)
            });
        }
    }
    
    updateSectionTime(sectionId) {
        if (!this.sectionStartTime) return;
        
        const timeSpent = Date.now() - this.sectionStartTime;
        
        if (!this.sectionTimes.has(sectionId)) {
            const section = document.getElementById(sectionId);
            this.sectionTimes.set(sectionId, {
                section_id: sectionId,
                section_type: section?.dataset.sectionType || 'unknown',
                section_content_preview: section?.textContent.substring(0, 500) || '',
                total_time_seconds: 0,
                view_count: 0,
                first_view_at: new Date().toISOString(),
                last_view_at: new Date().toISOString()
            });
        }
        
        const sectionData = this.sectionTimes.get(sectionId);
        sectionData.total_time_seconds += timeSpent / 1000;
        sectionData.view_count += 1;
        sectionData.last_view_at = new Date().toISOString();
    }
    
    // ============================================
    // TRACKING DE MOUSE (HEATMAP)
    // ============================================
    
    startMouseTracking() {
        let lastSample = 0;
        
        document.addEventListener('mousemove', (e) => {
            const now = Date.now();
            if (now - lastSample > this.mouseSampleRate) {
                this.heatmapData.mouseMovements.push({
                    x: e.clientX,
                    y: e.clientY,
                    timestamp: now
                });
                lastSample = now;
                
                // Limitar tamaño del buffer
                if (this.heatmapData.mouseMovements.length > 1000) {
                    this.heatmapData.mouseMovements = this.heatmapData.mouseMovements.slice(-500);
                }
            }
        });
    }
    
    // ============================================
    // REGISTRO DE EVENTOS
    // ============================================
    
    trackEvent(eventType, data = {}) {
        const event = {
            event_type: eventType,
            timestamp: new Date().toISOString(),
            time_since_session_start: this.getSessionDuration() / 1000,
            ...data
        };
        
        this.events.push(event);
        this.metrics.totalInteractions++;
        
        // Sync si buffer está lleno
        if (this.events.length >= this.batchSize) {
            this.syncData();
        }
    }
    
    // ============================================
    // ✅ CORRECCIÓN PROBLEMA 1: DETECCIÓN PRECISA DE IDLE
    // ============================================
    
    updateIdleAccumulator() {
        const now = Date.now();
        const timeSinceLastCheck = now - this.lastIdleCheck;
        const timeSinceActivity = now - this.lastActivityTime;
        
        // Si estamos idle (más de 30s sin actividad)
        if (timeSinceActivity > this.idleThreshold) {
            if (!this.currentlyIdle) {
                // Acabamos de entrar en idle
                this.currentlyIdle = true;
                console.log('⏸️  Usuario entró en idle');
            }
            // Acumular el tiempo que ha pasado desde el último check
            this.totalIdleTime += timeSinceLastCheck;
        } else {
            if (this.currentlyIdle) {
                // Acabamos de salir de idle
                this.currentlyIdle = false;
                console.log('▶️  Usuario salió de idle');
            }
            // No acumulamos nada si está activo
        }
        
        this.lastIdleCheck = now;
    }
    
    startIdleDetection() {
        // Actualizar acumulador cada 5 segundos
        setInterval(() => {
            if (this.isActive) {
                this.updateIdleAccumulator();
                
                const timeSinceActivity = Date.now() - this.lastActivityTime;
                
                // Log cada 30s para debug
                if (timeSinceActivity > this.idleThreshold && Math.floor(timeSinceActivity / 30000) > Math.floor((timeSinceActivity - 5000) / 30000)) {
                    console.log(`⏸️  Idle detectado: ${Math.floor(timeSinceActivity / 1000)}s sin actividad`);
                    this.trackEvent('pause_study', {
                        metadata: { idle_duration: timeSinceActivity }
                    });
                }
            }
        }, 5000); // Check cada 5 segundos para mayor precisión
    }
    
    updateActivity() {
        const wasIdle = (Date.now() - this.lastActivityTime) > this.idleThreshold;
        
        if (wasIdle && this.isActive) {
            console.log('▶️  Usuario activo de nuevo');
            this.trackEvent('resume_study', {});
        }
        
        // Actualizar el tiempo de última actividad
        this.lastActivityTime = Date.now();
        this.lastIdleCheck = Date.now(); // Resetear también el check
        this.currentlyIdle = false; // Ya no está idle
    }
    
    // ============================================
    // SINCRONIZACIÓN CON BACKEND
    // ============================================
    
    async syncData(isFinal = false) {
        if (this.events.length === 0 && !isFinal) return;
        
        // ✅ CORRECCIÓN PROBLEMA 1: Actualizar acumulador antes de sincronizar
        this.updateIdleAccumulator();
        
        const payload = {
            session_id: this.sessionId,
            events: [...this.events],
            section_times: Array.from(this.sectionTimes.values()),
            heatmap_data: {
                clicks: [...this.heatmapData.clicks],
                mouse_movements: this.heatmapData.mouseMovements.slice(-500),
                scroll_points: [...this.heatmapData.scrollPoints]
            },
            metrics: {
                ...this.getMetricsSummary(),
                total_time_seconds: Math.floor(this.getSessionDuration() / 1000),
                active_time_seconds: Math.floor(this.calculateActiveTime() / 1000)
            }
        };
        
        try {
            const response = await fetch('/api/tracking/session/sync/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(payload),
                keepalive: isFinal
            });
            
            if (response.ok) {
                console.log(`✅ Sincronizado: ${this.events.length} eventos | Active: ${Math.floor(this.calculateActiveTime() / 1000)}s | Idle: ${Math.floor(this.totalIdleTime / 1000)}s`);
                
                // Limpiar buffers después de sync exitoso
                this.events = [];
                this.heatmapData.clicks = [];
                this.heatmapData.scrollPoints = [];
            }
        } catch (error) {
            console.error('❌ Error sincronizando:', error);
        }
    }
    
    startPeriodicSync() {
        // Sincronizar cada 60 segundos
        setInterval(() => {
            if (this.isActive) {
                this.syncData();
            }
        }, 60000);
    }
    
    // ============================================
    // UTILIDADES
    // ============================================
    
    getSessionDuration() {
        return Date.now() - this.sessionStartTime;
    }
    
    // ✅ CORRECCIÓN PROBLEMA 1: Calcular tiempo activo correctamente
    calculateActiveTime() {
        const totalTime = this.getSessionDuration();
        // Tiempo activo = tiempo total - tiempo idle acumulado
        return Math.max(0, totalTime - this.totalIdleTime);
    }
    
    calculateScrollDepth() {
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        const scrollTop = window.scrollY;
        
        const scrollPercentage = ((scrollTop + windowHeight) / documentHeight) * 100;
        return Math.min(100, Math.round(scrollPercentage));
    }
    
    getMetricsSummary() {
        return {
            total_interactions: this.metrics.totalInteractions,
            scroll_events: this.metrics.scrollEvents,
            click_events: this.metrics.clickEvents,
            hover_events: this.metrics.hoverEvents,
            focus_changes: this.metrics.focusChanges,
            sections_visited: Array.from(this.metrics.sectionsVisited),
            max_scroll_depth: this.metrics.maxScrollDepth,
            unique_sections_count: this.metrics.sectionsVisited.size
        };
    }
    
    isImportantElement(element) {
        const importantTags = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'];
        const importantClasses = ['flashcard', 'arbol-nodo', 'code-block', 'comparison-table'];
        
        return importantTags.includes(element.tagName) ||
               importantClasses.some(cls => element.classList.contains(cls));
    }
    
    getDeviceType() {
        const ua = navigator.userAgent;
        if (/mobile/i.test(ua)) return 'mobile';
        if (/tablet/i.test(ua)) return 'tablet';
        return 'desktop';
    }
    
    getBrowser() {
        const ua = navigator.userAgent;
        if (ua.includes('Chrome')) return 'Chrome';
        if (ua.includes('Firefox')) return 'Firefox';
        if (ua.includes('Safari')) return 'Safari';
        if (ua.includes('Edge')) return 'Edge';
        return 'Unknown';
    }
    
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
}

// ============================================
// INICIALIZACIÓN AUTOMÁTICA
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Obtener material ID de la URL o del DOM
    const materialId = window.location.pathname.match(/\/material\/(\d+)\//)?.[1];
    const userId = JSON.parse(localStorage.getItem('user') || '{}').id;
    
    if (materialId && userId) {
        window.studyTracker = new StudyTracker(materialId, userId);
        
        // ✅ CORRECCIÓN PROBLEMA 2: Inicializar listeners después de que se cargue el contenido
        // Esperar a que el contenido del material se cargue en el DOM
        const observer = new MutationObserver((mutations, obs) => {
            const materialContent = document.getElementById('materialContent');
            if (materialContent && materialContent.children.length > 0) {
                console.log('📄 Contenido del material cargado, inicializando listeners...');
                window.studyTracker.initMaterialSpecificListeners();
                obs.disconnect(); // Dejar de observar una vez inicializado
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // También intentar inicializar después de 2 segundos por si acaso
        setTimeout(() => {
            window.studyTracker.initMaterialSpecificListeners();
        }, 2000);
        
        console.log(`
╔═══════════════════════════════════════╗
║   🎯 STUDY TRACKER ACTIVADO           ║
║   Material ID: ${materialId.padEnd(23)}║
║   Sesión: ${window.studyTracker.sessionId.substring(0, 8)}...          ║
╚═══════════════════════════════════════╝
        `);
    } else {
        console.warn('⚠️  No se pudo inicializar StudyTracker: faltan datos');
    }

    window.addEventListener('DOMContentLoaded', () => {
        const btn = document.createElement('button');
        btn.textContent = '🛑 CERRAR SESIÓN';
        btn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;padding:15px;background:#dc3545;color:white;border:none;border-radius:5px;cursor:pointer;font-weight:bold;font-size:16px;';
        btn.onclick = () => {
            if (window.studyTracker) {
                window.studyTracker.endSession('manual');
                btn.textContent = '✅ CERRADA';
                btn.disabled = true;
            }
        };
        document.body.appendChild(btn);
    }); 
});