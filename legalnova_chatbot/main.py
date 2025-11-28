from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import json
import re
import uvicorn
import os
import requests
from typing import Dict, Optional
import logging


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== CONFIG =====================
# IMPORTANTE: Mover estas credenciales a variables de entorno en producción
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBhiAh2hHZTXqHF0JHMKyy7m15draaClwQ")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "NOVERBOT_LEGALNOVA_2025")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "EAAVJwuGv7D4BQNuKGm6sJrUay91jZB9dqess03dZB1CDkKvklEavmZAJkvmewQizr21cWGZBg9vngnZAit9zeYwtiZBZBD5zRJFZBXMgsnk196skeQmBIVRZAJrieuBZBVLdG6LEUam8rplpvlH9ammEITP2VL0ZBpwIOeDC7nS1Wa3Xlf2DRGj1Eajoer54OrdpGEYY5M0aqTu7jqP3T6xHMS60vKRGPqTVx5bq6TfaUOmqO3upZCvFbvqG0pm4twA2KwfaQ4g4jCrUToeHADQNzBQPvTw6")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "921364574387453")

genai.configure(api_key=GEMINI_API_KEY)

# Cargar knowledge base
try:
    logging.info("Cargando knowledge_base_limpia.json")
    with open('knowledge_base_limpia.json', 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
except FileNotFoundError:
    print("⚠️ Advertencia: knowledge_base_limpia.json no encontrado")
    knowledge = {}
except json.JSONDecodeError as e:
    print(f"⚠️ Error al parsear JSON: {e}")
    knowledge = {}

# ===================== CONSTANTES =====================
MENU = """¡Hola! Soy Nover BOT, tu asistente virtual inteligente de LegalNova 🚀
Estamos aquí para ayudarte a crecer en Colombia y Estados Unidos con soluciones legales, contables y de innovación de alto nivel.

¿En qué puedo apoyarte hoy?

1. Constituir empresa en USA → LLC desde USD 970  
2. Internacionalización → Diagnóstico desde USD 2.500  
3. Impuestos y cumplimiento USA → Franchise Tax, BOI, Annual Report  
4. Contratos y Trusts → Revisión desde USD 300  
5. Contabilidad y auditoría → Membresías desde USD 1.000/mes  
6. Hablar con un experto → Te conecto de inmediato"""

PDF_CATALOG = {
    "llc_constitucion": {
        "url": "https://drive.google.com/file/d/1Cpxo6AqMjGNByySJefzDyBJJVGdhibpU/view?usp=sharing",
        "nombre": "Brochure de Constitución de LLC",
        "keywords": ["llc", "constituir", "crear empresa", "abrir empresa", "delaware", "wyoming", "formar empresa"]
    },
    "liquidacion_delaware": {
        "url": "https://drive.google.com/file/d/18wayyL4OfWAKS0rgCYAKYsfBq6LXedTT/view?usp=sharing",
        "nombre": "Manual de Liquidación Delaware",
        "keywords": ["liquidacion delaware", "cerrar delaware", "disolver delaware"]
    },
    "liquidacion_florida": {
        "url": "https://drive.google.com/file/d/1Du9d79UfleMS4lcUF2k7son2vakMXHgF/view?usp=sharing",
        "nombre": "Manual de Liquidación Florida",
        "keywords": ["liquidacion florida", "cerrar florida", "disolver florida"]
    },
    "impuestos_usa": {
        "url": "https://drive.google.com/file/d/1Kj10wt5346AA_JF3zcFizYJ1DrTQqOoC/view?usp=sharing",
        "nombre": "Guía de Impuestos USA 2025",
        "keywords": ["franchise tax", "boi", "annual report", "impuestos", "tax", "1065"]
    },
    "contratos_trusts": {
        "url": "https://drive.google.com/file/d/1dxu3hw38K3RFRA2Pac6HXyGTVAfSDXhA/view?usp=sharing",
        "nombre": "Brochure Contratos y Trusts",
        "keywords": ["contrato", "trust", "revocable living trust", "revision"]
    },
    "contabilidad": {
        "url": "https://drive.google.com/file/d/1JyqLE4yO2W8Tde8jISHqKwXgOaPqamJw/view?usp=sharing",
        "nombre": "Catálogo Membresías Contabilidad",
        "keywords": ["contabilidad", "contador", "auditoria", "accounting", "membresia"]
    },
    "internacionalizacion": {
        "url": "https://drive.google.com/file/d/1cLfe25G-DfZqdcCb7A84AkNry5mEtFQj/view?usp=sharing",
        "nombre": "Brochure Institucional LegalNova",
        "keywords": ["internacionalizacion", "diagnostico", "quienes somos", "sobre ustedes"]
    }
}

SYSTEM_PROMPT = """Eres Nover BOT, el asistente virtual inteligente oficial de LegalNova.

=== IDENTIDAD Y TONO ===
- Eres conversacional, cercano pero profesional
- Explicas con claridad y naturalidad
- NUNCA envíes PDFs o brochures a menos que el usuario EXPLÍCITAMENTE los pida
- Tu objetivo es CONVERSAR primero, resolver dudas, y SOLO AL FINAL ofrecer documentación

=== FLUJO OBLIGATORIO ===
FASE 1 - Responde naturalmente con info del RAG (máximo 3 párrafos cortos)
FASE 2 - Solo si el usuario pide "envíame info", "brochure", "pdf" → pasa a FASE 3
FASE 3 - Captura datos: "¿Podrías indicarme tu nombre completo y correo?"
FASE 4 - Si tiene ambos datos → Responde: [ENVIAR_PDF:{tema_actual}]

=== DERIVACIÓN A EXPERTO ===
Si el usuario pide hablar con alguien o hace pregunta muy técnica:
- Pide datos primero
- Luego responde: [CONTACTAR_EXPERTO]

=== CONTEXTO ACTUAL ===
Historial: {historial}
Información RAG: {RAG_results}
Tiene nombre: {tiene_nombre}
Tiene email: {tiene_email}
Tema actual: {tema_actual}

Pregunta: {input}

Responde de forma natural y útil. NO ofrezcas PDFs sin que te los pidan."""

# ===================== MEMORIA DE CONVERSACIONES =====================
conversation_memory: Dict[str, Dict] = {}

def get_conversation_state(phone_number: str) -> Dict:
    """Obtiene o crea el estado de conversación del usuario"""
    if phone_number not in conversation_memory:
        conversation_memory[phone_number] = {
            "historial": [],
            "menu_mostrado": False,
            "esperando_datos": False,
            "tema_actual": None,
            "tiene_nombre": False,
            "tiene_email": False,
            "nombre": None,
            "email": None
        }
    return conversation_memory[phone_number]

def actualizar_conversacion(phone_number: str, user_msg: str, bot_msg: str):
    """Actualiza el historial (máximo 20 mensajes)"""
    state = get_conversation_state(phone_number)
    state["historial"].append(f"Usuario: {user_msg}")
    state["historial"].append(f"Bot: {bot_msg}")
    if len(state["historial"]) > 20:
        state["historial"] = state["historial"][-20:]

def extraer_datos_contacto(texto: str) -> Dict[str, Optional[str]]:
    """Extrae email y nombre del texto"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, texto)
    
    nombre_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'
    nombre_match = re.search(nombre_pattern, texto)
    
    return {
        "email": email_match.group(0) if email_match else None,
        "nombre": nombre_match.group(0) if nombre_match else None
    }

def identificar_tema(texto: str) -> Optional[str]:
    """Identifica el tema basado en keywords"""
    texto_lower = texto.lower()
    max_coincidencias = 0
    tema_detectado = None
    
    for tema, info in PDF_CATALOG.items():
        coincidencias = sum(1 for kw in info["keywords"] if kw in texto_lower)
        if coincidencias > max_coincidencias:
            max_coincidencias = coincidencias
            tema_detectado = tema
    
    return tema_detectado if max_coincidencias > 0 else None

def buscar_en_knowledge(pregunta: str) -> str:
    """Busca información relevante en la knowledge base"""
    q = pregunta.lower()
    resultados = []
    
    for filename, content in knowledge.items():
        if isinstance(content, str) and q in content.lower():
            index = max(0, content.lower().find(q) - 150)
            fragmento = content[index:index+500]
            resultados.append(f"Fuente: {filename}\n{fragmento}...")
    
    return "\n\n".join(resultados[:3]) if resultados else "No encontré información específica en documentos."

def send_whatsapp_message(to_number: str, message_text: str) -> bool:
    """Envía mensaje vía WhatsApp Cloud API"""
    if not WHATSAPP_PHONE_ID or not META_ACCESS_TOKEN:
        print("❌ ERROR: Configuración de WhatsApp incompleta")
        return False

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Mensaje enviado a {to_number}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar mensaje: {e}")
        try:
            print(f"Detalle: {response.text}")
        except:
            pass
        return False

# ===================== FASTAPI APP =====================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("test.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """<!DOCTYPE html>
        <html><body style="font-family:Arial;padding:50px;text-align:center;">
        <h1>🤖 Nover BOT - Online</h1><p style="color:green;">✅ Activo</p>
        </body></html>"""

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verifica el webhook de WhatsApp"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado exitosamente")
        return Response(content=challenge, media_type="text/plain")
    
    print("❌ Verificación fallida")
    return Response(content="Verificación fallida: token incorrecto", status_code=403)

@app.post("/webhook")
async def webhook(request: Request):
    """Maneja mensajes entrantes de WhatsApp"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return {"status": "error", "reason": "JSON inválido"}
    
    msg = None
    from_number = None 
    
    # ===================== EXTRACCIÓN DEL MENSAJE =====================
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]["value"]
        
        if "messages" not in changes:
            return {"status": "ok", "reason": "Status update, no es mensaje"}

        message_data = changes["messages"][0]
        from_number = message_data["from"] 
        
        if message_data.get("type") == "text":
            msg = message_data["text"]["body"]
        else:
            msg = f"[Mensaje tipo: {message_data.get('type')}]"

        print(f"\n📩 Mensaje de {from_number}: {msg}")

    except (KeyError, IndexError, TypeError) as e:
        # Fallback para pruebas locales
        if "message" in data:
            msg = data["message"]
            from_number = "test_user"
            print(f"🧪 Mensaje de prueba: {msg}")
        else:
            print(f"❌ Error extrayendo mensaje: {e}")
            return {"status": "error", "reason": "Extracción fallida"}

    if not msg or not from_number:
        return {"status": "ok", "reason": "Mensaje vacío"}
    
    # ===================== LÓGICA CONVERSACIONAL =====================
    state = get_conversation_state(from_number)
    msg_lower = msg.lower().strip()
    bot_response = ""

    # 1. MENÚ INICIAL
    if not state["menu_mostrado"] and re.search(r'\b(hola|buenos|inicio|men[uú]|hey)\b', msg_lower):
        bot_response = MENU
        state["menu_mostrado"] = True
    
    # 2. OPCIONES DEL MENÚ (1-6)
    elif re.match(r'^[1-6]$', msg_lower):
        opcion = msg_lower
        
        if opcion == "1":
            state["tema_actual"] = "llc_constitucion"
            bot_response = """¡Perfecto! Te cuento sobre la constitución de LLC en Estados Unidos.

Ofrecemos 3 paquetes:

🔹 LLC Simple (USD 970): Incluye constitución, EIN, Registered Agent por 1 año. Se completa en 3 semanas.

🔹 LLC Full (USD 1,900): Todo lo anterior + Operating Agreement personalizado + consultoría inicial.

🔹 LLC High-Level (USD 2,900): Paquete completo con estructura fiscal óptima y estrategia de negocios.

Los estados más populares son Delaware (protección legal máxima), Wyoming (privacidad total) y Florida (sin impuesto estatal sobre renta).

¿Qué estado te interesa o tienes alguna pregunta específica?"""
        
        elif opcion == "2":
            state["tema_actual"] = "internacionalizacion"
            bot_response = """Excelente elección. Nuestro servicio de Internacionalización incluye un diagnóstico completo desde USD 2,500.

¿Qué incluye?
✅ Análisis de viabilidad de mercado USA/Colombia
✅ Estructura legal y fiscal óptima
✅ Roadmap personalizado de entrada al mercado
✅ Conexiones estratégicas

Es ideal si ya tienes una empresa en tu país y quieres expandirte al mercado norteamericano de forma estructurada.

¿Cuál es tu situación actual? ¿Ya tienes empresa constituida o estás empezando?"""
        
        elif opcion == "3":
            state["tema_actual"] = "impuestos_usa"
            bot_response = """Claro, te explico las obligaciones fiscales principales en USA:

📌 Franchise Tax (Delaware): Vence 1 de marzo - desde USD 300/año
📌 BOI Report: Obligatorio antes del 31 de diciembre 2025 (nueva ley FinCEN)
📌 Annual Report: Mantenimiento anual del estado - varía según ubicación
📌 Tax Return 1065: Declaración de impuestos federales - vence 15 de marzo

Nosotros manejamos todo el cumplimiento tributario para que no tengas sanciones.

¿Ya tienes LLC constituida o estás evaluando dónde formarla?"""
        
        elif opcion == "4":
            state["tema_actual"] = "contratos_trusts"
            bot_response = """Perfecto. Manejamos dos áreas principales:

📄 CONTRATOS INTERNACIONALES:
• Revisión de contratos: desde USD 300
• Drafting personalizado: desde USD 500
• NDAs, Joint Ventures, Distribución, etc.

🏛️ TRUSTS:
• Revocable Living Trust: desde USD 2,000
• Protección de activos y planificación patrimonial
• Ideal para bienes raíces o inversiones en USA

¿Necesitas revisar un contrato existente o estás buscando proteger activos con un Trust?"""
        
        elif opcion == "5":
            state["tema_actual"] = "contabilidad"
            bot_response = """Genial. Ofrecemos membresías de Contabilidad y Auditoría desde USD 1,000/mes que incluyen:

✅ Contabilidad mensual USA (GAAP)
✅ Preparación de Tax Returns
✅ Franchise Tax y BOI filings
✅ Annual Reports
✅ Asesoría fiscal continua
✅ Dashboard financiero en tiempo real

También manejamos auditorías certificadas y servicios a la medida según tu industria.

¿En qué estado opera tu empresa y cuántas transacciones mensuales aproximadamente manejas?"""
        
        elif opcion == "6":
            if not state["tiene_nombre"] or not state["tiene_email"]:
                bot_response = "Con gusto te conecto con un especialista. Para coordinar la llamada, ¿podrías indicarme tu nombre completo y correo electrónico?"
                state["esperando_datos"] = True
                state["tema_actual"] = "contactar_experto"
            else:
                bot_response = f"Perfecto {state['nombre']}, te conecto de inmediato:\n\nhttps://api.whatsapp.com/send?phone=573117101017"
    
    # 3. SOLICITUD DE EXPERTO
    elif re.search(r'\b(experto|humano|especialista|hablar con alguien|asesor)\b', msg_lower):
        if not state["tiene_nombre"] or not state["tiene_email"]:
            bot_response = "Con gusto te conecto con un especialista. Para coordinar la llamada, ¿podrías indicarme tu nombre completo y correo electrónico?"
            state["esperando_datos"] = True
            state["tema_actual"] = "contactar_experto"
        else:
            bot_response = f"Perfecto {state['nombre']}, te conecto de inmediato:\n\nhttps://api.whatsapp.com/send?phone=573117101017"
    
    # 4. CAPTURA DE DATOS
    elif state["esperando_datos"]:
        datos = extraer_datos_contacto(msg)
        
        if datos["email"]:
            state["email"] = datos["email"]
            state["tiene_email"] = True
        if datos["nombre"]:
            state["nombre"] = datos["nombre"]
            state["tiene_nombre"] = True
        
        # Verificar si ya tenemos ambos datos
        if state["tiene_nombre"] and state["tiene_email"]:
            if state["tema_actual"] == "contactar_experto":
                bot_response = f"Perfecto {state['nombre']}, te conecto de inmediato:\n\nhttps://api.whatsapp.com/send?phone=573117101017"
            elif state["tema_actual"] and state["tema_actual"] in PDF_CATALOG:
                pdf_info = PDF_CATALOG[state["tema_actual"]]
                bot_response = f"¡Excelente {state['nombre']}! Aquí tienes el {pdf_info['nombre']}:\n\n{pdf_info['url']}\n\nRevísalo con calma y si tienes dudas, aquí estoy. ¿Te gustaría agendar una asesoría personalizada?"
            state["esperando_datos"] = False
        else:
            # Pedir dato faltante
            if not state["tiene_nombre"]:
                bot_response = "Perfecto, ¿y cuál es tu nombre completo?"
            elif not state["tiene_email"]:
                bot_response = "Gracias. ¿Cuál es tu correo electrónico?"
    
    # 5. SOLICITUD EXPLÍCITA DE DOCUMENTACIÓN
    elif any(palabra in msg_lower for palabra in ["envíame", "enviame", "manda", "mándame", "brochure", "pdf", "documento", "guia", "guía", "manual", "quiero info", "más información", "mas informacion"]):
        tema = identificar_tema(msg)
        
        if tema:
            state["tema_actual"] = tema
            if not state["tiene_nombre"] or not state["tiene_email"]:
                pdf_info = PDF_CATALOG[tema]
                bot_response = f"Con gusto te envío el {pdf_info['nombre']}. ¿Podrías indicarme tu nombre completo y correo electrónico?"
                state["esperando_datos"] = True
            else:
                pdf_info = PDF_CATALOG[tema]
                bot_response = f"Aquí tienes el {pdf_info['nombre']}:\n\n{pdf_info['url']}\n\n¿Tienes alguna duda específica?"
        else:
            bot_response = "Con gusto te envío información. ¿Sobre qué tema específico te gustaría recibir documentación? (LLC, impuestos, contratos, contabilidad, etc.)"
    
    # 6. CONVERSACIÓN NORMAL CON GEMINI + RAG
    else:
        tema = identificar_tema(msg)
        if tema:
            state["tema_actual"] = tema
        
        rag = buscar_en_knowledge(msg)
        historial_texto = "\n".join(state["historial"][-10:])
        
        prompt = SYSTEM_PROMPT.format(
            historial=historial_texto,
            RAG_results=rag,
            input=msg,
            tiene_nombre=state["tiene_nombre"],
            tiene_email=state["tiene_email"],
            tema_actual=state["tema_actual"] if state["tema_actual"] else "ninguno"
        )
        
        try:
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            response_model = model.generate_content(prompt)
            bot_response = response_model.text
            
            # Procesar comandos especiales
            if "[ENVIAR_PDF:" in bot_response:
                match = re.search(r'\[ENVIAR_PDF:(\w+)\]', bot_response)
                if match and state["tiene_nombre"] and state["tiene_email"]:
                    tema_pdf = match.group(1)
                    if tema_pdf in PDF_CATALOG:
                        pdf_info = PDF_CATALOG[tema_pdf]
                        bot_response = bot_response.replace(
                            f"[ENVIAR_PDF:{tema_pdf}]", 
                            f"Aquí tienes el {pdf_info['nombre']}:\n{pdf_info['url']}"
                        )
            
            if "[CONTACTAR_EXPERTO]" in bot_response:
                bot_response = bot_response.replace(
                    "[CONTACTAR_EXPERTO]",
                    "Te conecto de inmediato:\nhttps://api.whatsapp.com/send?phone=573117101017"
                )
        
        except Exception as e:
            print(f"❌ Error con Gemini: {e}")
            bot_response = "Disculpa, tuve un problema técnico. ¿Podrías repetir tu pregunta?"
    
    # ===================== ACTUALIZAR HISTORIAL Y ENVIAR =====================
    actualizar_conversacion(from_number, msg, bot_response)
    
    print(f"🤖 Respuesta: {bot_response[:100]}...")
    
    # Enviar respuesta
    if from_number != "test_user":
        exito = send_whatsapp_message(from_number, bot_response)
        return {"status": "ok", "whatsapp_sent": exito}
    else:
        return {"response": bot_response}

# ===================== EJECUCIÓN =====================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



