# Provider And Tool Research

Actualizado: 2026-05-05.

El producto vigente soporta Codex local. La investigación de otros providers y
tools queda separada del código activo.

## Codex Local

Fuente primaria:

```text
~/.codex/sessions/**/rollout-*.jsonl
```

El collector PowerShell:

- busca rollouts locales;
- extrae eventos de token usage;
- asocia modelo cuando la metadata existe;
- agrega por día/modelo;
- usa los últimos 90 días;
- envía solo filas agregadas.

La confianza es `medium` porque es telemetría local de una máquina, no billing
oficial de OpenAI.

## SQLite Legacy

El adapter Python conserva lectura best-effort de `state_5.sqlite` y
`logs_2.sqlite` para desarrollo e investigación. No es el flujo candidato.

## Provider Org APIs

APIs de organización/admin de Anthropic, OpenAI, Google, xAI u otros providers
siguen fuera del producto actual. Requieren permisos que un candidato individual
normalmente no tiene y cambian el modelo de privacidad.

## Claude Code Y Cursor

Pendientes. Cualquier investigación futura debe demostrar que puede extraer
solo métricas agregadas sin leer contenido sensible.

## Regla Para Nuevas Fuentes

Una fuente nueva solo debe entrar al producto si puede cumplir:

- sin claves admin;
- sin contenido crudo;
- preview antes de submit;
- source y confidence explícitos;
- tests de privacidad;
- documentación operativa clara.
