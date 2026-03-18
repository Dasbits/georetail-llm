from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from auth.jwt import verificar_token
from db.conexion import get_db
from db.modelos import Usuario

bearer_scheme = HTTPBearer()


def get_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Dependencia que protege los endpoints.
    Extrae el token del header Authorization: Bearer <token>
    y devuelve el usuario de la BD.
    """
    credenciales_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verificar_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credenciales_error
    except JWTError:
        raise credenciales_error

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if usuario is None:
        raise credenciales_error

    return usuario