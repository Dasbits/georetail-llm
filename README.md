# GeoRetail — LLM Backend

Módulo de IA del proyecto GeoRetail. Recibe la idea de negocio del usuario en lenguaje natural, extrae un perfil estructurado y gestiona el contexto de sesión para el refinamiento conversacional.

> ⚠️ Este repositorio contiene únicamente el backend LLM (Fases 1 y 2 del flujo completo de GeoRetail). Las fases de PostGIS, XGBoost y frontend están pendientes de integrar.

---

## Qué hace este módulo

- Recibe texto libre del usuario ("quiero abrir una barbería para hombres jóvenes...")
- Llama a un LLM para extraer un perfil estructurado del negocio en JSON
- Valida que el negocio sea un local físico (rechaza negocios online)
- Guarda el perfil en Redis como contexto de sesión
- Permite refinamiento conversacional sin perder el contexto
- Diseñado para cambiar de proveedor LLM (OpenAI / Anthropic / Ollama) tocando una línea en `.env`

---

## Estructura del proyecto

```
georetail/
├── docker-compose.yml          # PostgreSQL + Redis
└── backend/
    ├── .env                    # Variables de entorno (no subir a git)
    ├── requirements.txt
    ├── main.py                 # Entrada FastAPI
    ├── api/
    │   └── buscar.py           # Endpoints /buscar y /refinar
    └── agente/
        ├── llm_provider.py     # Wrapper multi-proveedor LLM
        ├── agente.py           # Lógica principal del agente
        └── prompts/
            ├── sistema.txt              # Prompt de sistema
            └── extraccion_perfil.txt   # Few-shots para extracción de perfil
```

---

## Requisitos previos

- Python 3.11+
- Docker Desktop
- Una API key de OpenAI (o Anthropic si prefieres Claude)

---

## Instalación y arranque

### 1. Clona el repositorio

```bash
git clone https://github.com/Dasbits/georetail-llm
cd georetail-llm
```

### 2. Configura las variables de entorno

Crea el fichero `backend/.env` con este contenido:

```env
# Proveedor activo: openai | anthropic | ollama
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o

# Keys (solo necesitas la del proveedor activo)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Servicios
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://georetail:georetail123@localhost:5432/georetail
```

### 3. Levanta Redis y PostgreSQL con Docker

```bash
docker compose up -d
```

Verifica que están corriendo:

```bash
docker compose ps
```

### 4. Crea el entorno virtual e instala dependencias

```bash
cd backend

# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 5. Arranca la API

```bash
uvicorn main:app --reload --port 8000
```

Cuando veas esto, todo está funcionando:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

## Probar los endpoints

### Opción A — Swagger (sin instalar nada)

Abre el navegador en:

```
http://localhost:8000/docs
```

### Opción B — Thunder Client (extensión VS Code)

**POST /buscar** — primera búsqueda

```
POST http://localhost:8000/buscar
Content-Type: application/json

{
  "input_usuario": "quiero abrir una barbería para hombres jóvenes, precio asequible, zona céntrica"
}
```

Respuesta esperada:

```json
{
  "ok": true,
  "session_id": "abc-123-...",
  "perfil": {
    "sector": "barbería",
    "cliente_objetivo": { "edad": "18-35", "genero": "masculino", "renta": "media" },
    "ticket_medio_min": 15,
    "ticket_medio_max": 25,
    "m2_min": 40,
    "m2_max": 80,
    "es_negocio_local": true
  },
  "descripcion": "Para una barbería orientada a hombres jóvenes..."
}
```

**POST /refinar** — refinamiento conversacional (usa el session_id del paso anterior)

```
POST http://localhost:8000/refinar
Content-Type: application/json

{
  "session_id": "abc-123-...",
  "mensaje": "¿hay zonas con alquiler más barato que mantengan buen flujo peatonal?"
}
```

### Opción C — curl (CMD)

```bash
curl -X POST http://localhost:8000/buscar ^
  -H "Content-Type: application/json" ^
  -d "{\"input_usuario\": \"quiero abrir una cafeteria en el centro\"}"
```

---

## Cambiar de proveedor LLM

Solo edita `backend/.env`:

```env
# Usar Claude en vez de GPT
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...

# Usar modelo local gratuito con Ollama
LLM_PROVIDER=ollama
LLM_MODEL=llama3
```

El resto del código no cambia nada.

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Comprueba que la API está viva |
| POST | `/buscar` | Extrae perfil del negocio y devuelve recomendación inicial |
| POST | `/refinar` | Refinamiento conversacional manteniendo el contexto de sesión |

---

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Connection refused :6379` | Docker no está corriendo | `docker compose up -d` |
| `OPENAI_API_KEY not set` | Falta el `.env` | Crea `backend/.env` con tu key |
| `Module not found` | Venv no activado | `venv\Scripts\activate` (Windows) |
| Puerto 8000 ocupado | Otro proceso usa el puerto | `uvicorn main:app --reload --port 8001` |
| `JSONDecodeError` | El LLM devolvió texto extra | Revisa el prompt en `extraccion_perfil.txt` |

---

## Estado del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| Fase 1 | Entrada del usuario | ✅ Hecho |
| Fase 2 | Extracción de perfil con LLM | ✅ Hecho |
| Fase 3 | Consulta geoespacial PostGIS | 🔲 Pendiente |
| Fase 4 | Scoring XGBoost | 🔲 Pendiente |
| Fase 5 | NLP de reseñas | 🔲 Pendiente |
| Fase 6 | Análisis Street View | 🔲 Pendiente |
| Fase 7-10 | Ranking, análisis financiero, exportación | 🔲 Pendiente |

---

## Contexto del proyecto completo

Este módulo forma parte de **GeoRetail**, una aplicación web de análisis geoespacial que recomienda ubicaciones comerciales en Barcelona a emprendedores. El stack completo incluye Next.js en el frontend, FastAPI + Celery en el backend, PostgreSQL + PostGIS como base de datos y XGBoost para el scoring de ubicaciones.
