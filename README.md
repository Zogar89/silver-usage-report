# Silver Token Ledger

Silver Token Ledger is an open source usage importer and dashboard for AI token spend.

The goal is simple: a developer opens a web page, connects or imports their provider usage, and gets a clear view of token consumption and spend across tools like Anthropic, OpenAI, Gemini, xAI/Grok, and local AI coding clients.

## Why this exists

AI spend is scattered across provider consoles, local CLI logs, API responses, billing exports, and team dashboards. Existing token trackers usually solve one side of the problem:

- Local apps parse machine logs, but require installation and ongoing background processes.
- Provider dashboards show billing, but each provider is isolated.
- Proxies can track future traffic, but do not recover historical usage.

Silver Token Ledger should make the first experience fast:

1. Open the web app.
2. Create an import session.
3. Run a one-shot local command or connect a provider API key.
4. Review normalized usage in one dashboard.

No prompts, conversations, source code, or provider API keys should be stored by default.

## Proposed MVP

The first useful version should focus on trust and a tight path to value:

- Web dashboard hosted under `open.silver.dev`.
- Import session flow with a short-lived upload token.
- One-shot CLI importer.
- Anthropic usage and cost import.
- OpenAI usage and cost import.
- Manual CSV/JSON import.
- Normalized daily usage table by provider, model, and date.
- Basic charts for spend, input tokens, output tokens, cached tokens, and reasoning tokens.

Gemini and xAI/Grok can follow once the ingestion path is validated. Their public APIs are less uniform for account-wide usage than Anthropic/OpenAI, so the first implementation should support them through response logs, exports, or local adapters.

## Privacy Promise

By default, the importer uploads only aggregated usage metrics:

- Provider name
- Model name
- Date or time bucket
- Input tokens
- Output tokens
- Cached tokens
- Reasoning tokens
- Request count
- Estimated or actual cost

It must not upload:

- Prompts
- Responses
- Conversation histories
- Source code
- API keys
- Raw provider logs
- File paths, unless the user explicitly opts in

## Repo Structure

```text
.
├── README.md
├── CONTRIBUTING.md
├── LICENSE
└── docs
    ├── architecture.md
    ├── product-spec.md
    ├── provider-research.md
    ├── roadmap.md
    └── security-privacy.md
```

## Candidate CLI Flow

```bash
npx -y @silver/token-ledger import
```

Expected flow:

1. The web app shows a session code or deep link.
2. The CLI scans supported local sources and asks which providers to import.
3. Provider keys are read from environment variables or entered locally.
4. The CLI previews the aggregate data before uploading.
5. The web dashboard updates immediately.

## Links

- Open Silver: https://open.silver.dev
- Open Silver repository: https://github.com/silver-dev-org/open-silver
- Anthropic Usage and Cost API: https://docs.anthropic.com/en/api/usage-cost-api
- OpenAI Usage and Costs API: https://platform.openai.com/docs/api-reference/usage/costs
- Gemini token usage metadata: https://ai.google.dev/gemini-api/docs/tokens
- xAI cost tracking: https://docs.x.ai/developers/cost-tracking

