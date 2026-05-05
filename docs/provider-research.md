# Provider And Tool Research

Last reviewed: 2026-05-04.

Provider APIs and AI tool storage formats change often. This document captures what is known now and what should be verified during implementation.

## Research Lens

Silver Usage Report needs broad reporting coverage, not perfect tracking coverage.

Evaluate each source by:

- Can it report historical or recent usage now?
- Does it require the user to install ongoing tracking?
- Does it work for many users or only one tool?
- Can it produce aggregate metrics without exposing prompts or source code?
- Can the report row be labeled with a clear confidence level?

The Deel article that triggered the Silver thread claims Deel Engage integrates with Anthropic Claude, Cursor, and GitHub Copilot, with Microsoft Copilot and Gemini planned. It also says OpenAI enterprise analytics need work on OpenAI's side. Treat these as competitive/category signals, not as proof that equivalent public APIs are available to this project.

## Provider Org APIs Are Out Of Current Scope

Current product scope is individual employee/community self-reporting, not enterprise/company import.

Employees usually do not have provider admin keys, organization billing exports, or company-wide analytics permissions. Therefore provider org APIs are useful research context, but they should not drive the MVP.

## Anthropic

Out of scope for current employee-focused MVP.

Anthropic documents an organization-level Usage and Cost Admin API:

- Usage endpoint: `/v1/organizations/usage_report/messages`
- Cost endpoint: `/v1/organizations/cost_report`
- Supports daily, hourly, and minute buckets for usage.
- Supports daily buckets for cost.
- Can group by model, API key, workspace, service tier, and context window.
- Requires an Admin API key, not a standard API key.
- Admin API is unavailable for individual accounts.

Implementation detail: do not build this path in the current MVP. If company/admin mode is ever added, admin keys should stay outside Silver's web app and be handled in the organization's own environment.

Fit for Silver Usage Report:

- High confidence for organization admins if this scope is ever added.
- Not useful for the current employee self-report mode.
- Individual accounts cannot use this Admin API.
- Should not appear as a primary import path in the MVP.

Docs:

- https://docs.anthropic.com/en/api/usage-cost-api
- https://docs.anthropic.com/en/api/admin-api/usage-cost/get-messages-usage-report

## OpenAI

Out of scope for current employee-focused MVP.

OpenAI documents organization usage endpoints and a costs endpoint:

- Usage endpoint family: `/v1/organization/usage/...`
- Costs endpoint: `/v1/organization/costs`
- Usage can be grouped by project, user, API key, model, batch, and service tier depending on endpoint.
- Costs can be grouped by project and line item.
- The costs endpoint is preferred for financial reconciliation.

Implementation detail: use usage endpoints for token breakdowns and costs endpoint for spend reconciliation.

Fit for Silver Usage Report:

- High confidence for organization admins if this scope is ever added.
- Not useful for most employees.
- Not enough for users whose AI usage happens through coding tools or consumer products.
- Should not appear as a primary import path in the MVP.

Docs:

- https://platform.openai.com/docs/api-reference/usage/costs

## Gemini

Useful, but likely not the first account-wide import.

Gemini API responses include `usage_metadata`, including prompt token count, candidate token count, total token count, cached content token count, and thoughts token count in supported flows.

This is good for future traffic, local logs, wrappers, SDK instrumentation, and CSV imports. It is not enough by itself to reconstruct account-wide historical usage unless the user already stored responses or has billing exports.

For a first Gemini integration, prefer:

- CSV/JSON import.
- Local wrapper logs.
- Google Cloud billing export, if the user's Gemini usage is billed through Google Cloud.
- Future proxy or SDK instrumentation.

Fit for Silver Usage Report:

- Medium or low confidence unless backed by structured billing/export data.
- Useful as an adapter after the report contract exists.

Docs:

- https://ai.google.dev/gemini-api/docs/tokens

## xAI / Grok

Useful, but ingestion path depends on source.

xAI documents:

- Usage Explorer in the console for team admins.
- Token and cost dimensions in Usage Explorer.
- Per-response `usage` data.
- `cost_in_usd_ticks` in API responses for exact per-request charged cost.

This makes future-traffic instrumentation strong. Account-wide historical import needs verification because the public docs emphasize console Usage Explorer rather than a public usage export API.

For a first xAI integration, prefer:

- Response logs containing `usage.cost_in_usd_ticks`.
- CSV export if available.
- Local wrapper/proxy instrumentation.

Fit for Silver Usage Report:

- High confidence for structured response logs.
- Medium or low confidence for manual console exports.
- Not a blocker for MVP.

Docs:

- https://docs.x.ai/console/usage
- https://docs.x.ai/developers/cost-tracking
- https://docs.x.ai/docs/consumption-and-rate-limits

## Local AI Coding Tools

Local tools matter because the X thread showed that single-provider reporting will not be enough.

Candidate tools:

- Claude Code.
- Codex.
- Cursor.

MVP support targets:

1. Cursor.
2. Claude Code.
3. Codex.

Other tools can be considered later after the core report flow works.

Privacy risk is higher because local logs may include prompts, responses, file paths, tool outputs, or source code. The importer must parse locally and upload only aggregate metrics.

Important distinction: providers do not generally write local logs on the user's machine. Local import means reading data produced by tools such as Cursor, Claude Code, Codex, or user apps. Each tool needs its own adapter and privacy review.

### Tool Variant Support Matrix

The product should distinguish providers from clients.

For example, "Anthropic" is the provider, while "Claude Code" or a `claude` CLI is the client. "OpenAI" is the provider, while Codex Desktop or a Codex VS Code integration is the client.

Initial support posture:

| Client / tool | Should support? | Likely source | Current confidence |
| --- | --- | --- | --- |
| Codex Desktop | Yes | Local Codex session JSONL, SQLite fallback | Medium after public-tool research plus fixtures |
| Codex VS Code / Codex Desktop with VS Code source | Yes, if it shares `.codex` session storage | Local Codex session JSONL, SQLite fallback | Medium after public-tool research plus fixtures |
| Claude Code | Yes | Local stats/logs or provider/account data | Unknown until storage is inspected |
| Cursor | Yes | Export, local telemetry, or manual | Unknown |

Do not assume that two clients for the same provider store data the same way. Each client needs its own adapter contract.

Fit for Silver Usage Report:

- Good for coverage.
- Medium confidence when logs include token fields.
- Requires careful redaction tests.
- Should not require ongoing tracking.

### Codex Local History

Early user signal: a separate Codex session was reportedly able to inspect the local machine and estimate how much had been spent.

This suggests Codex may be a strong first target for agent-assisted local introspection.

Current implementation direction:

- Prefer Codex session JSONL rollouts under `~/.codex/sessions` for local
  usage extraction.
- Existing public Codex usage tools commonly read session files rather than
  treating SQLite logs as a stable public contract.
- SQLite sources such as `state_5.sqlite` and `logs_2.sqlite` are useful
  fallback/research artifacts, but should be treated as undocumented internal
  state.

Public references found during implementation:

- `ryoppippi/ccusage` documents `@ccusage/codex` for OpenAI Codex usage
  analysis from local JSONL files.
- Tokage describes itself as a local-only Codex token tracker that scans
  `~/.codex/sessions`.
- Codex Token Usage, a VS Code extension, says it reads Codex session JSONL log
  files and extracts token usage records written at the end of sessions.
- `xiangz19/codex-ratelimit` parses `~/.codex/sessions` rollout JSONL files for
  token usage and rate-limit records.
- OpenAI's public Codex GitHub discussions point users at rollout JSONL under
  `~/.codex/sessions` for inspecting local session context.

Validated local SQLite finding from one machine:

- Codex Desktop stores local SQLite state in `.codex`.
- `logs_2.sqlite` rows from `codex_core::session::turn` can contain
  `post sampling token usage`.
- `state_5.sqlite` can contain thread-level `tokens_used` rollups.
- The source measures Codex local usage on one machine, not total OpenAI account
  usage.

Open validation questions:

- Where does Codex store usage metadata?
- Is token/spend data stored directly, or must it be reconstructed from session metadata?
- Can aggregate usage be computed without reading prompt/response text?
- Can the importer scope itself to usage metadata only?
- How does pricing get determined if the local record only contains model and token counts?
- Are the SQLite schema, module names, and log field names stable across versions?
- Are auto-review/internal approval tokens useful for Silver's report, or should they be separated from user-directed work?
- Does Codex VS Code always write to the same `.codex/logs_2.sqlite` telemetry store?

Fit for Silver Usage Report:

- Potentially high value for the Silver audience if many users use Codex.
- Medium confidence until storage format and pricing reconstruction are verified.
- Privacy-sensitive because Codex session history may include rich transcripts and tool outputs.
- Should report `source: "codex_local_telemetry"` and clearly label it as machine-local usage.

### Claude Code

Claude Code should be supported as a separate adapter from Anthropic provider APIs.

Important distinction:

- Anthropic Admin Usage/Cost API covers organization-level provider usage for admins.
- Claude Code usage may be stored locally by the client, but that storage format must be discovered.
- A personal Claude/Claude Code user may not have Anthropic Admin API access.

Open validation questions:

- Does Claude Code expose a local usage summary, stats command, or telemetry file?
- Can token usage be extracted without reading conversation transcripts?
- Can cost be derived, or only token counts?
- Are local records scoped to one machine or synced across devices?

Fit for Silver Usage Report:

- Desired adapter because Gabriel explicitly mentioned Anthropic/Claude-style usage.
- Unknown confidence until local storage is inspected.
- Should not be blocked on Anthropic Admin API because that only helps org admins.

### Cursor

Cursor is one of the three MVP tools.

Open validation questions:

- Does Cursor expose user-visible token usage or cost data?
- Does Cursor store local telemetry that includes token counts?
- Does Cursor provide exports or account-level usage screens available to a normal employee?
- Can any local usage data be read without source code, prompts, responses, or file paths?
- Is usage scoped to one machine, one workspace, or the user's Cursor account?

Fit for Silver Usage Report:

- Required MVP adapter because Cursor is one of the most common AI coding tools.
- Confidence unknown until storage/export behavior is inspected.
- Manual/paste fallback should exist if no safe local telemetry is found.

## Existing Trackers Mentioned In The Thread

Existing trackers are useful references, but they are not the first product.

### Claude Code Usage Monitors

Strength:

- Good real-time usage monitoring for Claude Code.

Why insufficient:

- Claude Code only.
- Installation required.
- Future/ongoing tracking.

### Codeburn-Style TUI Dashboards

Strength:

- Good local observability across multiple coding tools.

Why insufficient:

- Installation required.
- User-facing dashboard, not Silver-facing report intake.
- Still asks users to begin tracking and wait.

### Burntop-Style Products

Strength:

- Good inspiration for sharing progress and analytics.

Why insufficient:

- Tracker-first framing.
- Silver needs a quick reporting flow tied to its own intake/review needs.

### SDKs, Gateways, And Proxies

Strength:

- Strong future traffic measurement.
- Useful for apps already routed through them.

Why insufficient:

- Requires prior instrumentation.
- Does not recover historical usage.
- Does not work for all AI coding tools.

## Recommended Priority

Recommended order:

1. Web report session with sample/manual data.
2. CSV/JSON report import.
3. CLI/MCP importer skeleton.
4. Codex local telemetry adapter.
5. Claude Code local usage investigation.
6. Cursor local/export investigation.
7. Manual/paste fallback polish for all three tools.
8. Future tools after MVP validation.
