# Deep Research Backend - Docker Container

Dockerized FastAPI backend für das Deep Research System mit Gemini 2.5 Flash.

---

## 🚀 Quick Start

### 1. Setup Environment Variables

**WICHTIG:** Zuerst API Keys konfigurieren!

```bash
# Navigiere zum backend Ordner
cd backend

# Kopiere .env.example zu .env (falls vorhanden)
# oder erstelle .env direkt:
nano .env
```

Erforderliche Keys in `.env`:
```bash
GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_key  # kann gleich wie GEMINI_API_KEY sein
TAVILY_API_KEY=your_tavily_key

# Optional:
PORT=8000
LANGSMITH_API_KEY=your_key
LANGSMITH_TRACING=false
```

### 2. Starte Docker Container

```bash
# Mit Docker Compose (Empfohlen)
docker-compose up -d

# Oder baue neu und starte
docker-compose up --build

# Backend läuft auf http://localhost:8000
```

### 3. Teste die API

```bash
# Health Check
curl http://localhost:8000/health
# Response: {"status":"healthy","version":"1.0.0"}

# Einfacher Test
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Was ist LangGraph?"}'
```

---

## 📡 API Dokumentation

### Endpoint

```
POST http://localhost:8000/research/stream
```

### Request Format

```json
{
  "message": "Deine Research-Frage"
}
```

**Parameter:**
- `message` (string, required): Die Research-Frage oder das Thema

**Model:** Hardcoded zu `openrouter:google/gemini-2.5-flash` (Gemini 2.5 Flash)

### Response Format (Server-Sent Events)

Der Backend streamt Events im SSE Format:

```
data: {"event":"on_chain_start","name":"LangGraph","metadata":{...}}

data: {"event":"on_chain_start","name":"clarify_with_user",...}

data: {"event":"on_chain_start","name":"write_research_brief",...}

data: {"event":"on_tool_start","name":"tavily_search","data":{...}}

data: {"event":"on_chat_model_stream","data":{"chunk":"Text..."}}

data: {"event":"done"}
```

### Event-Typen

| Event | Beschreibung |
|-------|-------------|
| `on_chain_start` | LangGraph Node startet (z.B. supervisor, researcher) |
| `on_chain_end` | Node endet |
| `on_chain_stream` | Streaming Daten vom Node |
| `on_chat_model_start` | LLM Model startet |
| `on_chat_model_stream` | Streaming Text vom LLM |
| `on_chat_model_end` | LLM Model endet |
| `on_tool_start` | Tool wird aufgerufen (z.B. Tavily Search) |
| `on_tool_end` | Tool Ergebnis |
| `done` | Recherche abgeschlossen |
| `error` | Fehler aufgetreten |

### Metadata in jedem Event

```json
{
  "research_model": "openrouter:google/gemini-2.5-flash",
  "summarization_model": "openrouter:google/gemini-2.5-flash",
  "compression_model": "openrouter:google/gemini-2.5-flash",
  "final_report_model": "openrouter:google/gemini-2.5-flash",
  "search_api": "tavily",
  "allow_clarification": false,
  "max_concurrent_research_units": 3
}
```

### LangGraph Workflow Nodes

Die Events kommen von diesen Nodes (in typischer Reihenfolge):

1. **clarify_with_user** - Prüft ob Klarstellung nötig ist
2. **write_research_brief** - Erstellt Research Brief
3. **supervisor** - Plant Research-Strategie
4. **supervisor_tools** - Delegiert Research-Tasks
5. **researcher** - Führt einzelne Research-Units aus
6. **researcher_tools** - Tool Calls (Search, Web Fetch)
7. **compress_research** - Komprimiert Findings
8. **final_report_generation** - Generiert finalen Report

---

## 🔧 Konfiguration

### Interne Backend-Konfiguration (Hardcoded)

Diese Werte sind fest im Backend konfiguriert:

```python
{
  "model": "openrouter:google/gemini-2.5-flash",  # Für alle 4 Rollen
  "search_api": "tavily",                          # Immer Tavily
  "allow_clarification": false,                    # Keine User-Interaktion
  "max_concurrent_research_units": 3               # Parallelität
}
```

Das Model wird für **alle 4 Rollen** verwendet:
- `research_model` - Hauptrecherche
- `summarization_model` - Tavily-Zusammenfassungen
- `compression_model` - Findings-Komprimierung
- `final_report_model` - Finaler Report

---

## 🏗️ Architektur

### System-Übersicht

```
┌─────────────┐      HTTP POST       ┌──────────────────┐
│  Next.js    │ ──────────────────► │  FastAPI Server  │
│  Frontend   │      /research/stream│  (Port 8000)     │
│             │                       │                  │
│             │ ◄────────────────── │  deep_researcher │
└─────────────┘      SSE Stream      │  (LangGraph)     │
                                      └──────────────────┘
                                              │
                                              ▼
                                      ┌──────────────────┐
                                      │  OpenRouter      │
                                      │  (Gemini 2.5)    │
                                      │                  │
                                      │  Tavily Search   │
                                      └──────────────────┘
```

### Datenfluss

1. **Client → Backend**: `{"message":"..."}`
2. **Backend → LangGraph**: Startet Research Workflow
3. **LangGraph → OpenRouter**: LLM Calls (Gemini 2.5 Flash)
4. **LangGraph → Tavily**: Web Searches
5. **Backend → Client**: SSE Stream mit Events

### Ordnerstruktur

```
backend/
├── backend_server.py    # FastAPI Server (SSE Streaming)
├── Dockerfile           # Container Definition
├── docker-compose.yml   # Container Orchestrierung
├── requirements.txt     # Python Dependencies
├── pyproject.toml       # Package Configuration
├── .env                 # API Keys (nicht in Git)
├── .dockerignore        # Build Excludes
├── src/                 # Source Code
│   └── open_deep_research/
│       ├── deep_researcher.py    # LangGraph Workflow
│       ├── configuration.py      # Config
│       ├── state.py              # State Definitions
│       └── utils/
│           └── model_utils.py    # Model Init
└── README.md            # Diese Datei
```

---

## 🛠️ Development

### Lokales Testen (ohne Docker)

```bash
# Install Dependencies
pip install -e .

# Run Server
python backend_server.py

# Test
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Test"}'
```

### Docker Commands

```bash
# Start Container
docker-compose up -d

# View Logs
docker logs -f deep-research-backend

# Stop Container
docker-compose down

# Rebuild
docker-compose build --no-cache
docker-compose up -d

# Check Status
docker ps
```

---

## 📝 Frontend Integration

### Next.js Example

```typescript
// lib/research.ts
const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'

export async function streamResearch(message: string) {
  const response = await fetch(`${BACKEND_URL}/research/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader!.read()
    if (done) break

    const text = decoder.decode(value)
    const lines = text.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6))
        console.log(event)
      }
    }
  }
}
```

### Environment Variable

```bash
# .env (Next.js)
RESEARCH_BACKEND_URL=http://localhost:8000
```

---

## 🧪 Testing

### Quick Test (2-5 Sekunden)

```bash
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"2+2"}' \
  --no-buffer
```

### Full Deep Research Test (1-10 Minuten)

```bash
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Was sind die wichtigsten Features in LangGraph 0.2?"}' \
  --no-buffer > research_test.log

# Check log size
du -h research_test.log

# View results
tail -100 research_test.log
```

**Erfolgreiche Research zeigt:**
- ✅ Mehrere `on_chain_start` Events
- ✅ `on_tool_start` Events (Tavily Searches)
- ✅ `on_chat_model_stream` mit Text-Chunks
- ✅ `on_chain_end` mit finalem Report
- ✅ Keine 401 Fehler
- ✅ 15-50 Research Units delegiert
- ✅ Finaler Report in Deutsch

---

## 🐛 Troubleshooting

### Container startet nicht

```bash
# Check Logs
docker-compose logs

# Check Status
docker ps -a

# Überprüfe API Keys
cat .env
```

### 401 Authentication Errors

- ✅ Prüfe `.env` Datei existiert
- ✅ Prüfe `GEMINI_API_KEY` oder `OPENROUTER_API_KEY` gesetzt
- ✅ Prüfe `load_dotenv()` in backend_server.py
- ✅ Restart Container nach .env Änderung

### Import Fehler

- Stelle sicher dass `src/open_deep_research/` korrekt kopiert wird
- Check Dockerfile COPY Befehle
- Rebuild: `docker-compose build --no-cache`

### Keine Events zurück

- Überprüfe CORS Settings in backend_server.py
- Check Frontend URL (Port 4290 oder 3000)
- Test mit curl direkt

### Port 8000 bereits belegt

```bash
# Option 1: Ändere Port in docker-compose.yml
ports:
  - "8001:8000"

# Option 2: Stoppe anderen Service
lsof -i :8000
kill <PID>
```

### Research hängt/bricht ab

- Check Tavily API Key und Quota
- Check OpenRouter Credits
- View Logs: `docker logs -f deep-research-backend`

---

## 🔒 Production Deployment

### Checkliste

1. **API Keys sicher verwalten**
   - Railway Secrets
   - AWS Secrets Manager
   - Kubernetes Secrets

2. **CORS Origins einschränken**
   ```python
   # backend_server.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],  # Nicht "*"
       ...
   )
   ```

3. **Resource Limits setzen**
   ```yaml
   # docker-compose.yml
   services:
     research-backend:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 4G
   ```

4. **Health Checks monitoren**
   ```bash
   # Automatisches Monitoring
   watch -n 30 'curl -s http://localhost:8000/health'
   ```

5. **Logging aktivieren**
   ```bash
   # LangSmith
   LANGSMITH_API_KEY=your_key
   LANGSMITH_TRACING=true
   ```

6. **Rate Limiting**
   - Implementiere Rate Limiting in FastAPI
   - Verwende nginx Reverse Proxy

### Production Docker Compose

```yaml
version: '3.8'

services:
  research-backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: deep-research-backend
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
      - LANGSMITH_TRACING=true
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    networks:
      - research-network

networks:
  research-network:
    driver: bridge
```

---

## 📊 Performance

### Typische Research-Zeiten

| Query-Typ | Dauer | Research Units | Events |
|-----------|-------|---------------|--------|
| Einfache Frage | 2-5s | 1-3 | ~100 |
| Mittlere Recherche | 10-30s | 5-15 | ~500 |
| Deep Research | 1-10min | 15-50 | ~2000+ |

### Optimierung

1. **Parallelität erhöhen**: `max_concurrent_research_units: 5`
2. **Caching**: LangSmith oder Redis
3. **Rate Limits**: OpenRouter und Tavily beachten
4. **Resource Limits**: CPU/Memory in docker-compose.yml

---

## 📄 License

Same as parent project.
