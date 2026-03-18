import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET      = os.getenv("JWT_SECRET")
ALGORITHM   = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MIN  = int(os.getenv("JWT_EXPIRE_MINUTES", 1440))


def crear_token(datos: dict) -> str:
    """Genera un JWT con los datos del usuario."""
    payload = datos.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=EXPIRE_MIN)
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict:
    """
    Verifica el JWT y devuelve el payload.
    Lanza JWTError si es inválido o ha expirado.
    """
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])