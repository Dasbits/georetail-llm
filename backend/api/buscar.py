import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from agente.agente import procesar_busqueda, procesar_respuestas, refinar_busqueda
from auth.dependencias import get_usuario_actual
from db.modelos import Usuario

router = APIRouter()


class BusquedaRequest(BaseModel):
    input_usuario: str
    session_id: str | None = None

class RespuestasRequest(BaseModel):
    session_id: str
    respuestas: dict

class RefinamientoRequest(BaseModel):
    session_id: str
    mensaje: str


@router.post("/buscar")
def buscar(
    req: BusquedaRequest,
    usuario: Usuario = Depends(get_usuario_actual)  # ← protegido
):
    session_id = req.session_id or str(uuid.uuid4())
    resultado = procesar_busqueda(session_id, req.input_usuario)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado


@router.post("/responder")
def responder(
    req: RespuestasRequest,
    usuario: Usuario = Depends(get_usuario_actual)  # ← protegido
):
    resultado = procesar_respuestas(req.session_id, req.respuestas)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado


@router.post("/refinar")
def refinar(
    req: RefinamientoRequest,
    usuario: Usuario = Depends(get_usuario_actual)  # ← protegido
):
    resultado = refinar_busqueda(req.session_id, req.mensaje)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado