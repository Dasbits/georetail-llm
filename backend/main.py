from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.buscar import router as buscar_router
from api.auth import router as auth_router
from db.conexion import engine
from db.modelos import Base
from dotenv import load_dotenv

load_dotenv()

# Crea las tablas si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GeoRetail API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(buscar_router)

@app.get("/health")
def health():
    return {"status": "ok"}