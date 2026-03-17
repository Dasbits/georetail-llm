import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agente.agente import procesar_busqueda, refinar_busqueda

router = APIRouter()


# --- Modelos de request ---

class BusquedaRequest(BaseModel):
    input_usuario: str
    session_id: str | None = None
    filtros: dict | None = None  # presupuesto, m2, barrio (opcional)


class RefinamientoRequest(BaseModel):
    session_id: str
    mensaje: str


# --- Endpoints ---

@router.post("/buscar")
def buscar(req: BusquedaRequest):
    """
    Recibe la idea del usuario en lenguaje natural y devuelve
    el perfil extraído + descripción de zonas recomendadas.
    """
    session_id = req.session_id or str(uuid.uuid4())

    resultado = procesar_busqueda(session_id, req.input_usuario)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado


@router.post("/refinar")
def refinar(req: RefinamientoRequest):
    """
    Permite al usuario afinar la búsqueda conversacionalmente
    sin perder el contexto del negocio.
    """
    resultado = refinar_busqueda(req.session_id, req.mensaje)

    if not resultado.get("ok"):
        raise HTTPException(status_code=400, detail=resultado.get("error"))

    return resultado