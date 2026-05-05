# Configuracion

Silver Usage Report lee configuracion desde variables de entorno y, en desarrollo, desde un archivo `.env` si existe. La definicion vive en `app/core/config.py`.

## Variables Soportadas

| Variable | Default en codigo | Uso |
| --- | --- | --- |
| `APP_NAME` | `Silver Usage Report` | Nombre de la aplicacion FastAPI/configurable. |
| `APP_BASE_URL` | `http://localhost:8000` | URL base publica usada para generar links y `collector.ps1`. |
| `DATABASE_URL` | `sqlite:///./silver_usage_report.db` | URL SQLAlchemy para SQLite o PostgreSQL. |
| `SECRET_KEY` | `dev-secret-change-me` | Secreto general de la app. Debe ser fuerte en produccion. |
| `ADMIN_TOKEN` | vacio | Token para proteger `/admin` en produccion. |
| `ENVIRONMENT` | `development` | Modo de ejecucion. `production` activa exigencias admin y cookies secure. |

Pydantic Settings mapea estas variables a campos snake_case (`APP_BASE_URL` -> `app_base_url`).

## `.env.example`

El archivo incluido esta pensado para Docker Compose local:

```text
DATABASE_URL=postgresql+psycopg://silver:silver@db:5432/silver_usage_report
SECRET_KEY=dev-secret-change-me
ADMIN_TOKEN=
APP_BASE_URL=http://localhost:8002
ENVIRONMENT=development
```

Compose usa `env_file: .env.example` por defecto. Para un entorno real, preparar un `.env` propio o inyectar variables desde el proveedor de deploy.

## Desarrollo Sin Docker

Si no hay `.env`, la app usa SQLite local:

```text
DATABASE_URL=sqlite:///./silver_usage_report.db
APP_BASE_URL=http://localhost:8000
```

Comando tipico:

```bash
uvicorn app.main:app --reload
```

Con SQLite, la base se crea automaticamente en startup por `init_database()`.

## Desarrollo Con Docker Compose

Compose publica la web en el host:

```text
http://localhost:8002
```

Dentro de la red de Compose:

```text
web -> db:5432
```

PostgreSQL no se expone al host. La URL correcta para `web` es:

```text
DATABASE_URL=postgresql+psycopg://silver:silver@db:5432/silver_usage_report
```

Comandos:

```bash
docker compose up --build
docker compose run --rm web alembic upgrade head
docker compose run --rm web pytest
```

## Produccion

Configurar valores reales:

```text
ENVIRONMENT=production
SECRET_KEY=<secreto fuerte y unico>
ADMIN_TOKEN=<token admin fuerte>
APP_BASE_URL=https://reports.tu-dominio.example
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

Requisitos:

- `ADMIN_TOKEN` no puede quedar vacio en produccion.
- `APP_BASE_URL` debe ser la URL publica que usaran candidatos y collector.
- `DATABASE_URL` debe apuntar a PostgreSQL persistente, no a SQLite local.
- `SECRET_KEY` no debe reutilizar el valor de desarrollo.

## Admin

En desarrollo, si `ADMIN_TOKEN` esta vacio, las rutas admin quedan abiertas para facilitar pruebas locales.

En produccion:

- `/admin/login` acepta un formulario con `ADMIN_TOKEN`.
- Al autenticarse, se emite cookie `silver_admin_token`.
- Scripts o clientes internos pueden usar `x-admin-token: ADMIN_TOKEN`.
- Si `ENVIRONMENT=production` y `ADMIN_TOKEN` falta, las rutas admin devuelven error de configuracion.

## URLs Y Tokens De Sesion

Las sesiones de reporte tienen un `PRIVATE_TOKEN`. Ese token no sale de la creacion de sesion y de los links privados generados.

Ejemplos:

```text
/reports/sessions/{session_id}?token=PRIVATE_TOKEN
/reports/sessions/{session_id}/collector.ps1?token=PRIVATE_TOKEN
/api/usage-report/sessions/{session_id}/status?token=PRIVATE_TOKEN
```

El collector necesita que `APP_BASE_URL` sea correcto, porque el script generado usa esa base para llamar a la API.

Los POST privados que contienen datos no aceptan solamente el token en la URL.
Tambien deben incluir `X-Silver-Timestamp` y `X-Silver-Signature`, calculados con
HMAC-SHA256 sobre el body crudo usando el `PRIVATE_TOKEN`. No hay una variable de
entorno global para esta firma: cada sesion usa su propio token privado.

Para controlar abuso, la app limita a 5 sesiones por candidato identificable
cuando recibe datos como `candidate_ref`, email, GitHub, X o nombre.

## Migraciones

La app ejecuta `Base.metadata.create_all` al iniciar para facilitar entornos nuevos, pero las migraciones versionadas se administran con Alembic:

```bash
docker compose run --rm web alembic upgrade head
```

Ejecutar migraciones como parte del deploy y antes de validar smoke tests.

## Checklist De Configuracion

- Crear `.env` real o configurar variables en el proveedor.
- Cambiar `ENVIRONMENT=production` para produccion.
- Generar `SECRET_KEY` fuerte.
- Generar `ADMIN_TOKEN` fuerte.
- Configurar `APP_BASE_URL` publico con HTTPS.
- Configurar `DATABASE_URL` PostgreSQL persistente.
- Ejecutar `alembic upgrade head`.
- Verificar `/health`.
