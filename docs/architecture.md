# Abundance Architecture

Abundance separates its research domain from the workflow framework and provider
SDKs. This keeps product behavior testable and prevents runtime-specific details
from becoming a public API.

## Boundaries

### Web application

The Next.js application owns authentication, local research history, research
mode selection, and browser-facing Server-Sent Events. It consumes only the
event types defined in `frontend/lib/types.ts`.

### Research API

The FastAPI service accepts a product-level inquiry at
`POST /api/v1/research-runs/stream`. It selects a bounded research profile and
translates runtime events before returning them to clients.

### Domain

`abundance_research.domain` defines inquiries, research plans, evidence records,
claims, counterevidence, confidence, open questions, and structured reports.
These models do not import LangGraph.

### Workflow

The workflow contains four executable areas:

1. `planning` scopes the inquiry and prepares the research brief.
2. `coordination` selects independent evidence and falsification questions.
3. `investigation` collects and reviews evidence for one bounded question.
4. `workflow` synthesizes the dossiers into the final report.

LangGraph is used inside this boundary for scheduling and state transitions.

### Adapters

Search and model utilities integrate Tavily, arXiv, PubMed, OpenRouter, and
optional MCP tools. Provider results are not part of the public event contract.

## Streaming contract

Clients may receive:

- `run.accepted`, `run.completed`, `run.failed`
- `inquiry.scoping`
- `plan.created`
- `evidence.collection.started`, `evidence.search.started`, `evidence.discovered`
- `evidence.review.started`
- `synthesis.started`
- `report.delta`, `report.completed`

New internal graph nodes must be mapped to these events instead of being exposed
directly.

## Quality model

`abundance_research.evaluation` calculates deterministic metrics from structured
reports. The initial metrics are claim-evidence coverage, challenged-claim ratio,
primary-source ratio, broken evidence links, and open-question count.

These metrics are intentionally explainable. Model-based evaluators can be added
later as a separate layer rather than replacing deterministic checks.
