# Provider Research

Last reviewed: 2026-05-04.

Provider APIs change often. This document captures what is known now and what should be verified during implementation.

## Anthropic

Best MVP candidate.

Anthropic documents an organization-level Usage and Cost Admin API:

- Usage endpoint: `/v1/organizations/usage_report/messages`
- Cost endpoint: `/v1/organizations/cost_report`
- Supports daily, hourly, and minute buckets for usage.
- Supports daily buckets for cost.
- Can group by model, API key, workspace, service tier, and context window.
- Requires an Admin API key, not a standard API key.
- Admin API is unavailable for individual accounts.

Important implementation detail: the key should be handled by the CLI importer unless a secure browser-side connection story is explicitly designed.

Docs:

- https://docs.anthropic.com/en/api/usage-cost-api
- https://docs.anthropic.com/en/api/admin-api/usage-cost/get-messages-usage-report

## OpenAI

Strong MVP candidate.

OpenAI documents organization usage endpoints and a costs endpoint:

- Usage endpoint family: `/v1/organization/usage/...`
- Costs endpoint: `/v1/organization/costs`
- Usage can be grouped by project, user, API key, model, batch, and service tier depending on endpoint.
- Costs can be grouped by project and line item.
- The costs endpoint is preferred for financial reconciliation.

Implementation detail: use usage endpoints for token breakdowns and costs endpoint for spend reconciliation.

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

Docs:

- https://docs.x.ai/console/usage
- https://docs.x.ai/developers/cost-tracking
- https://docs.x.ai/docs/consumption-and-rate-limits

## Local AI Coding Tools

Local tools are a good follow-up because they provide immediate value for developers:

- Claude Code logs.
- Codex logs.
- Gemini CLI logs.
- Cursor or Copilot exports where available.

Privacy risk is higher because local logs may include prompts, responses, file paths, tool outputs, or source code. The importer must parse locally and upload only aggregate metrics.

## Provider Priority

Recommended order:

1. Anthropic provider API.
2. OpenAI provider API.
3. Manual CSV/JSON import.
4. Local AI coding tool logs.
5. xAI response-log import.
6. Gemini response-log or billing-export import.
7. MCP interface over the same importer core.

