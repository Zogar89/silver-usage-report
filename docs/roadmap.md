# Roadmap

Actualizado: 2026-05-05.

## Estado Actual

El MVP vigente es el flujo Codex local:

- sesión web privada;
- collector PowerShell servido por sesión;
- lectura de `~/.codex/sessions/**/rollout-*.jsonl`;
- preview local;
- confirmación;
- submit agregado firmado;
- detalle candidato con métricas;
- admin review con búsqueda, paginación y acciones.

## Completado

- FastAPI + Jinja2 + HTMX.
- SQLAlchemy + Alembic.
- Docker Compose con PostgreSQL.
- Sesiones privadas con token.
- Panel candidato y panel admin.
- Collector PowerShell sin binario.
- Firma HMAC para POST privados de datos.
- Limite de 5 reportes por candidato identificable.
- Diagnósticos sanitizados del collector.
- CLI de desarrollo para Codex local.
- Adapter Codex local con rollouts y SQLite legacy.
- Tests de API, web, CLI y privacidad.
- Eliminacion de MCP server, prompt MCP y build PyInstaller.

## Próximo Trabajo

1. Smoke test Docker local.
2. Smoke test deployado.
3. Agregar nonce one-time por submit si se necesita una barrera anti-replay mas fuerte.
4. Mejorar mensajes de error del collector.
5. Mejorar soporte de múltiples rutas Codex.
6. Investigar Claude Code/Cursor bajo las mismas reglas de privacidad.

## No Reabrir Sin Nueva Decisión

Los caminos eliminados no son backlog activo. Si alguna vez vuelven, deben pasar
por un diseño nuevo, tests de privacidad y aprobación explícita.
