# Security And Privacy

## Promesa

Silver Usage Report sube métricas agregadas de Codex local, no contenido.

## Nunca Subir

- Prompts.
- Respuestas.
- Conversaciones.
- Código fuente.
- Logs crudos.
- API keys.
- Variables de entorno.
- Rutas locales completas.

## Datos Permitidos

- Provider.
- Tool.
- Source `codex_local_telemetry`.
- Periodo.
- Modelo cuando exista.
- Request count.
- Token counts.
- Cost source `unknown`.
- Confidence.
- Evidence metadata agregada.

## Collector

El collector PowerShell lee `~/.codex/sessions/**/rollout-*.jsonl`, muestra
preview local y solo envía datos si el usuario confirma. Los POST que contienen
datos se firman con HMAC-SHA256 usando el `PRIVATE_TOKEN` de la sesion.

Si falla, puede enviar un diagnóstico técnico mínimo:

- etapa;
- tipo de error;
- mensaje sanitizado;
- versión del collector;
- versión de PowerShell;
- estado de carpeta;
- cantidad de rollouts detectados.

El diagnóstico no debe incluir contenido sensible.

## Sesiones Privadas Y Firma

Cada sesion tiene un `private_token` que se guarda hasheado en base de datos. Las
rutas privadas requieren `token=PRIVATE_TOKEN`.

Los endpoints `preview`, `submit` y `collector-diagnostics` ademas requieren:

- `X-Silver-Timestamp`;
- `X-Silver-Signature`.

La firma se calcula sobre `timestamp + "." + raw_body` con HMAC-SHA256 y expira
a los 5 minutos. Esto evita envios anonimos o alterados y reduce replay, aunque
no puede demostrar de forma perfecta que el cliente sea el script original si un
usuario copia el token y reimplementa la firma.

La creacion de sesiones limita a 5 reportes por candidato identificable para
reducir abuso y crecimiento accidental de base de datos.

## Admin

En producción, `ADMIN_TOKEN` es obligatorio. Las rutas admin aceptan cookie
emitida por `/admin/login` o header `x-admin-token`.

## Validación

El servidor rechaza campos sensibles recursivamente y valida rangos de fechas,
tokens no negativos y confirmación de preview antes del submit.
Los diagnosticos solo aceptan contexto tecnico acotado (`days` y `session_id`).
