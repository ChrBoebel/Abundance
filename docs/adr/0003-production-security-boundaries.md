# ADR 0003: Fail closed at production service boundaries

- Status: Accepted
- Date: 2026-08-25

## Context

Per-process limits do not work across serverless instances, and a publicly
reachable FastAPI endpoint could bypass the frontend password gate.

## Decision

Production browser routes require a shared Upstash rate-limit store. Next.js and
FastAPI use a separate service bearer token for research requests. Missing
production configuration returns `503`; local development retains a bounded
in-process limiter and may omit the internal token.

## Consequences

Deployment requires Redis and matching secrets. Configuration failures are
visible immediately rather than silently reducing protection. Multi-user
identity remains outside the current single-user product scope.
