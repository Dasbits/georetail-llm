import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from db.conexion import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre        = Column(String(255), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)