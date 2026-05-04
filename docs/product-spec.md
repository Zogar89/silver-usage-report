# Product Spec

## Summary

Silver Token Ledger is a web-first token spending tracker for developers and small teams using multiple AI providers and AI coding tools.

The product should answer:

- How many tokens did I use?
- How much did it cost?
- Which provider and model drove the spend?
- What changed this week or month?
- Can I share this usage with Silver without exposing my private data?

## Users

Primary users:

- Developers using AI coding agents or provider APIs.
- Small teams that want a quick usage snapshot.
- Silver community members who want to participate in an open benchmark or usage challenge.

Secondary users:

- Maintainers adding provider integrations.
- Silver admins reviewing aggregate usage submissions.

## Goals

- Provide a useful usage dashboard within minutes.
- Support historical imports where provider APIs allow it.
- Support one-shot local import without requiring a long-running daemon.
- Normalize usage across providers.
- Make the privacy boundary clear enough that users trust it.
- Keep the implementation open source.

## Non-Goals

- Replacing provider billing dashboards.
- Acting as a proxy for all future AI traffic in the first version.
- Storing prompts or conversations.
- Managing team budgets or enforcing hard spend limits in the first version.
- Building a desktop app.

## Core User Flow

1. User visits the Silver Token Ledger web app.
2. The app creates a short-lived import session.
3. User chooses an import method:
   - Connect provider admin key in browser.
   - Run the one-shot CLI importer.
   - Upload CSV/JSON.
4. User previews normalized usage before final submission.
5. Dashboard shows spend and token breakdowns.
6. User can delete the imported data.

## MVP Screens

- Landing/import screen.
- Import session page.
- Provider connection form.
- CLI instructions page.
- Import preview table.
- Dashboard overview.
- Provider/model breakdown.
- Data deletion page.

## Normalized Usage Model

```ts
type UsageBucket = {
  provider: "anthropic" | "openai" | "gemini" | "xai" | "other";
  source: "provider_api" | "local_log" | "csv" | "manual";
  bucketStart: string;
  bucketEnd: string;
  bucketWidth: "1m" | "1h" | "1d" | "custom";
  model?: string;
  projectId?: string;
  apiKeyId?: string;
  requestCount?: number;
  inputTokens?: number;
  outputTokens?: number;
  cachedInputTokens?: number;
  cacheCreationInputTokens?: number;
  reasoningTokens?: number;
  audioInputTokens?: number;
  imageInputTokens?: number;
  costUsd?: number;
  costSource: "provider_actual" | "provider_report" | "estimated" | "unknown";
};
```

## Import Contract

The CLI and browser importers should produce the same normalized payload:

```ts
type ImportPayload = {
  importSessionId: string;
  generatedAt: string;
  schemaVersion: "2026-05-04";
  buckets: UsageBucket[];
  warnings: ImportWarning[];
};

type ImportWarning = {
  provider: string;
  code: string;
  message: string;
};
```

## UX Copy Principles

- Say exactly what data will be uploaded.
- Show a preview before upload.
- Use "actual cost" only when the provider returns billed cost.
- Use "estimated cost" when calculating from token prices.
- Make deletion visible.

