import os
import json
import uuid
import redis
from pathlib import Path
from agente.llm_provider import get_llm

# --- Conexión Redis ---
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True
)

# --- Carga de prompts desde ficheros ---
PROMPTS_DIR = Path(__file__).parent / "prompts"

def _cargar_prompt(nombre: str) -> str:
    return (PROMPTS_DIR / nombre).read_text(encoding="utf-8")

PROMPT_SISTEMA = _cargar_prompt("sistema.txt")
PROMPT_EXTRACCION = _cargar_prompt("extraccion_perfil.txt")


# --- LLM ---
llm = get_llm(temperature=0)


# -------------------------------------------------------------------
# PASO 1: Extracción del perfil del negocio
# -------------------------------------------------------------------

def extraer_perfil(input_usuario: str) -> dict:
    """
    Llama al LLM para extraer un perfil estructurado del negocio
    a partir del texto libre del usuario.
    Devuelve un dict con los campos del perfil.
    """
    prompt_completo = f"{PROMPT_EXTRACCION}\n\nINPUT: \"{input_usuario}\"\nOUTPUT:"

    respuesta = llm.invoke(prompt_completo)
    texto = respuesta.content.strip()

    try:
        perfil = json.loads(texto)
    except json.JSONDecodeError:
        # Intento de limpieza si el LLM añade texto extra
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            perfil = json.loads(texto[inicio:fin])
        else:
            raise ValueError(f"El LLM no devolvió un JSON válido: {texto}")

    return perfil


# -------------------------------------------------------------------
# PASO 2: Validación del negocio
# -------------------------------------------------------------------

def validar_negocio(perfil: dict) -> tuple[bool, str]:
    """
    Comprueba si el negocio es válido para GeoRetail.
    Devuelve (es_valido, mensaje_error).
    """
    if not perfil.get("es_negocio_local", False):
        return False, (
            "GeoRetail está diseñado para negocios físicos locales "
            "(cafeterías, tiendas, gimnasios, etc.). "
            "Parece que tu idea no requiere un local físico en Barcelona."
        )
    return True, ""


# -------------------------------------------------------------------
# PASO 3: Gestión de sesión en Redis
# -------------------------------------------------------------------

def guardar_sesion(session_id: str, perfil: dict) -> None:
    """Guarda el perfil del negocio en Redis con TTL de 1 hora."""
    redis_client.setex(
        f"sesion:{session_id}:perfil",
        3600,
        json.dumps(perfil, ensure_ascii=False)
    )

def cargar_sesion(session_id: str) -> dict | None:
    """Recupera el perfil guardado en Redis para una sesión."""
    datos = redis_client.get(f"sesion:{session_id}:perfil")
    if datos:
        return json.loads(datos)
    return None


# -------------------------------------------------------------------
# PASO 4: Respuesta en lenguaje natural (placeholder hasta tener PostGIS)
# -------------------------------------------------------------------

def generar_respuesta_placeholder(perfil: dict) -> str:
    """
    Genera una respuesta de prueba mientras no está conectado PostGIS.
    Eliminar cuando esté implementada la Fase 3.
    """
    prompt = (
        f"{PROMPT_SISTEMA}\n\n"
        f"El usuario quiere abrir: {perfil.get('sector', 'un negocio')} "
        f"para clientes {perfil.get('cliente_objetivo', {})}.\n"
        f"Ticket medio: {perfil.get('ticket_medio_min')}€ - {perfil.get('ticket_medio_max')}€.\n"
        f"Espacio necesario: {perfil.get('m2_min')}m² - {perfil.get('m2_max')}m².\n\n"
        f"Explica en 2-3 frases qué tipo de zona de Barcelona encajaría mejor "
        f"y qué variables son más importantes para este negocio."
    )
    respuesta = llm.invoke(prompt)
    return respuesta.content


# -------------------------------------------------------------------
# FUNCIÓN PRINCIPAL: procesar_busqueda
# -------------------------------------------------------------------

def procesar_busqueda(session_id: str, input_usuario: str) -> dict:
    """
    Orquesta todo el flujo:
    1. Extrae el perfil del negocio
    2. Valida que sea un negocio local
    3. Guarda el perfil en Redis
    4. (Fase 3 pendiente) Consulta zonas en PostGIS
    5. Devuelve resultado
    """

    # 1. Extraer perfil
    try:
        perfil = extraer_perfil(input_usuario)
    except Exception as e:
        return {
            "ok": False,
            "error": f"No pude interpretar tu idea de negocio. Intenta describir mejor el tipo de local. ({str(e)})"
        }

    # 2. Validar
    es_valido, mensaje_error = validar_negocio(perfil)
    if not es_valido:
        return {"ok": False, "error": mensaje_error}

    # 3. Guardar sesión
    guardar_sesion(session_id, perfil)

    # 4. Respuesta (placeholder hasta Fase 3 con PostGIS)
    descripcion = generar_respuesta_placeholder(perfil)

    return {
        "ok": True,
        "session_id": session_id,
        "perfil": perfil,
        "descripcion": descripcion,
        # "zonas": []  <-- aquí irá el resultado de PostGIS en la Fase 3
    }


# -------------------------------------------------------------------
# REFINAMIENTO CONVERSACIONAL (Fase 9)
# -------------------------------------------------------------------

def refinar_busqueda(session_id: str, mensaje_usuario: str) -> dict:
    """
    Permite al usuario seguir conversando para afinar la búsqueda.
    Recupera el perfil de Redis y responde en contexto.
    """
    perfil = cargar_sesion(session_id)

    if not perfil:
        return {
            "ok": False,
            "error": "Sesión expirada. Por favor realiza una nueva búsqueda."
        }

    prompt = (
        f"{PROMPT_SISTEMA}\n\n"
        f"Contexto del negocio que el usuario quiere abrir:\n{json.dumps(perfil, ensure_ascii=False, indent=2)}\n\n"
        f"El usuario ahora dice: \"{mensaje_usuario}\"\n\n"
        f"Responde de forma útil y concisa en español."
    )

    respuesta = llm.invoke(prompt)

    return {
        "ok": True,
        "session_id": session_id,
        "respuesta": respuesta.content
    }