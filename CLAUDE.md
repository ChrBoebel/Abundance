# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Open Deep Research is an automated deep research engine powered by Google's Gemini 2.5 Flash and Tavily Search. The system uses LangGraph to orchestrate a multi-agent research workflow where a supervisor delegates research tasks to specialized sub-agents, then synthesizes findings into comprehensive reports.

## Core Architecture

### Multi-Agent Research Pipeline

The system follows a hierarchical agent architecture implemented in `src/open_deep_research/deep_researcher.py`:

1. **Clarification Phase** (`clarify_with_user`): Analyzes user queries to determine if clarification is needed before starting research
2. **Research Planning** (`write_research_brief`): Transforms user messages into structured research briefs
3. **Research Execution** (`supervisor_subgraph`): Main supervisor coordinates parallel research units
   - **Supervisor** (`supervisor`): Plans research strategy and delegates to researchers using `ConductResearch` tool
   - **Supervisor Tools** (`supervisor_tools`): Executes delegated research and handles `think_tool` for strategic reflection
4. **Individual Research** (`researcher_subgraph`): Individual researchers conduct focused research
   - **Researcher** (`researcher`): Uses search tools, MCP tools, and `think_tool` for information gathering
   - **Researcher Tools** (`researcher_tools`): Executes search and MCP tools
   - **Compress Research** (`compress_research`): Synthesizes findings into concise summaries
5. **Report Generation** (`final_report_generation`): Produces final comprehensive report from all research findings

### State Management

States are defined in `src/open_deep_research/state.py`:
- `AgentState`: Main workflow state with messages, research brief, notes
- `SupervisorState`: Supervisor-specific state with iteration tracking
- `ResearcherState`: Individual researcher state with tool call iterations
- Structured outputs: `ClarifyWithUser`, `ResearchQuestion`, `ConductResearch`, `ResearchComplete`

### Configuration System

All configuration is managed in `src/open_deep_research/configuration.py`:
- Model selection for research, summarization, compression, and final report
- Search API configuration (Tavily, OpenAI, Anthropic, or None)
- Concurrency limits (`max_concurrent_research_units`)
- Iteration limits (`max_researcher_iterations`, `max_react_tool_calls`)
- MCP server configuration for external tool integration

## Development Commands

### Running Research

**Interactive CLI (Recommended)**:
```bash
python3.11 deepresearch_cli.py
```

**One-shot research**:
```bash
python3.11 run_research.py "Your research question"
```

**LangGraph Studio (Web UI)**:
```bash
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev
```

**Flask Web Frontend**:
```bash
cd flask_frontend
python app.py
# Opens on http://localhost:4290
```

### Installation

```bash
python3.11 -m pip install -e .
```

### Testing

The project uses pytest for testing. Tests should validate:
- API connectivity (Gemini, Tavily)
- Model inference
- Search integration
- Full research pipeline

## Model Configuration

All models use Gemini 2.5 Flash by default. The model naming format is critical:
- **Correct**: `google_genai:models/gemini-2.5-flash`
- **Incorrect**: `google_genai:gemini-2.5-flash` (missing `models/` prefix)

Models are configurable via `Configuration` class:
- `research_model`: Main research agent model
- `summarization_model`: For summarizing Tavily search results
- `compression_model`: For compressing researcher findings
- `final_report_model`: For generating final reports

## Key Implementation Patterns

### Token Limit Handling

The system implements progressive token limit retry logic in:
- `compress_research`: Removes older messages up to last AI message on token limit
- `final_report_generation`: Progressively truncates findings by 10% per retry (max 3 attempts)

### Parallel Execution

- Researchers execute in parallel using `asyncio.gather()` in `supervisor_tools`
- Maximum concurrency controlled by `max_concurrent_research_units`
- Tool executions within researchers also run in parallel

### Tool Calling

Two types of tools are used:
1. **Research Tools**: Search APIs (Tavily, OpenAI web search, Anthropic web search) and MCP tools
2. **Strategic Tools**: `think_tool` for reflection between actions in both supervisor and researchers

### Error Handling

- Structured output retries: `max_structured_output_retries` (default: 3)
- Token limit detection via `is_token_limit_exceeded()` in `utils.py`
- Safe tool execution with `execute_tool_safely()` wrapper
- Graceful degradation when research units exceed limits

## Environment Setup

Required environment variables in `.env`:
```
GEMINI_API_KEY=your-gemini-key
GOOGLE_API_KEY=your-google-key  # Can be same as GEMINI_API_KEY
TAVILY_API_KEY=your-tavily-key
```

## Frontend Options

### CLI (`deepresearch_cli.py`)
- Rich terminal UI with markdown rendering
- Session management and history
- Slash commands: `/help`, `/save`, `/load`, `/history`, `/settings`
- Keyboard shortcuts for history search

### Flask Web (`flask_frontend/app.py`)
- Single-port solution (default: 4290)
- Server-Sent Events (SSE) for real-time streaming
- Dark/light mode with Tailwind CSS
- Vanilla JavaScript, no build tools required

### LangGraph Studio
- Visual workflow debugging
- Interactive graph execution
- Requires LangGraph CLI

## Code Style

The project uses Ruff for linting with the following conventions:
- Pydocstyle: Google convention
- Docstrings required for all modules and functions
- First line should be imperative mood
- Imports sorted with isort
