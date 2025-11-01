# 🔬 Open Deep Research - Web Application

Vollautomatisierte Deep Research Engine mit **Docker Backend** und **Next.js Frontend**.

Powered by **Gemini 2.5 Flash** via **OpenRouter** und **Tavily Search**.

## ✅ Status: VOLL FUNKTIONSFÄHIG

- ✅ Docker Backend (FastAPI + LangGraph)
- ✅ Next.js Frontend (React + SSE Streaming)
- ✅ Gemini 2.5 Flash via OpenRouter
- ✅ Tavily Search Integration

---

## 🚀 Schnellstart

### 1️⃣ Backend starten (Docker)

```bash
cd backend
docker-compose up -d
```

Backend läuft auf: **http://localhost:8000**

Prüfe Status:
```bash
curl http://localhost:8000/health
```

### 2️⃣ Frontend starten (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft auf: **http://localhost:4290**

### 3️⃣ Öffne im Browser

```
http://localhost:4290
```

Login-Passwort siehe `frontend/.env` → `APP_PASSWORD`

---

## ⚙️ Konfiguration

### Backend Environment (`backend/.env`)
```bash
GEMINI_API_KEY=your-key
GOOGLE_API_KEY=your-key
TAVILY_API_KEY=your-key
OPENROUTER_API_KEY=your-key
```

### Frontend Environment (`frontend/.env`)
```bash
APP_PASSWORD=your-password
SESSION_SECRET=your-session-secret
GEMINI_API_KEY=your-key
GOOGLE_API_KEY=your-key
TAVILY_API_KEY=your-key
OPENROUTER_API_KEY=your-key
PORT=4290
```

### Modell-Konfiguration

Alle Modelle sind hardcoded auf **Gemini 2.5 Flash** via **OpenRouter**:
- Model: `openrouter:google/gemini-2.5-flash`
- Search API: **Tavily** (Standard)

Konfiguration in: `backend/backend_server.py`

---

## 📁 Projektstruktur

```
open_deep_research/
├── backend/                    # 🐳 Docker Backend
│   ├── src/                   # LangGraph research engine
│   │   ├── deep_researcher.py # Main agent graph
│   │   ├── supervisor.py      # Research coordinator
│   │   ├── researcher.py      # Research executor
│   │   ├── configuration.py   # Model config
│   │   └── utils/             # Utilities
│   ├── backend_server.py      # FastAPI + SSE streaming
│   ├── Dockerfile             # Docker image
│   ├── docker-compose.yml     # Docker orchestration
│   ├── requirements.txt       # Python deps
│   └── README.md              # Backend docs
│
├── frontend/                  # ⚛️ Next.js Frontend
│   ├── app/                  # Next.js app router
│   │   ├── page.tsx          # Main chat UI
│   │   ├── login/            # Login page
│   │   └── api/              # API routes
│   ├── components/           # React components
│   ├── lib/                  # Frontend utilities
│   ├── package.json          # Node deps
│   └── README.md             # Frontend docs
│
├── .env.example              # Environment template
├── .gitignore                # Git ignore
├── CLAUDE.md                 # Project instructions
├── README.md                 # This file
├── OPENROUTER_FEATURES.md    # Feature documentation
└── workflow_architecture.md  # Architecture diagrams
```

---

## 💡 Verwendung

1. **Öffne Browser**: http://localhost:4290
2. **Login**: Passwort aus `frontend/.env`
3. **Stelle Frage**: z.B. "What are the latest developments in AI?"
4. **Warte auf Ergebnis**: Live-Streaming der Research-Schritte
5. **Lese Report**: Comprehensive research report

---

## 🎯 Features

### Backend
- ✅ **LangGraph Workflow**: Multi-agent research orchestration
- ✅ **Parallel Research**: Multiple sub-agents working concurrently
- ✅ **Tavily Search**: Web search integration
- ✅ **OpenRouter**: Gemini 2.5 Flash routing
- ✅ **SSE Streaming**: Real-time event streaming
- ✅ **Docker Deployment**: Self-contained containerization

### Frontend
- ✅ **Next.js 14**: React Server Components
- ✅ **Real-time Updates**: SSE-based live streaming
- ✅ **Authentication**: Password-protected access
- ✅ **Responsive UI**: Works on desktop and mobile
- ✅ **Dark Mode**: Theme toggle
- ✅ **Progress Tracking**: Visual research progress indicators

---

## 🔧 Troubleshooting

### Backend startet nicht
```bash
# Check Docker status
docker ps

# Check logs
cd backend
docker-compose logs -f

# Rebuild if needed
docker-compose down
docker-compose up --build -d
```

### Frontend startet nicht
```bash
# Check port 4290 is free
lsof -i :4290

# Kill if occupied
kill <PID>

# Restart frontend
cd frontend
npm run dev
```

### API Connection Failed
```bash
# Check backend is running
curl http://localhost:8000/health

# Check frontend .env has correct BACKEND_URL
cat frontend/.env | grep RESEARCH_BACKEND_URL
```

---

## 📊 Deployment

### Production Deployment

**Backend (Railway/Docker Host):**
```bash
cd backend
railway up
# oder
docker push your-registry/deep-research-backend
```

**Frontend (Vercel/Railway):**
```bash
cd frontend
vercel deploy
# oder
railway up
```

Siehe `backend/README.md` und `frontend/README.md` für Details.

---

**Powered by Gemini 2.5 Flash via OpenRouter** 🤖
