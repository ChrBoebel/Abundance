# Contributing to Abundance

## Development workflow

1. Create a focused branch from `main`.
2. Keep domain decisions separate from provider-specific implementation details.
3. Add tests for behavior changes.
4. Run the checks documented in the root README.
5. Use a descriptive conventional commit message.

Examples:

- `feat(evidence): add source freshness assessment`
- `fix(events): preserve report completion ordering`
- `test(research): cover counterevidence metrics`

## Research principles

Changes to research behavior should preserve these principles:

- connect material claims to evidence;
- seek credible counterevidence;
- distinguish facts, inference, and speculation;
- expose uncertainty and source limitations;
- prefer primary and current sources where appropriate;
- never describe retrieval alone as verification.

## Attribution

Do not remove third-party copyright or license notices. When adapting additional
open-source code, update `THIRD_PARTY_NOTICES.md` in the same change.
