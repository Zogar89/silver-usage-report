# Collector PowerShell

El camino candidato actual no usa binario. La pagina de sesion sirve un
`collector.ps1` generado para esa sesion:

```powershell
irm "https://open.silver.dev/reports/sessions/SESSION_ID/collector.ps1?token=PRIVATE_TOKEN" | iex
```

El script corre una sola vez, usa solo PowerShell y APIs del sistema, lee
`$env:USERPROFILE\.codex\sessions`, muestra un resumen agregado local, pide
confirmacion y solo entonces envia filas normalizadas firmadas a Silver.

## Por Que No Hay `.exe`

Empaquetar Python con PyInstaller produce un runtime demasiado grande para esta
tarea. Incluso optimizado, el binario seguia pesando varios MB y podia quedar
cacheado/desactualizado en el servidor o en `%TEMP%`.

El script PowerShell evita esos problemas:

- No descarga binarios.
- No requiere Python.
- No deja un ejecutable temporal.
- Es auditable en texto plano.
- Se actualiza con cada deploy web.

## Datos Que Lee

Fuente primaria:

```powershell
$env:USERPROFILE\.codex\sessions
```

El script busca `rollout-*.jsonl`, toma eventos `token_count`, asocia el modelo
desde otros eventos metadata del mismo rollout cuando existe, agrega por
dia/modelo los ultimos 90 dias y muestra una previsualizacion local en
PowerShell. Si el usuario confirma, envia solo metricas agregadas.

La telemetria local de Codex no trae costo real por request o por dia. El
collector envia tokens agregados y el servidor calcula un costo estimado con la
tabla local `app/data/openai_model_prices.json`, preparada desde la pagina
oficial de pricing de OpenAI.

Cuando el envio termina bien, el script muestra la confirmacion del servidor,
filas/tokens recibidos y le indica al usuario volver a la pagina donde copio el
comando. Esa pagina queda esperando recepcion de datos, se actualiza sola y
redirige al detalle del reporte.

Si algo falla, el script imprime la etapa, el detalle del error y posibles
soluciones: revisar la carpeta local de Codex, correr con el mismo usuario de
Windows, verificar conectividad o crear una nueva sesion si el link expiro.
Tambien intenta enviar a Silver un diagnostico tecnico minimo del fallo:

```text
POST /api/usage-report/sessions/{session_id}/collector-diagnostics?token=PRIVATE_TOKEN
```

Ese diagnostico incluye etapa, mensaje de error sanitizado, version de
PowerShell, version del collector, estado de la carpeta local y cantidad de
rollouts detectados si se pudo calcular. No incluye prompts, respuestas, codigo
fuente, logs crudos, variables de entorno ni API keys.

## Firma Del Envio

El token privado de la sesion no se usa solo como query param. Cada POST que
manda datos desde el collector (`submit` y `collector-diagnostics`) incluye:

```text
X-Silver-Timestamp: <unix seconds>
X-Silver-Signature: HMAC_SHA256(private_token, timestamp + "." + raw_body)
```

El servidor acepta timestamps dentro de una ventana de 5 minutos. Esto prueba
posesion del token privado para esa sesion, protege la integridad del body y
reduce replays simples. No es una prueba absoluta de que el script no fue
copiado o reimplementado por alguien que ya tiene el token.

## Privacidad

No se suben prompts, respuestas, codigo fuente, logs crudos, variables de
entorno ni API keys. El script extrae solo:

- Provider/tool/source.
- Periodo.
- Modelo cuando exista.
- Requests.
- Tokens input/output/cache/reasoning/total.
- Metadata de evidencia agregada, como plan, ventana de contexto y rate limits
  cuando Codex los registra.

## CLI De Desarrollo

El CLI Python sigue existiendo para desarrollo y tests:

```powershell
python -m cli.main preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions"
python -m cli.main submit-codex --session SESSION_ID --token PRIVATE_TOKEN --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url http://localhost:8002
```

No es el camino recomendado para candidatos.
