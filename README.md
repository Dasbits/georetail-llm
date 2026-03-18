# GeoRetail — LLM Backend

Módulo de IA del proyecto GeoRetail. Recibe la idea de negocio del usuario en lenguaje natural, evalúa si la información es suficiente, lanza un cuestionario si falta algo, valida las respuestas y extrae un perfil estructurado listo para la búsqueda geoespacial. Incluye autenticación con JWT.

> ⚠️ Este repositorio contiene únicamente el backend LLM (Fases 1 y 2 del flujo completo de GeoRetail). Las fases de PostGIS, XGBoost y frontend están pendientes de integrar.

---

## Qué hace este módulo

- Registro y login de usuarios con JWT
- Protección de todos los endpoints con token Bearer
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
├── database/
│   └── init.sql                      # Esquema inicial de la BD
└── backend/
    ├── Dockerfile
    ├── .env                          # Variables de entorno (no subir a git)
    ├── requirements.txt
    ├── main.py                       # Entrada FastAPI
    ├── api/
    │   ├── auth.py                   # Endpoints /auth/register, /auth/login, /auth/me
    │   └── buscar.py                 # Endpoints /buscar, /responder, /refinar (protegidos)
    ├── auth/
    │   ├── jwt.py                    # Generación y verificación de tokens JWT
    │   └── dependencias.py           # Dependencia get_usuario_actual
    ├── db/
    │   ├── conexion.py               # Pool de conexiones SQLAlchemy
    │   └── modelos.py                # Modelos ORM
    └── agente/
        ├── llm_provider.py           # Wrapper multi-proveedor LLM
        ├── agente.py                 # Lógica principal del agente
        └── prompts/
            ├── sistema.txt
            ├── extraccion_perfil.txt
            ├── evaluacion_input.txt
            ├── generar_preguntas.txt
            └── validar_respuestas.txt
```

---

## Requisitos previos

- Docker Desktop (es todo lo que necesitas para levantar el proyecto)
- Una API key de OpenAI (o Anthropic si prefieres Claude)

---

## Instalación y arranque

### 1. Clona el repositorio

```bash
git clone https://github.com/tu-usuario/georetail-llm.git
cd georetail-llm
```

### 2. Configura las variables de entorno

Crea el fichero `backend/.env`:

```env
# Proveedor LLM: openai | anthropic | ollama
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# JWT — genera un secret seguro con: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=cambia_esto_por_una_clave_larga_y_aleatoria
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

> Las variables `REDIS_URL` y `DATABASE_URL` las inyecta el `docker-compose.yml` automáticamente. No hace falta ponerlas en el `.env`.

### 3. Levanta todo con Docker

```bash
docker compose up -d
```

La primera vez construye la imagen del backend, las siguientes es instantáneo.

Comprueba que todo está corriendo:

```bash
docker compose ps
```

Logs del backend en tiempo real:

```bash
docker compose logs -f backend
```

### 4. Comandos útiles

```bash
# Parar todo
docker compose down

# Parar y borrar la base de datos (fuerza re-ejecución del init.sql)
docker compose down -v

# Reconstruir tras cambiar requirements.txt o Dockerfile
docker compose up -d --build
```

---

## Flujo completo de la aplicación

```
Register / Login  →  JWT token
                          │
              Authorization: Bearer <token>
                          │
POST /buscar  →  input del usuario
                          │
                 [evaluar_input]
                          │
            ┌─────────────┴─────────────┐
       suficiente                  insuficiente
            │                           │
    [extraer_perfil]          [generar_preguntas]
            │                           │
       tipo: "perfil"           tipo: "cuestionario"
            ✅                           │
                              POST /responder
                                         │
                               [validar_respuestas]
                                         │
                      ┌──────────────────┼──────────────────┐
                   online             vago /             válido
                      │            incoherente               │
              error_definitivo           │           [extraer_perfil]
                      ❌          ¿reintentos < 2?            │
                                  │            │         tipo: "perfil"
                                 SÍ            NO              ✅
                                  │            │
                           [cuestionario   error_definitivo
                            de nuevo con    tras 2 intentos]
                            mensaje claro]       ❌
```

---

## Endpoints disponibles

### Autenticación (sin token)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Crea una cuenta nueva y devuelve token |
| POST | `/auth/login` | Login con email y contraseña, devuelve token |
| GET | `/auth/me` | Devuelve los datos del usuario autenticado |

### Búsqueda (requieren token Bearer)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/buscar` | Evalúa el input y devuelve perfil o cuestionario |
| POST | `/responder` | Valida las respuestas del cuestionario |
| POST | `/refinar` | Refinamiento conversacional con contexto de sesión |

### Utilidades

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Comprueba que la API está viva |
| GET | `/docs` | Swagger con todos los endpoints |

---

## Tipos de respuesta

El campo `tipo` indica al frontend qué renderizar:

| `tipo` | Cuándo ocurre | Qué mostrar |
|--------|--------------|-------------|
| `perfil` | Input completo y válido | Mapa con resultados ✅ |
| `cuestionario` | Falta información o respuesta inválida | Formulario con preguntas ⚠️ |
| `error_definitivo` | Negocio online o 2 reintentos fallidos | Mensaje de error y limpiar ❌ |

---

## Probar con Thunder Client

### Paso 0 — Comprobar que la API está viva

```
GET http://localhost:8000/health
```

Respuesta esperada: `{"status": "ok"}`

---

### Paso 1 — Register

```
POST http://localhost:8000/auth/register
Content-Type: application/json

{
  "email": "test@georetail.com",
  "password": "mipassword123",
  "nombre": "Test"
}
```

Respuesta:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "usuario": {
    "id": "uuid...",
    "email": "test@georetail.com",
    "nombre": "Test"
  }
}
```

👉 Guarda el `access_token`. Lo necesitas en todos los siguientes pasos.

---

### Paso 2 — Login (para las siguientes veces)

```
POST http://localhost:8000/auth/login
Content-Type: application/json

{
  "email": "test@georetail.com",
  "password": "mipassword123"
}
```

---

### Cómo añadir el token en Thunder Client

En cada petición protegida ve a la pestaña **Auth → Bearer Token** y pega el token. O en **Headers**:

```
Authorization: Bearer <tu_token>
```

Sin token → `401 Unauthorized`. Con token → respuesta normal.

---

### Escenario A — Input completo, va directo al perfil

```
POST http://localhost:8000/buscar
Authorization: Bearer <token>
Content-Type: application/json

{
  "input_usuario": "quiero abrir una barbería para hombres jóvenes, precio asequible, zona céntrica"
}
```

Respuesta esperada: `tipo: "perfil"` directo. ✅

---

### Escenario B — Input pobre, cuestionario y respuestas válidas

**Paso 1:**
```
POST http://localhost:8000/buscar
Authorization: Bearer <token>

{
  "input_usuario": "quiero abrir un negocio"
}
```

Respuesta esperada: `tipo: "cuestionario"` con preguntas.

👉 Copia el `session_id` de la respuesta.

**Paso 2:**
```
POST http://localhost:8000/responder
Authorization: Bearer <token>

{
  "session_id": "PEGA_AQUI_EL_SESSION_ID",
  "respuestas": {
    "sector": "Cafetería",
    "cliente_objetivo": "Adultos (30-50)",
    "precio": "Precio medio"
  }
}
```

Respuesta esperada: `tipo: "perfil"`. ✅

---

### Escenario C — Respuesta vaga, reintento y corrección

**Paso 1:**
```
POST http://localhost:8000/buscar
Authorization: Bearer <token>

{
  "input_usuario": "quiero montar algo"
}
```

👉 Copia el `session_id`.

**Paso 2 — respuesta vaga a propósito:**
```
POST http://localhost:8000/responder
Authorization: Bearer <token>

{
  "session_id": "PEGA_AQUI_EL_SESSION_ID",
  "respuestas": {
    "sector": "Otro",
    "cliente_objetivo": "no sé",
    "precio": "Precio medio"
  }
}
```

Respuesta esperada: `tipo: "cuestionario"` con `"reintento": 1` y mensaje explicativo. ⚠️

**Paso 3 — respuesta correcta:**
```
POST http://localhost:8000/responder
Authorization: Bearer <token>

{
  "session_id": "PEGA_AQUI_EL_SESSION_ID",
  "respuestas": {
    "sector": "Restaurante",
    "cliente_objetivo": "Familias",
    "precio": "Precio medio"
  }
}
```

Respuesta esperada: `tipo: "perfil"`. ✅

---

### Escenario D — Negocio online, error definitivo

**Paso 1:**
```
POST http://localhost:8000/buscar
Authorization: Bearer <token>

{
  "input_usuario": "quiero montar algo"
}
```

**Paso 2:**
```
POST http://localhost:8000/responder
Authorization: Bearer <token>

{
  "session_id": "PEGA_AQUI_EL_SESSION_ID",
  "respuestas": {
    "sector": "Vender cosas por internet",
    "precio": "Precio bajo"
  }
}
```

Respuesta esperada: `ok: false`, `tipo: "error_definitivo"`. ❌

---

### Escenario E — Refinamiento conversacional

Usa el `session_id` de cualquier escenario anterior que haya devuelto `tipo: "perfil"` (TTL de Redis: 1 hora).

```
POST http://localhost:8000/refinar
Authorization: Bearer <token>

{
  "session_id": "PEGA_AQUI_EL_SESSION_ID",
  "mensaje": "¿hay zonas con alquiler más barato que mantengan buen flujo peatonal?"
}
```

Respuesta esperada: texto en español con contexto del negocio. ✅

---

### Resumen de qué comprobar en cada escenario

| Escenario | Campo a mirar | Valor esperado |
|-----------|--------------|----------------|
| A | `tipo` | `perfil` |
| B paso 1 | `tipo` | `cuestionario` |
| B paso 2 | `tipo` | `perfil` |
| C paso 2 | `tipo` + `reintento` | `cuestionario` + `1` |
| C paso 3 | `tipo` | `perfil` |
| D paso 2 | `ok` + `tipo` | `false` + `error_definitivo` |
| E | `respuesta` | Texto en español con contexto |

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
| `401 Unauthorized` | Token ausente o expirado | Haz login de nuevo y usa el nuevo token |
| `400 Already exists` | Email ya registrado | Usa otro email o ve directo a `/auth/login` |
| `Connection refused :6379` | Docker no está corriendo | `docker compose up -d` |
| `OPENAI_API_KEY not set` | Falta el `.env` | Crea `backend/.env` con tu key |
| `JSONDecodeError` | El LLM devolvió texto extra | Revisa los prompts en `/agente/prompts/` |
| Puerto 8000 ocupado | Otro proceso usa el puerto | Cambia el puerto en `docker-compose.yml` |

---

## Estado del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| Auth | Registro, login y protección JWT | ✅ Hecho |
| Fase 1 | Entrada del usuario | ✅ Hecho |
| Fase 2 | Evaluación, cuestionario y extracción de perfil | ✅ Hecho |
| Fase 3 | Consulta geoespacial PostGIS | 🔲 Pendiente |
| Fase 4 | Scoring XGBoost | 🔲 Pendiente |
| Fase 5 | NLP de reseñas | 🔲 Pendiente |
| Fase 6 | Análisis Street View | 🔲 Pendiente |
| Fase 7-10 | Ranking, análisis financiero, exportación | 🔲 Pendiente |

---

## Contexto del proyecto completo

Este módulo forma parte de **GeoRetail**, una aplicación web de análisis geoespacial que recomienda ubicaciones comerciales en Barcelona a emprendedores. El stack completo incluye Next.js en el frontend, FastAPI + Celery en el backend, PostgreSQL + PostGIS como base de datos y XGBoost para el scoring de ubicaciones.