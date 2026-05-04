# Security and Privacy

Silver Token Ledger only works if users believe the import process is safe.

## Data Classification

### Never Upload by Default

- Prompts.
- Model responses.
- Conversation histories.
- Source code.
- Raw local logs.
- API keys.
- Environment variables.
- Full file paths.
- Unredacted project names.

### Safe to Upload by Default

- Provider name.
- Model name.
- Date or time bucket.
- Token counts.
- Request counts.
- Cost numbers.
- Cost source.
- Import warnings.

### Upload Only With Explicit Opt-In

- Project labels.
- API key labels.
- Team names.
- Machine names.
- Fine-grained hourly or minute-level activity.

## Credential Handling

Provider credentials should stay on the user's machine when possible.

Rules:

- Do not send provider API keys to Silver by default.
- Prefer the CLI importer for admin keys.
- Read credentials from environment variables or local prompt input.
- Do not write credentials to disk unless the user explicitly asks.
- Do not log credentials.
- Redact credentials from error messages.

## Import Preview

Before upload, the CLI should show:

- Providers detected.
- Date range.
- Number of rows.
- Token totals.
- Cost totals.
- Fields that will be uploaded.
- Warnings.

The user should confirm before upload.

## Retention

Default retention proposal:

- Unconfirmed import sessions expire quickly.
- Confirmed aggregate data remains until the user deletes it.
- Import tokens are short-lived and single-use.
- Raw upload payloads are not stored separately from normalized rows.

## Deletion

Users should be able to delete:

- A single import session.
- All usage data associated with their account or anonymous session.

Deletion should remove aggregate rows and warnings. If backups exist, document the backup retention period.

## Threat Model

Main risks:

- Accidental prompt upload from local logs.
- API key exposure in browser or logs.
- Replay of import session tokens.
- Duplicate imports causing misleading totals.
- Overly precise activity data revealing work patterns.
- Provider API changes leading to incorrect cost estimates.

Mitigations:

- Parse and aggregate locally.
- Validate payload schema server-side.
- Use short-lived import tokens.
- Hash provider project and API key IDs by default.
- Label estimated costs clearly.
- Keep provider adapters small and tested with fixtures.

