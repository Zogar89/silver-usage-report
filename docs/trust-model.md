# Trust Model

Silver Usage Report should not pretend every submitted number is equally reliable.

The product cannot fully prevent lying or hallucination. It can make source quality explicit, limit what is accepted, and prevent freeform claims from being treated as verified data.

## Core Rule

Never accept "I used X tokens" as a standalone truth.

Accept:

```text
usage rows
+ source
+ confidence
+ evidence metadata
+ preview confirmation
```

## Confidence Levels

Confidence is calculated from source and evidence. The client or LLM should not freely choose it.

| Source | Confidence |
| --- | --- |
| Provider official API or verified official export | High, out of current MVP scope for employees |
| Deterministic local telemetry adapter | Medium |
| Tool stats command or structured paste | Medium |
| CSV/JSON from user export | Medium or low depending on schema |
| Screenshot/OCR | Low or medium depending on parser confidence |
| Manual entry | Low |
| LLM estimate without evidence | Reject or low with warning |

## Evidence Requirements

Every non-manual source should include evidence metadata.

Examples:

- Adapter name/version.
- Row count.
- Dedupe key.
- Date range.
- Query fingerprint.
- Source hash when safe.
- Warning list.

Do not upload the raw source by default.

## Server-Side Validation

The server should validate:

- Required fields.
- Allowed source values.
- Non-negative token counts.
- Valid date ranges.
- Reasonable period length.
- Duplicate report rows.
- Disallowed sensitive fields.
- Payload size limits.
- Confidence derived from source, not client trust.

Sensitive fields to reject:

- Prompts.
- Responses.
- Raw logs.
- Source code.
- API keys.
- Environment variables.
- Full local paths.
- Conversation transcript content.

## Preview Before Submit

Preview is mandatory.

The user must see:

- Provider.
- Tool.
- Period.
- Token counts.
- Cost if available.
- Source.
- Confidence.
- Evidence metadata.
- Warnings.
- What will and will not be sent.

Submission should happen only after confirmation.

## LLM Role

The LLM can orchestrate. It should not be the calculator of record.

Good:

```text
LLM finds supported source
→ runs deterministic adapter
→ shows preview
→ submits structured rows
```

Bad:

```text
LLM reads some logs
→ guesses a number
→ submits high-confidence report
```

## Handling Manual Reports

Manual data is allowed because the product must work for everyone.

Rules:

- Always label manual rows as `confidence: "low"`.
- Show manual rows separately in Silver review.
- Do not combine manual and computed rows into a single unlabeled total.
- Ask for period and source note.
- Allow optional evidence attachment only with explicit user opt-in.

## Handling Cost

Cost is harder than tokens.

Rules:

- Local telemetry token counts are not billing.
- Estimated cost needs a pricing table and model-specific rules.
- Cached/reasoning tokens may need different pricing.
- If cost cannot be computed safely, use `costSource: "unknown"`.
- Never show estimated cost as actual billed spend.

## Admin Review

Silver review should group reports by confidence:

- Computed from local telemetry.
- Parsed from tool stats.
- Imported from CSV/JSON.
- Manual.

Review UI should show warnings and source metadata before any comparison or leaderboard.

## Product Framing

Token spend is a signal, not a performance score.

The product should avoid:

- Ranking people purely by tokens.
- Saying high token spend means high productivity.
- Hiding confidence/source labels.
- Employer-surveillance framing.

Silver Usage Report should be transparent, consent-based, and honest about uncertainty.
