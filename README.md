# Silver Usage Report

Silver Usage Report es un flujo open source para que una persona reporte a Silver
su uso agregado de herramientas de IA sin exponer prompts, respuestas, código
fuente, logs crudos ni API keys.

El producto actual es web-first y collector-first:

1. La persona abre la web de Silver Usage Report.
2. Crea una sesión privada de reporte.
3. Copia un comando PowerShell generado para esa sesión.
4. El collector lee telemetría local soportada, muestra una previsualización en
   la terminal y pide confirmación.
5. Solo después de confirmar, envía filas agregadas a Silver.
6. La web detecta el envío, redirige al detalle del reporte y permite borrar
   los datos agregados.

No es un dashboard personal de gasto, un tracker permanente ni una integración
company-wide. La primera necesidad es que Silver pueda recibir reportes
comparables de candidatos o comunidad con la menor fricción posible.

## Estado Actual

Disponible hoy:

- FastAPI para API y páginas web.
- Jinja2 + HTMX para UI server-rendered.
- UI visible en español.
- Sesiones privadas con `PRIVATE_TOKEN`.
- Collector PowerShell one-shot para Codex local.
- Preview local antes de subir datos.
- Envío de métricas agregadas por día/modelo.
- Firma HMAC de los POST privados del collector/CLI.
- Diagnóstico técnico sanitizado si el collector falla.
- Panel admin con búsqueda, paginación, edición y borrado.
- CLI Python para desarrollo y pruebas.
- Docker Compose con web + PostgreSQL.

El scope actual conserva un solo camino de reporte: collector Codex local.

## Stack

- Python 3.13.
- FastAPI.
- Jinja2.
- HTMX.
- Pydantic.
- SQLAlchemy.
- Alembic.
- PostgreSQL en Docker.
- SQLite como default local liviano si no se configura `DATABASE_URL`.
- `argparse` para el CLI de desarrollo.
- pytest.

## Estructura

```text
.
├── app
│   ├── api
│   ├── adapters
│   ├── core
│   ├── db
│   ├── schemas
│   ├── services
│   └── web
├── cli
├── docs
├── tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Desarrollo Local

Instalar dependencias:

```bash
python -m pip install -e ".[dev]"
```

Correr tests:

```bash
python -m pytest
```

Correr la app sin Docker:

```bash
uvicorn app.main:app --reload
```

Por default, sin `.env`, la app usa SQLite en `./silver_usage_report.db`.

## Desarrollo Con Docker

```bash
docker compose up --build
```

La web queda en:

```text
http://localhost:8002
```

El contenedor web escucha en `8000`; Compose publica `8002:8000`. PostgreSQL
queda dentro de la red de Compose como `db:5432` y no se publica al host.

Comandos útiles:

```bash
docker compose run --rm web pytest
docker compose run --rm web alembic upgrade head
docker compose logs -f web
```

## Configuración

Variables principales:

```text
DATABASE_URL=postgresql+psycopg://silver:silver@db:5432/silver_usage_report
SECRET_KEY=dev-secret-change-me
ADMIN_TOKEN=
APP_BASE_URL=http://localhost:8002
ENVIRONMENT=development
```

En producción:

- `ENVIRONMENT=production`.
- `SECRET_KEY` debe ser fuerte y único.
- `ADMIN_TOKEN` debe estar configurado.
- `APP_BASE_URL` debe ser la URL pública real.
- `DATABASE_URL` debe apuntar a PostgreSQL persistente.

Ver [Configuración](docs/configuration.md) y [Deploy](docs/deployment.md).

## Flujo Candidato

La página de sesión muestra un comando con el token privado embebido:

```powershell
irm "https://open.silver.dev/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | iex
```

El script:

- lee `$env:USERPROFILE\.codex\sessions`;
- busca `rollout-*.jsonl`;
- toma los últimos 90 días;
- agrega uso por día/modelo;
- muestra requests, tokens y top models;
- pide confirmación;
- firma y envía el reporte confirmado;
- intenta enviar un diagnóstico mínimo si falla.

No descarga un `.exe`, no requiere Python y no instala nada permanente.

## Datos Que Se Envían

Solo métricas agregadas:

- provider;
- tool;
- source;
- modelo cuando exista;
- período;
- request count;
- input/output/cached/reasoning/total tokens;
- estimated cost and cost source;
- confidence;
- evidence metadata agregada.

Terminología visible en la UI:

- `Tokens totales`: volumen agregado reportado para el período.
- `Input total`: input completo reportado por la telemetría.
- `Input nuevo`: porción de input no servida desde caché.
- `Input cacheado`: porción de input servida desde caché.
- `Output`: tokens de salida.
- `Razonamiento`: tokens de razonamiento cuando la telemetría los informa.

Algunas tomas de telemetría pueden informar `cached_input_tokens` como subconjunto
de `input_tokens`, mientras otras pueden informarlo como bucket separado. Para
costos y porcentajes, la app infiere la semántica que mejor cierra contra
`total_tokens`.

OpenAI costs are estimated server-side from `app/data/openai_model_prices.json`,
which is prepared from the official OpenAI API pricing page and can be updated
when new models or prices are published.

No se envían:

- prompts;
- respuestas;
- conversaciones;
- código fuente;
- logs crudos;
- API keys;
- variables de entorno;
- rutas locales completas.

## API

Los endpoints de sesión requieren `token=PRIVATE_TOKEN` excepto la creación.
Los POST privados que aceptan datos (`preview`, `submit` y
`collector-diagnostics`) además requieren firma HMAC del body con ese token:
headers `X-Silver-Timestamp` y `X-Silver-Signature`. La ventana aceptada es de
5 minutos para reducir replay.

La creación de sesiones aplica un límite de 5 reportes por candidato cuando hay
identificadores comparables (`candidate_ref`, email, X o nombre).

```text
POST   /api/usage-report/sessions
GET    /api/usage-report/sessions/{session_id}?token=PRIVATE_TOKEN
GET    /api/usage-report/sessions/{session_id}/status?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/preview?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/submit?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/collector-diagnostics?token=PRIVATE_TOKEN
DELETE /api/usage-report/sessions/{session_id}?token=PRIVATE_TOKEN
```

Rutas web principales:

```text
GET  /
POST /reports/sessions
POST /reports/sessions/open
GET  /reports/sessions/{session_id}?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/collector.ps1?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/report?token=PRIVATE_TOKEN
GET  /reports/sessions/{session_id}/status?token=PRIVATE_TOKEN
GET  /admin
GET  /admin/reports
GET  /admin/reports/{session_id}
```

## CLI De Desarrollo

El CLI Python es para desarrollo y pruebas del collector Codex. No es el camino
recomendado para candidatos.

Preview Codex local:

```powershell
python -m cli.main preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions" --days 90
```

Submit Codex:

```powershell
python -m cli.main submit-codex --session SESSION_ID --token PRIVATE_TOKEN --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url http://localhost:8002
```

## Admin

En desarrollo, `/admin/reports` puede quedar abierto si `ADMIN_TOKEN` está vacío.

En producción, `ADMIN_TOKEN` es obligatorio. El admin puede autenticarse desde
`/admin` y usar cookie HTTP-only, o llamar rutas admin con:

```text
x-admin-token: ADMIN_TOKEN
```

El panel admin permite revisar reportes, filtrar/paginar, ver detalle, editar
identidad de candidato/campaña y borrar datos de un reporte.

Las métricas de uso viven en el detalle de cada reporte/candidato. La lista
admin queda para búsqueda, paginación, estado y acciones operativas.

El detalle muestra métricas agregadas, desglose por tipo de token y serie diaria.
La métrica principal de intensidad es `Tokens por día activo`, calculada como
tokens totales divididos por días con uso. No debe interpretarse como tamaño de
una request individual. Las fechas con hora se muestran en horario de Argentina.

## Documentación

- [Flujo de reporte](docs/report-flow.md).
- [Collector PowerShell](docs/collector.md).
- [Arquitectura](docs/architecture.md).
- [Arquitectura técnica](docs/technical-architecture.md).
- [Configuración](docs/configuration.md).
- [Deploy](docs/deployment.md).
- [Seguridad y privacidad](docs/security-privacy.md).
- [Trust model](docs/trust-model.md).
- [Roadmap](docs/roadmap.md).

## CI

GitHub Actions corre:

- `python -m pytest`.
- `docker compose build`.

## Links

- Open Silver: https://open.silver.dev
- Open Silver repository: https://github.com/silver-dev-org/open-silver
