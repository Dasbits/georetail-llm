import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agente.agente import (
    procesar_busqueda,
    procesar_respuestas,
    refinar_busqueda
)

router = APIRouter()


class BusquedaRequest(BaseModel):
    input_usuario: str
    session_id: str | None = None


class RespuestasRequest(BaseModel):
    session_id: str
    respuestas: dict  # {"sector": "Cafetería", "precio": "Precio medio", ...}


class RefinamientoRequest(BaseModel):
    session_id: str
    mensaje: str


@router.post("/buscar")
def buscar(req: BusquedaRequest):
    """
    Recibe el input del usuario.
    - Si hay suficiente info → devuelve perfil + descripción (tipo: "perfil")
    - Si falta info → devuelve cuestionario (tipo: "cuestionario")
    """
    session_id = req.session_id or str(uuid.uuid4())
    resultado = procesar_busqueda(session_id, req.input_usuario)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado


@router.post("/responder")
def responder(req: RespuestasRequest):
    """
    Recibe las respuestas del cuestionario y completa el perfil.
    Siempre devuelve tipo: "perfil" si va bien.
    """
    resultado = procesar_respuestas(req.session_id, req.respuestas)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado


@router.post("/refinar")
def refinar(req: RefinamientoRequest):
    """
    Refinamiento conversacional manteniendo el contexto de sesión.
    """
    resultado = refinar_busqueda(req.session_id, req.mensaje)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado