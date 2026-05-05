# Silver Usage Report Agent-Assisted Import

You are helping a developer prepare an aggregate AI usage report for Silver.

The goal is to produce normalized usage rows and show a preview before submit.
The report is for aggregate usage only. It is not a prompt, transcript, source
code, or raw log export.

## Privacy Boundary

Do not upload prompts.
Do not upload responses.
Do not upload source code.
Do not upload raw logs.
Do not upload API keys.
Do not upload environment variables.
Do not upload full local file paths unless the user explicitly opts in.

If a source contains sensitive material, summarize only aggregate metrics and
record a warning. If aggregate metrics cannot be separated safely, stop and ask
the user to use manual entry.

## Required Flow

1. Identify the source type: local telemetry, tool stats paste, CSV, JSON, or manual.
2. Convert the data into `UsageReportRow` objects.
3. Add source and confidence labels.
4. Show a preview before submit.
5. Ask for explicit confirmation before uploading.
6. Submit only normalized aggregate rows.

## UsageReportRow Shape

```json
{
  "provider": "openai",
  "tool": "codex",
  "source": "json",
  "period_start": "2026-05-01T00:00:00Z",
  "period_end": "2026-05-02T00:00:00Z",
  "period_width": "1d",
  "model": "gpt-5.5",
  "request_count": 12,
  "input_tokens": 1000,
  "output_tokens": 500,
  "cached_input_tokens": 0,
  "reasoning_tokens": 0,
  "total_tokens": 1500,
  "cost_source": "manual",
  "confidence": "medium",
  "evidence": {
    "adapter": "codex_local",
    "adapter_version": "0.1.0",
    "row_count": 12,
    "warnings": []
  }
}
```

## Confidence Rules

- `high`: provider or tool aggregate export with clear dates and model labels.
- `medium`: parsed local telemetry or structured CSV/JSON supplied by the user.
- `low`: manual estimates, screenshots, or copied stats without machine-readable evidence.

Manual rows must stay low confidence even if the user is confident.

## Preview Summary

Before submit, show:

- Row count.
- Total tokens.
- Providers/tools included.
- Period covered.
- Confidence breakdown.
- Warnings.
- A reminder that only aggregate usage data will be submitted.

Use the Silver Usage Report API, CLI, or MCP helper to preview before submit.
