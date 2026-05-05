# Product Spec

## Summary

Silver Usage Report is a web-first reporting flow for AI token usage.

The product should answer:

- How can a user report their AI token usage to Silver quickly?
- What tools/providers contributed to that usage?
- How much of the report is actual provider data versus estimated or manual data?
- Can Silver compare reports across people who use different AI tools?
- Can the user submit useful metrics without exposing private data?

The product is not primarily a personal finance dashboard. A dashboard can exist, but the core job is intake: make usage reporting easy, trustworthy, and normalized.

## Problem Discovery

The X thread around Silver's ask surfaced several rejected paths. The quote tweet came from Deel's "Token spend is coming for your performance review" article, so the broader category context is AI usage becoming part of workforce, performance, and management conversations.

The product should respond to that context without copying the framing. Silver Usage Report should make token reporting transparent, user-controlled, and source-labeled. It should not imply that token spend alone equals productivity.

### Existing Claude Code Trackers

People suggested real-time Claude Code usage monitors. These help an individual observe Claude Code usage, but they are too narrow for Silver's need.

Reason rejected:

- Works for Claude Code only.
- Requires local installation.
- Measures ongoing/future usage.
- Does not automatically produce a Silver-ready report.

### TUI Dashboards Like Codeburn

Codeburn-style tools show where AI coding tokens go across tools like Claude Code, Codex, and Cursor.

Reason rejected:

- Still requires users to install software.
- Still assumes ongoing tracking.
- Silver would have to wait for users to collect data.
- It is built as user-facing observability, not Silver-facing report intake.

### OpenCode `/stats`

OpenCode can show usage stats for OpenCode users.

Reason rejected:

- It does not work for everyone.
- Silver needs provider/tool coverage across heterogeneous workflows.

### Existing AI Usage Products

Products like Burntop may provide AI usage tracking and sharing.

Reason rejected or insufficient:

- Useful as inspiration, but likely still tracker-first.
- Silver needs a purpose-built flow for report submission and normalization.
- The key user action is "submit my usage to Silver," not "adopt a new analytics product."

### AI SDKs, Gateways, And Proxies

SDK/gateway tracking can measure traffic that passes through the gateway.

Reason rejected or deferred:

- Captures future traffic only.
- Requires prior instrumentation.
- Does not help users who already used Claude Code, Cursor, OpenCode, Gemini, Grok, or direct provider consoles outside that gateway.

### Candidate Tracking / ATS Integration

Silver already tracks candidates internally.

Reason rejected:

- The missing piece is not candidate status.
- The missing piece is external usage reporting.

## Users

Primary users:

- Developers who want to submit AI usage to Silver.
- Silver community members participating in usage challenges, benchmarks, or open calls.
- External participants who use different AI tools.

Secondary users:

- Silver admins reviewing submitted usage reports.
- Maintainers adding provider and tool adapters.
- Developers who want a local preview before sharing anything.

## Goals

- Let a user submit a useful usage report within minutes.
- Avoid requiring ongoing background tracking.
- Support one-shot local import for tools that expose local usage data.
- Provide manual/CSV fallback when automation is unavailable.
- Avoid relying on provider org/admin APIs.
- Normalize data across providers and tools.
- Preserve a clear privacy boundary.
- Provide a healthier alternative to opaque HR/performance-surveillance framing.
- Keep the implementation open source.

## Non-Goals

- Replacing provider billing dashboards.
- Building a full spend management suite.
- Acting as a proxy for all future AI traffic in the first version.
- Storing prompts or conversations.
- Ranking users by token spend without context.
- Treating token spend as a direct performance score.
- Managing team budgets or enforcing spend limits in the first version.
- Building a desktop app.
- Solving Silver's internal candidate tracking.
- Importing company-wide or team-wide enterprise usage.
- Asking employees for provider admin keys or organization billing exports.

## Core User Flow

1. User visits the Silver Usage Report web app.
2. The app creates a short-lived report session.
3. User chooses an import method:
   - Run the one-shot CLI importer.
   - Paste stats from a supported tool.
   - Upload CSV/JSON.
   - Enter manual totals for unsupported tools.
4. User previews normalized usage before final submission.
5. User sees confidence and source labels for each row.
6. User confirms submission.
7. Silver receives aggregate report data.
8. User can delete the submitted report.

Reporter login is not required for the MVP. The report session should use a short code and private management link. Silver admins need login for the internal review view.

The private management link lets the reporter verify submission status, inspect
aggregate totals, and delete submitted aggregate data. It must require the
private token generated at session creation.

Silver links reports to candidates through optional identity metadata collected
at session creation: name/label, email, GitHub handle, X handle, candidate ref,
and campaign ref. These fields are visible in admin review and detail pages.

## MVP Screens

- Report start screen.
- Report session page.
- Import method picker.
- Tool-specific import instructions.
- CLI instructions page.
- CSV/JSON/manual fallback form.
- Report preview table.
- Confirmation screen.
- Silver admin report review.
- Silver admin report detail.
- Reporter private status/management page.
- Data deletion page.

## Web Design Direction

The Silver Usage Report web UI must follow the existing Open Silver visual language at `https://open.silver.dev/`.

Open Silver is the design reference for:

- Brand placement, navigation, and page rhythm.
- The "Para talento" / "Para empresas" information architecture style when relevant.
- Link and product-card presentation.
- Typography scale, spacing, borders, button treatment, and neutral page layout.
- Plain, direct copy that reads like part of the Silver ecosystem rather than a standalone SaaS dashboard.

Silver Usage Report should feel like a native Open Silver tool hosted under `open.silver.dev`, not a separate branded product. Any custom UI for report sessions, import options, previews, confirmations, and admin review must adapt the Open Silver design system before introducing new visual patterns.

## Language Direction

The product UI is Spanish-first. Reporter-facing and admin-facing web copy must
be written in Spanish, including navigation, page headings, form labels, helper
text, banners, warnings, empty states, table headings, and action buttons.

Technical contracts may remain in English where precision matters: API field
names, enum values, CLI commands, provider/tool identifiers, package names, and
third-party product names.

## MVP Import Strategy

The MVP should support multiple ways for an individual to report usage:

- Local MCP/assistant import for supported tools.
- One-shot CLI helper.
- Pasted stats or exports when supported.
- CSV/JSON import.
- Manual entry.
- Optional screenshot evidence only with explicit opt-in.

The MVP should not ask employees for provider admin keys or organization credentials.

## Trust Requirements

Every submitted row must include:

- Source.
- Confidence.
- Evidence metadata when not manual.
- Preview confirmation.

The server should reject raw prompts, responses, source code, API keys, raw logs, environment variables, and full local paths.

## Normalized Report Model

```ts
type UsageReportRow = {
  provider: "anthropic" | "openai" | "gemini" | "xai" | "other";
  tool?: "claude_code" | "cursor" | "codex" | "other";
  source: "codex_local_telemetry" | "tool_stats_paste" | "local_log" | "csv" | "json" | "manual" | "screenshot_ocr" | "response_log";
  periodStart: string;
  periodEnd: string;
  periodWidth: "1h" | "1d" | "1w" | "1m" | "custom";
  model?: string;
  requestCount?: number;
  inputTokens?: number;
  outputTokens?: number;
  cachedInputTokens?: number;
  cacheCreationInputTokens?: number;
  reasoningTokens?: number;
  totalTokens?: number;
  costUsd?: number;
  costSource: "provider_actual" | "provider_report" | "estimated" | "manual" | "unknown";
  confidence: "high" | "medium" | "low";
  evidence?: EvidenceMetadata;
};

type EvidenceMetadata = {
  adapter?: string;
  adapterVersion?: string;
  rowCount?: number;
  dedupeKey?: string;
  queryFingerprint?: string;
  warnings?: string[];
};
```

## Report Contract

All import paths should produce the same normalized payload:

```ts
type UsageReportPayload = {
  reportSessionId: string;
  generatedAt: string;
  schemaVersion: "2026-05-04";
  rows: UsageReportRow[];
  warnings: ReportWarning[];
  userConfirmation: {
    previewShown: boolean;
    confirmedAt: string;
  };
};

type ReportWarning = {
  provider?: string;
  tool?: string;
  code: string;
  message: string;
};
```

## UX Copy Principles

- Say exactly what data will be submitted to Silver.
- Show a preview before upload.
- Say "actual cost" only when the provider returns billed cost.
- Say "estimated cost" when calculating from token prices.
- Label manual entries clearly.
- Avoid implying token spend equals productivity.
- Avoid performance-review scare language.
- Make deletion visible.
