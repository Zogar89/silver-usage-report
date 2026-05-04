# Contributing

Silver Token Ledger should be easy to review, easy to run, and careful with user data.

## Principles

- Keep the first version small.
- Prefer provider APIs and structured exports over scraping.
- Upload aggregates, not raw logs.
- Make privacy behavior obvious in the UI and CLI.
- Treat API keys as local-only secrets.
- Avoid provider-specific assumptions in the normalized data model.

## Good First Contributions

- Add a provider import design note.
- Add sample anonymized fixture data.
- Improve the normalized usage schema.
- Build a CSV importer.
- Add documentation for a provider's billing or usage API.
- Add tests for cost normalization edge cases.

## Documentation Style

- Write short, direct docs.
- Separate known facts from assumptions.
- Link to provider documentation when behavior depends on an external API.
- Include the date when documenting provider behavior that may change.

## Security Expectations

Any contribution that touches import, authentication, upload, storage, or provider credentials should include a short note explaining:

- What sensitive data exists at that point in the flow.
- Whether it leaves the user's machine.
- How long it is retained.
- How the user can inspect or delete it.

