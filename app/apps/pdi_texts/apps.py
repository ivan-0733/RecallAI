from django.apps import AppConfig


class PdiTextsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pdi_texts"
    verbose_name = "Textos PDI y Cuestionarios"
    
    def ready(self):
        """Importar signals cuando la app esté lista"""
        import apps.pdi_texts.models