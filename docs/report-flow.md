# Report Flow

Silver Usage Report is web-first.

The web app is the front door. Local assistants, CLI, MCP, pasted stats, CSV, screenshots, and manual entry are import methods inside the web report flow.

## Scope

Current scope:

- Individual employee self-report.
- External participant self-report.
- Community/open-call reporting.
- Local tool usage visible to the user.
- Manual fallback when automation fails.

Out of scope:

- Company-wide imports.
- Team analytics.
- Enterprise exports.
- Provider org/admin APIs.
- Asking employees for admin keys.
- Employer surveillance or performance scoring.

## No Required Login For Reporters

The reporter should not need to create an account for the MVP.

Flow:

```text
open.silver.dev/usage-report
→ Create report session
→ Get short code / private link
→ Import or enter usage
→ Preview
→ Confirm
→ Submit to Silver
```

The report session can collect optional identity fields when Silver needs them:

- Name.
- Email.
- X handle.
- GitHub handle.
- Candidate reference.
- Campaign reference.
- Freeform label.

These fields should be optional unless a specific Silver campaign requires them.

Silver admins need login to review submitted reports. Reporters do not.

## Reporter Status And Management

When a session is created, the reporter receives a private management link. That
link is the reporter's proof and control surface for the report.

The status page shows:

- Session code.
- Current state: draft, previewed, submitted, or deleted.
- Row count and total tokens.
- Submitted timestamp.
- Candidate/campaign linkage fields that were provided.
- Delete action for the submitted aggregate data.

The private management link must include a token. The public session id or
public code alone must not allow report deletion or private status access.

## Candidate Linkage

Silver links usage reports to its candidate records through optional metadata
collected at session creation:

- `reporter_label`
- `reporter_email`
- `github_handle`
- `x_handle`
- `candidate_ref`
- `campaign_ref`

For open calls and campaigns, Silver should prefer campaign-specific links that
pre-fill `campaign_ref` or `candidate_ref`. The reporter can still submit
without login, but the admin review view must expose these fields for matching
and reconciliation.

## MVP User Flow

1. User opens `open.silver.dev/usage-report`.
2. Web app creates a report session.
3. User selects tools they use:
   - Codex Desktop / Codex VS Code.
   - Claude Code.
   - Cursor.
   - Other / manual fallback.
4. Web app recommends the best available import method for each tool.
5. User imports or enters usage.
6. Web app shows normalized preview.
7. User confirms.
8. Silver receives aggregate rows only.

## Import Methods

### Local Assistant / MCP

Best for supported local tools.

The web app gives the user a prompt, report session, and ready-to-run local command. The user pastes it into Codex, Claude Code, or a Cursor-oriented local workflow when available.

The agent inspects local usage metadata, builds normalized rows, and sends them to Silver through the MCP server after preview.

### One-Shot Collector

Best when the user is comfortable running a command.

```powershell
.\silver-usage-collector.exe submit-codex --session SESSION_ID --sessions-dir "$env:USERPROFILE\.codex\sessions" --base-url https://open.silver.dev
```

The collector should run once, show a preview, ask for confirmation, submit aggregate rows, and exit. It must not install an ongoing tracker or daemon. The Python CLI remains available for development and source checkouts, but the candidate path should not require Python.

### Pasted Stats

Best for supported tools with visible stats or export text.

The web app asks the user to paste stats output. The server or browser parser extracts fields and labels the row source.

### CSV / JSON

Best for structured user exports.

The web app validates schema, displays parsed rows, and marks source/confidence appropriately.

### Screenshot

Useful fallback when the tool only shows usage in UI.

OCR can be added later. In the MVP, screenshots can be stored as optional evidence only if the user explicitly opts in.

### Manual Entry

Universal fallback.

Manual rows are useful but low confidence. They must be labeled as manual and never mixed silently with computed rows.

## Source Router

The web app should not ask "connect your provider" first.

It should ask:

```text
What do you use?
```

Then route:

```text
Codex → MCP/CLI local telemetry.
Claude Code → local stats/log investigation or manual.
Cursor → export/local/manual.
Other → CSV/JSON/manual.
```

## Preview Requirements

Every import path must end in the same preview:

```text
Tool: Codex Desktop
Provider: OpenAI
Period: 2026-05-01 to 2026-05-04
Total tokens: 34,807,293
Source: codex_local_telemetry
Confidence: medium
Evidence: 779 rows, deduped by turn_id

This will be sent:
provider, tool, model, period, token counts, cost if available, source, confidence, evidence metadata.

This will not be sent:
prompts, responses, source code, raw logs, API keys, full file paths.
```

## Silver Review View

Silver needs an internal review view for submitted reports.

It should show:

- Reporter label or anonymous/private link.
- Reporter email, GitHub, X, candidate ref, and campaign ref when present.
- Period.
- Provider/tool/model breakdown.
- Total tokens.
- Cost if available.
- Source.
- Confidence.
- Evidence metadata.
- Warnings.

It should not show hidden prompts, raw logs, source code, or private local paths because those should never be uploaded by default.
