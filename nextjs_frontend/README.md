# Abundance Next.js Frontend

Modern Next.js frontend for Open Deep Research with TypeScript, Tailwind CSS, and SSE streaming.

## Features

- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **iron-session** for authentication
- **SSE Streaming** for real-time research updates
- **Python Bridge** for deep_researcher integration
- **Dark/Light Mode** with next-themes
- **Minimal Dependencies** (only 8 production packages)

## Project Structure

```
nextjs_frontend/
├── app/                    # Next.js App Router
│   ├── api/               # API Routes
│   ├── layout.tsx         # Root Layout
│   ├── page.tsx           # Chat Page
│   ├── login/page.tsx     # Login Page
│   └── globals.css        # Global Styles
├── components/            # React Components
│   ├── ChatInput.tsx
│   ├── ChatMessage.tsx
│   └── ResearchStatus.tsx
├── lib/                   # Utilities
│   ├── auth.ts           # Authentication
│   ├── research.ts       # Job Management + Python Bridge
│   └── types.ts          # TypeScript Types
├── scripts/
│   └── research_bridge.py # Python Integration
└── public/               # Static Assets
```

## Setup

### 1. Install Dependencies

```bash
cd nextjs_frontend
npm install
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
APP_PASSWORD=your-password
SESSION_SECRET=your-secret-key-at-least-32-characters
GEMINI_API_KEY=your-gemini-key
TAVILY_API_KEY=your-tavily-key
```

### 3. Install Python Dependencies

The Python bridge requires the parent package:

```bash
cd ..
pip install -e .
```

### 4. Run Development Server

```bash
cd nextjs_frontend
npm run dev
```

Open [http://localhost:4290](http://localhost:4290)

## Building for Production

```bash
npm run build
npm start
```

## Deployment (Railway)

The `nixpacks.toml` configures Railway to:
1. Install Node.js and Python 3.11
2. Install npm and pip dependencies
3. Build Next.js
4. Start production server

Environment variables needed:
- `APP_PASSWORD`
- `SESSION_SECRET`
- `GEMINI_API_KEY`
- `TAVILY_API_KEY`

Railway automatically sets `PORT`.

## Architecture

### Authentication
- Uses `iron-session` with httpOnly cookies
- Middleware protects all routes except `/login` and `/api/auth/*`
- Simple password-based auth

### SSE Streaming
- `/api/chat/stream` endpoint with job management
- Python bridge spawns `research_bridge.py` for each research
- Events streamed to client via EventSource
- Auto-reconnect support with job IDs

### Python Integration
- `scripts/research_bridge.py` reads JSON from stdin
- Streams events from `deep_researcher.astream_events()`
- Outputs JSON lines to stdout
- Next.js API route spawns and manages Python process

### State Management
- React `useState` for local state
- No external state library needed
- In-memory job storage (can be upgraded to Redis)

## Key Differences from Flask

- **No Templates**: Pure React components
- **SSE via ReadableStream**: Native Next.js streaming
- **iron-session vs Flask Sessions**: More secure, httpOnly cookies
- **Child Process vs Direct Import**: Python bridge isolates concerns
- **TypeScript**: Full type safety
- **Component-Based**: Reusable UI components
