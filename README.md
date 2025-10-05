# 🔬 Open Deep Research - Gemini 2.5 Flash Edition

Vollautomatisierte Deep Research Engine mit **Gemini 2.5 Flash** und **Tavily Search**.

Jetzt mit **Premium Interactive CLI** - inspiriert von Gemini CLI, Claude Code & Codex CLI!

## ✅ Status: VOLL FUNKTIONSFÄHIG

Alle Tests bestanden:
- ✅ Gemini 2.5 Flash API funktioniert
- ✅ Tavily Search API funktioniert
- ✅ LangChain Integration funktioniert
- ✅ Complete Research Pipeline funktioniert
- ✅ Premium CLI mit Rich UI funktioniert

---

## 🚀 Schnellstart

### 🌟 Option 1: Premium Interactive CLI (EMPFOHLEN)

```bash
python3.11 deepresearch_cli.py
```

**Features:**
- ✨ Interaktive Multi-turn Conversations
- ⌨️ Keyboard Shortcuts (Ctrl+R, Escape, etc.)
- 📋 Slash Commands (/help, /save, /history)
- 💾 Automatic Session Management
- 🎨 Beautiful Rich Terminal UI
- 📊 Real-time Progress Indicators
- 📝 Markdown Rendering

**Siehe [CLI_GUIDE.md](CLI_GUIDE.md) für vollständige Anleitung!**

---

### Option 2: Simple One-Shot Script

```bash
python3.11 run_research.py "Was ist künstliche Intelligenz?"
```

**Weitere Beispiele:**
```bash
python3.11 run_research.py "Explain quantum computing"
python3.11 run_research.py "Latest developments in renewable energy"
python3.11 run_research.py "Wie funktioniert maschinelles Lernen?"
```

### Option 3: LangGraph Studio (mit GUI)

```bash
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev
```

Dies öffnet eine Web-UI im Browser für interaktive Research.

---

## ⚙️ Konfiguration

### API Keys (in `.env`)
```
GEMINI_API_KEY=AIzaSyCQANQ-oRtHnGOD7AFTySZLxvveqI0tpIA
GOOGLE_API_KEY=AIzaSyCQANQ-oRtHnGOD7AFTySZLxvveqI0tpIA
TAVILY_API_KEY=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
```

### Modelle (in `src/open_deep_research/configuration.py`)
Alle 4 Modelle nutzen **Gemini 2.5 Flash**:
- Research Model: `google_genai:models/gemini-2.5-flash`
- Summarization Model: `google_genai:models/gemini-2.5-flash`
- Compression Model: `google_genai:models/gemini-2.5-flash`
- Final Report Model: `google_genai:models/gemini-2.5-flash`

### Search API
- Standard: **Tavily** (konfiguriert und funktionsfähig)
- Alternativen: OpenAI, Anthropic, None

---

## 📦 Installation

Bereits installiert! Falls nötig:

```bash
python3.11 -m pip install -e .
```

---

## 🧪 Tests

Alle Tests erfolgreich durchgeführt:

1. **API-Verbindung**: ✅
2. **Modell-Inference**: ✅
3. **Search-Integration**: ✅
4. **Full Pipeline**: ✅

---

## 📁 Projektstruktur

```
open_deep_research/
├── .env                      # API Keys
├── deepresearch_cli.py       # 🌟 Premium Interactive CLI (NEU!)
├── CLI_GUIDE.md              # Vollständige CLI-Dokumentation
├── run_research.py           # Simple One-Shot CLI
├── langgraph.json            # LangGraph Konfiguration
├── pyproject.toml            # Dependencies
├── test_cli.py               # CLI Tests
└── src/open_deep_research/
    ├── configuration.py      # Gemini 2.5 Flash Konfiguration
    ├── deep_researcher.py    # Haupt-Agent
    ├── prompts.py            # System Prompts
    ├── state.py              # State Management
    └── utils.py              # Utilities

~/.deepresearch/              # User data
├── history.txt               # Command history
└── sessions/                 # Saved sessions
    └── *.json
```

---

## 💡 Beispiel-Nutzung

```python
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def research():
    from open_deep_research.deep_researcher import deep_researcher

    result = await deep_researcher.ainvoke({
        "messages": [{
            "role": "user",
            "content": "What are the benefits of renewable energy?"
        }]
    })

    print(result["final_report"])

asyncio.run(research())
```

---

## ⚠️ Wichtige Hinweise

- **Python Version**: Mindestens Python 3.10 (3.11 empfohlen)
- **Modellname-Format**: Gemini-Modelle benötigen `models/` Prefix
- **Rate Limits**: Achte auf API Rate Limits bei vielen Anfragen
- **Concurrency**: Standard 3 parallele Research Units (anpassbar)

---

## 🎯 Features

### 🌟 Premium CLI Features (NEU!)
- ✅ **Interactive REPL**: Multi-turn Konversationen wie bei Gemini/Claude/Codex CLI
- ✅ **Rich Terminal UI**: Schöne Panels, Markdown-Rendering, Syntax-Highlighting
- ✅ **Keyboard Shortcuts**: Ctrl+R (history search), Escape (stop), Tab (autocomplete)
- ✅ **Slash Commands**: /help, /save, /load, /history, /settings, etc.
- ✅ **Session Management**: Automatisches Speichern & Laden von Conversations
- ✅ **Progress Indicators**: Real-time Research-Visualisierung mit Spinners & Progress Bars
- ✅ **History Search**: Durchsuchbare Command History
- ✅ **Auto-Save**: Jede Research wird automatisch gespeichert

### Research Engine Features
- ✅ **Parallele Research**: Mehrere Sub-Agents arbeiten gleichzeitig
- ✅ **Web Search**: Integrierte Tavily Search
- ✅ **Smart Compression**: Intelligente Zusammenfassung großer Datensätze
- ✅ **Structured Output**: Klar strukturierte Forschungsberichte
- ✅ **Streaming Support**: Real-time Output während der Research

---

## 🔧 Troubleshooting

### "No module named 'open_deep_research'"
```bash
python3.11 -m pip install -e .
```

### "404 model not found"
Stelle sicher, dass der Modellname das `models/` Prefix hat:
`google_genai:models/gemini-2.5-flash`

### Tavily API Fehler
Überprüfe deinen API Key in `.env`:
```bash
echo $TAVILY_API_KEY
```

---

## 📊 Performance

- **Gemini 2.5 Flash**: Schnell, kosteneffizient, hohe Qualität
- **Tavily Search**: Zuverlässige Web-Suche mit guten Ergebnissen
- **Durchschnittliche Research-Zeit**: 2-5 Minuten (je nach Komplexität)

---

**Erstellt mit Gemini 2.5 Flash** 🤖
