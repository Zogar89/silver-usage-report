# Discovery Notes

Actualizado: 2026-05-05.

La decisión vigente es enfocar Silver Usage Report en un solo flujo:

```text
web session + Codex local PowerShell collector
```

## Decisión De Producto

Silver necesita recibir usage agregado de forma rápida y confiable. El producto
actual no intenta ser universal: prioriza un collector concreto, auditable y
sin instalación permanente.

## Fuente Actual

Codex local:

- Directorio: `~/.codex/sessions`.
- Archivos: `rollout-*.jsonl`.
- Periodo: últimos 90 días.
- Agregado: día/modelo.
- Source: `codex_local_telemetry`.
- Cost source: `unknown`.
- Confidence: `medium`.

## Por Qué Este Camino

- No requiere claves provider/org/admin.
- No pide instalar un tracker.
- No espera semanas de tracking futuro.
- Muestra preview local antes de enviar.
- No sube prompts, respuestas, código fuente ni logs crudos.

## Cosas Eliminadas

Se eliminó el código y documentación de los experimentos que no forman parte del
producto:

- carga por archivos externos;
- carga desde formularios libres;
- lectura de imágenes;
- binario descargable;
- tracking permanente.

## Preguntas Abiertas

- Qué tan estable es el formato local de rollouts de Codex.
- Cómo soportar múltiples instalaciones Codex sin leer de más.
- Cómo mejorar mensajes de error del collector.
- Cómo investigar Claude Code o Cursor sin reabrir caminos genéricos.
