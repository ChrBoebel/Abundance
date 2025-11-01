# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Deep Research is an automated deep research engine powered by LangGraph and configurable LLM providers. The system uses LangGraph to orchestrate a multi-agent research workflow where a supervisor delegates research tasks to specialized sub-agents, then synthesizes findings into comprehensive reports.

**Current Default Setup**: All models route through OpenRouter using Gemini 2.5 Flash (`openrouter:google/gemini-2.5-flash`)

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

**Docker Backend + Next.js Frontend** (web interface with SSE streaming):
```bash
# Start backend
cd backend
docker-compose up -d  # Runs on http://localhost:8000

# Start frontend (in separate terminal)
cd frontend
npm run dev  # Opens on http://localhost:4290
```

**LangGraph Studio** (visual workflow debugging):
```bash
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev
```

### Testing
```bash
pytest  # Tests API connectivity, model inference, search integration
```

### Linting and Code Quality
```bash
ruff check .     # Check for linting issues
ruff format .    # Format code
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
- **Supervisor level**: Multiple researchers run via `asyncio.gather()` in `supervisor_tools` at `deep_researcher.py:305`
- **Researcher level**: Tool calls execute in parallel via `asyncio.gather()` at `deep_researcher.py:479`
- Concurrency limit: `max_concurrent_research_units` prevents resource exhaustion (default: 10)
- Research tasks are distributed across sub-agents to maximize throughput while staying within rate limits

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
- Safe execution: `execute_tool_safely()` wrapper in `deep_researcher.py:427-432`
- Graceful degradation: Overflow research calls return error ToolMessage in `deep_researcher.py:316-321`
- Token overflow detection: Catches token limit errors and automatically retries with truncated context

## Environment Configuration

Required `.env` variables:
```bash
GEMINI_API_KEY=your-key
GOOGLE_API_KEY=your-key  # Can be same as GEMINI_API_KEY
TAVILY_API_KEY=your-key
OPENROUTER_API_KEY=your-key

# Frontend authentication:
APP_PASSWORD=your-password
SESSION_SECRET=your-secret-key
```

**Note**: Separate `.env` files exist in `backend/.env` and `frontend/.env` for their respective services.

## Architecture Overview

The project has two deployment modes:

### 1. Web Application (Production)
- **Backend**: Docker container (`backend/`) with FastAPI server
  - Source code in `backend/src/`
  - Runs on port 8000
  - SSE streaming via `/research/stream`
- **Frontend**: Next.js app (`frontend/`)
  - React components, Server-Side Rendering
  - Runs on port 4290
  - Communicates with backend via HTTP/SSE

### 2. Local Development (CLI/Scripts)
- **Source**: `src/open_deep_research/` (shared Python package)
- **Tools**: `deepresearch_cli.py`, `run_research.py`, LangGraph Studio
- **Tests**: `tests/` directory

**Important**: `src/open_deep_research/` and `backend/src/` contain duplicate code. This is intentional:
- `src/open_deep_research/` - For local tools (CLI, tests, LangGraph Studio)
- `backend/src/` - For Docker backend (self-contained deployment)

## Frontend Architecture

**CLI** (`deepresearch_cli.py`):
- Rich terminal UI with markdown rendering
- Session management via `SessionManager` class
- Slash commands: `/help`, `/save`, `/load`, `/history`
- Persistent history in `~/.deepresearch/`

**Next.js Web** (`frontend/`):
- Password authentication with iron-session
- SSE streaming for real-time updates
- React components with TypeScript
- Communicates with Docker backend

**LangGraph Studio**:
- Visual workflow debugging
- Requires `langgraph-cli[inmem]`

## Code Style (Ruff)
- Pydocstyle: Google convention
- Docstrings: Required for all modules/functions
- First line: Imperative mood
- Imports: Sorted with isort
- Config: See `pyproject.toml` for full linting rules

## Important Notes

### Model Provider Specifics
- **Gemini models**: Always use `models/` prefix (e.g., `google_genai:models/gemini-2.5-flash`)
- **Native web search**: OpenAI and Anthropic models support native web search without Tavily
- **MCP tools**: Optional external tool integration for custom research capabilities

### Configuration Best Practices
- Use `allow_clarification=False` for automated research workflows
- Adjust `max_concurrent_research_units` based on API rate limits (default: 10)
- Set `max_search_results` higher (15-20) for comprehensive research, lower (5-10) for faster results
- Token limits: Compression model needs sufficient tokens to summarize findings (default: 8192)
