# ADR 0001: Publish domain events instead of runtime events

- Status: Accepted
- Date: 2026-08-25

## Context

LangGraph callback and node events expose internal names, provider objects, and
version-specific payloads. Making them the browser contract couples product
behavior to the orchestration runtime.

## Decision

Graph nodes write explicit `ResearchEvent` payloads through LangGraph's custom
stream. FastAPI publishes only these Abundance events. Runtime update, task, and
debug streams remain internal.

## Consequences

The browser contract is stable across graph refactors and internal errors can be
redacted consistently. Adding a user-visible stage requires an intentional
event-contract change and regression test.
