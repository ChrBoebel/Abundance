# Backend

FastAPI backend for Abundance. It exposes a single streaming endpoint that forwards LangGraph research events as Server-Sent Events.

## Responsibilities

- build the LangGraph research workflow
- call Tavily for search
- call OpenRouter for model inference
- stream research progress and final output to the frontend

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

### `POST /research/stream`

Request body:

```json
{
  "message": "Summarize the latest agent engineering patterns"
}
```

Response:

- content type: `text/event-stream`
- streams LangGraph events
- ends with `{"event":"done"}` on success

## Local Python Run

```bash
pip install -r requirements.txt
python3 backend_server.py
```
