# Deploy

Esta guia describe un deploy Docker Compose de Silver Usage Report con FastAPI y PostgreSQL. Ajustar nombres de host, proxy TLS y gestion de secretos segun el proveedor.

## Supuestos

- Se usa la imagen construida desde el `Dockerfile` del repo.
- La app corre en el servicio `web` y escucha dentro del contenedor en `8000`.
- PostgreSQL corre como servicio `db` o como base externa compatible con `postgresql+psycopg`.
- El trafico publico llega a `APP_BASE_URL` por HTTPS.
- El panel admin se protege con `ADMIN_TOKEN`.

## Checklist Rapido

1. Preparar `.env` real.
2. Setear `ENVIRONMENT=production`.
3. Generar `SECRET_KEY` fuerte.
4. Generar `ADMIN_TOKEN` fuerte.
5. Setear `APP_BASE_URL` publico.
6. Setear `DATABASE_URL` PostgreSQL persistente.
7. Ejecutar `docker compose build`.
8. Ejecutar `docker compose up -d`.
9. Ejecutar `docker compose run --rm web alembic upgrade head`.
10. Verificar `/health`.
11. Hacer smoke test de `collector.ps1` con token.
12. Entrar a `/admin/login` y revisar `/admin/reports`.

## 1. Preparar Variables

Crear un `.env` real o configurar variables desde el orquestador:

```text
ENVIRONMENT=production
SECRET_KEY=<secreto fuerte y unico>
ADMIN_TOKEN=<token admin fuerte>
APP_BASE_URL=https://reports.tu-dominio.example
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

No usar `dev-secret-change-me` ni credenciales de ejemplo en produccion.

## 2. Construir Y Levantar

```bash
docker compose build
docker compose up -d
```

El `docker-compose.yml` del repo publica `web` en `localhost:8002` para desarrollo. En produccion, normalmente un reverse proxy o plataforma publica el puerto del contenedor `web:8000` con TLS.

PostgreSQL en Compose queda solo en la red interna como `db:5432`. Si se usa una base administrada externa, reemplazar `DATABASE_URL`.

## 3. Ejecutar Migraciones

```bash
docker compose run --rm web alembic upgrade head
```

La app tambien ejecuta `Base.metadata.create_all` en startup, pero Alembic es el mecanismo para aplicar cambios versionados de schema.

Despues de migrar, reiniciar `web` si el proceso ya estaba sirviendo trafico:

```bash
docker compose restart web
```

## 4. Verificar Salud

Local con el Compose del repo:

```bash
curl -fsS http://localhost:8002/health
```

Produccion:

```bash
curl -fsS https://reports.tu-dominio.example/health
```

Respuesta esperada:

```json
{"status":"ok","service":"silver-usage-report"}
```

Tambien revisar healthchecks:

```bash
docker compose ps
docker compose logs -f web
```

## 5. Smoke Test De Sesion Y Collector

Crear una sesion:

```bash
curl -fsS -X POST https://reports.tu-dominio.example/api/usage-report/sessions \
  -H "Content-Type: application/json" \
  -d '{"reporter_label":"smoke-test"}'
```

Guardar `id` y `private_token` de la respuesta.

Descargar/verificar el collector generado:

```bash
curl -fsS "https://reports.tu-dominio.example/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | head
```

En una maquina Windows de prueba con telemetria local soportada:

```powershell
irm "https://reports.tu-dominio.example/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | iex
```

Confirmar que:

- El script muestra preview local.
- El submit pide confirmacion.
- El collector firma el submit y el servidor lo acepta.
- La pagina privada abre con `?token=PRIVATE_TOKEN`.
- La pagina privada se redirige sola al detalle despues de recibir datos.
- `/api/usage-report/sessions/{session_id}/status?token=PRIVATE_TOKEN` devuelve estado y totales.

## 6. Verificar Admin

Abrir:

```text
https://reports.tu-dominio.example/admin/login
```

Ingresar `ADMIN_TOKEN`. Luego revisar:

```text
https://reports.tu-dominio.example/admin/reports
```

Para scripts internos:

```bash
curl -fsS https://reports.tu-dominio.example/admin/reports \
  -H "x-admin-token: ADMIN_TOKEN"
```

## 7. Comandos Operativos

Tests dentro del contenedor:

```bash
docker compose run --rm web pytest
```

Logs:

```bash
docker compose logs -f web
docker compose logs -f db
```

Aplicar migraciones:

```bash
docker compose run --rm web alembic upgrade head
```

Recrear app tras cambio de imagen:

```bash
docker compose build web
docker compose up -d web
```

## 8. Riesgos A Evitar

- `ADMIN_TOKEN` vacio con `ENVIRONMENT=production`.
- `APP_BASE_URL` apuntando a `localhost`, porque rompe links publicos y collector.
- `DATABASE_URL` SQLite en produccion.
- Exponer Postgres al host sin necesidad.
- Usar credenciales de `.env.example`.
- Ejecutar smoke tests sin token privado: las rutas de sesion existentes requieren `token=PRIVATE_TOKEN`.
- Probar `submit` con `curl` sin firma HMAC: los POST privados de datos deben
  responder 401 si faltan `X-Silver-Timestamp` y `X-Silver-Signature`.

## Rollback

Para rollback de app:

1. Volver a la imagen o commit anterior.
2. Levantar `web`.
3. Revisar logs y `/health`.

Las migraciones Alembic deben tratarse con cuidado: si una migracion modifica datos o elimina columnas, definir un plan de downgrade antes de aplicarla en produccion.
