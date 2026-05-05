# Roadmap

Este roadmap refleja el estado actual del producto al 5 de mayo de 2026. El
proyecto ya no es un tracker genérico de tokens: es un flujo de reporte para que
Silver reciba señales comparables de uso de IA de candidatos y comunidad, sin
pedir prompts, respuestas, código fuente, logs crudos ni API keys.

## Principios De Producto

- La web es Spanish-first: toda UI visible para reporteros y admin debe estar en
  español.
- El diseño web debe sentirse nativo de Open Silver y tomar como referencia
  `https://open.silver.dev/`.
- El primer caso de uso es individual/self-report, no importación company-wide
  con claves admin.
- Cada envío debe mostrar preview antes de subir datos.
- Los reportes deben ser agregados, borrables y vinculables a candidatos o
  campañas de Silver.
- El collector debe funcionar como one-shot: corre, muestra preview, confirma y
  termina.

## Fase 0: Descubrimiento Y Contrato

Estado: completo.

Resultado: el problema quedó definido como "usage reporting" para Silver, no como
dashboard personal ni observabilidad permanente.

- Proyecto renombrado a Silver Usage Report.
- Contexto del thread de X y del problema de performance/review documentado.
- Privacidad, trust model y límites de datos sensibles documentados.
- Esquema normalizado de reporte definido con Pydantic.
- APIs provider/org/admin explícitamente fuera del MVP individual.

## Fase 1: Sesiones De Reporte Web

Estado: completo.

Resultado: un usuario puede crear una sesión, cargar datos, previsualizar,
confirmar, verificar estado con link privado y borrar datos agregados.

- Dockerfile y Docker Compose.
- FastAPI + Jinja2 + HTMX.
- PostgreSQL en Docker, SQLite local para desarrollo/tests.
- Modelos SQLAlchemy y migración inicial.
- Creación de sesiones de reporte.
- Preview y submit por API.
- Link privado de gestión para el reportero.
- Estado de sesión, totales, filas y warnings visibles para el usuario.
- Delete flow para datos agregados.
- UI web en español.
- Visual integrado con Open Silver.

## Fase 2: Importación Local Como Camino Único

Estado: activo.

Resultado: la web de candidato queda enfocada en el collector/agente local. Los
fallbacks manual, CSV y JSON no se muestran ni se usan por ahora.

- Página de sesión con comando de collector.
- Panel de preview que se actualiza cuando el collector envía datos.
- Confirmación web después de recibir filas agregadas.
- Validación de fechas, tokens, confianza y campos sensibles.
- Cálculo derivado de `total_tokens`.
- Fixtures sintéticos y cobertura de importación.

## Fase 3: CLI Y Collector Standalone

Estado: completo, con polish continuo.

Resultado: un candidato puede correr un comando local o un binario standalone,
ver el resumen y enviar el reporte sin instalar Python.

- CLI `silver-usage-collector`.
- Comandos `preview`, `preview-csv`, `submit`.
- Comandos `preview-codex` y `submit-codex`.
- `--yes` para flujos no interactivos y confirmación interactiva por defecto.
- Identificación HTTP con `User-Agent` propio.
- Manejo explícito de errores HTTP, red caída y respuestas no JSON.
- Build con PyInstaller.
- Workflow de release multi-OS para binarios.
- Documentación de uso en `docs/collector.md`.

## Fase 4: Importación Asistida Por MCP/Agente

Estado: parcial.

Resultado actual: existen helpers y contrato de flujo para agentes locales, pero
falta empaquetarlo como MCP instalable/end-to-end.

Hecho:

- Helpers `preview_report`, `submit_report`, `preview_codex_local`,
  `submit_codex_local`.
- Prompt template para importación asistida.
- Preview-before-submit.
- Envío a API usando el mismo contrato normalizado.

Pendiente:

- Servidor MCP real con transporte/manifest instalable.
- Instrucciones finales para Codex, Claude Code y Cursor.
- Soporte primario del MCP para `~/.codex/sessions`, no solo SQLite legacy.
- Smoke test end-to-end desde un cliente MCP real.

## Fase 5: Fuentes Locales De Herramientas

Estado: Codex avanzado; resto pendiente.

Resultado actual: Codex tiene adapter útil sobre session rollouts; Cursor y
Claude Code quedan pendientes hasta tener integración local propia.

Hecho para Codex:

- Fuente primaria: `~/.codex/sessions`.
- Fallback legacy: `state_5.sqlite` y `logs_2.sqlite`.
- Agregado por día/modelo.
- Default últimos 30 días con `--days` y `--since`.
- Breakdown de requests, input, cached input, output, reasoning, total y top
  models.
- Warnings para datos best-effort.

Pendiente:

- Detección/documentación de múltiples instalaciones Codex.
- Soporte para rutas múltiples de sesiones.
- Investigación e implementación de Claude Code.
- Investigación e implementación de Cursor.
- Mensajes UX más claros cuando una fuente local no existe o no tiene datos.

## Fase 6: Admin Y Vinculación Silver

Estado: primer corte completo; hardening pendiente.

Resultado actual: Silver puede revisar reportes y vincularlos con candidatos o
campañas.

Hecho:

- `/admin/reports`.
- Detalle admin por sesión.
- Campos `reporter_label`, `reporter_email`, `github_handle`, `x_handle`,
  `candidate_ref`, `campaign_ref`.
- Token admin configurable por `ADMIN_TOKEN`.
- Totales, estado, filas y warnings visibles en admin.

Pendiente:

- Filtros/búsqueda por campaña, candidato, email o handle.
- Export CSV desde admin.
- Mejor separación de permisos entre admin y reportero.
- Auditoría de delete/status para evitar endpoints demasiado permisivos en
  producción.

## Fase 7: Deploy, QA Y Confianza Operativa

Estado: en curso.

Resultado buscado: Gabriel puede revisar el producto con confianza de senior:
instalación reproducible, tests verdes, smoke real y documentación que no miente.

Pendiente inmediato:

- Smoke local con Docker.
- Smoke remoto en `silver-usage-dev.fulanito3d.com.ar`.
- Checklist de deploy.
- Documentar variables de entorno de producción.
- Validar links de descarga del collector en entorno deployado.
- Revisar copy de errores de usuario final.
- Revisar seguridad de endpoints de gestión.

## Fase 8: Sharing Y Campañas

Estado: futuro.

- Links por campaña.
- Modo benchmark anónimo.
- Cards/shareables con reportes sintéticos.
- Ejemplos públicos.
- Guía de contribución para nuevos adapters.
- Framing responsable: el uso de tokens es señal técnica contextual, no score
  directo de productividad.

## Ruta Recomendada

El orden actual sigue siendo:

1. Web report session.
2. Collector one-shot.
3. Codex local adapter.
4. MCP instalable.
5. Claude Code y Cursor.
6. Admin hardening y campañas.

La decisión de no arrancar por APIs provider/org/admin sigue vigente: son útiles
para compañías, pero no resuelven bien el caso de un candidato individual que no
tiene permisos de admin.
