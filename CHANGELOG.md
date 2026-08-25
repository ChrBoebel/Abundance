# Changelog

All notable changes to Abundance are documented here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

## Unreleased

### Added

- Abundance domain models, application ports, and evidence-capability policy.
- Typed LangGraph workflow with bounded parallel evidence units and optional
  checkpointing.
- LangChain `ChatOpenRouter` adapter with strict Pydantic structured output.
- Stable SSE domain events, heartbeat support, monotonic IDs, and cancellation.
- Deterministic report rendering and claim/evidence quality evaluation.
- Frontend SSE regression tests and backend graph/checkpoint/security tests.
- Distributed production rate limiting and internal service authentication.
- Non-root backend and frontend container builds.
- Versioned evidence-assessment golden fixtures and a reproducible legacy
  failure baseline.
- Cost-bounded semantic evidence assessment with exact quote/ID binding,
  shadow-mode metrics, and component-level live evaluation.

### Changed

- Upgraded the workspace to Next.js 16 and React 19.
- Replaced process-local polling with a direct authenticated POST stream.
- Replaced trusted HTML rendering with constrained React Markdown rendering.
- Reduced provider access to reviewed model aliases and one read-only search
  adapter per evidence unit.
- Expanded CI with tests, full type checking, dependency audits, and Dependabot.
- Added a non-blocking LangGraph evidence-assessment stage before synthesis;
  shadow results are persisted without rewriting admitted evidence.

### Removed

- Legacy `/research/stream` transport and raw runtime-event mapping.
- Dynamic MCP/tool assembly and unbounded agent repair loops.
- Obsolete provider, document-processing, and frontend rendering dependencies.

### Security

- Added nonce-based CSP, strict sessions, origin checks, request-size limits,
  public error redaction, evidence URL admission, shared production limits, and
  service-to-service bearer authentication.
