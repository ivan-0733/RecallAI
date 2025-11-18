/**
 * ========================================
 * SISTEMA DE TRACKING ROBUSTO - RecallAI
 * ✅ CORRECCIONES APLICADAS:
 * - Problema 1: Detección precisa de tiempo inactivo
 * - Problema 2: Event listeners dinámicos para flashcards
 * - Problema 3: Datos de heatmap correctamente formateados
 * - Fix Definitivo: Conteo de nodos 100% preciso mediante integración directa con D3
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
        
        // Acumuladores de tiempo
        this.totalIdleTime = 0; 
        this.lastIdleCheck = Date.now(); 
        this.currentlyIdle = false; 
        
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

        // ✅ FIX: Persistencia en memoria para nodos visitados
        // Usamos un Set para almacenar IDs únicos. Esto sobrevive a la destrucción/creación del DOM por D3.
        this.visitedNodes = new Set();
        
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
                keepalive: true 
            });
            
            console.log('✅ Sesión finalizada:', endData);
        } catch (error) {
            console.error('❌ Error finalizando sesión:', error);
        }
    }
    
    // ============================================
    // EVENT LISTENERS GENÉRICOS
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
        
        // FOCUS
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        
        // COPY TEXT
        document.addEventListener('copy', (e) => this.handleCopy(e));
        
        // KEYBOARD
        document.addEventListener('keydown', (e) => this.handleKeyPress(e));
    }

    // ============================================
    // ✅ NUEVO: API PÚBLICA PARA REGISTRO DE NODOS (FIX 100% PRECISIÓN)
    // Este método es llamado directamente desde el código D3 en el template
    // ============================================
    registerNodeView(nodeId, nodeText, isInitial = false) {
        if (!nodeId) return;

        // 1. Verificar persistencia en memoria: Si ya lo visitamos, ignorar.
        // Esto cumple los requisitos 2 y 3: no contar dobles, y mantener el conteo aunque se cierre.
        if (this.visitedNodes.has(nodeId)) {
            // console.log(`🔄 Nodo ya registrado anteriormente (Memoria): ${nodeId}`);
            return;
        }

        // 2. Registrar nueva visita
        this.visitedNodes.add(nodeId);
        console.log(`✨ Nuevo nodo registrado: ${nodeId} (${isInitial ? 'Carga Inicial' : 'Interacción Usuario'})`);

        // 3. Enviar evento al backend
        this.trackEvent('node_expand', {
            element_id: nodeId,
            element_text: nodeText ? nodeText.substring(0, 100) : 'Sin texto',
            trigger: isInitial ? 'initial_load' : 'user_click'
        });
    }

    // ============================================
    // LISTENERS ESPECÍFICOS DEL MATERIAL
    // ============================================
    
    initMaterialSpecificListeners() {
        console.log('🔧 Inicializando listeners específicos del material...');
        
        setTimeout(() => {
            // FLASHCARD FLIPS
            document.body.addEventListener('click', (e) => {
                const flashcard = e.target.closest('.flashcard');
                if (flashcard) {
                    const cardId = flashcard.id || flashcard.getAttribute('data-card-id');
                    this.trackEvent('flashcard_flip', {
                        element_id: cardId,
                        element_text: flashcard.querySelector('.front, .content-front')?.textContent.substring(0, 100)
                    });
                }
            });
            
            // NOTA: Eliminamos el listener global de '.arbol-nodo' aquí.
            // Ahora el árbol llama directamente a registerNodeView() para evitar errores de sincronización.
            
            // TABS DE RESUMEN
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

            console.log('✅ Listeners específicos inicializados');
        }, 500); 
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
            
            if (this.currentSection && this.sectionStartTime) {
                this.updateSectionTime(this.currentSection);
                this.sectionStartTime = null;
            }
        } else {
            this.tabVisible = true;
            this.trackEvent('tab_visible', {});
            this.updateActivity();
            
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
        const shortcuts = { 'ctrl+f': 'search', 'ctrl+c': 'copy', 'f11': 'fullscreen' };
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
        const sectionSelectors = [
            '.weak-section', '.review-section', '.flashcard', 
            '.arbol-nodo', '.summary-block', '.comparison-table', '.code-block'
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
        
        if (this.events.length >= this.batchSize) {
            this.syncData();
        }
    }
    
    // ============================================
    // DETECCIÓN DE IDLE
    // ============================================
    
    updateIdleAccumulator() {
        const now = Date.now();
        const timeSinceLastCheck = now - this.lastIdleCheck;
        const timeSinceActivity = now - this.lastActivityTime;
        
        if (timeSinceActivity > this.idleThreshold) {
            if (!this.currentlyIdle) {
                this.currentlyIdle = true;
                console.log('⏸️  Usuario entró en idle');
            }
            this.totalIdleTime += timeSinceLastCheck;
        } else {
            if (this.currentlyIdle) {
                this.currentlyIdle = false;
                console.log('▶️  Usuario salió de idle');
            }
        }
        this.lastIdleCheck = now;
    }
    
    startIdleDetection() {
        setInterval(() => {
            if (this.isActive) {
                this.updateIdleAccumulator();
                const timeSinceActivity = Date.now() - this.lastActivityTime;
                
                if (timeSinceActivity > this.idleThreshold && Math.floor(timeSinceActivity / 30000) > Math.floor((timeSinceActivity - 5000) / 30000)) {
                    console.log(`⏸️  Idle detectado: ${Math.floor(timeSinceActivity / 1000)}s sin actividad`);
                    this.trackEvent('pause_study', {
                        metadata: { idle_duration: timeSinceActivity }
                    });
                }
            }
        }, 5000);
    }
    
    updateActivity() {
        const wasIdle = (Date.now() - this.lastActivityTime) > this.idleThreshold;
        
        if (wasIdle && this.isActive) {
            console.log('▶️  Usuario activo de nuevo');
            this.trackEvent('resume_study', {});
        }
        
        this.lastActivityTime = Date.now();
        this.lastIdleCheck = Date.now();
        this.currentlyIdle = false;
    }
    
    // ============================================
    // SINCRONIZACIÓN CON BACKEND
    // ============================================
    
    async syncData(isFinal = false) {
        if (this.events.length === 0 && !isFinal) return;
        
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
                this.events = [];
                this.heatmapData.clicks = [];
                this.heatmapData.scrollPoints = [];
            }
        } catch (error) {
            console.error('❌ Error sincronizando:', error);
        }
    }
    
    startPeriodicSync() {
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
    
    calculateActiveTime() {
        const totalTime = this.getSessionDuration();
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
    const materialId = window.location.pathname.match(/\/material\/(\d+)\//)?.[1];
    const userId = JSON.parse(localStorage.getItem('user') || '{}').id;
    
    if (materialId && userId) {
        window.studyTracker = new StudyTracker(materialId, userId);
        
        const observer = new MutationObserver((mutations, obs) => {
            const materialContent = document.getElementById('materialContent');
            if (materialContent && materialContent.children.length > 0) {
                console.log('📄 Contenido del material cargado, inicializando listeners...');
                window.studyTracker.initMaterialSpecificListeners();
                obs.disconnect(); 
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // Fallback
        setTimeout(() => {
            if (window.studyTracker) {
                window.studyTracker.initMaterialSpecificListeners();
            }
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

    // Botón de debug para cerrar sesión manual
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