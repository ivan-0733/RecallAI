/**
 * ========================================
 * SISTEMA DE TRACKING ROBUSTO - RecallAI
 * ========================================
 * 
 * Este script captura TODA la actividad del usuario mientras estudia
 * y la envía al backend para análisis exhaustivo.
 * 
 * Agregar este script al final de material_viewer.html
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
        
        // INTERACCIONES ESPECÍFICAS DEL MATERIAL
        this.initMaterialSpecificListeners();
        
        // KEYBOARD
        document.addEventListener('keydown', (e) => this.handleKeyPress(e));
    }
    
    initMaterialSpecificListeners() {
        // Flashcard flips
        document.querySelectorAll('.flashcard').forEach(card => {
            card.addEventListener('click', () => {
                this.trackEvent('flashcard_flip', {
                    element_id: card.id,
                    element_text: card.querySelector('.front')?.textContent.substring(0, 100)
                });
            });
        });
        
        // Árbol de decisión - expandir/colapsar nodos
        document.querySelectorAll('.arbol-nodo').forEach(node => {
            node.addEventListener('click', (e) => {
                const isExpanding = node.classList.contains('collapsed');
                this.trackEvent(isExpanding ? 'node_expand' : 'node_collapse', {
                    element_id: node.id,
                    element_text: node.textContent.substring(0, 100)
                });
            });
        });
        
        // Tabs de resumen
        document.querySelectorAll('.tab-button').forEach(tab => {
            tab.addEventListener('click', () => {
                this.trackEvent('tab_change', {
                    element_id: tab.id,
                    tab_name: tab.textContent
                });
            });
        });
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
    // DETECCIÓN DE IDLE
    // ============================================
    
    startIdleDetection() {
        setInterval(() => {
            const timeSinceActivity = Date.now() - this.lastActivityTime;
            
            if (timeSinceActivity > this.idleThreshold && this.isActive) {
                console.log('⏸️  Usuario idle');
                this.trackEvent('pause_study', {
                    metadata: { idle_duration: timeSinceActivity }
                });
            }
        }, 10000); // Check cada 10 segundos
    }
    
    updateActivity() {
        const wasIdle = (Date.now() - this.lastActivityTime) > this.idleThreshold;
        
        if (wasIdle && this.isActive) {
            console.log('▶️  Usuario activo de nuevo');
            this.trackEvent('resume_study', {});
        }
        
        this.lastActivityTime = Date.now();
    }
    
    // ============================================
    // SINCRONIZACIÓN CON BACKEND
    // ============================================
    
    async syncData(isFinal = false) {
        if (this.events.length === 0 && !isFinal) return;
        
        const payload = {
            session_id: this.sessionId,
            events: [...this.events],
            section_times: Array.from(this.sectionTimes.values()),
            heatmap_data: {
                clicks: [...this.heatmapData.clicks],
                mouse_movements: this.heatmapData.mouseMovements.slice(-500), // Últimos 500
                scroll_points: [...this.heatmapData.scrollPoints]
            },
            metrics: this.getMetricsSummary()
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
                console.log(`✅ Sincronizado: ${this.events.length} eventos`);
                
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
    
    calculateActiveTime() {
        // Tiempo activo = tiempo total - tiempo idle
        // (simplificado, se puede mejorar)
        const totalTime = this.getSessionDuration();
        const idleTime = Math.max(0, Date.now() - this.lastActivityTime - this.idleThreshold);
        return totalTime - idleTime;
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
});