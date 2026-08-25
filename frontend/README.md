# Frontend

Next.js research workspace for Abundance. It authenticates the user, manages
local research history, and renders the framework-independent Abundance event
stream.

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
- start research runs in quick, balanced, or thorough mode
- proxy backend SSE events without exposing graph internals
- render the research trail, sources, and final synthesis

## Main Routes

- `/` research workspace
- `/login` password login page
- `/api/research-runs/stream` browser streaming endpoint
- `/api/research-runs/[id]` research-session reset endpoint
- `/api/health` frontend and backend health check

## Development

Make sure the backend is already running on `http://localhost:8000`, then start the frontend:

```bash
npm run dev
```
