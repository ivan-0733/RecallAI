from django.db.models import Avg
from apps.pdi_texts.models import MaterialEffectiveness
import logging

logger = logging.getLogger(__name__)


def get_recommended_material(user, text):
    """
    Recomienda el tipo de material más efectivo
    Solo funciona si el usuario tiene >= 5 registros
    """
    
    total_records = MaterialEffectiveness.objects.filter(
        user=user,
        text=text
    ).count()
    
    if total_records < 5:
        return {
            'has_recommendation': False,
            'recommended_type': None,
            'expected_improvement': 0,
            'all_effectiveness': {},
            'reason': 'insufficient_data',
            'message': f'Completa {5 - total_records} intento(s) más para recibir recomendaciones personalizadas'
        }
    
    # Calcular mejora promedio por tipo
    effectiveness = {}
    material_types = ['flashcard', 'decision_tree', 'mind_map', 'summary']
    
    for material_type in material_types:
        records = MaterialEffectiveness.objects.filter(
            user=user,
            text=text,
            material_type=material_type
        )
        
        if records.exists():
            avg_improvement = records.aggregate(
                avg_imp=Avg('improvement')
            )['avg_imp']
            effectiveness[material_type] = round(avg_improvement, 1)
        else:
            effectiveness[material_type] = 0
    
    # Encontrar el mejor
    if not effectiveness or all(v == 0 for v in effectiveness.values()):
        return {
            'has_recommendation': False,
            'recommended_type': None,
            'expected_improvement': 0,
            'all_effectiveness': effectiveness,
            'reason': 'no_positive_data',
            'message': 'Aún no tienes suficiente historial positivo'
        }
    
    best_material = max(effectiveness, key=effectiveness.get)
    best_score = effectiveness[best_material]
    
    if best_score < 5:
        return {
            'has_recommendation': False,
            'recommended_type': None,
            'expected_improvement': 0,
            'all_effectiveness': effectiveness,
            'reason': 'low_improvement',
            'message': 'Ningún material ha mostrado mejora significativa aún'
        }
    
    material_names = {
        'flashcard': 'Flashcards',
        'decision_tree': 'Árbol de Decisión',
        'mind_map': 'Mapa Mental',
        'summary': 'Resumen Estructurado'
    }
    
    message = f"Basado en tus últimos {total_records} intentos, {material_names[best_material]} te ha ayudado a mejorar en promedio {best_score}%"
    
    logger.info(f"Recomendación para {user.email}: {best_material} (+{best_score}%)")
    
    return {
        'has_recommendation': True,
        'recommended_type': best_material,
        'expected_improvement': best_score,
        'all_effectiveness': effectiveness,
        'reason': 'success',
        'message': message
    }


def get_fallback_recommendation():
    """
    Recomendación global cuando no hay data del usuario
    """
    
    global_effectiveness = {}
    material_types = ['flashcard', 'decision_tree', 'mind_map', 'summary']
    
    for material_type in material_types:
        records = MaterialEffectiveness.objects.filter(
            material_type=material_type
        )
        
        if records.exists():
            avg = records.aggregate(avg_imp=Avg('improvement'))['avg_imp']
            global_effectiveness[material_type] = round(avg, 1)
        else:
            global_effectiveness[material_type] = 0
    
    if global_effectiveness and any(v > 0 for v in global_effectiveness.values()):
        best = max(global_effectiveness, key=global_effectiveness.get)
        
        material_names = {
            'flashcard': 'Flashcards',
            'decision_tree': 'Árboles de Decisión',
            'mind_map': 'Mapas Mentales',
            'summary': 'Resúmenes'
        }
        
        return {
            'has_recommendation': True,
            'recommended_type': best,
            'expected_improvement': global_effectiveness[best],
            'all_effectiveness': global_effectiveness,
            'reason': 'global_stats',
            'message': f"{material_names[best]} han funcionado mejor para otros estudiantes (mejora promedio: +{global_effectiveness[best]}%)"
        }
    
    return {
        'has_recommendation': True,
        'recommended_type': 'flashcard',
        'expected_improvement': 0,
        'all_effectiveness': {},
        'reason': 'default',
        'message': 'Las Flashcards son el tipo más popular. ¡Pruébalas!'
    }