# ADR 0004: Durable PostgreSQL runtime

- Status: accepted
- Date: 2026-08-25

## Context

Browser-local history cannot resume interrupted LangGraph execution, support stable sharing, aggregate evaluation feedback, or survive client storage loss.

## Decision

Production-like environments use PostgreSQL for both Abundance run records and LangGraph checkpoints. Schema changes are immutable, explicit, forward-applied migrations. Local development may omit the database and use the bounded in-memory repository.

The public share capability stores only a SHA-256 digest of a cryptographically random token. Provider prompts, raw completions, credentials, and source excerpts are excluded from run metrics and public records.

## Consequences

- Runs, metrics, feedback, shares, and graph checkpoints survive process restarts.
- Startup fails when a configured database lacks required migrations.
- Deployment must run migrations before rolling out the application.
- Database rollback uses a corrective forward migration; application rollback reuses immutable container tags.
