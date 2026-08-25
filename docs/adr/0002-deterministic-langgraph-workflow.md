# ADR 0002: Use a deterministic LangGraph workflow

- Status: Accepted
- Date: 2026-08-25

## Context

Open-ended tool selection allows retrieved prompt injection to influence which
capability runs, increases cost unpredictability, and makes resumption difficult
to reason about.

## Decision

Use a fixed graph: scope, plan, bounded evidence fan-out, admission/review, and
synthesis. `Send` provides parallel map work; run-local semaphores enforce mode
budgets. Models create structured plans and reports but never select or execute
tools. State is checkpoint-serializable.

## Consequences

The workflow is inspectable, cancellable, and testable. New capabilities require
code, policy, and tests. The system gives up unconstrained autonomous behavior in
exchange for predictable permissions and cost.
