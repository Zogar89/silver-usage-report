# Standalone Collector

El collector standalone es el camino recomendado para candidatos que no tienen
Python instalado. Es un binario por sistema operativo que reutiliza el mismo
entrypoint del CLI (`cli.main`) y corre una sola vez: lee fuentes locales
soportadas, muestra una previsualizacion, pide confirmacion y envia solo filas
agregadas a Silver.

## Uso para candidatos

Windows, desde la pagina de sesion:

```powershell
irm "https://open.silver.dev/reports/sessions/SESSION_ID/collector.ps1" | iex
```

Ese script descarga `silver-usage-collector.exe` a `$env:TEMP` y lo ejecuta con
la sesion correcta. El collector muestra una previsualizacion y pide
confirmacion antes de subir datos.

Windows, ejecucion manual:

```powershell
.\silver-usage-collector.exe submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --days 30 --base-url https://open.silver.dev
```

macOS/Linux:

```bash
./silver-usage-collector submit-codex --session SESSION_ID --sessions-dir "$HOME/.codex/sessions" --days 30 --base-url https://open.silver.dev
```

Por defecto, `preview-codex` y `submit-codex` reportan los ultimos 30 dias. Se
puede cambiar con `--days N` o usar una fecha absoluta con `--since YYYY-MM-DD`.

La previsualizacion imprime filas agregadas por dia/modelo, requests,
`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`,
`total_tokens` y los modelos principales. Si el usuario no confirma, no se sube
nada.

## Build local

PyInstaller genera binarios para el sistema operativo donde corre. Para crear un
binario local:

```bash
python -m pip install -e ".[collector]"
python -m PyInstaller packaging/pyinstaller/silver-usage-collector.spec --noconfirm --clean
```

Salidas esperadas:

- Windows: `dist/silver-usage-collector.exe`
- macOS/Linux: `dist/silver-usage-collector`

## Release

El workflow `.github/workflows/collector.yml` compila el collector en
`windows-latest`, `macos-latest` y `ubuntu-latest`, ejecuta un smoke test con
`--help` y sube cada binario como artifact.

## Privacidad

El collector no sube prompts, respuestas, codigo fuente, logs crudos, variables
de entorno ni API keys. El adaptador de Codex usa `~/.codex/sessions` como
fuente primaria y normaliza solo metricas agregadas de tokens.

Los paths SQLite legacy (`--state-db`, `--logs-db`) quedan como fallback
best-effort para entornos antiguos.
