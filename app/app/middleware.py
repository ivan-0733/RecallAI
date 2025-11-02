import logging

logger = logging.getLogger(__name__)


class DisableFrameOptionsMiddleware:
    """
    Middleware para permitir que archivos media se muestren en iframes
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Log para debug
        if request.path.startswith('/media/'):
            logger.info(f"🔍 Middleware procesando: {request.path}")
            
            # Eliminar todas las restricciones de frame para archivos media
            if 'X-Frame-Options' in response:
                del response['X-Frame-Options']
                logger.info("✅ X-Frame-Options eliminado")
            
            # No establecer ninguna política de frame
            # Esto permite que se muestre en cualquier iframe
            response['X-Frame-Options'] = 'ALLOWALL'
            
            logger.info(f"📤 Response headers: {response.items()}")
        
        return response