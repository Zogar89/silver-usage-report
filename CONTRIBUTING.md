# Contributing

Silver Usage Report should be easy to review, easy to run, and careful with user data.

## Principles

- Keep the first version small.
- Optimize for completed reports, not perfect dashboards.
- Prefer provider APIs and structured exports over scraping.
- Upload aggregates, not raw logs.
- Make privacy behavior obvious in the UI and CLI.
- Treat API keys as local-only secrets.
- Label every row with source and confidence.
- Avoid provider-specific assumptions in the normalized data model.

## Good First Contributions

- Add sample anonymized report data.
- Improve the normalized report schema.
- Build a CSV importer.
- Add a manual report form.
- Add documentation for a provider's billing or usage API.
- Add tests for cost normalization edge cases.
- Add a source adapter design note for a local AI coding tool.

## Documentation Style

- Write short, direct docs.
- Separate known facts from assumptions.
- Link to provider documentation when behavior depends on an external API.
- Include the date when documenting provider behavior that may change.
- Explain why a proposed source does or does not fit the report-intake problem.

## Security Expectations

Any contribution that touches import, authentication, upload, storage, provider credentials, local logs, or manual evidence should include a short note explaining:

- What sensitive data exists at that point in the flow.
- Whether it leaves the user's machine.
- How long it is retained.
- How source and confidence are represented.
- How the user can inspect or delete it.
