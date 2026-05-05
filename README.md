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

Run the web app:

```bash
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

Initial API endpoints:

```text
POST   /api/usage-report/sessions
GET    /api/usage-report/sessions/{session_id}
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

Submit a local JSON report after explicit confirmation:

```bash
python -m cli.main submit --session SESSION_ID --file report.json --base-url http://localhost:8002 --yes
```

Agent-assisted imports should use the prompt template at `mcp_server/prompts/agent-assisted-import.md`.

## Candidate CLI Flow

```bash
npx -y @silver/usage-report import
```

Expected flow:

1. The web app shows a report session code or deep link.
2. The CLI detects supported local sources and provider credentials.
3. The user chooses which sources to include.
4. The CLI normalizes usage into report rows.
5. The CLI previews exactly what will be sent.
6. The user confirms upload.
7. The web report session updates immediately.

## Key Design Documents

- [Report flow](docs/report-flow.md): web-first MVP, no required reporter login, import methods, and Silver review.
- [MCP-assisted import](docs/mcp-assisted-import.md): prompt + MCP flow for local agents like Codex or Claude Code.
- [Technical architecture](docs/technical-architecture.md): Docker, FastAPI, Jinja2, HTMX, database, CLI, and MCP layout.
- [Trust model](docs/trust-model.md): source, confidence, evidence, validation, and anti-hallucination rules.
- [Discovery notes](docs/discovery-notes.md): decisions from the X thread, Deel context, Codex local telemetry finding, and scope cuts.

## Links

- Open Silver: https://open.silver.dev
- Open Silver repository: https://github.com/silver-dev-org/open-silver
