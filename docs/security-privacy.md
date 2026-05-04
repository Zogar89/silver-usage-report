# Security And Privacy

Silver Usage Report only works if users believe the report process is safe.

## Data Classification

### Never Upload By Default

- Prompts.
- Model responses.
- Conversation histories.
- Source code.
- Raw local logs.
- API keys.
- Environment variables.
- Full file paths.
- Unredacted project names.
- Machine names.
- Team names.
- Candidate-private notes.

### Safe To Upload By Default

- Provider name.
- Tool name, when known.
- Model name, when known.
- Date or reporting period.
- Token counts.
- Request counts.
- Cost numbers.
- Cost source.
- Confidence level.
- Report warnings.

### Upload Only With Explicit Opt-In

- Project labels.
- API key labels.
- Team labels.
- Machine labels.
- Fine-grained hourly or minute-level activity.
- Screenshots used as evidence.

## Credential Handling

Provider credentials should stay on the user's machine when possible.

Rules:

- Do not send provider API keys to Silver by default.
- Do not ask employees for provider admin keys or organization credentials.
- Read credentials from environment variables or local prompt input.
- Do not write credentials to disk unless the user explicitly asks.
- Do not log credentials.
- Redact credentials from error messages.
- Make browser-side provider connection a separate, explicit design decision.

## Report Preview

Before upload, the UI or CLI should show:

- Providers detected.
- Tools detected.
- Reporting period.
- Number of rows.
- Token totals.
- Cost totals.
- Cost source and confidence.
- Fields that will be submitted to Silver.
- Warnings.

The user should confirm before upload.

## Anti-Hallucination And Misreporting Controls

Silver Usage Report cannot fully prevent lying or mistakes, but it should prevent unsupported claims from looking verified.

Rules:

- Do not accept a freeform number without source and confidence.
- Require evidence metadata for computed imports.
- Derive or cap confidence server-side.
- Reject sensitive fields.
- Reject payloads that include raw prompts, responses, raw logs, source code, API keys, environment variables, or full local paths.
- Show warnings for manual, estimated, or low-confidence rows.
- Never mix manual and computed rows into an unlabeled total.

See [Trust model](trust-model.md).

## Manual And Low-Confidence Data

Manual reporting is acceptable as a fallback, but it must be labeled.

Rules:

- Manual entries should use `confidence: "low"` unless supported by a structured export.
- Estimated costs should never be displayed as billed cost.
- Screenshot/OCR imports should show extracted fields before submission.
- Silver review screens should make source and confidence visible.

## Retention

Default retention proposal:

- Unconfirmed report sessions expire quickly.
- Confirmed aggregate report data remains until the user or Silver policy deletes it.
- Report tokens are short-lived and single-use.
- Raw upload payloads are not stored separately from normalized rows.
- Raw logs and API keys are never stored.

## Deletion

Users should be able to delete:

- A single report session.
- All usage report data associated with their account or anonymous session.

Deletion should remove aggregate rows and warnings. If backups exist, document the backup retention period.

## Threat Model

Main risks:

- Accidental prompt upload from local logs.
- API key exposure in browser or logs.
- Replay of report session tokens.
- Duplicate reports causing misleading totals.
- Overly precise activity data revealing work patterns.
- Tool/provider changes leading to incorrect parsing or cost estimates.
- Manual estimates being mistaken for verified provider data.
- Token spend being misinterpreted as productivity.

Mitigations:

- Parse and aggregate locally.
- Validate payload schema server-side.
- Use short-lived report tokens.
- Exclude project/API key/team identifiers by default.
- Label estimated and manual costs clearly.
- Carry confidence on every report row.
- Keep provider/tool adapters small and tested with fixtures.
- Avoid leaderboard or performance-review language in product copy.
