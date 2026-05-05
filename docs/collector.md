# Standalone Collector

El collector standalone es el camino recomendado para candidatos que no tienen
Python instalado. Es un binario por sistema operativo que reutiliza el mismo
entrypoint del CLI (`cli.main`) y corre una sola vez: lee fuentes locales
soportadas, muestra una previsualizacion, pide confirmacion y envia solo filas
agregadas a Silver.

## Uso para candidatos

Windows:

```powershell
.\silver-usage-collector.exe submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url https://open.silver.dev
```

macOS/Linux:

```bash
./silver-usage-collector submit-codex --session SESSION_ID --sessions-dir "$HOME/.codex/sessions" --base-url https://open.silver.dev
```

El comando imprime `Rows` y `Total tokens` antes de pedir confirmacion. Si el
usuario no confirma, no se sube nada.

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
