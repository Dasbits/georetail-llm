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

# --- Carga de prompts ---
PROMPTS_DIR = Path(__file__).parent / "prompts"

def _cargar_prompt(nombre: str) -> str:
    return (PROMPTS_DIR / nombre).read_text(encoding="utf-8")

PROMPT_SISTEMA          = _cargar_prompt("sistema.txt")
PROMPT_EXTRACCION       = _cargar_prompt("extraccion_perfil.txt")
PROMPT_EVALUACION       = _cargar_prompt("evaluacion_input.txt")
PROMPT_PREGUNTAS        = _cargar_prompt("generar_preguntas.txt")
PROMPT_VALIDAR          = _cargar_prompt("validar_respuestas.txt")

MAX_REINTENTOS = 2

# --- LLM ---
llm = get_llm(temperature=0)


# ---------------------------------------------------------------
# UTILIDAD: parsear JSON de respuesta LLM
# ---------------------------------------------------------------

def _parsear_json(texto: str) -> dict:
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio != -1 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ValueError(f"No se pudo parsear JSON: {texto}")


# ---------------------------------------------------------------
# PASO 1: Evaluar si el input tiene suficiente información
# ---------------------------------------------------------------

def evaluar_input(input_usuario: str) -> dict:
    """
    Devuelve {"suficiente": True} o
             {"suficiente": False, "campos_faltantes": [...]}
    """
    prompt = f"{PROMPT_EVALUACION}\n\nINPUT: \"{input_usuario}\"\nOUTPUT:"
    respuesta = llm.invoke(prompt)
    return _parsear_json(respuesta.content)


# ---------------------------------------------------------------
# PASO 2a: Generar preguntas si falta información
# ---------------------------------------------------------------

def generar_preguntas(campos_faltantes: list) -> dict:
    """
    Genera el cuestionario para los campos que faltan.
    Devuelve {"preguntas": [...]}
    """
    prompt = (
        f"{PROMPT_PREGUNTAS}\n\n"
        f"CAMPOS FALTANTES: {json.dumps(campos_faltantes)}\n"
        f"OUTPUT:"
    )
    respuesta = llm.invoke(prompt)
    return _parsear_json(respuesta.content)


# ---------------------------------------------------------------
# PASO 2b: Extraer perfil completo
# ---------------------------------------------------------------

def extraer_perfil(input_usuario: str) -> dict:
    prompt = f"{PROMPT_EXTRACCION}\n\nINPUT: \"{input_usuario}\"\nOUTPUT:"
    respuesta = llm.invoke(prompt)
    return _parsear_json(respuesta.content)


# ---------------------------------------------------------------
# PASO 3: Validación del negocio
# ---------------------------------------------------------------

def validar_negocio(perfil: dict) -> tuple[bool, str]:
    if not perfil.get("es_negocio_local", False):
        return False, (
            "GeoRetail está diseñado para negocios físicos locales. "
            "Parece que tu idea no requiere un local físico en Barcelona."
        )
    return True, ""


# ---------------------------------------------------------------
# PASO 4: Gestión de sesión en Redis
# ---------------------------------------------------------------

def guardar_sesion(session_id: str, datos: dict, clave: str = "perfil") -> None:
    redis_client.setex(
        f"sesion:{session_id}:{clave}",
        3600,
        json.dumps(datos, ensure_ascii=False)
    )

def cargar_sesion(session_id: str, clave: str = "perfil") -> dict | None:
    datos = redis_client.get(f"sesion:{session_id}:{clave}")
    return json.loads(datos) if datos else None


# ---------------------------------------------------------------
# PASO 5: Respuesta en lenguaje natural (placeholder hasta PostGIS)
# ---------------------------------------------------------------

def generar_respuesta_placeholder(perfil: dict) -> str:
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


# ---------------------------------------------------------------
# FUNCIÓN PRINCIPAL: procesar_busqueda
# ---------------------------------------------------------------

def procesar_busqueda(session_id: str, input_usuario: str) -> dict:
    """
    Flujo completo:
    1. Evalúa si el input tiene suficiente información
    2a. Si NO → devuelve cuestionario y guarda el input original en Redis
    2b. Si SÍ → extrae perfil, valida y devuelve recomendación
    """

    # 1. Evaluar calidad del input
    try:
        evaluacion = evaluar_input(input_usuario)
    except Exception as e:
        return {"ok": False, "error": f"Error evaluando el input: {str(e)}"}

    # 2a. Input insuficiente → devolver cuestionario
    if not evaluacion.get("suficiente"):
        campos_faltantes = evaluacion.get("campos_faltantes", [])

        try:
            cuestionario = generar_preguntas(campos_faltantes)
        except Exception as e:
            return {"ok": False, "error": f"Error generando preguntas: {str(e)}"}

        # Guardar el input original para combinarlo con las respuestas después
        guardar_sesion(session_id, {"input_original": input_usuario}, clave="input")

        return {
            "ok": True,
            "tipo": "cuestionario",
            "session_id": session_id,
            "mensaje": "Necesito un poco más de información para encontrar la mejor ubicación.",
            "preguntas": cuestionario.get("preguntas", [])
        }

    # 2b. Input suficiente → extraer perfil
    try:
        perfil = extraer_perfil(input_usuario)
    except Exception as e:
        return {"ok": False, "error": f"Error extrayendo perfil: {str(e)}"}

    es_valido, mensaje_error = validar_negocio(perfil)
    if not es_valido:
        return {"ok": False, "error": mensaje_error}

    guardar_sesion(session_id, perfil)
    descripcion = generar_respuesta_placeholder(perfil)

    return {
        "ok": True,
        "tipo": "perfil",
        "session_id": session_id,
        "perfil": perfil,
        "descripcion": descripcion
    }


# ---------------------------------------------------------------
# FUNCIÓN: procesar_respuestas_cuestionario
# ---------------------------------------------------------------

def validar_respuestas(respuestas: dict) -> dict:
    """
    Valida que las respuestas del cuestionario tengan sentido.
    Devuelve {"valido": True} o {"valido": False, "motivo": ..., "mensaje_usuario": ...}
    """
    prompt = (
        f"{PROMPT_VALIDAR}\n\n"
        f"INPUT: {json.dumps(respuestas, ensure_ascii=False)}\n"
        f"OUTPUT:"
    )
    respuesta = llm.invoke(prompt)
    return _parsear_json(respuesta.content)

def _detectar_campos_problematicos(respuestas: dict, motivo: str) -> list:
    """
    Según el motivo del fallo, devuelve los campos que hay que volver a preguntar.
    """
    if motivo == "vago":
        # Devolver solo los campos con respuestas genéricas
        campos = []
        valores_vagos = {"otro", "otros", "no sé", "no se", "algo", "cosas", "varios"}
        for campo, valor in respuestas.items():
            if str(valor).lower().strip() in valores_vagos:
                campos.append(campo)
        return campos if campos else ["sector"]  # fallback

    if motivo == "incoherente":
        # Volver a preguntar precio y m² que suelen ser los que chocan
        return ["precio", "m2"]

    return ["sector"]  # fallback genérico

def procesar_respuestas(session_id: str, respuestas: dict) -> dict:
    """
    Recibe las respuestas del cuestionario.
    Valida que sean coherentes antes de extraer el perfil.
    Si no son válidas, devuelve un nuevo cuestionario o un error claro.
    """

    # 1. Validar las respuestas
    try:
        validacion = validar_respuestas(respuestas)
    except Exception as e:
        return {"ok": False, "error": f"Error validando respuestas: {str(e)}"}

    if not validacion.get("valido"):
        motivo = validacion.get("motivo")
        mensaje = validacion.get("mensaje_usuario", "Algo no cuadra en tu respuesta.")

        # Negocio online → error definitivo, no tiene sentido seguir preguntando
        if motivo == "online":
            return {
                "ok": False,
                "tipo": "error_definitivo",
                "error": mensaje
            }

        # Respuesta vaga o incoherente → comprobar reintentos
        sesion_reintentos = cargar_sesion(session_id, clave="reintentos")
        reintentos = sesion_reintentos.get("count", 0) if sesion_reintentos else 0

        if reintentos >= MAX_REINTENTOS:
            return {
                "ok": False,
                "tipo": "error_definitivo",
                "error": (
                    "No hemos podido entender bien tu idea de negocio después de varios intentos. "
                    "Intenta describir tu negocio de forma más concreta, por ejemplo: "
                    "'cafetería de especialidad', 'barbería clásica', 'tienda de ropa sostenible'."
                )
            }

        # Guardar reintento y devolver nuevo cuestionario
        guardar_sesion(session_id, {"count": reintentos + 1}, clave="reintentos")

        # Detectar qué campos siguen siendo problemáticos
        campos_problematicos = _detectar_campos_problematicos(respuestas, motivo)
        try:
            cuestionario = generar_preguntas(campos_problematicos)
        except Exception as e:
            return {"ok": False, "error": f"Error generando preguntas: {str(e)}"}

        return {
            "ok": True,
            "tipo": "cuestionario",
            "session_id": session_id,
            "mensaje": mensaje,  # mensaje explicativo del problema
            "preguntas": cuestionario.get("preguntas", []),
            "reintento": reintentos + 1,
            "max_reintentos": MAX_REINTENTOS
        }

    # 2. Respuestas válidas → resetear reintentos y extraer perfil
    guardar_sesion(session_id, {"count": 0}, clave="reintentos")

    datos_input = cargar_sesion(session_id, clave="input")
    input_original = datos_input.get("input_original", "") if datos_input else ""

    respuestas_texto = ", ".join([f"{k}: {v}" for k, v in respuestas.items()])
    input_combinado = f"{input_original}. Datos adicionales: {respuestas_texto}".strip(". ")

    try:
        perfil = extraer_perfil(input_combinado)
    except Exception as e:
        return {"ok": False, "error": f"Error extrayendo perfil: {str(e)}"}

    es_valido, mensaje_error = validar_negocio(perfil)
    if not es_valido:
        return {"ok": False, "tipo": "error_definitivo", "error": mensaje_error}

    guardar_sesion(session_id, perfil)
    descripcion = generar_respuesta_placeholder(perfil)

    return {
        "ok": True,
        "tipo": "perfil",
        "session_id": session_id,
        "perfil": perfil,
        "descripcion": descripcion
    }

# ---------------------------------------------------------------
# FUNCIÓN: refinamiento conversacional (Fase 9)
# ---------------------------------------------------------------

def refinar_busqueda(session_id: str, mensaje_usuario: str) -> dict:
    perfil = cargar_sesion(session_id)

    if not perfil:
        return {"ok": False, "error": "Sesión expirada. Por favor realiza una nueva búsqueda."}

    prompt = (
        f"{PROMPT_SISTEMA}\n\n"
        f"Contexto del negocio:\n{json.dumps(perfil, ensure_ascii=False, indent=2)}\n\n"
        f"El usuario dice: \"{mensaje_usuario}\"\n\n"
        f"Responde de forma útil y concisa en español."
    )

    respuesta = llm.invoke(prompt)
    return {
        "ok": True,
        "session_id": session_id,
        "respuesta": respuesta.content
    }