# Open Deep Research - Workflow Architecture

## Complete System Overview

This document provides a visual representation of the multi-agent research workflow using Mermaid diagrams.

## Main Deep Researcher Graph

```mermaid
graph TB
    START([START]) --> clarify_with_user[clarify_with_user]
    clarify_with_user -->|needs clarification| END1([END - Ask Question])
    clarify_with_user -->|no clarification needed| write_research_brief[write_research_brief]
    write_research_brief --> research_supervisor[research_supervisor<br/>Supervisor Subgraph]
    research_supervisor --> final_report_generation[final_report_generation]
    final_report_generation --> END2([END - Final Report])

    style clarify_with_user fill:#e1f5ff
    style write_research_brief fill:#e1f5ff
    style research_supervisor fill:#fff4e1
    style final_report_generation fill:#e1f5ff
```

## Supervisor Subgraph

```mermaid
graph TB
    START([START]) --> supervisor[supervisor<br/>Plans Strategy & Delegates]
    supervisor --> supervisor_tools[supervisor_tools<br/>Executes Tools]

    supervisor_tools -->|think_tool| supervisor
    supervisor_tools -->|ConductResearch| researcher1[Researcher 1<br/>Subgraph]
    supervisor_tools -->|ConductResearch| researcher2[Researcher 2<br/>Subgraph]
    supervisor_tools -->|ConductResearch| researcherN[Researcher N<br/>Subgraph]
    supervisor_tools -.->|parallel execution| researcher1
    supervisor_tools -.->|parallel execution| researcher2
    supervisor_tools -.->|parallel execution| researcherN

    researcher1 --> results[Aggregate Results]
    researcher2 --> results
    researcherN --> results

    results --> supervisor

    supervisor_tools -->|ResearchComplete OR<br/>max iterations| END([END])

    style supervisor fill:#fff4e1
    style supervisor_tools fill:#ffe1e1
    style researcher1 fill:#e1ffe1
    style researcher2 fill:#e1ffe1
    style researcherN fill:#e1ffe1
    style results fill:#f0f0f0
```

## Researcher Subgraph

```mermaid
graph TB
    START([START]) --> researcher[researcher<br/>Conducts Research]
    researcher --> researcher_tools[researcher_tools<br/>Executes Tools]

    researcher_tools -->|think_tool| researcher
    researcher_tools -->|search tools| tool1[Search API<br/>Tavily/OpenAI/Anthropic]
    researcher_tools -->|MCP tools| tool2[MCP Tools<br/>External Integrations]

    tool1 -.->|results| researcher
    tool2 -.->|results| researcher

    researcher_tools -->|max iterations OR<br/>no tool calls| compress_research[compress_research<br/>Synthesize Findings]
    compress_research --> END([END])

    style researcher fill:#e1ffe1
    style researcher_tools fill:#ffe1e1
    style tool1 fill:#f0f0f0
    style tool2 fill:#f0f0f0
    style compress_research fill:#e1ffe1
```

## Complete System Flow

```mermaid
graph TB
    subgraph "Main Graph"
        M1([START]) --> M2[clarify_with_user]
        M2 -->|needs clarification| M3([END])
        M2 -->|proceed| M4[write_research_brief]
        M4 --> M5[Supervisor Subgraph]
        M5 --> M6[final_report_generation]
        M6 --> M7([END])
    end

    subgraph "Supervisor Subgraph"
        S1([START]) --> S2[supervisor]
        S2 --> S3[supervisor_tools]
        S3 -->|loop| S2
        S3 -->|ConductResearch| S4[Parallel Researchers]
        S4 --> S3
        S3 -->|complete| S5([END])
    end

    subgraph "Researcher Subgraph Multiple Instances"
        R1([START]) --> R2[researcher]
        R2 --> R3[researcher_tools]
        R3 -->|loop| R2
        R3 -->|complete| R4[compress_research]
        R4 --> R5([END])
    end

    M5 -.->|invokes| S1
    S4 -.->|invokes N times| R1
    S5 -.->|returns| M5
    R5 -.->|returns| S4

    style M5 fill:#fff4e1
    style S4 fill:#e1ffe1
```

## Key Decision Points

### clarify_with_user
- **Input**: User messages
- **Decision**:
  - If `allow_clarification=False` → skip to write_research_brief
  - If needs clarification → END with question
  - If no clarification needed → proceed to write_research_brief

### supervisor_tools
- **Input**: Tool calls from supervisor
- **Decision**:
  - If `think_tool` → record reflection, continue loop
  - If `ConductResearch` → spawn parallel researchers (up to `max_concurrent_research_units`)
  - If `ResearchComplete` OR `max_researcher_iterations` exceeded → END
  - If no tool calls → END

### researcher_tools
- **Input**: Tool calls from researcher
- **Decision**:
  - If no tool calls and no native search → compress_research
  - If tool calls present → execute in parallel
  - If `max_react_tool_calls` exceeded OR `ResearchComplete` → compress_research
  - Otherwise → continue loop

## Parallel Execution Strategy

### Supervisor Level
```
supervisor_tools → ConductResearch(topic1, topic2, ..., topicN)
                ↓
        asyncio.gather() in parallel
                ↓
        [Researcher1, Researcher2, ..., ResearcherN]
                ↓
        Aggregate compressed results
```

### Researcher Level
```
researcher_tools → [search_call1, search_call2, ..., mcp_call]
                ↓
        asyncio.gather() in parallel
                ↓
        [result1, result2, ..., resultN]
                ↓
        Return to researcher
```

## State Flow

```mermaid
stateDiagram-v2
    [*] --> AgentState

    AgentState --> SupervisorState: write_research_brief
    note right of SupervisorState
        Adds: research_iterations
        Messages: supervisor_messages
    end note

    SupervisorState --> ResearcherState: ConductResearch
    note right of ResearcherState
        Adds: tool_call_iterations
        Messages: researcher_messages
    end note

    ResearcherState --> SupervisorState: compress_research
    note left of ResearcherState
        Returns: compressed_research
        Returns: raw_notes
    end note

    SupervisorState --> AgentState: ResearchComplete
    note left of SupervisorState
        Updates: notes (aggregated)
        Updates: research_brief
    end note

    AgentState --> [*]: final_report_generation
    note right of AgentState
        Generates: final_report
        Clears: notes
    end note
```

## Node Descriptions

### Main Graph Nodes

| Node | File | Description |
|------|------|-------------|
| `clarify_with_user` | `clarification.py:42` | Analyzes user query, asks clarifying questions if needed |
| `write_research_brief` | `clarification.py:100` | Converts user messages into structured research brief |
| `research_supervisor` | `supervisor.py` | Supervisor subgraph - delegates research to sub-agents |
| `final_report_generation` | `deep_researcher.py:35` | Synthesizes all findings into comprehensive report |

### Supervisor Subgraph Nodes

| Node | File | Description |
|------|------|-------------|
| `supervisor` | `supervisor.py:36` | Plans strategy, uses think_tool and ConductResearch |
| `supervisor_tools` | `supervisor.py:84` | Executes tools, spawns parallel researchers |

### Researcher Subgraph Nodes

| Node | File | Description |
|------|------|-------------|
| `researcher` | `researcher.py:64` | Conducts focused research with search/MCP tools |
| `researcher_tools` | `researcher.py:126` | Executes search/MCP tools in parallel |
| `compress_research` | `researcher.py:203` | Synthesizes research findings into concise summary |

## Tools Available

### Supervisor Tools
- `think_tool`: Strategic reflection
- `ConductResearch`: Delegate research to sub-agent
- `ResearchComplete`: Signal completion

### Researcher Tools
- `think_tool`: Strategic reflection
- Search APIs: Tavily, OpenAI web_search, Anthropic web_search
- MCP Tools: Custom external tools (if configured)
- `ResearchComplete`: Signal individual task completion (not typically used)
