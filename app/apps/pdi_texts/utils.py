import PyPDF2
import pdfplumber
import re
from typing import Dict, Tuple


def extract_text_from_pdf(pdf_file) -> Tuple[str, Dict]:
    """
    Extrae texto de un archivo PDF usando PyPDF2 y pdfplumber
    
    Args:
        pdf_file: Archivo PDF (Django UploadedFile)
    
    Returns:
        Tuple[str, Dict]: (texto_extraido, metadata)
    """
    
    text_content = ""
    metadata = {
        'pages': 0,
        'method': 'pdfplumber',
        'success': False
    }
    
    try:
        # Intentar primero con pdfplumber (mejor para PDFs con texto)
        with pdfplumber.open(pdf_file) as pdf:
            metadata['pages'] = len(pdf.pages)
            
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n\n"
            
            if text_content.strip():
                metadata['success'] = True
                metadata['method'] = 'pdfplumber'
                return clean_extracted_text(text_content), metadata
    
    except Exception as e:
        print(f"pdfplumber falló: {str(e)}, intentando con PyPDF2...")
    
    # Fallback: intentar con PyPDF2
    try:
        pdf_file.seek(0)  # Resetear puntero del archivo
        
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        metadata['pages'] = len(pdf_reader.pages)
        
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                text_content += text + "\n\n"
        
        if text_content.strip():
            metadata['success'] = True
            metadata['method'] = 'PyPDF2'
            return clean_extracted_text(text_content), metadata
    
    except Exception as e:
        metadata['error'] = str(e)
        raise Exception(f"No se pudo extraer texto del PDF: {str(e)}")
    
    if not text_content.strip():
        raise Exception("El PDF no contiene texto extraíble (puede ser una imagen escaneada)")
    
    return clean_extracted_text(text_content), metadata


def clean_extracted_text(text: str) -> str:
    """
    Limpia el texto extraído del PDF
    """
    
    # Eliminar múltiples espacios
    text = re.sub(r' +', ' ', text)
    
    # Eliminar múltiples saltos de línea
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Eliminar saltos de línea dentro de párrafos (texto continuo)
    # pero preservar saltos de línea dobles (separación de párrafos)
    lines = text.split('\n')
    cleaned_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            cleaned_lines.append('')
            continue
        
        # Si la línea termina con punto, pregunta o dos puntos, es fin de oración
        if line[-1] in '.?:!':
            cleaned_lines.append(line)
        else:
            # Si no, probablemente es continuación del párrafo
            cleaned_lines.append(line + ' ')
    
    text = '\n'.join(cleaned_lines)
    
    # Limpiar espacios al inicio/final
    text = text.strip()
    
    return text


def extract_text_from_txt(txt_file) -> str:
    """
    Extrae texto de un archivo TXT
    
    Args:
        txt_file: Archivo TXT (Django UploadedFile)
    
    Returns:
        str: Texto extraído
    """
    
    try:
        # Intentar UTF-8 primero
        content = txt_file.read().decode('utf-8')
    except UnicodeDecodeError:
        # Fallback a latin-1
        txt_file.seek(0)
        content = txt_file.read().decode('latin-1')
    
    return clean_extracted_text(content)


def estimate_reading_time(text: str) -> int:
    """
    Estima el tiempo de lectura en minutos
    Asume velocidad promedio de 200 palabras por minuto
    
    Args:
        text: Texto a analizar
    
    Returns:
        int: Tiempo estimado en minutos (mínimo 5)
    """
    
    word_count = len(text.split())
    minutes = max(5, round(word_count / 200))
    
    return minutes

# ... (Mantén todo tu código anterior de pdf/txt intacto) ...

# ========================================================
# AGREGAR ESTO AL FINAL DEL ARCHIVO PARA LOGS CSV
# ========================================================

import csv
import os
import json
from datetime import datetime
from django.conf import settings

# Definir rutas absolutas para los CSV en la raíz del proyecto
CSV_SESSION_PATH = os.path.join(settings.BASE_DIR, 'GRUPO_2_CON_APP.csv')
CSV_ITEM_PATH = os.path.join(settings.BASE_DIR, 'QUIZ_GRUPO2_CON_APP.csv')

def initialize_csvs():
    """
    Crea los archivos CSV con sus encabezados si no existen.
    Se debe llamar al inicio de la aplicación o la primera vez que se loguea.
    """
    # 1. CSV DE SESIONES (Resumen por intento/ciclo)
    if not os.path.exists(CSV_SESSION_PATH):
        try:
            with open(CSV_SESSION_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Estructura: User, Texto, Sesión (0,1,2...), Score, Temas Débiles, Fecha
                writer.writerow(['user_id', 'text_id', 'session_order', 'score', 'weak_topics', 'timestamp'])
        except Exception as e:
            print(f"❌ Error creando CSV de Sesiones: {e}")

    # 2. CSV DE ITEMS (Respuestas binarias 1/0 a cada pregunta)
    if not os.path.exists(CSV_ITEM_PATH):
        try:
            with open(CSV_ITEM_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Estructura: User, Texto, Tipo, Sesión, Score, item_1 ... item_20
                header = ['user_id', 'text_id', 'quiz_type', 'session_number', 'score'] + [f'item_{i+1}' for i in range(20)]
                writer.writerow(header)
        except Exception as e:
            print(f"❌ Error creando CSV de Items: {e}")

def log_session_summary(user_id, text_id, session_order, score, weak_topics):
    """
    Registra el resumen de una sesión en GRUPO_2_CON_APP.csv
    """
    initialize_csvs() # Asegura que exista
    try:
        # Convertir lista de temas a string separado por pipes para que no rompa el CSV
        topics_str = "|".join(weak_topics) if isinstance(weak_topics, list) else str(weak_topics)
        
        with open(CSV_SESSION_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                user_id, 
                text_id, 
                session_order, 
                score, 
                topics_str,
                datetime.now().isoformat()
            ])
        print(f"✅ Log guardado en GRUPO_2_CON_APP.csv (Sesión {session_order})")
    except Exception as e:
        print(f"❌ Error escribiendo en CSV Session: {e}")

def log_quiz_items(user_id, text_id, quiz_type, session_number, score, answers_vector):
    """
    Registra el vector de respuestas (1/0) en QUIZ_GRUPO2_CON_APP.csv
    answers_vector: Lista de 20 enteros/booleanos [1, 0, 1, 1...]
    """
    initialize_csvs() # Asegura que exista
    try:
        # Validación estricta de longitud
        if len(answers_vector) != 20:
            print(f"⚠️ ALERTA: Vector de respuestas tiene {len(answers_vector)} items, se esperaban 20. Rellenando con 0.")
            # Rellenar o cortar para evitar error de formato
            answers_vector = (answers_vector + [0]*20)[:20]

        row = [user_id, text_id, quiz_type, session_number, score] + answers_vector
        
        with open(CSV_ITEM_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        print(f"✅ Log guardado en QUIZ_GRUPO2_CON_APP.csv ({quiz_type})")
    except Exception as e:
        print(f"❌ Error escribiendo en CSV Items: {e}")