# Abundance research workspace

Next.js 16 and React 19 browser workspace for Abundance research runs.

## Responsibilities

- protect the workspace with an encrypted, HTTP-only session;
- enforce same-origin requests and distributed abuse limits;
- proxy the backend SSE body without process-local job state;
- propagate browser cancellation to the research API;
- render model-controlled Markdown without trusting raw HTML;
- keep research history locally in the browser.

## Environment

Local development requires:

- `RESEARCH_BACKEND_URL=http://localhost:8000`
- `SESSION_SECRET` with at least 32 characters
- `APP_PASSWORD` with at least 12 characters

Production also requires:

- `RESEARCH_BACKEND_TOKEN` matching the backend service token;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`.

Without a shared rate-limit store production requests fail closed. Development
uses a bounded in-process limiter.

## Run and verify

```bash
cp .env.example .env
npm ci
npm run dev

npm test
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=high
```

Main routes:

- `/` — research workspace;
- `/login` — password login;
- `/api/research-runs/stream` — authenticated POST/SSE proxy;
- `/api/health` — frontend/backend health projection.
