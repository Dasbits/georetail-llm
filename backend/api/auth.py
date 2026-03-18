from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from db.conexion import get_db
from db.modelos import Usuario
from auth.jwt import crear_token
from auth.dependencias import get_usuario_actual as get_usuario_actual_from_auth

router = APIRouter(prefix="/auth", tags=["auth"])


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Modelos de request/response ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nombre: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: dict


# --- Utilidades ---

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verificar_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# --- Endpoints ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registro de nuevo usuario."""

    # Comprobar si el email ya existe
    if db.query(Usuario).filter(Usuario.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese email"
        )

    # Crear usuario
    usuario = Usuario(
        email=req.email,
        password_hash=hash_password(req.password),
        nombre=req.nombre
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # Generar token
    token = crear_token({"sub": str(usuario.id), "email": usuario.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": str(usuario.id),
            "email": usuario.email,
            "nombre": usuario.nombre
        }
    }


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login con email y contraseña."""

    usuario = db.query(Usuario).filter(Usuario.email == req.email).first()

    if not usuario or not verificar_password(req.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos"
        )

    token = crear_token({"sub": str(usuario.id), "email": usuario.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": str(usuario.id),
            "email": usuario.email,
            "nombre": usuario.nombre
        }
    }


@router.get("/me")
def me(usuario: Usuario = Depends(get_usuario_actual_from_auth)):
    """Devuelve los datos del usuario autenticado."""
    return {
        "id": str(usuario.id),
        "email": usuario.email,
        "nombre": usuario.nombre
    }