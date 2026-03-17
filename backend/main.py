from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.buscar import router as buscar_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="GeoRetail API",
    description="API de análisis geoespacial para recomendación de locales comerciales",
    version="1.0.0"
)

# CORS para que el frontend Next.js pueda conectar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(buscar_router)

@app.get("/health")
def health():
    return {"status": "ok"}