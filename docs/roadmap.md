# Roadmap

## Phase 0: Documentation and Design

Status: current.

- Define product scope.
- Document privacy boundary.
- Document provider feasibility.
- Define normalized usage schema.
- Define CLI and web import contracts.

## Phase 1: Web Import Skeleton

Outcome: users can create an import session and upload sample data.

- Add app route under Open Silver.
- Create import session API.
- Create sample usage payload.
- Render import preview.
- Render basic dashboard.
- Add delete flow.

## Phase 2: CLI Importer Skeleton

Outcome: users can run a local command and upload fixture data.

- Create `@silver/token-ledger` package.
- Implement session pairing.
- Implement local preview.
- Implement aggregate upload.
- Add schema validation.
- Add test fixtures.

## Phase 3: Anthropic and OpenAI

Outcome: users can import real historical provider data from the two clearest APIs.

- Anthropic usage importer.
- Anthropic cost importer.
- OpenAI usage importer.
- OpenAI costs importer.
- Duplicate import detection.
- Provider warning display.

## Phase 4: Local Logs and CSV

Outcome: users without admin provider keys can still get value.

- CSV import template.
- JSON import template.
- Local log parser interface.
- First local AI coding tool parser.
- Redaction tests.

## Phase 5: Gemini, xAI, and MCP

Outcome: broader provider support and agent-friendly import.

- xAI response-log importer.
- Gemini response-log importer.
- Google Cloud billing export investigation.
- MCP server that wraps the CLI importer core.
- Agent prompt for guided import.

## Phase 6: Sharing and Community

Outcome: Silver can use the project as an open community artifact.

- Shareable usage cards.
- Anonymous benchmark mode.
- Public examples with synthetic data.
- Contributor guide for new provider adapters.

