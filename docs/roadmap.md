# Roadmap

## Phase 0: Discovery And Documentation

Status: current.

- Rename project from Silver Token Ledger to Silver Usage Report.
- Document findings from the X thread.
- Document the Deel/performance-review context that triggered the thread.
- Capture rejected solution categories and why they do not fit.
- Define privacy boundary.
- Define normalized usage report schema.
- Define web, CLI, and manual report contracts.
- Document why provider org APIs are out of scope for the employee-focused MVP.

## Phase 1: Report Session Skeleton

Outcome: users can create a report session and submit sample report data.

- Add Dockerfile and docker-compose.
- Add FastAPI app with Jinja2 + HTMX.
- Add PostgreSQL, SQLAlchemy, and Alembic.
- Add usage report route under Open Silver.
- Create report session API.
- Create short code/private-link report sessions without required reporter login.
- Create sample usage report payload.
- Render report preview.
- Add confidence/source labels.
- Add confirmation flow.
- Add delete flow.
- Add minimal Silver admin/review view.

## Phase 2: Manual, CSV, And JSON Fallback

Outcome: every user has at least one path to submit a report.

- Create CSV template.
- Create JSON schema.
- Create manual entry form.
- Validate report payloads.
- Label manual data as lower confidence.
- Add duplicate period warnings.
- Add synthetic fixture reports.

## Phase 3: CLI Importer Skeleton

Outcome: users can run a local command and upload fixture or local aggregate data.

- Create `@silver/usage-report` package.
- Implement session pairing.
- Implement local preview.
- Implement aggregate upload.
- Add schema validation.
- Add test fixtures.
- Ensure no raw logs are uploaded.

## Phase 4: MCP / Agent-Assisted Import

Outcome: users can ask a local agent to inspect supported local usage sources and submit a structured report.

- MCP server with strict `preview_report` and `submit_report` schemas.
- Prompt template for Codex, Claude Code, and Cursor-oriented workflows.
- Sensitive-field rejection.
- Evidence metadata for local telemetry/stat sources.
- Preview-before-submit flow.
- Confidence labels calculated by source type.
- Codex prompt template using the local telemetry recipe.

## Phase 5: Local Tools

Outcome: users without admin provider keys can still report useful usage.

- Local log parser interface.
- Codex local history usage investigation.
- Codex local telemetry proof-of-concept using `logs_2.sqlite` and `post sampling token usage` rows.
- Separate Codex auto-review/internal approval tokens from normal work tokens.
- Claude Code parser investigation.
- Codex parser investigation.
- Cursor export/local telemetry investigation.
- Redaction tests.

## Phase 6: MVP Tool Polish

Outcome: the three MVP tools have usable report paths and clear fallback behavior.

- Codex adapter hardening.
- Claude Code adapter or guided manual fallback.
- Cursor adapter or guided manual fallback.
- Cross-tool preview polish.
- Source/confidence messaging.

## Phase 7: Sharing And Campaigns

Outcome: Silver can use reports as part of open calls, benchmarks, or campaigns.

- Campaign-specific report links.
- Anonymous benchmark mode.
- Shareable usage cards.
- Public examples with synthetic data.
- Contributor guide for new provider/tool adapters.
- Responsible framing guidelines so usage reports are not presented as direct productivity scores.

## Implementation Paths

There are several viable paths, but they are not equally good for the first move.

### Path A: Web Report First

Build the report session, manual/CSV import, preview, confirmation, and admin review before local automation.

Pros:

- Fastest path to a working product.
- Validates the real Silver workflow.
- Works for everyone on day one.
- Avoids provider/admin-key dead ends for employees.

Cons:

- Some reports are manual or low-confidence at first.
- Less magical than automatic provider import.

### Path B: CLI Importer First

Build the local one-shot importer before the web flow.

Pros:

- Strong privacy story.
- Good foundation for local tool telemetry and pasted/exported stats.
- Matches the "paste this in your terminal" idea.

Cons:

- Still asks users to run software.
- Harder to show value without the web report session.
- Can drift back into tracker-tool territory.

### Path C: Provider APIs First

Start with Anthropic and OpenAI usage/cost APIs.

Pros:

- High-confidence data.
- Strong demo for users with admin/org access.

Cons:

- Excludes many users.
- Admin keys and account permissions create friction.
- Does not solve Cursor/Claude Code/Codex users immediately.
- Misreads org/admin APIs as universal "connect account" flows.
- Out of current scope because we are not building company/admin mode.

### Path D: Full Tracker

Build an ongoing tracker/dashboard.

Pros:

- Useful long-term.
- Can become a personal analytics product.

Cons:

- Misaligned with the thread's constraints.
- Requires installation or instrumentation.
- Delays useful data collection.

## Recommended Path

Start with Path A, then add MCP-assisted import and the CLI skeleton.

The first implementation should prove the report workflow:

1. Create a report session.
2. Accept sample/manual/CSV data.
3. Preview normalized rows.
4. Confirm submission.
5. Let Silver review the report.

After that, add the CLI importer and local source adapters to improve automation and confidence.

Provider org/admin APIs remain out of scope until Silver explicitly decides to support company/admin reports.
