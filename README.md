# GeoRetail — LLM Backend

Módulo de IA del proyecto GeoRetail. Recibe la idea de negocio del usuario en lenguaje natural, evalúa si la información es suficiente, lanza un cuestionario si falta algo, valida las respuestas y extrae un perfil estructurado listo para la búsqueda geoespacial.

> ⚠️ Este repositorio contiene únicamente el backend LLM (Fases 1 y 2 del flujo completo de GeoRetail). Las fases de PostGIS, XGBoost y frontend están pendientes de integrar.

---

## Qué hace este módulo

- Recibe texto libre del usuario ("quiero abrir una barbería para hombres jóvenes...")
- Evalúa si la información es suficiente para hacer una búsqueda
- Si falta información → genera un cuestionario con preguntas relevantes
- Valida las respuestas del cuestionario (detecta negocios online, respuestas vagas e incoherencias)
- Si las respuestas no son válidas → reintenta el cuestionario hasta 2 veces con un mensaje explicativo
- Si son válidas → extrae un perfil estructurado del negocio en JSON
- Guarda el perfil en Redis como contexto de sesión
- Permite refinamiento conversacional sin perder el contexto
- Diseñado para cambiar de proveedor LLM (OpenAI / Anthropic / Ollama) tocando una línea en `.env`

---

## Estructura del proyecto

```
georetail/
├── docker-compose.yml
└── backend/
    ├── .env                          # Variables de entorno (no subir a git)
    ├── requirements.txt
    ├── main.py                       # Entrada FastAPI
    ├── api/
    │   └── buscar.py                 # Endpoints /buscar, /responder y /refinar
    └── agente/
        ├── llm_provider.py           # Wrapper multi-proveedor LLM
        ├── agente.py                 # Lógica principal del agente
        └── prompts/
            ├── sistema.txt               # Prompt de sistema
            ├── extraccion_perfil.txt     # Few-shots para extraer perfil
            ├── evaluacion_input.txt      # Evalúa si el input es suficiente
            ├── generar_preguntas.txt     # Genera el cuestionario
            └── validar_respuestas.txt    # Valida las respuestas del cuestionario
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
git clone https://github.com/tu-usuario/georetail-llm.git
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

## Flujo completo

```
POST /buscar  →  input del usuario
                       │
              [evaluar_input]
                       │
            ┌──────────┴──────────┐
       suficiente             insuficiente
            │                     │
    [extraer_perfil]        [generar_preguntas]
            │                     │
       tipo: "perfil"        tipo: "cuestionario"
            ✅                     │
                         POST /responder
                                   │
                          [validar_respuestas]
                                   │
                  ┌────────────────┼────────────────┐
               online           vago /          válido
                  │           incoherente           │
          error_definitivo         │         [extraer_perfil]
                  ❌         ¿reintentos < 2?       │
                              │          │      tipo: "perfil"
                             SÍ          NO         ✅
                              │          │
                        [cuestionario  error_definitivo
                         de nuevo con   tras 2 intentos]
                         mensaje claro]      ❌
```

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Comprueba que la API está viva |
| POST | `/buscar` | Evalúa el input y devuelve perfil o cuestionario |
| POST | `/responder` | Valida las respuestas del cuestionario y devuelve perfil |
| POST | `/refinar` | Refinamiento conversacional manteniendo el contexto de sesión |

---

## Tipos de respuesta

Todos los endpoints devuelven un campo `tipo` que el frontend usa para saber qué renderizar:

| `tipo` | Cuándo ocurre | Qué mostrar |
|--------|--------------|-------------|
| `perfil` | Input completo y válido | Mapa con resultados ✅ |
| `cuestionario` | Falta información o respuesta inválida | Formulario con preguntas ⚠️ |
| `error_definitivo` | Negocio online o 2 reintentos fallidos | Mensaje de error y limpiar ❌ |

---

## Probar los endpoints

### Opción A — Swagger (sin instalar nada)

```
http://localhost:8000/docs
```

### Opción B — Thunder Client (extensión VS Code)

---

#### Caso 1 — Input completo, va directo al perfil

```
POST http://localhost:8000/buscar
Content-Type: application/json

{
  "input_usuario": "quiero abrir una barbería para hombres jóvenes, precio asequible, zona céntrica"
}
```

Respuesta:

```json
{
  "ok": true,
  "tipo": "perfil",
  "session_id": "abc-123",
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

---

#### Caso 2 — Input pobre, genera cuestionario

```
POST http://localhost:8000/buscar
Content-Type: application/json

{
  "input_usuario": "quiero abrir un negocio"
}
```

Respuesta:

```json
{
  "ok": true,
  "tipo": "cuestionario",
  "session_id": "abc-123",
  "mensaje": "Necesito un poco más de información para encontrar la mejor ubicación.",
  "preguntas": [
    {
      "id": "sector",
      "pregunta": "¿Qué tipo de negocio quieres abrir?",
      "tipo": "single_select",
      "opciones": ["Cafetería", "Barbería / Peluquería", "Restaurante", "Tienda de ropa", "Gimnasio / Estudio", "Otro"]
    },
    {
      "id": "cliente_objetivo",
      "pregunta": "¿A quién va dirigido tu negocio?",
      "tipo": "single_select",
      "opciones": ["Jóvenes (18-30)", "Adultos (30-50)", "Familias", "Profesionales", "Turistas", "Mixto"]
    },
    {
      "id": "precio",
      "pregunta": "¿Qué nivel de precios tendrá tu negocio?",
      "tipo": "single_select",
      "opciones": ["Precio bajo (económico)", "Precio medio", "Precio alto (premium)"]
    }
  ]
}
```

---

#### Caso 2a — Respuestas válidas del cuestionario

```
POST http://localhost:8000/responder
Content-Type: application/json

{
  "session_id": "abc-123",
  "respuestas": {
    "sector": "Cafetería",
    "cliente_objetivo": "Adultos (30-50)",
    "precio": "Precio medio"
  }
}
```

Respuesta:

```json
{
  "ok": true,
  "tipo": "perfil",
  "session_id": "abc-123",
  "perfil": { ... },
  "descripcion": "..."
}
```

---

#### Caso 2b — Respuesta vaga, vuelve a preguntar

```
POST http://localhost:8000/responder
Content-Type: application/json

{
  "session_id": "abc-123",
  "respuestas": {
    "sector": "Otro",
    "precio": "no sé"
  }
}
```

Respuesta:

```json
{
  "ok": true,
  "tipo": "cuestionario",
  "session_id": "abc-123",
  "mensaje": "Tu respuesta es un poco general. ¿Puedes concretar un poco más?",
  "preguntas": [ ... ],
  "reintento": 1,
  "max_reintentos": 2
}
```

---

#### Caso 2c — Negocio online, error definitivo

```
POST http://localhost:8000/responder
Content-Type: application/json

{
  "session_id": "abc-123",
  "respuestas": {
    "sector": "Vender cosas por internet",
    "precio": "Precio bajo"
  }
}
```

Respuesta:

```json
{
  "ok": false,
  "tipo": "error_definitivo",
  "error": "GeoRetail está pensado para negocios con local físico en Barcelona. ¿Tienes algún negocio presencial en mente?"
}
```

---

#### Caso 3 — Refinamiento conversacional

```
POST http://localhost:8000/refinar
Content-Type: application/json

{
  "session_id": "abc-123",
  "mensaje": "¿hay zonas con alquiler más barato que mantengan buen flujo peatonal?"
}
```

Respuesta:

```json
{
  "ok": true,
  "session_id": "abc-123",
  "respuesta": "Sí, barrios como Sant Antoni o el Poble Sec ofrecen..."
}
```

---

## Cambiar de proveedor LLM

Solo edita `backend/.env`, el código no cambia nada:

```env
# Usar Claude en vez de GPT
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...

# Usar modelo local gratuito con Ollama
LLM_PROVIDER=ollama
LLM_MODEL=llama3
```

---

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Connection refused :6379` | Docker no está corriendo | `docker compose up -d` |
| `OPENAI_API_KEY not set` | Falta el `.env` | Crea `backend/.env` con tu key |
| `Module not found` | Venv no activado | `venv\Scripts\activate` (Windows) |
| Puerto 8000 ocupado | Otro proceso usa el puerto | `uvicorn main:app --reload --port 8001` |
| `JSONDecodeError` | El LLM devolvió texto extra | Revisa los prompts en `/agente/prompts/` |

---

## Estado del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| Fase 1 | Entrada del usuario | ✅ Hecho |
| Fase 2 | Evaluación del input, cuestionario y extracción de perfil con LLM | ✅ Hecho |
| Fase 3 | Consulta geoespacial PostGIS | 🔲 Pendiente |
| Fase 4 | Scoring XGBoost | 🔲 Pendiente |
| Fase 5 | NLP de reseñas | 🔲 Pendiente |
| Fase 6 | Análisis Street View | 🔲 Pendiente |
| Fase 7-10 | Ranking, análisis financiero, exportación | 🔲 Pendiente |

---

## Contexto del proyecto completo

Este módulo forma parte de **GeoRetail**, una aplicación web de análisis geoespacial que recomienda ubicaciones comerciales en Barcelona a emprendedores. El stack completo incluye Next.js en el frontend, FastAPI + Celery en el backend, PostgreSQL + PostGIS como base de datos y XGBoost para el scoring de ubicaciones.
