# Deep Research Frontend - Next.js UI

Next.js Frontend für das Deep Research System. Kommuniziert mit dem Docker Backend über HTTP/SSE.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Setup Environment Variables

```bash
# Kopiere .env.example zu .env
cp .env.example .env

# Bearbeite .env
nano .env
```

Erforderliche Variables in `.env`:
```bash
RESEARCH_BACKEND_URL=http://localhost:8000
SESSION_SECRET=your-secret-key-here
```

### 3. Start Development Server

```bash
npm run dev
```

Frontend läuft auf: **http://localhost:4290**

### 4. Start Backend (parallel)

Das Frontend benötigt das laufende Backend:

```bash
# In anderem Terminal
cd ../backend
docker-compose up -d
```

Backend läuft auf: **http://localhost:8000**

---

## 📡 Architektur

### System-Übersicht

```
┌─────────────────┐     Browser      ┌─────────────────┐
│                 │ ◄─────────────► │                 │
│  User (Browser) │                  │  Next.js        │
│                 │                  │  Frontend       │
└─────────────────┘                  │  (Port 4290)    │
                                     └────────┬────────┘
                                              │
                                              │ HTTP/SSE
                                              ▼
                                     ┌─────────────────┐
                                     │  FastAPI        │
                                     │  Backend        │
                                     │  (Port 8000)    │
                                     └────────┬────────┘
                                              │
                                              ▼
                                     ┌─────────────────┐
                                     │  LangGraph      │
                                     │  + OpenRouter   │
                                     │  + Tavily       │
                                     └─────────────────┘
```

### Datenfluss

1. **User Input** → Next.js Frontend (UI)
2. **Frontend** → Backend API: `POST /research/stream` mit `{"message":"..."}`
3. **Backend** → LangGraph Research Workflow
4. **Backend** → Frontend: SSE Stream mit Events
5. **Frontend** → User: Live Research Updates + Final Report

---

## 📂 Ordnerstruktur

```
frontend/
├── app/                    # Next.js App Router
│   ├── page.tsx           # Hauptseite (Chat UI)
│   ├── layout.tsx         # Root Layout
│   ├── globals.css        # Global Styles
│   ├── login/             # Login Page
│   └── api/               # API Routes (Next.js Backend)
│       ├── chat/
│       │   └── stream/    # SSE Endpoint für Frontend
│       ├── auth/          # Login/Logout
│       ├── health/        # Health Check
│       └── thread/        # Thread Management
├── components/            # React Components
│   ├── ChatInput.tsx     # Chat Input Field
│   ├── ResearchStatus.tsx # Research Progress Display
│   ├── ThemeToggle.tsx   # Dark/Light Mode Toggle
│   └── ...
├── lib/                  # Utility Functions
│   ├── research.ts       # Backend Integration (HTTP Client)
│   └── types.ts          # TypeScript Types
├── public/               # Static Assets
│   └── neuesbild-copy.svg
├── package.json          # Dependencies
├── next.config.js        # Next.js Config
├── tsconfig.json         # TypeScript Config
├── tailwind.config.js    # Tailwind CSS Config
├── .env.example          # Environment Template
└── README.md             # Diese Datei
```

---

## 🔧 Development

### Commands

```bash
# Install Dependencies
npm install

# Start Dev Server (Port 4290)
npm run dev

# Build for Production
npm run build

# Start Production Server
npm start

# Lint Code
npm run lint
```

### Environment Variables

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `RESEARCH_BACKEND_URL` | Backend API URL | `http://localhost:8000` |
| `SESSION_SECRET` | Session Encryption Key | - (required) |
| `PORT` | Next.js Server Port | `4290` |

---

## 🛠️ Backend Integration

### API Client: `lib/research.ts`

Das Frontend kommuniziert mit dem Backend über `lib/research.ts`:

```typescript
import { startResearch } from '@/lib/research'

// Start Research
await startResearch(
  jobId,      // Unique Job ID
  message,    // User Query
  threadId    // Thread ID für History
)
```

**Request an Backend:**
```json
POST http://localhost:8000/research/stream
Content-Type: application/json

{
  "message": "Was sind die Features in LangGraph 0.2?"
}
```

**Response vom Backend (SSE):**
```
data: {"event":"on_chain_start","name":"supervisor",...}
data: {"event":"on_tool_start","name":"tavily_search",...}
data: {"event":"on_chat_model_stream","data":{"chunk":"..."}}
data: {"event":"done"}
```

### Event-Mapping

Frontend mappt Backend-Events zu UI-Events:

| Backend Event | Frontend Event | UI Effekt |
|--------------|----------------|-----------|
| `on_chain_start` | `step_start`, `current_activity` | Zeigt aktiven Step |
| `on_tool_start` | `tool_call_start` | Zeigt Tool Execution |
| `on_chat_model_stream` | `report_stream` | Streamt Final Report |
| `on_chain_end` | `step_complete`, `agent_message` | Step Complete + Report |
| `done` | `done` | Research Complete |
| `error` | `error` | Error Display |

---

## 🎨 UI Components

### ChatInput.tsx

Input Field mit Send-Button und Model Selector (optional deaktiviert).

**Props:**
```typescript
{
  onSend: (message: string, model: string) => void
  disabled?: boolean
}
```

### ResearchStatus.tsx

Zeigt Research Progress und Live Updates.

**Props:**
```typescript
{
  events: Event[]
  currentStep?: string
  currentActivity?: string
}
```

---

## 🧪 Testing

### Local Testing

```bash
# 1. Start Backend
cd ../backend
docker-compose up -d

# 2. Start Frontend
cd ../frontend
npm run dev

# 3. Open Browser
open http://localhost:4290
```

### Test Queries

**Einfache Frage (2-5s):**
```
Was ist 2+2?
```

**Mittlere Recherche (10-30s):**
```
Was ist LangGraph?
```

**Deep Research (1-10min):**
```
Was sind die wichtigsten Features in LangGraph 0.2 vs 0.1?
```

---

## 🚢 Deployment

### Vercel Deployment

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Login
vercel login

# 3. Deploy
vercel

# 4. Set Environment Variables in Vercel Dashboard
RESEARCH_BACKEND_URL=https://your-backend.railway.app
SESSION_SECRET=your-secret-key
```

### Railway Deployment

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Initialize
railway init

# 4. Set Variables
railway variables set RESEARCH_BACKEND_URL=http://backend:8000
railway variables set SESSION_SECRET=your-secret

# 5. Deploy
railway up
```

### Docker Deployment (Optional)

Du kannst das Frontend auch dockerizen:

**Dockerfile:**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 4290
CMD ["npm", "start"]
```

**Build & Run:**
```bash
docker build -t deep-research-frontend .
docker run -p 4290:4290 \
  -e RESEARCH_BACKEND_URL=http://backend:8000 \
  -e SESSION_SECRET=secret \
  deep-research-frontend
```

---

## 🐛 Troubleshooting

### Backend Connection Failed

**Problem:** Frontend kann Backend nicht erreichen

**Lösung:**
```bash
# 1. Check Backend läuft
curl http://localhost:8000/health

# 2. Check .env Variable
cat .env | grep RESEARCH_BACKEND_URL

# 3. Restart Frontend
npm run dev
```

### CORS Errors

**Problem:** CORS Fehler in Browser Console

**Lösung:**
- Backend muss Frontend-URL in CORS Origins haben
- Check `backend/backend_server.py`:
  ```python
  allow_origins=["http://localhost:4290", "http://localhost:3000"]
  ```

### Session Errors

**Problem:** Session-Fehler beim Login

**Lösung:**
```bash
# 1. Generate neuen SESSION_SECRET
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# 2. Setze in .env
SESSION_SECRET=<generated-key>

# 3. Restart
npm run dev
```

### Port Already in Use

**Problem:** Port 4290 bereits belegt

**Lösung:**
```bash
# Option 1: Ändere Port in .env
echo "PORT=3000" >> .env

# Option 2: Kill Process
lsof -i :4290
kill <PID>
```

---

## 🔒 Security

### Production Checklist

- [ ] **SESSION_SECRET** gesetzt und sicher
- [ ] **RESEARCH_BACKEND_URL** auf HTTPS
- [ ] CORS Origins eingeschränkt
- [ ] CSP Headers konfiguriert
- [ ] Rate Limiting aktiviert
- [ ] Authentication aktiviert

### Environment Variables Sicher Setzen

**Niemals committen:**
```bash
# .env sollte in .gitignore sein
echo ".env" >> .gitignore
```

**Verwende Secrets Management:**
- Vercel: Dashboard → Settings → Environment Variables
- Railway: Dashboard → Variables
- Docker: Environment Variables oder Secrets

---

## 📊 Performance

### Build Optimization

```bash
# Analyze Bundle Size
npm run build

# Next.js zeigt automatisch Bundle Analysis
```

### Production Best Practices

1. **SSR für bessere SEO** (bereits aktiviert)
2. **Image Optimization** mit next/image
3. **Code Splitting** automatisch von Next.js
4. **Caching** für API Requests

---

## 📄 License

Same as parent project.
