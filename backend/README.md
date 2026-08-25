# Backend

FastAPI backend for Abundance. It exposes a stable, framework-independent stream
of research-domain events over Server-Sent Events.

## Responsibilities

- scope inquiries and coordinate evidence questions
- call Tavily for search
- search arXiv and PubMed for academic evidence
- call OpenRouter for model inference
- review counterevidence and source limitations
- stream Abundance progress events and final reports

## Required Environment Variables

Copy the example file first:

```bash
cp .env.example .env
```

Required for the default setup:

- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`

Optional:

- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_TRACING`
- `PORT`

## Run With Docker

```bash
docker-compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

## API

### `GET /health`

Returns:

```json
{"status":"healthy","version":"1.0.0"}
```

### `POST /api/v1/research-runs/stream`

Request body:

```json
{
  "inquiry": "Which evidence supports and challenges the proposed policy?",
  "model": "mercury",
  "mode": "balanced"
}
```

Response:

- content type: `text/event-stream`
- streams Abundance events such as `plan.created`, `evidence.discovered`, and
  `report.completed`
- ends with `run.completed` on success

`POST /research/stream` remains temporarily available as a compatibility route
for older clients.

## Local Python Run

```bash
pip install -e ".[dev]"
python3 backend_server.py
```

## Tests

```bash
python -m ruff check backend_server.py src tests
python -m pytest -q
```
