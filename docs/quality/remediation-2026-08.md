# Architecture and security remediation

Date: 2026-08-25

This report closes the findings recorded in
`architecture-audit-2026-08.md`. The original audit remains unchanged as the
historical baseline.

| Finding | Status | Verification |
| --- | --- | --- |
| Trusted generated HTML | Closed | React Markdown skips raw HTML and rejects unsafe URLs; production CSP uses nonces |
| Framework types in domain state | Closed | Domain and ports have no LangGraph/LangChain imports; graph state is application-owned and serializable |
| Vulnerable frontend baseline | Closed | Next.js 16 / React 19; `npm audit` reports zero known vulnerabilities |
| Exception text exposed to clients | Closed | Stable failure codes and correlation IDs; provider causes remain server-side |
| Model-controlled tool permissions | Closed | Fixed graph, read-only evidence port, reviewed model aliases, hard mode budgets |
| Polling and process-local run storage | Closed | Direct POST stream with cancellation propagation and SSE heartbeats |
| Ambiguous legacy configuration | Closed | Application settings accept documented `ABUNDANCE_*` names only |

## Additional controls delivered

- LangGraph custom events instead of runtime callbacks;
- optional checkpoint injection with a tested serializable state contract;
- evidence URL admission before browser streaming;
- raw evidence excerpts excluded from public report payloads;
- same-origin request enforcement and bounded bodies;
- distributed production rate limits with fail-closed configuration;
- internal Next.js-to-FastAPI bearer authentication;
- non-root container images and loopback-bound backend Compose service;
- CI gates for tests, lint, static typing, builds, and dependency audits;
- automated npm, Python, and GitHub Actions dependency updates.

## Residual risks

1. The password gate is single-user authentication, not a multi-user identity
   system. Add OIDC and role-based authorization before broader access.
2. The default HTTP composition root is not durably checkpointed. Configure an
   async production saver and retention policy before offering resume/replay.
3. Tavily source classification is heuristic. High-stakes deployments require
   domain-specific source review and evaluation datasets.
4. Local rate limiting is intentionally process-scoped. Only development may use
   it; production requires the shared store.
5. Provider availability, model schema support, and search quality remain
   external dependencies and need operational monitoring.
