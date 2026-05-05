# MCP-Assisted Import

Status: initial helper contract added.

The repository now includes:

- `mcp_server/main.py`: dependency-free helper functions for `preview_report`, `submit_report`, and `get_report_status`.
- `preview_codex_local(logs_db_path)`: explicit-path helper for Codex local telemetry previews.
- `mcp_server/prompts/agent-assisted-import.md`: the first prompt template for Codex, Claude Code, Cursor, or another local agent.
- Shared validation through `app.schemas.usage_report`.

The current helper layer is intentionally transport-agnostic. The next step is
to bind these functions to a concrete Python MCP server package once the
deployment target and MCP runtime are chosen.

The required user flow remains:

1. Inspect only local aggregate usage sources.
2. Produce normalized rows.
3. Show preview before submit.
4. Ask for explicit confirmation.
5. Submit only aggregate rows.

The helper layer must reject or avoid prompts, responses, source code, raw logs,
API keys, environment variables, and full local paths.

## Codex Local Preview

The Codex helper is intentionally explicit-path only. It must not scan the user's
home directory or auto-discover `.codex` files without the user's consent.

The primary Codex source is now the local session JSONL directory
`~/.codex/sessions`, because existing Codex usage tools commonly parse session
rollouts rather than treating `logs_2.sqlite` as a stable public contract.
SQLite files remain best-effort fallbacks only.

CLI preview:

```powershell
python -m cli.main preview-codex --sessions-dir "$env:USERPROFILE\.codex\sessions"
```

CLI submit:

```powershell
python -m cli.main submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url http://localhost:8002
```

The legacy SQLite adapter can query `state_5.sqlite` thread rollups, or
`logs_2.sqlite` rows that match:

- `target = "codex_core::session::turn"`
- `feedback_log_body` containing `post sampling token usage`

It ignores non-usage rows and excludes events that look like internal approval or
auto-review usage. It emits `source: "codex_local_telemetry"` and confidence
`medium`, because local telemetry is useful but not official provider billing.

MCP helpers expose both preview and submit paths:

- `preview_codex_local(logs_db_path)`
- `submit_codex_local(report_session_id, logs_db_path, base_url, confirmed=True)`

MCP-assisted import is the main automation idea for the employee-focused product.

It matches the thread's direction:

```text
Web-first
plus
"paste this prompt in your terminal/agent"
plus
one-shot report generation
```

## Concept

Silver publishes an MCP server that accepts structured usage report rows.

The web app creates a report session and generates a prompt. The user pastes the prompt into their local coding agent.

The agent inspects local usage sources that the user can access, shows a preview, and submits only aggregate rows through the MCP server.

## Example User Flow

```text
1. User opens open.silver.dev/usage-report.
2. Web app creates report session ABC123.
3. Web app shows a prompt:
   "Calculate my local AI usage for the last 30 days..."
4. User pastes prompt into Codex / Claude Code / Cursor-oriented local workflow.
5. Agent finds local usage telemetry or stats.
6. Agent calls silver_usage_report.preview_report.
7. User sees preview in the web app or agent.
8. User confirms.
9. Agent calls silver_usage_report.submit_report.
```

## MCP Tools

Initial MCP tool surface:

```text
silver_usage_report.preview_report
silver_usage_report.submit_report
silver_usage_report.get_report_status
```

Later:

```text
silver_usage_report.detect_supported_sources
silver_usage_report.validate_rows
```

## Strict Schema

The MCP must not accept freeform summaries as proof.

Each row should match the normalized report model:

```ts
type UsageReportRow = {
  provider: "anthropic" | "openai" | "gemini" | "xai" | "other";
  tool?: "claude_code" | "cursor" | "codex" | "other";
  source:
    | "codex_local_telemetry"
    | "tool_stats_paste"
    | "local_log"
    | "csv"
    | "json"
    | "manual"
    | "screenshot_ocr"
    | "response_log";
  periodStart: string;
  periodEnd: string;
  model?: string;
  inputTokens?: number;
  outputTokens?: number;
  cachedInputTokens?: number;
  reasoningTokens?: number;
  totalTokens?: number;
  costUsd?: number;
  costSource: "provider_actual" | "estimated" | "manual" | "unknown";
  confidence: "high" | "medium" | "low";
  evidence: EvidenceMetadata;
};
```

## Evidence Metadata

Evidence metadata is required so Silver can distinguish computed reports from guesses.

Examples:

```ts
type EvidenceMetadata = {
  adapter?: string;
  adapterVersion?: string;
  rowCount?: number;
  dedupeKey?: string;
  periodSource?: string;
  sourceHash?: string;
  queryFingerprint?: string;
  warnings?: string[];
};
```

For Codex local telemetry:

```json
{
  "adapter": "codex_local_telemetry",
  "adapterVersion": "0.1.0",
  "rowCount": 779,
  "dedupeKey": "turn_id",
  "queryFingerprint": "codex_core_session_turn_post_sampling_v1"
}
```

## Prompt Template

The prompt should be generated by the web app and include the report session code.

Example:

```text
Create a Silver Usage Report for the last 30 days.

Rules:
- Use only usage metadata, stats, or local telemetry available to my user.
- Do not read or send prompts, responses, source code, raw logs, environment variables, API keys, full file paths, or secrets.
- If you cannot find reliable usage metadata, say so and ask me to use manual entry.
- Produce normalized rows with provider, tool, model, period, token counts, cost if available, source, confidence, and evidence metadata.
- Show me a preview first.
- Only submit to Silver after I confirm.

Report session: ABC123
```

## What The Agent Can Do

The agent may:

- Locate known telemetry files.
- Run deterministic adapter code.
- Count rows.
- Deduplicate by known IDs.
- Group by day/model/tool.
- Produce source/confidence labels.
- Call the MCP preview/submit tools.

The agent should not:

- Estimate from vibes.
- Upload transcript content.
- Upload raw logs.
- Upload secrets.
- Claim provider billing accuracy from local telemetry.
- Mark its own guesses as high confidence.

## Codex First Adapter

Codex is a strong first adapter candidate because one local test found usage metadata in:

```text
C:\Users\Gabriel\.codex\logs_2.sqlite
```

Useful rows:

```text
target = codex_core::session::turn
feedback_log_body contains "post sampling token usage"
```

Useful fields:

- `turn_id`
- `model`
- `total_usage_tokens`
- `estimated_token_count`

Required label:

```text
Codex Desktop local usage on this machine.
```

Not:

```text
OpenAI total account billing.
```

## Why MCP Instead Of Tracker

MCP-assisted import avoids the rejected paths from the thread:

- No ongoing daemon.
- No waiting one month.
- No universal provider OAuth assumption.
- No employee admin keys.
- No tracker-first product identity.

It lets each local agent help inspect its own environment while Silver keeps a strict report contract.
