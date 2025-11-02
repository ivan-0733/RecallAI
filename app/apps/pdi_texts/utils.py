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