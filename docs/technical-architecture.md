# Technical Architecture

Silver Usage Report will be built as a Python-first Dockerized web application.

Chosen stack:

- Python.
- FastAPI.
- Jinja2.
- HTMX.
- Pydantic.
- SQLAlchemy.
- Alembic.
- PostgreSQL in Docker.
- SQLite only for lightweight local experiments if needed.
- A small argparse CLI for the first skeleton; Typer can replace it once the package interface stabilizes.
- Python MCP server for agent-assisted import.
- pytest for tests.

## Why This Stack

Python is the preferred project language.

FastAPI gives a clean API surface, strong Pydantic integration, and enough flexibility to serve both HTML and JSON.

Jinja2 + HTMX keeps the frontend simple:

- No React build pipeline.
- Server-rendered forms and previews.
- Small interactive pieces.
- Easy to understand and modify.

Docker keeps the dev and production environment consistent.

## Runtime Shape

```text
docker compose
├── web        FastAPI + Jinja2 + HTMX
├── worker     optional later, background jobs/import processing
└── db         PostgreSQL
```

The MVP can start with only:

```text
web + db
```

## Repository Shape

Recommended structure:

```text
.
├── app
│   ├── main.py
│   ├── api
│   │   └── usage_report.py
│   ├── web
│   │   ├── routes.py
│   │   ├── templates
│   │   └── static
│   ├── core
│   │   ├── config.py
│   │   ├── security.py
│   │   └── validation.py
│   ├── db
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations
│   ├── schemas
│   │   └── usage_report.py
│   ├── services
│   │   ├── report_sessions.py
│   │   ├── report_validation.py
│   │   └── evidence.py
│   └── adapters
│       ├── codex_local.py
│       ├── opencode_stats.py
│       ├── csv_import.py
│       └── manual.py
├── cli
│   └── main.py
├── mcp_server
│   └── main.py
├── tests
├── docs
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Web App

The web app serves:

- Report start page.
- Report session page.
- Tool/source picker.
- Manual entry form.
- CSV/JSON paste/upload.
- Pasted stats form.
- Preview page.
- Confirmation page.
- Delete report page.
- Silver admin review pages.

The web interface must match the existing Open Silver site at `https://open.silver.dev/`. Templates and CSS should be treated as an extension of that site: reuse the same brand feel, navigation structure, link/product-card conventions, spacing, typography, and restrained visual style before adding any new component patterns.

The rendered web UI is Spanish-first. Jinja templates, route banners, form
labels, admin headings, navigation labels, and empty states should use Spanish
copy by default. Keep code identifiers, schema fields, CLI commands, and
integration-specific values in English when they are part of a technical
contract.

HTMX should be used for:

- Adding/removing report rows.
- CSV/JSON preview refresh.
- Tool-specific import instructions.
- Preview validation.
- Submit confirmation.

## API

The API should support both the web app and MCP/CLI.

Initial endpoints:

```text
POST   /api/usage-report/sessions
GET    /api/usage-report/sessions/{session_id}
POST   /api/usage-report/sessions/{session_id}/preview
POST   /api/usage-report/sessions/{session_id}/submit
DELETE /api/usage-report/sessions/{session_id}
GET    /api/usage-report/admin/reports
```

Preview and submit must use the same Pydantic schema and validation rules.

## Database

Use PostgreSQL in Docker.

Core tables:

```text
report_sessions
- id
- public_code
- private_token_hash
- reporter_label nullable
- status
- created_at
- expires_at
- submitted_at nullable

usage_report_rows
- id
- report_session_id
- provider
- tool nullable
- source
- period_start
- period_end
- model nullable
- total_tokens nullable
- input_tokens nullable
- output_tokens nullable
- cached_input_tokens nullable
- reasoning_tokens nullable
- cost_usd nullable
- cost_source
- confidence
- evidence_json nullable
- created_at

report_warnings
- id
- report_session_id
- row_id nullable
- code
- message
- created_at
```

## Schema And Validation

Pydantic models are the contract across:

- Web forms.
- API.
- CLI.
- MCP server.
- Adapters.
- Tests.

Validation rules:

- Reject negative token counts.
- Reject invalid date ranges.
- Reject unknown source values.
- Reject sensitive fields.
- Derive or cap confidence from source/evidence.
- Require preview before submit.

## CLI

Initial CLI:

```bash
silver-usage-report import --session ABC123 --source codex
silver-usage-report preview --file report.json
```

The CLI should:

- Run once.
- Inspect local source via adapters.
- Show a local preview.
- Submit only after confirmation.
- Never run as a daemon.

Current commands:

```bash
python -m cli.main preview report.json
python -m cli.main preview-csv report.csv
python -m cli.main preview-codex --logs-db "C:\Users\YOU\.codex\logs_2.sqlite"
python -m cli.main submit --session SESSION_ID --file report.json --base-url http://localhost:8002 --yes
python -m cli.main submit-codex --session SESSION_ID --logs-db "C:\Users\YOU\.codex\logs_2.sqlite" --base-url http://localhost:8002 --yes
```

## MCP Server

Python MCP server:

```text
silver_usage_report.preview_report
silver_usage_report.submit_report
silver_usage_report.get_report_status
```

The MCP server should reuse the same schemas and validation logic as the web API.

The initial implementation exposes these as transport-agnostic helpers in
`mcp_server/main.py` and pairs them with the agent prompt at
`mcp_server/prompts/agent-assisted-import.md`.

Codex local telemetry preview is also exposed as an explicit-path helper. It
does not auto-discover user log files.

## Docker

Development commands should be Docker-first:

```bash
docker compose up --build
docker compose run --rm web pytest
docker compose run --rm web alembic upgrade head
```

The development Compose file publishes only the web app on host port `8002`.
PostgreSQL is reachable as `db:5432` from the web container but is not published
to the host by default. This avoids conflicts with local Postgres installs.

Both `web` and `db` define healthchecks. The web healthcheck calls `/health`;
the database healthcheck uses `pg_isready`.

Environment variables:

```text
DATABASE_URL=postgresql+psycopg://silver:silver@db:5432/silver_usage_report
SECRET_KEY=dev-secret
APP_BASE_URL=http://localhost:8000
```

No provider admin keys are required for the current MVP.

## First Implementation Slice

The first technical slice should include:

1. Dockerfile and docker-compose.
2. FastAPI app health route.
3. Jinja2 base layout.
4. Report session creation.
5. Manual row form.
6. Preview page.
7. Submit page.
8. PostgreSQL models and migration.
9. Pydantic schema tests.

Then add:

1. CSV/JSON paste.
2. MCP preview/submit server.
3. Codex local telemetry adapter.
4. CLI wrapper.
