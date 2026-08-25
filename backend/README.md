# Abundance research API

FastAPI service for the typed Abundance LangGraph workflow.

## Responsibilities

- validate research commands and reviewed model aliases;
- execute the bounded LangGraph plan/evidence/assessment/review/synthesis topology;
- use LangChain's OpenRouter integration for structured model output;
- normalize read-only Tavily results and enforce evidence admission;
- measure semantic evidence quality in a non-blocking shadow stage;
- stream stable Abundance events with cancellation and heartbeats;
- expose liveness and configuration readiness separately.

## Environment

Required:

- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`

Recommended for every non-local deployment:

- `ABUNDANCE_INTERNAL_API_TOKEN` — at least 32 characters;
- `ABUNDANCE_CORS_ORIGINS` — comma-separated explicit origins.

See `.env.example` for token, timeout, retry, and excerpt limits. Provider keys
are the only unprefixed application secrets.

## Run

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python backend_server.py
```

Or build the non-root container:

```bash
docker compose up --build
```

## API

`GET /health` checks process liveness. `GET /ready` constructs provider
adapters and returns `503` with a safe configuration error when credentials are
missing.

`POST /api/v1/research-runs/stream` accepts:

```json
{
  "inquiry": "Which evidence supports and challenges the proposed policy?",
  "model": "mercury",
  "mode": "balanced"
}
```

The response is `text/event-stream`. Every JSON event has a monotonic SSE ID;
heartbeat comments keep long model calls alive. A successful stream ends with
`run.completed`; a controlled failure ends with `run.failed`.

## Verification

```bash
python -m ruff check backend_server.py src tests
python -m mypy src backend_server.py
python -m pytest -q
python -m pip_audit
```

## Evaluation baseline gate

Validate the source-controlled dataset without provider calls:

```bash
python -m abundance_research.eval_harness --validate-only
python -m abundance_research.assessment_eval_harness --validate-only
python -m abundance_research.claim_verification_eval_harness --validate-only
```

The assessment fixture also has a source-controlled legacy baseline that
captures inherited retrieval relations, hostname-based source classification,
and missing quote binding:

```bash
python -m abundance_research.assessment_eval_harness --legacy-baseline
```

With provider credentials exported, score the configured assessor against the
same golden fixture:

```bash
python -m abundance_research.assessment_eval_harness \
  --model mercury \
  --output evals/results/evidence-assessment-candidate.json
```

Claim verification has a separate component gate. It pins the reviewed
`deepseek/deepseek-v4-flash-0731` profile behind the
`deepseek-v4-flash` alias and executes three independent trials with bounded
parallelism:

```bash
python -m abundance_research.claim_verification_eval_harness \
  --model deepseek-v4-flash \
  --runs 3 \
  --max-concurrency 3 \
  --output evals/results/claim-verification-candidate.json
```

Promotion requires a mean pass rate of at least 80%, every trial at least 70%,
and an improvement over the source-controlled legacy baseline. The accepted v3
artifact records 88.9% mean and 83.3% minimum accuracy across three trials.
Local candidate artifacts remain ignored; only reviewed baselines belong in
version control.

Create a live candidate artifact and compare it with an accepted, like-for-like
baseline:

```bash
python -m abundance_research.eval_harness \
  --models mercury \
  --output evals/results/candidate.json \
  --baseline evals/results/baseline.json \
  --comparison-output evals/results/comparison.json \
  --min-pass-rate 0.9 \
  --max-pass-rate-drop 0 \
  --max-duration-increase-ratio 0.25 \
  --max-cost-increase-ratio 0.25
```

The command exits unsuccessfully when the absolute quality gate or the baseline
regression budgets fail. Comparison requires identical dataset versions, model
profiles, and evaluated case sets.
