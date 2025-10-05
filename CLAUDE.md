# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Deep Research is an automated deep research engine powered by Google's Gemini 2.5 Flash and Tavily Search. The system uses LangGraph to orchestrate a multi-agent research workflow where a supervisor delegates research tasks to specialized sub-agents, then synthesizes findings into comprehensive reports.

## Core Architecture

### Multi-Agent Workflow (LangGraph)

The system implements a hierarchical agent architecture in `src/open_deep_research/deep_researcher.py`:

**Main Graph Flow:**
1. `clarify_with_user` → Determines if user query needs clarification
2. `write_research_brief` → Converts user messages to structured research brief
3. `supervisor_subgraph` → Coordinates parallel research execution
4. `final_report_generation` → Synthesizes findings into comprehensive report

**Supervisor Subgraph** (manages research delegation):
- `supervisor` node: Plans strategy, delegates via `ConductResearch` tool
- `supervisor_tools` node: Executes delegated research in parallel using `asyncio.gather()`
- Uses `think_tool` for strategic reflection between actions

**Researcher Subgraph** (executes individual research):
- `researcher` node: Conducts focused research with search/MCP tools
- `researcher_tools` node: Executes tool calls in parallel
- `compress_research` node: Synthesizes findings into concise summaries

### State Architecture

Three key states in `src/open_deep_research/state.py`:
- `AgentState`: Main workflow state with `messages`, `research_brief`, `notes`, `final_report`
- `SupervisorState`: Adds `research_iterations` counter
- `ResearcherState`: Adds `tool_call_iterations` counter

Critical pattern: `override_reducer` allows state reset via `{"type": "override", "value": new_value}`

### Configuration System

Single `Configuration` class in `src/open_deep_research/configuration.py`:
- **Models**: All 4 roles use separate configurable models (research, summarization, compression, final_report)
- **Search API**: Enum-based selection (Tavily, OpenAI, Anthropic, None)
- **Limits**: `max_concurrent_research_units`, `max_researcher_iterations`, `max_react_tool_calls`
- **MCP**: Optional external tool integration via `MCPConfig`

## Development Commands

### Installation
```bash
python3.11 -m pip install -e .
```

### Running Research

**Interactive CLI** (Rich terminal UI with session management):
```bash
python3.11 deepresearch_cli.py
```

**One-shot script**:
```bash
python3.11 run_research.py "Your research question"
```

**Flask Web Frontend** (password-protected, SSE streaming):
```bash
cd flask_frontend
python app.py  # Opens on http://localhost:4290
```

**LangGraph Studio** (visual workflow debugging):
```bash
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev
```

### Testing
```bash
pytest  # Tests API connectivity, model inference, search integration
```

## Key Implementation Patterns

### Model Configuration & Naming
**Critical**: Gemini models require `models/` prefix:
- ✅ Correct: `google_genai:models/gemini-2.5-flash`
- ❌ Incorrect: `google_genai:gemini-2.5-flash`

Four separate model configurations in `Configuration`:
- `research_model` - Main research agent
- `summarization_model` - Tavily search result summarization
- `compression_model` - Researcher findings compression
- `final_report_model` - Final report generation

### Parallel Execution Strategy
- **Supervisor level**: Multiple researchers run via `asyncio.gather()` in `supervisor_tools` (line 305)
- **Researcher level**: Tool calls execute in parallel via `asyncio.gather()` (line 479)
- Concurrency limit: `max_concurrent_research_units` prevents resource exhaustion

### Token Limit Handling
Progressive retry logic with automatic truncation:
- `compress_research`: Removes messages up to last AI message on overflow
- `final_report_generation`: Reduces findings by 10% per retry (max 3 attempts)
- Detection: `is_token_limit_exceeded()` in `utils.py`

### Tool Architecture
1. **Strategic Tool**: `think_tool` - Used by both supervisor and researchers for reflection
2. **Research Tools**: Search APIs (Tavily/OpenAI/Anthropic) + MCP tools
3. **Completion Signals**: `ResearchComplete` (supervisor), early exit on `no_tool_calls`

### Error Handling
- Structured output retries: `with_retry(stop_after_attempt=max_structured_output_retries)`
- Safe execution: `execute_tool_safely()` wrapper (line 427-432)
- Graceful degradation: Overflow research calls return error ToolMessage (line 316-321)

## Environment Configuration

Required `.env` variables:
```bash
GEMINI_API_KEY=your-key
GOOGLE_API_KEY=your-key  # Can be same as GEMINI_API_KEY
TAVILY_API_KEY=your-key

# Flask frontend only:
SECRET_KEY=your-secret-key
APP_PASSWORD=your-password
```

## Frontend Architecture

**CLI** (`deepresearch_cli.py`):
- Rich terminal UI with markdown rendering
- Session management via `SessionManager` class
- Slash commands: `/help`, `/save`, `/load`, `/history`
- Persistent history in `~/.deepresearch/`

**Flask Web** (`flask_frontend/app.py`):
- Password authentication with rate limiting
- SSE streaming via `astream_events(version="v2")`
- Real-time step/tool tracking with hierarchical display
- Session storage in memory (threads dict)

**LangGraph Studio**:
- Visual workflow debugging
- Requires `langgraph-cli[inmem]`

## Code Style (Ruff)
- Pydocstyle: Google convention
- Docstrings: Required for all modules/functions
- First line: Imperative mood
- Imports: Sorted with isort
