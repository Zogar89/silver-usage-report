# Contributing

Silver Usage Report debe ser fácil de correr, fácil de revisar y cuidadoso con
los datos privados de quienes reportan.

## Principios

- Mantener soluciones simples.
- Optimizar por reportes completados, no por dashboards perfectos.
- No agregar trackers permanentes para el MVP.
- Subir agregados, no logs crudos.
- Mostrar preview antes de enviar.
- Etiquetar cada fila con source, confidence y evidence metadata.
- No pedir provider admin keys para el flujo individual actual.
- No presentar paths futuros como si estuvieran disponibles.

## Estado Del Producto

El camino candidato actual es:

```text
web session -> collector.ps1 -> preview local -> confirmación -> submit agregado firmado -> detalle web
```

El producto actual conserva solo el collector Codex local; cualquier flujo nuevo
requiere una decisión explícita antes de entrar al código o la documentación.

## Buenas Contribuciones

- Mejorar mensajes de error del collector PowerShell.
- Agregar tests de privacidad para nuevos campos.
- Documentar una fuente local de uso con límites claros.
- Mejorar revisión admin, búsqueda, paginación o exportación interna.
- Investigar Claude Code o Cursor sin leer prompts/respuestas/código.
- Agregar fixtures sintéticos para adapters.

## Antes De Tocar Imports O Privacidad

Cualquier cambio que lea datos locales, valide payloads, suba reportes,
autentique usuarios o modifique admin debe explicar:

- Qué datos sensibles podrían existir en ese punto.
- Qué datos salen de la máquina del usuario.
- Qué se guarda en la base.
- Cómo se muestran source y confidence.
- Cómo puede el usuario inspeccionar o borrar el reporte.
- Si el cambio toca POST privados, cómo se conserva la firma HMAC y la ventana
  anti-replay.

## Documentación

Al actualizar docs:

- Separar estado actual de ideas futuras.
- Usar español para documentación de producto y operación.
- Mantener nombres técnicos, comandos, rutas y campos en inglés cuando son
  contratos del código.
- Incluir tokens privados en ejemplos de rutas privadas.
- No documentar endpoints inexistentes.
- Verificar con `rg` que no queden referencias obsoletas.

## Verificación Local

Antes de cerrar un cambio:

```bash
python -m pytest
```

Para cambios de Docker o deploy:

```bash
docker compose build
docker compose run --rm web pytest
```
