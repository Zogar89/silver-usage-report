# Discovery Notes

Last updated: 2026-05-04.

This file captures product discovery decisions before implementation starts.

## Current Understanding

Silver does not primarily need another token tracker.

Silver needs a way for external people to report their AI token usage quickly, across many tools and providers, with enough source/confidence metadata that Silver can compare reports without overtrusting rough estimates.

The best product framing is:

```text
Silver Usage Report
```

not:

```text
Silver Token Ledger
```

The first user action should be "submit my usage to Silver," not "start tracking my usage from now on."

## Evidence From The X Conversation

The original ask said Silver needed a token spending tracker. It quoted Deel's article "Token spend is coming for your performance review," which frames AI token usage as a future performance-review signal.

Deel's article argues that companies bought Claude, Cursor, ChatGPT Enterprise, Gemini, Copilot, and similar tools but often cannot tell who is getting value from them. It positions token usage as an adoption/proficiency signal when placed next to KPIs, competencies, check-ins, and performance reviews.

This matters because Silver's opportunity is not just "track tokens." The sharper opportunity is to give Silver and its community a credible, privacy-preserving way to collect usage data before the category gets defined by HR/performance tooling.

Reference:

- https://www.deel.com/blog/token-spend-is-coming-for-your-performance-review/

The replies revealed the sharper requirement.

People showed:

- Claude Code usage monitor.
- Codeburn-style local TUI usage dashboard.
- OpenCode `/stats`.
- Burntop-style AI usage tracking.
- AI SDK/gateway approaches.
- Candidate tracking / ATS integration idea.

Silver's responses clarified the constraints:

- "Tirame tu usage" implies the desired output is the user's usage data, not just a tool recommendation.
- "Todo eso implica que le pida a la gente que se instale software" rejects tracker-first solutions that require installation.
- "Ademas es ongoing -> tengo que esperar un mes" rejects solutions that only collect future data.
- "Quiero una experiencia web..." establishes web as the preferred front door.
- "Conectan su cuenta de anthropic/gemini/grok lo que sea que usen..." implies provider/tool abstraction, not one narrow tool.
- "Tambien podria ser un mcpcito..." makes CLI/MCP acceptable as a one-shot helper, not as the primary product identity.
- "Tiene que funcionar para todos" rejects single-tool stats as the whole solution.
- "Esto lo trackeamos nosotros bien" rejects candidate/ATS tracking as the missing piece.
- "Quiero algo que la gente pueda reportar sus tokens" confirms the core job is report intake.

## Product Requirements Derived So Far

- Web-first entry point under `open.silver.dev`.
- One-shot, not ongoing.
- No waiting period to collect new data.
- Works across heterogeneous providers and tools.
- Does not depend on the user having installed a tracker previously.
- Lets users submit a report even when automatic import is unavailable.
- Labels every row by source and confidence.
- Does not upload prompts, responses, source code, raw logs, or API keys by default.
- Provides Silver a review/admin view over submitted reports.
- Avoids framing token spend as a direct productivity or performance score.
- Preserves context: token usage is a signal, not the whole story.

## Competitive / Category Context

Deel Engage frames AI token usage as part of talent management and performance review workflows.

Important observed claims from the Deel article:

- Companies have access and license data, but not enough visibility into meaningful AI usage.
- Token usage data often lives in IT dashboards, away from performance conversations.
- Deel wants AI adoption data to sit beside KPIs, competencies, check-ins, and feedback.
- Deel says Engage currently integrates with Anthropic Claude, Cursor, and GitHub Copilot, with Microsoft Copilot and Gemini planned.
- Deel notes that OpenAI enterprise analytics need more work from OpenAI's side.

Implications for Silver:

- Silver should not copy the HR-performance framing blindly.
- Silver can position around open, user-controlled reporting instead of employer surveillance.
- The product should collect objective usage metrics while clearly warning that token spend alone is gameable and incomplete.
- Confidence/source labels become strategically important, not just technical metadata.
- A lightweight open-source reporting flow can be a counter-position to closed HR suites.

## What We Should Not Assume

### Not All Providers Have Useful OAuth

Do not assume "connect account" means OAuth for every provider.

Anthropic and OpenAI usage/cost paths are primarily API-key/admin/org-key driven, not a universal OAuth flow for all users.

### Anthropic Admin Usage API Is Not Universal

Anthropic's Usage and Cost Admin API is useful but limited:

- It requires an Admin API key.
- It is for organizations.
- It is unavailable for individual accounts.

Therefore it is out of scope for the current employee-focused product. It may be useful later only if Silver explicitly decides to support company/admin reports.

## Scope Decision: No Enterprise Mode

Current decision: do not build an enterprise/company/admin mode.

Reason:

- The people Gabriel wants to collect from are employees or external participants.
- Employees usually do not have Anthropic Admin API keys, OpenAI org admin keys, Google Cloud billing exports, or xAI team analytics exports.
- Asking employees for admin/provider credentials would fail and create trust problems.
- Company-wide usage import is a different product with different permissions, privacy, and legal risks.

Current product scope:

```text
Individual self-report
→ local tool telemetry
→ local stats commands
→ pasted stats
→ CSV/JSON
→ screenshots
→ manual fallback
```

Out of scope for now:

```text
Organization-wide usage import
Team analytics
Provider org/admin APIs
Enterprise exports
Gateway/proxy logs for whole companies
Per-employee employer surveillance
```

### Providers Do Not Store Logs Locally

Providers do not generally write usage logs to the user's machine.

Local data comes from tools or apps, not from the provider itself:

- Claude Code, Codex, and Cursor may have local logs, stats, summaries, or exports, but each must be investigated separately.
- Logs may contain sensitive prompts, responses, file paths, or source code.

Local parsing must be adapter-specific and privacy-reviewed.

### Manual Data Is Not Failure

Manual, paste, screenshot, CSV, or JSON data may be the only universal MVP path.

The product can still be useful if manual rows are clearly labeled as low confidence.

## Source Strategy

Use a source router, not a single import method.

```text
User selects provider/tool
→ Web recommends best available source
→ User imports or enters data
→ System normalizes rows
→ Preview shows source/confidence
→ User confirms submission
```

Recommended source hierarchy:

1. Provider usage/cost API or structured official export.
2. Tool-specific stats or local logs that include token/cost fields.
3. CSV/JSON export.
4. Pasted stats or copied console output.
5. Screenshot/OCR.
6. Manual entry.

## New Signal: Agent-Assisted Local Introspection

User reported asking another Codex session how much had been spent; that session analyzed the local machine and returned a usage/spend number.

This is an important product signal:

- A coding agent can potentially inspect local tool state and summarize usage without requiring an always-on tracker.
- This supports the "one-shot CLI/MCP helper" idea.
- It may work especially well for Codex itself because Codex has local session history and workspace context.
- It should be treated as an import method with strong privacy constraints, because local session history can contain prompts, tool outputs, file paths, source code, and other sensitive data.

Product implication:

```text
Web report session
→ "Use local assistant/importer"
→ Agent/CLI inspects supported local sources
→ Preview aggregate usage locally
→ User confirms upload
→ Silver receives only normalized rows
```

This should not replace the web-first flow. It is a promising assisted import path inside it.

### What The Codex Session Actually Found

After reading the referenced Codex thread, the useful mechanism was:

- It inspected `C:\Users\Gabriel\.codex\logs_2.sqlite`.
- It found token telemetry in local Codex Desktop logs.
- The most useful events were `codex_core::session::turn` log rows containing `post sampling token usage`.
- Those rows include fields such as:
  - `turn_id`
  - `model`
  - `total_usage_tokens`
  - `estimated_token_count`
  - local timestamp / thread context
- It deduplicated by `turn_id`.
- It filtered by local month boundary in `America/Buenos_Aires`.
- It grouped by model and day.

The reported result for May 2026 at that moment was:

- `34,807,293` total Codex Desktop tokens.
- `779` unique turns.
- `27,321,779` tokens attributed to `codex-auto-review`.
- `7,485,514` tokens attributed to normal work models:
  - `gpt-5.5`: `5,359,545`
  - `gpt-5.4-mini`: `1,741,065`
  - `gpt-5.4`: `384,904`

Important limits:

- This is local Codex Desktop usage, not official OpenAI account billing.
- It may miss usage from other devices, other OpenAI products, browser usage, API usage, or deleted logs.
- It gives token counts and model labels, not necessarily billed cost.
- Cost would need a separate pricing table and careful handling of cached/reasoning tokens if available.
- The database may contain sensitive logs, so an importer must query only telemetry rows and avoid reading transcript content.

Product implication:

- Codex local usage import is plausible.
- Confidence should be `medium` until the storage format is validated across machines/versions.
- Source should be something like `codex_local_telemetry`.
- The preview should say "Codex Desktop local usage on this machine," not "OpenAI total account usage."

## Client Variant Support

The project should support client/tool variants explicitly, not just provider names.

Questions raised:

- Does the reporting flow support Claude Code and a `claude` CLI?
- Does it support Codex and Codex when used through VS Code?

Current answer:

- The architecture supports them as separate adapters.
- Codex has one-machine evidence via local `.codex/logs_2.sqlite` telemetry.
- The referenced Codex session appears to have `originator: Codex Desktop` and `source: vscode`, suggesting VS Code-hosted Codex may share the same telemetry store. This must be validated.
- Claude Code / `claude` CLI support is desired but unvalidated. We need to inspect whether they expose safe local usage metadata without reading transcripts.
- Anthropic provider Admin API does not replace Claude Code / CLI adapters because it only helps organization admins and is out of current scope.

Product implication:

```text
Provider: Anthropic
Client: Claude Code

Provider: OpenAI
Clients: Codex Desktop, Codex VS Code

Provider: mixed / unknown until validated
Client: Cursor
```

Each client gets its own source label and confidence.

## Current Path Recommendation

Start with Web Report First.

Build:

- Report session.
- Import method picker.
- Manual entry.
- CSV/JSON paste or upload.
- Preview table with source/confidence.
- Confirmation.
- Silver review view.

Then add:

- One-shot CLI helper.
- Cursor, Claude Code, and Codex adapters.
- MCP-assisted importer over the same strict report contract.

The implementation docs that capture this direction are:

- [Report flow](report-flow.md)
- [MCP-assisted import](mcp-assisted-import.md)
- [Technical architecture](technical-architecture.md)
- [Trust model](trust-model.md)

## Open Questions

- Which tools should be first in the import method picker?
- Does Claude Code expose local token/cost summaries without reading sensitive transcripts?
- Does Codex expose local usage metadata in session logs consistently enough?
- Can a Codex agent reliably compute usage/spend from local Codex history without reading or uploading sensitive transcript content?
- Can `codex_core::session::turn` / `post sampling token usage` telemetry be relied on across Codex Desktop versions?
- Do Codex local telemetry rows include enough cached/reasoning token detail to estimate cost accurately?
- Does Codex VS Code always share the same local telemetry store as Codex Desktop?
- Does Claude Code expose safe local usage metadata?
- Does Cursor expose user-accessible token/cost data?
- Does Silver need reports tied to a declared identity on day one, or can reports start anonymous/private-link only?
- What minimum report fields does Silver need to make the report useful?
