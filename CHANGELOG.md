# Changelog

All notable changes to Abundance are documented here.

## Unreleased

### Added

- Abundance research-domain models for inquiries, evidence, claims, and reports.
- Stable domain event streaming at `/api/v1/research-runs/stream`.
- Quick, balanced, and thorough research modes.
- Evidence quality evaluation and backend tests.
- Live backend health reporting in the research workspace.

### Changed

- Renamed the Python package to `abundance_research`.
- Reworked prompts around evidence, counterevidence, and calibrated uncertainty.
- Replaced raw LangGraph events in the frontend with Abundance domain events.
- Reframed the interface from a chat view to a research workspace.

### Security

- Documented that exposed historical provider keys must be rotated before any
  repository-history cleanup.
