# Flujo De Reporte

Silver Usage Report tiene un solo flujo candidato vigente: sesión web privada y
collector PowerShell de Codex local.

## Alcance Actual

Incluido:

- Self-report individual.
- Sesión privada con `PRIVATE_TOKEN`.
- Collector one-shot servido por la web.
- Lectura local de `~/.codex/sessions/**/rollout-*.jsonl`.
- Agregado por día/modelo de los últimos 90 días.
- Preview local en PowerShell.
- Confirmación explícita antes de enviar.
- Submit firmado de filas agregadas.
- Redirección automática al detalle cuando llega el reporte.
- Panel privado de estado y borrado.
- Panel admin de Silver.

Fuera del producto actual:

- Cualquier flujo distinto del collector Codex local.
- Descarga de binarios.
- Tracker o daemon permanente.
- Importaciones con claves provider/org/admin.

## Flujo Candidato

```text
Crear sesión web
→ abrir URL privada con token
→ copiar comando PowerShell
→ leer telemetría local Codex
→ mostrar preview local
→ confirmar en terminal
→ firmar y enviar filas agregadas
→ la web detecta recepción
→ ver detalle e insights del reporte
```

Comando generado:

```powershell
irm "https://reports.tu-dominio.example/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | iex
```

El collector no instala nada. Corre una vez, termina y deja el control al usuario.

## Datos Compartidos

El submit contiene solamente filas normalizadas con:

- provider;
- tool;
- source `codex_local_telemetry`;
- periodo;
- modelo cuando exista;
- request count;
- tokens input, cached input, output, reasoning y total;
- `cost_source: "unknown"`;
- confidence;
- evidencia agregada.

No se suben prompts, respuestas, código fuente, logs crudos, variables de
entorno, API keys ni rutas locales completas.

## Lectura De Métricas En La UI

La UI usa nombres consistentes para evitar confundir volumen total con partes del
input:

- `Tokens totales`: total agregado de la fila, día o reporte.
- `Input total`: input completo informado.
- `Input nuevo`: input no cacheado.
- `Input cacheado`: input servido desde caché.
- `Output`: tokens de salida.
- `Razonamiento`: tokens de razonamiento cuando existen.

La app no asume que todas las tomas de Codex tengan la misma semántica. Si
`cached_input_tokens` parece estar incluido dentro de `input_tokens`, calcula
`Input nuevo = input_tokens - cached_input_tokens`. Si `total_tokens` cierra
mejor tratando caché como bucket separado, calcula `Input total = input_tokens +
cached_input_tokens`. La inferencia se hace contra `total_tokens`.

El resumen del detalle muestra `Tokens por día activo`, no tokens por request. Se
calcula como `tokens totales / días con uso`, porque el `request_count` del
collector representa eventos o filas agregadas y no siempre equivale a llamadas
individuales al modelo.

La serie diaria permite ocultar o mostrar `Input cacheado` para distinguir uso
nuevo de reutilización de caché. Las fechas con hora se muestran en horario de
Argentina; los buckets diarios conservan su día de reporte.

## Estado Y Gestión

Cada sesión tiene un link privado:

```text
/reports/sessions/SESSION_ID?token=PRIVATE_TOKEN
```

Ese link permite ver estado, totales, filas recibidas y borrar datos agregados.
Sin el token privado no se puede gestionar la sesión.

Los envios de datos desde collector/CLI tambien requieren firma HMAC del body.
El token via query identifica la sesion; la firma prueba posesion del token para
ese payload y reduce replay.

## Admin

Silver revisa reportes en:

```text
/admin/reports
```

En producción debe existir `ADMIN_TOKEN`. El admin puede entrar por `/admin` o
usar el header `x-admin-token`.

La lista admin soporta busqueda en vivo y paginacion. Las metricas de uso de IA
se revisan dentro del detalle de cada reporte/candidato, junto con el grafico de
serie temporal por tipo de token.
