# Slate POC

Sistema de asignación dinámica de ajustadores de seguros. Recibe siniestros (incidents), los asigna al ajustador óptimo usando OR-Tools, y notifica al ajustador en tiempo real vía Server-Sent Events.

## Arquitectura

```
slate-poc/
├── services/
│   ├── api/            # FastAPI — HTTP API principal (slate_api)
│   ├── core/           # Librería compartida — geoespacial + optimización (slate_core)
│   ├── notifications/  # Listener pg_notify + broadcaster SSE (slate_notifications)
│   └── jobs/           # Jobs en background — predicción de demanda (slate_jobs)
├── apps/
│   ├── admin/          # Vue 3 — CRUD de usuarios
│   ├── reporter/       # Vue 3 — levantamiento de siniestros
│   └── adjuster/       # Vue 3 — vista en tiempo real del ajustador con mapa
├── alembic/            # Migraciones de base de datos
└── docker-compose.yml  # Servicios locales (postgres, redis, tools)
```

### Flujo principal

```
Reporter (browser)
  └── POST /api/v1/incidents/          Crea siniestro con lat/lon

Map (browser)
  └── POST /api/v1/assignments/optimize  OR-Tools asigna ajustador óptimo
                                          └── PostgreSQL trigger
                                                └── pg_notify('assignment_events', payload)

Adjuster (browser)
  └── GET /api/v1/notifications/stream?adjuster_id=N   EventSource SSE
        └── asyncpg LISTEN → NotificationBroadcaster → asyncio.Queue → SSE
```

### Proveedores de rutas

La API soporta tres proveedores configurables con `TRAFFIC_PROVIDER`:

| Proveedor | Variable | Descripción |
|---|---|---|
| `osrm` | `OSRM_URL` | Open Source Routing Machine — rápido, datos OSM |
| `valhalla` | `VALHALLA_URL` | Con soporte de tráfico en tiempo real |
| `google` | `GOOGLE_ROUTES_API_KEY` | Google Routes API (requiere clave) |

---

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — gestor de paquetes Python
- Docker + Docker Compose
- Node 20+ y [pnpm](https://pnpm.io/) (solo para frontend)

---

## Levantar el proyecto

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/est-52/lennken-slate-poc
cd lennken-slate-poc
uv sync
```

### 2. Variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores locales. Las variables mínimas requeridas son:

```bash
DATABASE_URL=postgresql+asyncpg://slate:slate@localhost:5432/slate_dev
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=               # generar con: openssl rand -hex 32
```

### 3. Levantar servicios de infraestructura

```bash
# Solo PostgreSQL + Redis (mínimo para correr la API)
docker compose up -d

# Con PgAdmin (http://localhost:5050) y Jupyter (http://localhost:8888)
docker compose --profile tools up -d

# Con proveedor de rutas OSRM (requiere datos pre-procesados, ver sección OSRM)
docker compose --profile osrm up -d
```

Verificar que los contenedores están sanos:

```bash
docker compose ps
```

### 4. Aplicar migraciones

```bash
uv run alembic upgrade head
```

### 5. Iniciar la API

```bash
uv run uvicorn slate_api.main:app --reload --host 0.0.0.0 --port 8000
```

La API queda disponible en:

| URL | Descripción |
|---|---|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/map` | Mapa interactivo |

---

## Vistas HTML

La API sirve tres interfaces directamente (sin build de frontend):

| Ruta | Descripción |
|---|---|
| `/map` | Vista principal — colocar ajustadores, optimizar asignaciones, ver rutas |
| `/reporter` | Levantar siniestros — seleccionar usuario, click en mapa |
| `/adjuster` | Vista del ajustador — recibe asignaciones en tiempo real vía SSE |
| `/admin` | CRUD de usuarios |

---

## Endpoints principales

```
GET  /health

# Siniestros
POST   /api/v1/incidents/
GET    /api/v1/incidents/
GET    /api/v1/incidents/{id}
PATCH  /api/v1/incidents/{id}
DELETE /api/v1/incidents/{id}

# Ajustadores
POST   /api/v1/adjusters/
GET    /api/v1/adjusters/
GET    /api/v1/adjusters/{id}
PATCH  /api/v1/adjusters/{id}

# Asignaciones
POST   /api/v1/assignments/optimize    Ejecuta optimización OR-Tools
GET    /api/v1/assignments/
PATCH  /api/v1/assignments/{id}        Actualizar estado (accepted/en_route/arrived)
GET    /api/v1/assignments/route       Calcular ruta entre dos puntos

# Usuarios
POST   /api/v1/users/
GET    /api/v1/users/
GET    /api/v1/users/{id}
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}

# Notificaciones (SSE)
GET    /api/v1/notifications/stream?adjuster_id={id}
```

---

## Tests

```bash
# Crear .env.test con las variables del entorno de pruebas
cp .env.example .env.test
# Editar .env.test: cambiar DATABASE_URL a slate_test, agregar SECRET_KEY

# Correr tests (ENVIRONMENT=test se inyecta automáticamente via pyproject.toml)
uv run pytest

# Un servicio específico
uv run pytest services/api/

# Con cobertura
uv run pytest --cov=services --cov-report=term-missing
```

---

## Base de datos

### Crear una migración

```bash
uv run alembic revision --autogenerate -m "descripcion_del_cambio"
uv run alembic upgrade head
```

### Revertir la última migración

```bash
uv run alembic downgrade -1
```

### Ver historial

```bash
uv run alembic history
```

---

## OSRM (proveedor de rutas local)

OSRM requiere datos OSM pre-procesados. Solo es necesario la primera vez:

```bash
mkdir -p data/osrm

# Descargar mapa de México (~300MB)
wget -P data/osrm https://download.geofabrik.de/north-america/mexico-latest.osm.pbf

# Procesar datos (tarda ~10 min)
docker run -t -v $(pwd)/data/osrm:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/mexico-latest.osm.pbf
docker run -t -v $(pwd)/data/osrm:/data osrm/osrm-backend osrm-partition /data/mexico-latest.osrm
docker run -t -v $(pwd)/data/osrm:/data osrm/osrm-backend osrm-customize /data/mexico-latest.osrm

# Levantar OSRM
docker compose --profile osrm up -d
```

---

## Lint y formato

```bash
uv run ruff check services/
uv run ruff format services/
```

### Pre-commit (recomendado)

El repo incluye configuración de [pre-commit](https://pre-commit.com/) que corre ruff automáticamente antes de cada `git commit`. Instálalo una vez después de clonar:

```bash
uv run pre-commit install
```

A partir de ahí, cada `git commit` ejecuta lint y format automáticamente. Si algún archivo se modifica, el commit se cancela para que puedas revisar los cambios — simplemente vuelve a stagear y commitear:

```bash
git commit -m "mi cambio"
# pre-commit formatea archivos → commit cancelado

git add -A
git commit -m "mi cambio"   # pasa limpio
```

Para correr manualmente sobre todos los archivos:

```bash
uv run pre-commit run --all-files
```

---

## Infraestructura (GCP)

El proyecto corre en Google Cloud Platform:

| Recurso | Nombre | Descripción |
|---|---|---|
| Proyecto | `lennken-poc` | Proyecto GCP |
| Artifact Registry | `poc-images` | Imágenes Docker de los servicios |
| Cloud Storage | `lennken-poc-apps-dev` | Assets estáticos de los frontends |
| PostgreSQL | GCE VM | PostgreSQL 16 + PostGIS 3 en Debian 12 |
| API | Cloud Run | `slate-api` — `max-instances=10` |
| Notifications | Cloud Run | `slate-notifications` — **`max-instances=1`** (ver nota) |
| Jobs | Cloud Run Jobs | `slate-jobs` |

> **Nota `max-instances=1` en notifications:** el `NotificationBroadcaster` usa `asyncio.Queue` en memoria por ajustador. Con múltiples instancias, los eventos de `pg_notify` llegarían a una sola instancia y los otros browsers no recibirían nada. Para escalar: reemplazar con Redis Pub/Sub.

El deploy usa **Workload Identity Federation** — no hay JSON keys de service account en el repo. Los workflows de GitHub Actions intercambian el token OIDC de GitHub por credenciales GCP temporales.
