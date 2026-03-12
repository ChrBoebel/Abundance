# Frontend

Next.js frontend for Abundance. It authenticates the user with a single password and renders the live research stream coming from the backend.

## Setup

```bash
cp .env.example .env
npm install
npm run dev
```

## Environment Variables

Required:

- `RESEARCH_BACKEND_URL=http://localhost:8000`
- `SESSION_SECRET=<random secret>`
- `APP_PASSWORD=<password for demo access>`

Optional:

- `PORT=4290`

## Responsibilities

- protect the UI behind a password gate
- start research jobs from the browser
- proxy and normalize backend SSE events
- render progress, sources, and final reports

## Main Routes

- `/` main research UI
- `/login` password login page
- `/api/chat/stream` frontend streaming endpoint
- `/api/health` lightweight health check

## Development

Make sure the backend is already running on `http://localhost:8000`, then start the frontend:

```bash
npm run dev
```
