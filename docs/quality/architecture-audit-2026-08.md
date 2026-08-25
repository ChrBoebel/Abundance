# Abundance architecture and security baseline

Date: 2026-08-25  
Scope: browser workspace, Next.js boundary, FastAPI streaming API, research runtime,
model/tool adapters, and quality evaluation.

## Executive verdict

The product contract is recognizably Abundance, but the implementation still has
high coupling between application behavior and the orchestration framework. The
most urgent correction is to make research execution depend on typed Abundance
ports and events, with LangChain or LangGraph confined to infrastructure adapters.

Overall health: **medium risk**. No committed credentials were detected in the
current tree. The two release-blocking concerns are unsafe report HTML rendering
and a frontend dependency tree with known high-severity advisories.

## Severity-ranked findings

### High — generated report HTML crosses an unsafe rendering boundary

- Layer: platform rendering
- Evidence: `frontend/components/ResearchMessage.tsx` parses model-controlled
  Markdown and passes the resulting HTML to `dangerouslySetInnerHTML`. It also
  assigns generated link markup through `innerHTML`.
- Mechanism: retrieved text is untrusted and can contain direct or indirect prompt
  injection. Treating the generated report as trusted HTML creates an avoidable XSS
  surface.
- Correction: render Markdown through a React component with a strict element and
  URL allowlist. Never assign report content with `innerHTML`.
- Confidence: 1.0

### High — application state and runtime configuration expose framework types

- Layer: tool selection and persistence
- Evidence: `state.py`, `settings.py`, `planning.py`, `coordination.py`,
  `investigation.py`, and `workflow.py` import LangChain or LangGraph types directly.
- Mechanism: domain policy, provider configuration, retries, and graph execution are
  changed together. This makes deterministic testing and alternative runtimes
  unnecessarily expensive.
- Correction: define pure domain objects and application ports; translate framework
  messages and runtime configuration only inside adapters.
- Confidence: 0.98

### High — known vulnerable frontend dependency baseline

- Layer: platform and supply chain
- Evidence: `npm audit` reports 22 findings (12 high, 10 moderate), including direct
  findings through Next.js 14 and its lint toolchain.
- Mechanism: the application is on an old major release while Next.js 16 is the
  current supported line and has current security patches.
- Correction: migrate to the current supported Next.js and React versions, refresh
  the lockfile, and require a production-only audit in CI.
- Confidence: 1.0

### Medium — internal exception text is sent to clients

- Layer: tool interpretation and transport
- Evidence: `backend_server.py` includes `str(exc)` in failure events and the legacy
  stream exposes raw serialized runtime errors.
- Mechanism: provider, request, or infrastructure details can cross the public API
  boundary and reports become dependent on undocumented exceptions.
- Correction: use stable public error codes and correlation IDs; keep details only
  in structured server logs.
- Confidence: 1.0

### Medium — tool permissions are broader than the product policy

- Layer: tool selection and execution
- Evidence: tool lists are assembled dynamically and the model decides which tool
  to call. Completion and search limits are primarily expressed through prompts and
  graph iteration counts.
- Mechanism: prompt injection in retrieved content can influence subsequent tool
  selection. Prompt text is not an authorization control.
- Correction: introduce a code-level capability policy, validate tool calls against
  the assigned research unit, and keep all enabled tools read-only.
- Confidence: 0.9

### Medium — browser stream uses polling and process-local run storage

- Layer: persistence and transport
- Evidence: the Next.js SSE route polls a mutable in-memory run object every 100 ms.
- Mechanism: reconnects can lose events, instances do not share state, and cancelled
  browser streams do not necessarily cancel expensive backend work.
- Correction: add bounded replay IDs and cancellation propagation now; move durable
  runs to an external store before multi-instance deployment.
- Confidence: 0.95

### Low — configuration accepts legacy environment aliases

- Layer: configuration
- Evidence: `AbundanceSettings.from_runnable_config` falls back from
  `ABUNDANCE_*` variables to unprefixed legacy names.
- Mechanism: ambiguous configuration sources complicate deployment audits.
- Correction: accept only documented `ABUNDANCE_*` settings, with provider keys as
  explicit exceptions.
- Confidence: 0.95

## Ordered implementation plan

1. Close the report-rendering XSS boundary and upgrade the vulnerable frontend
   runtime.
2. Introduce pure application ports, typed failures, capability policy, and a
   research engine contract.
3. Move model, search, MCP, and orchestration integrations behind adapters.
4. Replace raw runtime event mapping with events emitted intentionally by the
   application service.
5. Add deterministic contract, policy, streaming, security, and evaluation tests.
6. Add cancellation, bounded replay, structured logging, and production audit gates.
7. Remove legacy endpoints and configuration after the browser uses only v1 domain
   contracts.

## Research basis

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview):
  LangGraph is a low-level orchestration runtime rather than a domain architecture.
- [LangGraph Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api):
  task inputs and outputs should be JSON-serializable; side effects should be
  idempotent when execution can resume.
- [LangGraph event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming):
  runtime streams provide typed projections, which should be translated before they
  become a product API.
- [FastAPI streaming responses](https://fastapi.tiangolo.com/advanced/custom-response/):
  async generators must reach await points so cancellation can be processed.
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/): credentials require
  explicit origins, methods, and headers.
- [Next.js response headers](https://nextjs.org/docs/app/api-reference/config/next-config-js/headers):
  security headers belong at the application boundary.
- [Next.js 16](https://nextjs.org/blog/next-16): the current major moves the platform
  to React 19 and a newer routing/runtime baseline.
- [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/):
  reduce tool functionality, permissions, and autonomy in code.
- [OWASP LLM07:2025 System Prompt Leakage](https://genai.owasp.org/llmrisk/llm072025-system-prompt-leakage/):
  prompts are neither secrets nor authorization mechanisms.

## Verification method

The baseline combined repository searches, dependency audit output, local tests,
and current official documentation. Findings are closed only when an automated test
or build gate demonstrates the corrected behavior.
