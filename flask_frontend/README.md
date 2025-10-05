# 🔬 Deep Search Flask Frontend

Minimales Flask-basiertes Web-Frontend für die Open Deep Research Engine.

**Im Stil des Referenzmaterials** - mit nur **einem Port** und **minimalem Code**.

## ✨ Features

- ✅ **Ein-Port-Lösung**: Backend + Frontend auf Port 4290
- ✅ **Real-time Streaming**: SSE (Server-Sent Events) für Live-Updates
- ✅ **Dark/Light Mode**: Umschaltbar mit einem Klick
- ✅ **Markdown-Rendering**: Vollständige Markdown-Unterstützung
- ✅ **Syntax-Highlighting**: Code-Blöcke mit highlight.js
- ✅ **Minimaler Code**: ~550 Zeilen gesamt (150 Python + 400 HTML/CSS/JS)
- ✅ **Vanilla JavaScript**: Keine Frameworks, nur natives JS
- ✅ **Tailwind CSS**: Via CDN, keine Build-Tools
- ✅ **Gemini 2.5 Flash**: Schnelle AI-Recherche
- ✅ **Tavily Search**: Integrierte Web-Suche

## 🚀 Schnellstart

### 1. Installation

```bash
cd flask_frontend
pip install -r requirements.txt
```

### 2. API-Keys konfigurieren

Kopiere die `.env` aus dem Parent-Verzeichnis oder erstelle eine neue:

```bash
# Im flask_frontend Verzeichnis
cp ../.env .env
```

Oder erstelle eine neue `.env`:

```env
GEMINI_API_KEY=dein-gemini-api-key
GOOGLE_API_KEY=dein-google-api-key
TAVILY_API_KEY=dein-tavily-api-key
```

### 3. Server starten

```bash
python app.py
```

### 4. Browser öffnen

Öffne [http://localhost:4290](http://localhost:4290) im Browser.

**Das war's!** 🎉

## 📁 Struktur

```
flask_frontend/
├── app.py                 # Flask Server (150 Zeilen)
│   ├── SSE-Streaming
│   ├── Thread Management
│   └── Deep Research Integration
├── static/
│   └── index.html        # Frontend (400 Zeilen)
│       ├── Tailwind CSS (CDN)
│       ├── Marked.js (CDN)
│       ├── Highlight.js (CDN)
│       └── Vanilla JavaScript
├── requirements.txt      # Python Dependencies
└── README.md            # Diese Datei
```

## 🎨 Design-System

### Farben (aus Referenzmaterial)

**Dark Mode**:
- Background: `hsl(0 0% 9%)`
- Foreground: `hsl(48 50% 97%)`
- Primary: `hsl(15 52% 51%)` (Orange)
- Card: `hsl(0 0% 12%)`

**Light Mode**:
- Background: `hsl(48 50% 97%)`
- Foreground: `hsl(0 0% 9%)`
- Primary: `hsl(15 52% 51%)` (Orange)
- Card: `hsl(48 33% 94%)`

### UI-Komponenten

- **Message Bubbles**: Abgerundete Karten mit Fade-in-Animation
- **Thinking Indicator**: Animierte Punkte während Verarbeitung
- **Theme Toggle**: Sun/Moon Icon für Dark/Light Mode
- **Markdown**: Vollständige GitHub Flavored Markdown (GFM)

## 🔧 API-Endpoints

### `GET /`
Serve Frontend (index.html)

### `GET /api/chat/stream`
SSE-Streaming für Chat-Nachrichten

**Query Parameters**:
- `message`: Die User-Nachricht
- `thread_id`: Session-ID (optional)

**Response**: Server-Sent Events (SSE)

Event Types:
- `thinking`: Research gestartet
- `chunk`: Streaming-Chunk
- `agent_message`: Vollständige Nachricht
- `done`: Research abgeschlossen
- `error`: Fehler aufgetreten

### `POST /api/thread/clear/{thread_id}`
Chat-Verlauf löschen

### `GET /api/health`
Health-Check Endpoint

## 💡 Verwendung

### Beispiel-Anfragen

1. **Einfache Recherche**:
   ```
   Was ist künstliche Intelligenz?
   ```

2. **Detaillierte Analyse**:
   ```
   Erkläre die neuesten Entwicklungen in der Quantencomputer-Technologie
   ```

3. **Vergleichende Recherche**:
   ```
   Vergleiche verschiedene maschinelle Lernansätze
   ```

### Code-Beispiele im Chat

Das Frontend rendert Code-Blöcke automatisch mit Syntax-Highlighting:

\`\`\`python
def hello_world():
    print("Hello, World!")
\`\`\`

## ⚙️ Konfiguration

### Port ändern

In `app.py`:
```python
port = int(os.getenv('PORT', 4290))  # Ändere 4290 zu gewünschtem Port
```

Oder via Environment Variable:
```bash
PORT=5000 python app.py
```

### Modell-Konfiguration

In `app.py`, Funktion `stream_research()`:
```python
config = {
    "configurable": {
        "research_model": "google_genai:models/gemini-2.5-flash",
        "search_api": "tavily",
        "max_concurrent_research_units": 3,
        # ... weitere Optionen
    }
}
```

## 🔍 Technische Details

### SSE (Server-Sent Events)

Das Frontend nutzt EventSource für Real-time Streaming:

```javascript
const eventSource = new EventSource('/api/chat/stream?message=...');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle events
};
```

### Deep Research Integration

Der Flask-Server ruft die bestehende Deep Research Engine auf:

```python
from src.open_deep_research.deep_researcher import deep_researcher

async for event in deep_researcher.astream_events(
    {"messages": [{"role": "user", "content": message}]},
    config=config,
    version="v2"
):
    # Stream events to frontend
```

## 🐛 Troubleshooting

### "Module 'open_deep_research' not found"

Installiere das Parent-Projekt:
```bash
cd ..
pip install -e .
```

### "Connection to API failed"

Überprüfe deine API-Keys in `.env`:
```bash
cat .env | grep API_KEY
```

### Port bereits belegt

Ändere den Port:
```bash
PORT=5000 python app.py
```

## 📊 Performance

- **Startup-Zeit**: < 2 Sekunden
- **Erste Antwort**: 2-5 Sekunden (abhängig von Recherche-Komplexität)
- **Streaming**: Real-time, keine zusätzliche Latenz
- **Memory**: ~200MB (Python + Deep Research Engine)

## 🔐 Sicherheit

⚠️ **Wichtig**: Dieses Frontend ist für **lokale Entwicklung** konzipiert.

Für Produktion:
- ✅ Authentifizierung hinzufügen
- ✅ Rate Limiting implementieren
- ✅ HTTPS verwenden
- ✅ Input-Validation verstärken
- ✅ CORS richtig konfigurieren

## 📝 Lizenz

MIT - Siehe Parent-Projekt

## 🙏 Credits

- **Design-Inspiration**: Referenzfrontend (Next.js)
- **Deep Research Engine**: Open Deep Research
- **UI-Framework**: Tailwind CSS
- **Markdown**: Marked.js
- **Syntax-Highlighting**: Highlight.js

---

**Erstellt mit ❤️ und minimalem Code** 🚀
