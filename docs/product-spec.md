# Product Spec

Actualizado: 2026-05-05.

Silver Usage Report es un flujo web-first y collector-first para que una persona
envíe a Silver métricas agregadas de uso local de Codex.

## Producto Actual

El producto hace una sola cosa:

```text
sesión privada -> collector Codex local -> preview local -> confirmación -> submit agregado firmado -> detalle web
```

No es un tracker, no es un dashboard personal y no es una integración de
organización.

## Usuarios

- Candidatos o participantes que usan Codex.
- Admins de Silver que revisan reportes.
- Maintainers que mejoran el collector Codex.

## Objetivos

- Recibir un reporte útil en minutos.
- Evitar instalaciones permanentes.
- Evitar claves provider/org/admin.
- Subir solo métricas agregadas.
- Mostrar preview antes de enviar.
- Mantener source, confidence y evidence metadata.
- Permitir borrar datos agregados.
- Proteger envios con token privado y firma HMAC por payload.

## No Objetivos

- Otros caminos de carga distintos del collector Codex local.
- Descarga de `.exe`.
- Daemon de tracking.
- Importación company-wide.
- Costeo real desde telemetría local si Codex no lo entrega.
- Guardar prompts, respuestas, código fuente o logs crudos.

## Flujo Principal

1. El usuario crea una sesión.
2. La web muestra un comando PowerShell con token privado.
3. El usuario corre el collector.
4. El collector lee `~/.codex/sessions/**/rollout-*.jsonl`.
5. El collector agrega los últimos 90 días por día/modelo.
6. El collector muestra preview local.
7. El usuario confirma.
8. El collector firma y envía filas agregadas.
9. La web detecta la recepción y redirige al detalle.
10. El candidato puede ver insights y borrar el reporte.
11. Silver lo revisa desde admin.

## Contrato De Fila

```ts
type UsageReportRow = {
  provider: "openai";
  tool: "codex";
  source: "codex_local_telemetry";
  period_start: string;
  period_end: string;
  period_width: "1d" | "custom";
  model?: string;
  request_count?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached_input_tokens?: number;
  cache_creation_input_tokens?: number;
  reasoning_tokens?: number;
  total_tokens?: number;
  cost_source: "unknown";
  confidence: "medium";
  evidence?: EvidenceMetadata;
};
```

El schema de Python sigue usando enums generales para provider/tool, pero el
camino de producto actual produce `codex_local_telemetry`.

## Privacidad

El producto debe decir claramente qué se comparte y qué no. La promesa central:
Silver recibe agregados, no contenido.

## UI

La UI visible es Spanish-first y debe sentirse parte de Open Silver.

El detalle del reporte es compartido por candidato y admin: ahi viven las
metricas, porcentajes y serie temporal por tipo de token. La lista admin queda
para busqueda, paginacion, fechas, estado y acciones como editar identidad o
borrar reporte.

La nomenclatura de tokens debe ser consistente en todas las vistas:

- `Tokens totales` para el volumen agregado.
- `Input total` para el input completo.
- `Input nuevo` para input no cacheado.
- `Input cacheado` para caché.
- `Output` para salida.
- `Razonamiento` para tokens de reasoning.

Para pricing y porcentajes, la implementación debe soportar tomas donde
`cached_input_tokens` sea subconjunto de `input_tokens` y tomas donde sea bucket
separado. La decisión se infiere comparando candidatos contra `total_tokens`.

El resumen debe priorizar `Tokens por día activo` como métrica de intensidad.
Evitar presentar `tokens / request` como métrica principal porque el collector
puede recibir eventos agregados, no requests individuales.

El gráfico diario debe mostrar series apiladas por tipo de token y un control
para mostrar u ocultar `Input cacheado`. Las fechas con hora visibles para
usuarios y admins se muestran en horario de Argentina.

La home debe usar el ancho disponible para que los campos principales sean
cómodos de completar. El historial local de reportes guardados muestra la acción
`Borrar` alineada a la derecha de cada fila.

## Seguridad Operativa

- La creacion de reportes limita a 5 sesiones por candidato identificable.
- Las rutas privadas requieren `PRIVATE_TOKEN`.
- Los POST privados que reciben datos requieren firma HMAC con timestamp.
- El token privado habilita gestion del reporte; no hay login candidato.
- El admin requiere `ADMIN_TOKEN` en produccion.
