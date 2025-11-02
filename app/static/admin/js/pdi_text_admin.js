// Función para generar quiz vía AJAX
function generateQuiz(textId, url) {
    const btn = document.getElementById(`quiz-btn-${textId}`);
    
    if (!btn) {
        alert('Error: No se encontró el botón');
        return;
    }
    
    // Deshabilitar botón y mostrar loading
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    
    // Hacer petición AJAX
    fetch(url, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Mostrar mensaje de éxito (como lo hace Django messages)
            // NO usar alert(), dejar que el mensaje del backend se muestre
            
            // Recargar la página para ver el mensaje del admin de Django
            window.location.reload();
        } else {
            // Mostrar error
            alert(data.message);
            
            // Restaurar botón
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-plus-circle"></i> Generar Quiz';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('❌ Error de conexión. Verifica que Celery esté corriendo.');
        
        // Restaurar botón
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus-circle"></i> Generar Quiz';
    });
}