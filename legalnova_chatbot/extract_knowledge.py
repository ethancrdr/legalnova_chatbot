import fitz  # PyMuPDF
from docx import Document
import os
import json
import re

data_dir = 'data/'

# Extraer texto normal de PDFs y DOCX
def extract_text(file_path):
    if file_path.endswith('.pdf'):
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    elif file_path.endswith('.docx'):
        try:
            return "\n".join([p.text for p in Document(file_path).paragraphs])
        except:
            return ""
    return ""

# Extraer servicios del PDF perfecto (Categoria de Servicios por area (1).pdf)
def extract_services_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    services = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    current_area = None
    for line in lines:
        # Detecta áreas (las que están en mayúsculas y conocidas)
        if line in ['Accounting', 'Innovation', 'International Accounting Services', 
                    'International Business Services', 'International Legal Services']:
            current_area = line
        
        # Detecta servicio (línea que no es área y no es vacío)
        elif current_area and line and not line.isdigit() and not line.startswith('●'):
            services.append({
                "servicio": line,
                "area": current_area
            })

    return services

print("Generando knowledge_base.json limpio...")

knowledge_base = {}

# Procesar todos los archivos
for file in os.listdir(data_dir):
    full_path = os.path.join(data_dir, file)
    if file.endswith(('.pdf', '.docx')):
        print(f"Procesando: {file}")
        text = extract_text(full_path)
        knowledge_base[file] = text
        
        # Extraer servicios solo del PDF correcto
        if "Categoria de Servicios por area" in file:
            knowledge_base['services'] = extract_services_from_pdf(full_path)

# Guardar JSON perfecto
with open('knowledge_base_limpia.json', 'w', encoding='utf-8') as f:
    json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

print("¡JSON LIMPIO GENERADO! Archivo: knowledge_base_limpia.json")
print(f"Servicios extraídos: {len(knowledge_base.get('services', []))}")