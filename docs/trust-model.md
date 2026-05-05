# Trust Model

Silver Usage Report confía en datos agregados producidos por un collector
determinístico, no en afirmaciones libres.

## Fuente Vigente

La única fuente vigente del producto es:

```text
codex_local_telemetry
```

Se considera confianza `medium`: es telemetría local útil, pero no billing
oficial de OpenAI ni uso total de la cuenta.

## Evidencia

Cada fila puede incluir metadata como:

- adapter;
- adapter version;
- row count;
- query fingerprint;
- modelo;
- ventana de contexto;
- plan/rate-limit metadata cuando exista.

No se sube la fuente cruda.

## Validación Actual

El servidor valida:

- posesion del `PRIVATE_TOKEN` en rutas privadas;
- firma HMAC de los POST que reciben datos;
- ventana temporal de 5 minutos para reducir replay;
- valores de enum permitidos;
- tokens no negativos;
- rangos de fechas válidos;
- confirmación antes de submit;
- rechazo recursivo de campos sensibles;
- derivación de `total_tokens` cuando se conocen partes.

Campos sensibles rechazados:

- `prompt`;
- `prompts`;
- `response`;
- `responses`;
- `conversation`;
- `conversation_history`;
- `api_key`;
- `secret`;
- `environment`;
- `env`;
- `source_code`;
- `raw_log`.

## Preview Antes De Enviar

El preview ocurre localmente en PowerShell. El submit solo se ejecuta si el
usuario confirma.

## Que Prueba La Firma

La firma HMAC prueba que quien envio el body conocia el token privado de esa
sesion y que el payload no fue modificado en transito. No prueba de forma
absoluta que el cliente sea el script oficial, porque el script corre en la
maquina del usuario y puede ser inspeccionado. Es una barrera contra envios
casuales, fruta sin token y replay simple; para garantias mas fuertes harian
falta desafios one-time, attestation o validacion externa.

## Límites

- No representa billing oficial.
- Puede omitir otros dispositivos o herramientas.
- Depende de que Codex conserve rollouts locales.
- No estima costo si no hay costo real en la fuente.
- Un usuario con el token podria reimplementar el cliente firmado.

## Regla Principal

Si no hay telemetría local Codex soportada, no se inventa un reporte.
