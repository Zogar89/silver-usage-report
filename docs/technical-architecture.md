# Arquitectura Tecnica

Silver Usage Report es una aplicacion FastAPI empaquetada como proyecto Python instalable. Sirve HTML con Jinja2/HTMX, expone una API HTTP para sesiones de reporte y persiste datos con SQLAlchemy sobre PostgreSQL o SQLite.

## Stack

- Python 3.13.
- FastAPI.
- Jinja2.
- HTMX.
- Pydantic y `pydantic-settings`.
- SQLAlchemy.
- Alembic.
- PostgreSQL en Docker Compose.
- SQLite como default local si no se configura `DATABASE_URL`.
- CLI con `argparse`.
- pytest para tests.

## Layout Del Repositorio

```text
.
├── app
│   ├── main.py
│   ├── api
│   │   └── usage_report.py
│   ├── adapters
│   │   └── codex_local.py
│   ├── core
│   │   └── config.py
│   ├── db
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations
│   ├── schemas
│   │   └── usage_report.py
│   ├── services
│   │   └── report_sessions.py
│   └── web
│       ├── routes.py
│       ├── static
│       └── templates
├── cli
│   └── main.py
├── tests
├── docs
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
└── pyproject.toml
```

## Aplicacion FastAPI

`app/main.py` crea la aplicacion, monta assets estaticos, registra routers y define `/health`.

En lifespan de startup se llama a:

```python
init_database()
```

`init_database()` ejecuta `Base.metadata.create_all(bind=engine)`. Esto permite levantar un entorno nuevo con una base vacia, pero Alembic sigue siendo la fuente de migraciones versionadas para deploys y upgrades controlados.

Routers:

- `app.api.usage_report.router`, con prefijo `/api/usage-report`.
- `app.web.routes.router`, con paginas web, collector y admin.

## Configuracion

`app/core/config.py` define `Settings` con `BaseSettings` y lee `.env` si existe.

Variables soportadas:

```text
APP_NAME
APP_BASE_URL
DATABASE_URL
SECRET_KEY
ADMIN_TOKEN
ENVIRONMENT
```

Defaults de codigo:

```text
APP_NAME=Silver Usage Report
APP_BASE_URL=http://localhost:8000
DATABASE_URL=sqlite:///./silver_usage_report.db
SECRET_KEY=dev-secret-change-me
ADMIN_TOKEN=
ENVIRONMENT=development
```

`.env.example` esta orientado a Docker Compose:

```text
DATABASE_URL=postgresql+psycopg://silver:silver@db:5432/silver_usage_report
SECRET_KEY=dev-secret-change-me
ADMIN_TOKEN=
APP_BASE_URL=http://localhost:8002
ENVIRONMENT=development
```

Ver [Configuracion](configuration.md).

## API HTTP

Las rutas API reales son:

```text
POST   /api/usage-report/sessions
GET    /api/usage-report/sessions/{session_id}?token=PRIVATE_TOKEN
GET    /api/usage-report/sessions/{session_id}/status?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/preview?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/submit?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/collector-diagnostics?token=PRIVATE_TOKEN
DELETE /api/usage-report/sessions/{session_id}?token=PRIVATE_TOKEN
```

Notas de contrato:

- `POST /sessions` crea una sesion y devuelve `private_token`.
- Todas las operaciones sobre una sesion existente requieren `token`.
- `preview` recibe filas normalizadas y warnings para clientes internos o CLI.
- `submit` requiere que `report_session_id` coincida con la sesion y que `user_confirmation.preview_shown` sea `true`.
- `collector-diagnostics` guarda diagnosticos tecnicos sanitizados.
- `preview`, `submit` y `collector-diagnostics` requieren firma HMAC-SHA256 del
  body con el `private_token`: `X-Silver-Timestamp` y `X-Silver-Signature`.
- La firma usa `timestamp + "." + body` y expira a los 5 minutos.
- La creacion de sesiones devuelve HTTP 429 si se supera el maximo de 5
  reportes para un mismo candidato identificable.
- No hay endpoints `/upload`, `/confirm` ni `/api/usage-report/admin/reports`.

## Web Y HTMX

Rutas web principales:

```text
GET  /
POST /reports/sessions
POST /reports/sessions/open
GET  /reports/sessions/{session_id}?token=PRIVATE_TOKEN
POST /reports/sessions/{session_id}/submit?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/report?token=PRIVATE_TOKEN
POST /reports/sessions/{session_id}/delete?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/status?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/preview-panel?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/report-redirect?token=PRIVATE_TOKEN
POST /reports/sessions/{session_id}/delete-managed
GET  /reports/sessions/{session_id}/collector.ps1?token=PRIVATE_TOKEN
```

HTMX se usa para actualizar paneles parciales y redirigir superficies de preview/reporte sin introducir un frontend build pipeline.

La pagina privada del candidato queda esperando recepcion de datos despues de
copiar el comando. Cuando el collector confirma y el submit llega al servidor,
`/report-redirect` devuelve `HX-Redirect` hacia el detalle del reporte.

La UI visible esta escrita en espanol. Identificadores de codigo, payloads y campos de integracion se mantienen en ingles.

## Admin

Rutas admin:

```text
GET  /admin
POST /admin/login
GET  /admin/reports
GET  /admin/reports/{session_id}
POST /admin/reports/{session_id}/delete
POST /admin/reports/{session_id}/identity
```

Reglas:

- En produccion, si `ENVIRONMENT=production` y falta `ADMIN_TOKEN`, las rutas admin responden error de configuracion.
- Con `ADMIN_TOKEN` configurado, el acceso acepta cookie `silver_admin_token` emitida por `/admin/login`.
- Tambien acepta header `x-admin-token: ADMIN_TOKEN` para usos internos o scripts.
- En desarrollo, si `ADMIN_TOKEN` esta vacio, las rutas admin quedan abiertas.
- `/admin/reports` soporta `q`, `page` y `per_page`; con `HX-Request` devuelve
  solo el partial de resultados para live search.
- Las metricas de uso por candidato viven en `/admin/reports/{session_id}`; la
  lista admin muestra estado, identidad, fechas y acciones.

## Modelos Y Persistencia

SQLAlchemy usa un engine global configurado desde `DATABASE_URL` y sesiones por request via dependency `get_db()`.

Tablas:

- `report_sessions`: sesion privada, token hasheado, identidad opcional y estado.
- `usage_report_rows`: filas agregadas por provider/tool/model/periodo.
- `report_warnings`: warnings asociados a sesion o fila.
- `collector_diagnostics`: fallas sanitizadas del collector.

Alembic esta configurado con:

```text
script_location = app/db/migrations
```

Migraciones existentes viven en `app/db/migrations/versions`.

## Esquemas Y Validacion

`app/schemas/usage_report.py` define enums y payloads compartidos por API, CLI, servicios y tests.

Validaciones importantes:

- `extra="forbid"` en modelos de entrada.
- Rechazo de campos sensibles anidados.
- Conteos de tokens y costos no negativos.
- `period_end` debe ser posterior a `period_start`.
- `total_tokens` se calcula desde partes conocidas cuando falta.
- Submit requiere confirmacion de preview.

Campos sensibles rechazados incluyen `prompt`, `response`, `conversation`, `api_key`, `secret`, `raw_log` y `source_code`.

## CLI

El CLI usa `argparse` y se registra como scripts de proyecto:

```text
silver-usage-report = cli.main:main
silver-usage-collector = cli.main:main
```

Comandos:

```powershell
python -m cli.main preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions" --days 90
python -m cli.main submit-codex --session SESSION_ID --token PRIVATE_TOKEN --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url http://localhost:8002 --days 90 --yes
```

El CLI no corre como daemon. Previsualiza localmente, pide confirmacion salvo `--yes`, y luego llama a `preview` y `submit` de la API.
Cuando la URL incluye `token`, firma los POST privados con los mismos headers
HMAC que exige la API.

## Collector PowerShell

La web sirve un collector generado por sesion:

```powershell
irm "https://reports.tu-dominio.example/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | iex
```

El script generado embebe:

- `SessionId`.
- `BaseUrl`, derivado de `APP_BASE_URL`.
- `PrivateToken`.

El collector envia:

- Submit firmado a `/api/usage-report/sessions/{session_id}/submit?token=...`.
- Diagnosticos firmados a `/api/usage-report/sessions/{session_id}/collector-diagnostics?token=...`.

El collector no publica preview remoto: la previsualizacion ocurre en la
terminal del usuario. Despues del submit, la pagina privada se actualiza sola y
lleva al detalle del reporte.

## Docker

`Dockerfile` usa:

```text
python:3.13-slim
pip install --no-cache-dir -e ".[dev]"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`docker-compose.yml` define:

```text
web  build local, uvicorn con --reload, env_file .env.example, puerto 8002:8000
db   postgres:16-alpine, red interna, volumen postgres-data
```

PostgreSQL no se publica al host. Desde `web`, la base esta disponible como `db:5432`.

Healthchecks:

- `web`: request HTTP a `http://127.0.0.1:8000/health`.
- `db`: `pg_isready -U silver -d silver_usage_report`.

Comandos frecuentes:

```bash
docker compose up --build
docker compose run --rm web pytest
docker compose run --rm web alembic upgrade head
docker compose logs -f web
```

## Deploy

En produccion configurar:

- `ENVIRONMENT=production`.
- `SECRET_KEY` fuerte y unico.
- `ADMIN_TOKEN` fuerte y no vacio.
- `APP_BASE_URL` con URL publica HTTPS.
- `DATABASE_URL` apuntando a PostgreSQL persistente.

Despues de construir y levantar servicios, ejecutar migraciones:

```bash
docker compose build
docker compose up -d
docker compose run --rm web alembic upgrade head
```

Verificar:

```bash
curl -fsS https://TU_DOMINIO/health
```

Ver [Deploy](deployment.md) para checklist completo.
