# Report Flow

Silver Usage Report es web-first y collector-first.

La web es la puerta de entrada: crea la sesión, muestra el comando local,
previsualiza los datos cuando llegan al servidor y permite confirmar o borrar el
reporte. Por ahora no hay carga manual, CSV, JSON, pasted stats ni screenshot en
la pantalla de candidato.

## Alcance

Incluido ahora:

- Self-report individual.
- Participantes externos y campañas de Silver.
- Uso local visible para el usuario.
- Collector one-shot para telemetría local soportada.
- Preview antes de confirmar.
- Link privado de estado y gestión.

Fuera de alcance por ahora:

- Carga manual web.
- Carga CSV/JSON web.
- Screenshot/OCR.
- Pasted stats.
- Importaciones company-wide.
- Team analytics.
- Provider org/admin APIs.
- Pedir admin keys.
- Tracking permanente o daemon.

## Sin Login Obligatorio Para Reporteros

El reportero no necesita crear una cuenta.

Flujo:

```text
open.silver.dev/usage-report
→ Crear sesión de reporte
→ Ver código / link privado
→ Ejecutar collector local
→ La web se actualiza cuando llegan los datos
→ Preview
→ Confirmar
→ Silver recibe filas agregadas
```

La sesión puede recoger campos opcionales para que Silver vincule el reporte:

- Nombre o etiqueta.
- Email.
- X handle.
- GitHub handle.
- Referencia de candidato.
- Referencia de campaña.

Silver admins necesitan acceso al panel interno. Reporteros no.

## Estado Y Gestión Del Reportero

Cada sesión genera un link privado. Ese link es la prueba y superficie de control
del reportero.

La creación de sesión usa redirect a una URL privada estable:

```text
/reports/sessions/SESSION_ID?token=PRIVATE_TOKEN
```

Esto evita que un refresh cree un nuevo id. La sesión también se guarda en
`localStorage` para mostrar "reportes existentes" en ese mismo navegador.

La página de estado muestra:

- Código de sesión.
- Estado: draft, previewed, submitted o deleted.
- Filas y tokens totales.
- Timestamp de envío.
- Campos de candidate/campaign linkage provistos.
- Acción para eliminar los datos agregados enviados.

El link privado debe incluir token. El session id o public code solos no deben
alcanzar para borrar o ver estado privado.

Sin login de reportero no hay recuperación cross-device: si el usuario cambia de
navegador o borra datos locales, necesita el link privado.

## Flujo MVP

1. El usuario abre `open.silver.dev/usage-report`.
2. La web crea una sesión.
3. La web muestra el comando del collector.
4. El usuario corre el collector local.
5. El collector lee telemetría agregada soportada, muestra preview local y envía
   filas agregadas.
6. El panel de la web se actualiza solo cuando recibe datos.
7. El usuario confirma el reporte.
8. Silver revisa el reporte desde admin.

## Importación Local

### Collector One-Shot

Camino principal para candidatos.

```powershell
irm "https://open.silver.dev/reports/sessions/SESSION_ID/collector.ps1" | iex
```

El script descarga el binario a una ruta temporal, corre una sola vez, muestra un
preview agregado por día/modelo, pide confirmación en terminal, envía filas
agregadas y termina. No instala un tracker permanente.

### MCP / Agente Local

Pendiente de empaquetado instalable. El objetivo es que un agente local pueda
usar el mismo contrato de preview/submit, pero el camino candidato actual sigue
siendo el collector.

## Preview

Todo envío debe terminar mostrando:

```text
Tool: Codex
Provider: OpenAI
Period: 2026-05-01 to 2026-05-04
Total tokens: 34,807,293
Source: codex_local_telemetry
Confidence: medium
Evidence: aggregate rows only
```

Se comparte:

- Provider.
- Tool.
- Model cuando se conozca.
- Período.
- Conteos agregados de tokens.
- Cost source/confidence cuando aplique.
- Evidence metadata agregada.

No se comparte:

- Prompts.
- Respuestas.
- Código fuente.
- Logs crudos.
- API keys.
- Variables de entorno.

## Silver Review

El panel interno debe mostrar:

- Reporter label o link privado anónimo.
- Email, GitHub, X, candidate ref y campaign ref cuando existan.
- Período.
- Provider/tool/model.
- Total tokens.
- Cost si está disponible.
- Source.
- Confidence.
- Evidence metadata.
- Warnings.

No debe mostrar prompts, raw logs, código fuente ni paths locales privados.
