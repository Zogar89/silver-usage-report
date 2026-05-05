# Silver Usage Report

Silver Usage Report is an open source intake flow for reporting AI token usage to Silver.

The goal is simple: a developer opens `open.silver.dev`, connects or imports usage from the AI tools they already use, previews exactly what will be shared, and sends Silver a normalized usage report without exposing prompts, responses, source code, raw logs, or API keys.

This is not primarily a personal spending dashboard. The first product job is to help Silver receive comparable token usage reports from many people with the lowest possible friction.

## What We Learned From The X Thread

The original ask was for a "token spending tracker for Silver." The replies clarified what Silver actually needs.

People suggested existing trackers and observability tools:

- Claude Code usage monitors.
- TUI dashboards like `codeburn`.
- OpenCode `/stats`.
- AI usage products like Burntop.
- AI gateways, SDKs, or proxy-based tracking.

Those tools are useful, but they do not solve Silver's immediate problem.

The key constraints surfaced in the conversation:

- Silver already tracks candidates internally.
- Silver wants people to report their token usage.
- Existing local trackers require users to install software.
- Ongoing trackers only collect future data, so Silver would have to wait weeks.
- Single-tool stats do not work for everyone.
- Gateway or SDK tracking only works for traffic that already passes through that layer.
- Many users do not know their own usage and estimate it by vibe.

The product should therefore be a usage reporting flow, not just another tracker.

## Product Thesis

Silver needs a fast, trustworthy way for external users to submit AI token usage.

The ideal first experience:

1. User opens the Silver Usage Report web page.
2. The page creates a short-lived report session.
3. User picks the fastest available import method.
4. User previews normalized metrics locally or in-browser.
5. User confirms the report.
6. Silver receives comparable aggregate usage data.

No ongoing daemon. No month-long waiting period. No provider-specific dead end.

Current scope is individual self-report. We are not building company-wide imports, team analytics, enterprise exports, or provider admin-key flows.

## Technical Direction

Silver Usage Report will be a Dockerized Python app:

- FastAPI for web/API.
- Jinja2 + HTMX for UI.
- Pydantic for report schemas and validation.
- SQLAlchemy + Alembic for persistence.
- PostgreSQL in Docker.
- Typer for the one-shot CLI.
- Python MCP server for agent-assisted import.

## Language Policy

The web product is Spanish-first from now on. All visible UI copy, navigation,
buttons, banners, empty states, admin labels, and reporter-facing instructions
must be written in Spanish.

Code identifiers, API fields, CLI commands, schema values, provider names, and
third-party product names may remain in English when that is the project or
integration contract.

## Proposed MVP

The first useful version should optimize for report completion:

- Web report session hosted under `open.silver.dev`.
- Short-lived report token or session code.
- One-shot CLI/MCP helper for local tool import.
- Browser/manual import path for CSV/JSON and copy-paste data.
- Manual, paste, CSV, and JSON imports as the universal fallback.
- Codex local telemetry adapter as the first validated local-source candidate.
- Cursor, Claude Code, and Codex as the three MVP tools.
- Normalized report preview before submission.
- Confidence labels for local telemetry, pasted stats, screenshots, estimated, or manually entered data.
- Admin/review view for Silver to inspect submitted reports.
- Deletion flow for submitted aggregate data.

Enterprise/org-admin imports are out of scope for now. Anthropic's usage/cost Admin API and OpenAI organization APIs are valuable for companies, but employees usually do not have those keys or permissions. Silver Usage Report should focus on what an individual employee or community member can report from their own tools.

## Privacy Promise

By default, Silver Usage Report uploads only aggregate usage metrics:

- Provider name
- Tool name, when known
- Model name, when known
- Date or reporting period
- Input tokens
- Output tokens
- Cached tokens
- Reasoning tokens
- Request count
- Estimated or actual cost
- Confidence/source metadata

It must not upload:

- Prompts
- Responses
- Conversation histories
- Source code
- API keys
- Raw provider logs
- Full file paths, unless the user explicitly opts in

## Repo Structure

```text
.
├── app
│   ├── main.py
│   ├── core
│   ├── schemas
│   ├── services
│   └── web
├── tests
├── README.md
├── CONTRIBUTING.md
├── Dockerfile
├── docker-compose.yml
├── LICENSE
├── pyproject.toml
└── docs
    ├── architecture.md
    ├── discovery-notes.md
    ├── mcp-assisted-import.md
    ├── product-spec.md
    ├── provider-research.md
    ├── report-flow.md
    ├── roadmap.md
    ├── security-privacy.md
    └── trust-model.md
```

## Local Development

Run tests:

```bash
python -m pytest
```

The repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`
that runs the test suite and verifies the Docker build.

Run the web app:

```bash
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

Docker Compose exposes the web app on `http://localhost:8002`. PostgreSQL stays
inside the Compose network to avoid colliding with a local database on port
`5432`. Both services define healthchecks.

La revision admin esta disponible en `/admin/reports`. En desarrollo puede quedar
abierta, pero produccion debe configurar `ADMIN_TOKEN`; las requests necesitan el
header `x-admin-token`.

Cada sesion de reporte genera un link privado de gestion. Ese link permite al
reportero verificar estado, filas, tokens totales y eliminar los datos agregados
enviados. Silver puede vincular reportes con candidatos usando los campos
opcionales `reporter_email`, `github_handle`, `x_handle`, `candidate_ref` y
`campaign_ref`, visibles en `/admin/reports` y en el detalle admin.

Initial API endpoints:

```text
POST   /api/usage-report/sessions
GET    /api/usage-report/sessions/{session_id}
GET    /api/usage-report/sessions/{session_id}/status?token=PRIVATE_TOKEN
POST   /api/usage-report/sessions/{session_id}/preview
POST   /api/usage-report/sessions/{session_id}/preview/csv
POST   /api/usage-report/sessions/{session_id}/submit
DELETE /api/usage-report/sessions/{session_id}
```

Preview a local JSON report file:

```bash
python -m cli.main preview report.json
```

Preview a local CSV report file:

```bash
python -m cli.main preview-csv report.csv
```

Preview Codex local usage from session JSONL files:

```powershell
python -m cli.main preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions"
```

The same command is available in the standalone collector binary, so candidates
do not need Python installed:

```powershell
.\silver-usage-collector.exe preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions"
```

Submit a local JSON report after explicit confirmation:

```bash
python -m cli.main submit --session SESSION_ID --file report.json --base-url http://localhost:8002 --yes
```

Submit Codex local telemetry after an interactive preview and confirmation:

```powershell
python -m cli.main submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url http://localhost:8002
```

For candidates, prefer the standalone collector:

```powershell
.\silver-usage-collector.exe submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url https://open.silver.dev
```

Build the local collector binary for the current OS:

```bash
python -m pip install -e ".[collector]"
python -m PyInstaller packaging/pyinstaller/silver-usage-collector.spec --noconfirm --clean
```

The binary is written to `dist/silver-usage-collector` on macOS/Linux and
`dist/silver-usage-collector.exe` on Windows. PyInstaller builds for the host OS,
so release binaries are produced by `.github/workflows/collector.yml` on Windows,
macOS, and Linux runners.

Agent-assisted imports should use the prompt template at `mcp_server/prompts/agent-assisted-import.md`.

The web session page presents the standalone Codex collector command as the
primary path. Manual rows plus CSV and JSON paste previews remain fallback paths
when local telemetry is unavailable.

Codex SQLite sources such as `state_5.sqlite` and `logs_2.sqlite` are treated as
legacy best-effort fallbacks because their local schema is not documented as a
stable public contract.

## Candidate Collector Flow

```bash
silver-usage-collector submit-codex --session SESSION_ID --base-url https://open.silver.dev
```

Expected flow:

1. The web app shows a report session code or deep link.
2. The user downloads the collector binary for their OS.
3. The collector detects supported local sources.
4. The collector normalizes usage into report rows.
5. The collector previews exactly what will be sent.
6. The user confirms upload.
7. The web report session updates immediately.

## Key Design Documents

- [Report flow](docs/report-flow.md): web-first MVP, no required reporter login, import methods, and Silver review.
- [Standalone collector](docs/collector.md): candidate binary usage, local build, release workflow, and privacy notes.
- [MCP-assisted import](docs/mcp-assisted-import.md): prompt + MCP flow for local agents like Codex or Claude Code.
- [Technical architecture](docs/technical-architecture.md): Docker, FastAPI, Jinja2, HTMX, database, CLI, and MCP layout.
- [Trust model](docs/trust-model.md): source, confidence, evidence, validation, and anti-hallucination rules.
- [Discovery notes](docs/discovery-notes.md): decisions from the X thread, Deel context, Codex local telemetry finding, and scope cuts.

## Links

- Open Silver: https://open.silver.dev
- Open Silver repository: https://github.com/silver-dev-org/open-silver
